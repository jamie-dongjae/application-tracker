def test_health(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["schema_version"] == 2


def test_create_geocodes_from_cache(client):
    resp = client.post("/api/applications", json={
        "company": "Acme", "title": "Analyst", "location": "Utrecht, Netherlands"})
    assert resp.status_code == 201
    rec = resp.json()
    assert rec["geo_status"] == "ok"
    assert abs(rec["latitude"] - 52.09083) < 0.001


def test_create_remote_never_geocodes(client):
    rec = client.post("/api/applications", json={
        "company": "Acme", "title": "Analyst", "location": "Remote (EU)"}).json()
    assert rec["geo_status"] == "remote"
    assert rec["latitude"] == ""


def test_create_unknown_location_marks_failed(client, geocoder, monkeypatch):
    monkeypatch.setattr(geocoder, "_request", lambda q: None)
    rec = client.post("/api/applications", json={
        "company": "Acme", "title": "Analyst", "location": "Nowhereville, Atlantis"}).json()
    assert rec["geo_status"] == "failed"


def test_patch_status_and_undo(client):
    rec = client.post("/api/applications", json={"company": "Acme", "title": "Analyst"}).json()
    app_id = rec["id"]

    patched = client.patch(f"/api/applications/{app_id}", json={"status": "Phone Screen"}).json()
    assert patched["status"] == "Phone Screen"

    undone = client.post("/api/undo").json()
    assert undone["id"] == app_id
    apps = client.get("/api/applications").json()["applications"]
    assert apps[0]["status"] == "Applied"


def test_undo_of_create_deletes(client):
    rec = client.post("/api/applications", json={"company": "Acme", "title": "Analyst"}).json()
    client.post("/api/undo")
    apps = client.get("/api/applications").json()["applications"]
    assert all(a["id"] != rec["id"] for a in apps)


def test_delete_and_undo_restores_same_id(client):
    rec = client.post("/api/applications", json={"company": "Acme", "title": "Analyst"}).json()
    client.delete(f"/api/applications/{rec['id']}")
    client.post("/api/undo")
    apps = client.get("/api/applications").json()["applications"]
    assert any(a["id"] == rec["id"] and a["company"] == "Acme" for a in apps)


def test_locked_workbook_returns_409(client, store):
    sentinel = store.path.parent / f"~${store.path.name}"
    sentinel.write_text("locked")
    resp = client.post("/api/applications", json={"company": "Acme", "title": "Analyst"})
    assert resp.status_code == 409
    assert resp.json()["error"] == "workbook_locked"
    sentinel.unlink()
    assert client.post("/api/applications",
                       json={"company": "Acme", "title": "Analyst"}).status_code == 201


def test_prep_crud(client):
    rec = client.post("/api/prep", json={
        "category": "Behavioral", "question": "Tell me about a conflict",
        "situation": "S", "task": "T", "action": "A", "result": "R"}).json()
    assert rec["id"] == 1

    client.patch(f"/api/prep/{rec['id']}", json={"tips": "Breathe"})
    items = client.get("/api/prep").json()["prep"]
    assert items[0]["tips"] == "Breathe"

    client.delete(f"/api/prep/{rec['id']}")
    assert client.get("/api/prep").json()["prep"] == []


def test_history_transitions(client):
    rec = client.post("/api/applications", json={"company": "Acme", "title": "Analyst"}).json()
    client.patch(f"/api/applications/{rec['id']}", json={"status": "Phone Screen"})
    client.patch(f"/api/applications/{rec['id']}", json={"status": "Technical"})
    body = client.get("/api/history").json()
    assert len(body["transitions"]) == 2
    assert body["transitions"][1]["to"] == "Technical"


def test_settings_roundtrip(client):
    client.put("/api/settings", json={"weekly_goal": 7})
    assert client.get("/api/settings").json()["weekly_goal"] == 7
    client.put("/api/settings", json={"weekly_goal": 5})
