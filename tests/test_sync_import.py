"""Sync-packet importer: idempotency, dedup, undo, and the last_sync watermark."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    # settings.json / sync_ledger.json / aliases.json live under
    # TRACKER_DATA_DIR (read at call time) — isolate them per test so the
    # ledger from one test can't mark another test's packet "already synced".
    monkeypatch.setenv("TRACKER_DATA_DIR", str(tmp_path))


def _packet(records, generated_at="2026-09-26T12:00:00", **extra):
    return {"packet_version": 1, "source": "manual", "generated_at": generated_at,
            "since": "", "records": records, "employers": [], "aliases": {}, **extra}


def _record(**over):
    base = {"company": "Acme Corp", "title": "Data Analyst", "match": {},
            "confidence": "high", "reason": "test", "fields": {},
            "patch": {}, "note": "", "events": [], "provenance": []}
    base.update(over)
    return base


def _post(client, packet, dry_run):
    return client.post("/api/import/sync", json={"packet": packet, "dry_run": dry_run})


def test_dry_run_changes_nothing(client, store):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    before = store.info()
    resp = _post(client, _packet([_record(patch={"stage_reached": "confirmed"})]), True).json()
    assert resp["dry_run"] is True and resp["updated"] == 1
    assert store.info() == before
    assert client.get("/api/health").json()["last_sync"] is None


def test_apply_update_add_and_events(client, store):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    packet = _packet([
        _record(patch={"stage_reached": "confirmed"},
                events=[{"date": "2026-09-25", "event": "confirmed",
                         "note": "ATS confirmation", "provenance": "gmail:abc123"}],
                provenance=["gmail:abc123"]),
        _record(company="Zeta", title="Product Manager",
                patch={"track": "career", "stage_reached": "applied",
                       "current_state": "awaiting_response"},
                fields={"date_applied": "2026-09-24", "source": "test site"}),
    ])
    resp = _post(client, packet, False).json()
    assert resp["updated"] == 1 and resp["added"] == 1 and resp["events_added"] == 1

    apps = {a["company"]: a for a in client.get("/api/applications").json()["applications"]}
    assert apps["Acme Corp"]["stage_reached"] == "confirmed"
    assert apps["Zeta"]["status"] == "Applied"  # derived from v4 fields
    events = client.get(f"/api/applications/{apps['Acme Corp']['id']}/events").json()["events"]
    assert len(events) == 1 and "(gmail:abc123)" in events[0]["note"]
    assert client.get("/api/health").json()["last_sync"] == "2026-09-26T12:00:00"


def test_reapply_same_packet_is_idempotent(client, store):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    packet = _packet([_record(
        patch={"stage_reached": "confirmed"},
        events=[{"date": "2026-09-25", "event": "confirmed", "note": "ATS confirmation",
                 "provenance": "gmail:abc123"}],
        provenance=["gmail:abc123"])])
    _post(client, packet, False)
    app_id = client.get("/api/applications").json()["applications"][0]["id"]
    n_events = len(client.get(f"/api/applications/{app_id}/events").json()["events"])

    resp = _post(client, packet, False).json()
    assert resp["updated"] == 0 and resp["added"] == 0 and resp["events_added"] == 0
    assert resp["records"][0]["skip_reason"] == "already synced"
    assert len(client.get(f"/api/applications/{app_id}/events").json()["events"]) == n_events


def test_event_dedup_against_manual_event(client, store):
    rec = client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"}).json()
    client.post(f"/api/applications/{rec['id']}/events",
                json={"date": "2026-09-25", "event": "note", "note": "call went well"})
    packet = _packet([_record(events=[
        {"date": "2026-09-25", "event": "note", "note": "call went well", "provenance": ""}])])
    resp = _post(client, packet, False).json()
    assert resp["events_added"] == 0 and resp["events_deduped"] == 1


def test_ambiguous_record_is_skipped(client):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Engineer"})
    resp = _post(client, _packet([_record(title="Data role",
                                          patch={"current_state": "closed", "outcome": "rejected_cv",
                                                 "closed_by": "employer"})]), False).json()
    assert resp["records"][0]["action"] == "skip"
    assert "AMBIGUOUS" in resp["records"][0]["skip_reason"]
    apps = client.get("/api/applications").json()["applications"]
    assert all(a["current_state"] != "closed" for a in apps)  # nothing guessed


def test_explicit_id_match_path(client):
    rec = client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"}).json()
    resp = _post(client, _packet([_record(company="whatever", title="whatever",
                                          match={"id": rec["id"]},
                                          patch={"stage_reached": "assessment"})]), False).json()
    assert resp["updated"] == 1
    app = client.get("/api/applications").json()["applications"][0]
    assert app["stage_reached"] == "assessment" and app["status"] == "Interview"


def test_employers_upsert_merges(client, store):
    client.put("/api/employers", json=[
        {"employer": "Acme Corp", "rule": "one at a time", "status": "slot used"},
        {"employer": "Beta B.V.", "rule": "cap 2", "status": ""}])
    packet = _packet([], employers=[
        {"employer": "Acme Corp", "rule": "one at a time", "status": "slot free"},
        {"employer": "Zeta", "rule": "referral only", "status": ""}])
    _post(client, packet, False)
    rows = {e["employer"]: e for e in client.get("/api/employers").json()["employers"]}
    assert len(rows) == 3
    assert rows["Acme Corp"]["status"] == "slot free"   # updated
    assert rows["Beta B.V."]["rule"] == "cap 2"         # preserved
    assert rows["Zeta"]["rule"] == "referral only"      # added


def test_invalid_enum_rejected(client):
    packet = _packet([_record(patch={"track": "bogus"})])
    assert _post(client, packet, True).status_code == 422


def test_settings_put_cannot_clobber_last_sync(client):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    _post(client, _packet([_record(patch={"stage_reached": "confirmed"})]), False)
    client.put("/api/settings", json={"weekly_goal": 9})
    assert client.get("/api/health").json()["last_sync"] == "2026-09-26T12:00:00"


def test_undo_reverses_last_synced_change(client):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    _post(client, _packet([_record(patch={"current_state": "closed", "outcome": "rejected_cv",
                                          "closed_by": "employer"})]), False)
    app = client.get("/api/applications").json()["applications"][0]
    assert app["status"] == "Rejected"
    client.post("/api/undo")
    app = client.get("/api/applications").json()["applications"][0]
    assert app["status"] == "Applied"


def test_no_changes_record_still_lands_in_ledger(client):
    """A record whose content is already absorbed gets its gmail ids ledgered
    so future sweeps skip it as 'already synced' instead of re-planning it."""
    rec = client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"}).json()
    client.post(f"/api/applications/{rec['id']}/events",
                json={"date": "2026-09-25", "event": "confirmed",
                      "note": "ATS confirmation (gmail:xyz789)"})
    packet = _packet([_record(
        events=[{"date": "2026-09-25", "event": "confirmed", "note": "ATS confirmation",
                 "provenance": "gmail:xyz789"}],
        provenance=["gmail:xyz789"])])
    resp = _post(client, packet, False).json()
    assert resp["records"][0]["skip_reason"] == "no changes"
    assert resp["events_deduped"] == 1
    resp2 = _post(client, packet, False).json()
    assert resp2["records"][0]["skip_reason"] == "already synced"


def test_history_entries(client):
    client.post("/api/applications", json={"company": "Acme Corp", "title": "Data Analyst"})
    _post(client, _packet([_record(patch={"stage_reached": "confirmed"})]), False)
    hist = client.get("/api/history").json()["history"]
    sync_entries = [h for h in hist if h["entity"] == "sync"]
    assert len(sync_entries) == 1
    assert any(h["entity"] == "application" and h["label"].startswith("Sync:") for h in hist)
