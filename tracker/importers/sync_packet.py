"""Sync-packet importer: plan and apply v1 packets against the store.

A packet (see models.SyncPacket) carries records from a Gmail sweep or a
claude.ai project export. Matching never guesses (ambiguity -> skip), events
are append-only with dedup, and every applied gmail id lands in a ledger so
re-sweeps are idempotent. Confidence gating happens client-side; this module
enforces invariants only.
"""
from __future__ import annotations

import json
from datetime import datetime

from .. import config
from .matching import V4_FIELDS, build_patch, match_record, new_record, norm

# Base columns a packet may fill on add / fill-if-empty on match.
FIELD_KEYS = ("date_applied", "source", "url", "portal_url", "location", "work_type",
              "sponsorship", "referral")


# ---------- aliases + ledger ----------

def load_aliases() -> dict:
    try:
        return json.loads(config.aliases_path().read_text())
    except (OSError, ValueError):
        return {}


def merge_aliases(new: dict) -> dict:
    merged = load_aliases()
    merged.update({norm(k): norm(v) for k, v in (new or {}).items() if k and v})
    config.aliases_path().write_text(json.dumps(merged, indent=2, sort_keys=True))
    return merged


def load_ledger() -> dict:
    try:
        data = json.loads(config.sync_ledger_path().read_text())
        data.setdefault("gmail_ids", [])
        data.setdefault("packets", [])
        return data
    except (OSError, ValueError):
        return {"gmail_ids": [], "packets": []}


def record_ledger(ids: set, packet_meta: dict) -> None:
    ledger = load_ledger()
    known = set(ledger["gmail_ids"])
    ledger["gmail_ids"] = sorted(known | {i for i in ids if i})
    ledger["packets"].append(packet_meta)
    config.sync_ledger_path().write_text(json.dumps(ledger, indent=2))


# ---------- planning ----------

def _event_key(date_value, event, note) -> tuple:
    return (str(date_value or "")[:10], str(event or "").strip(), norm(note)[:80])


def _stored_note(event) -> str:
    note = (event.get("note") or "").strip()
    prov = (event.get("provenance") or "").strip()
    if prov and prov not in note:
        note = f"{note} ({prov})".strip()
    return note


def _plan_events(store, app_id, events) -> tuple[list, int]:
    """Split incoming events into (new, duplicate-count) against the app's timeline."""
    if app_id is None:
        return [dict(e, note=_stored_note(e)) for e in events], 0
    existing = store.list_events(app_id)
    seen = {_event_key(e.get("date"), e.get("event"), e.get("note")) for e in existing}
    existing_notes = " ".join(str(e.get("note") or "") for e in existing)
    fresh, dups = [], 0
    for e in events:
        note = _stored_note(e)
        prov = (e.get("provenance") or "").strip()
        if _event_key(e.get("date"), e.get("event"), note) in seen \
                or (prov and prov in existing_notes):
            dups += 1
            continue
        fresh.append({"date": e.get("date") or "", "event": e["event"], "note": note})
    return fresh, dups


def _flatten(record: dict) -> dict:
    """SyncRecord -> the md dict shape the matching engine expects."""
    md = {"company": record["company"], "title": record["title"],
          "match": record.get("match") or {}, "note": record.get("note", "")}
    for k, v in (record.get("fields") or {}).items():
        if k in FIELD_KEYS and v:
            md[k] = v
    for k, v in (record.get("patch") or {}).items():
        if k in V4_FIELDS and v:
            md[k] = v
    return md


def plan_packet(store, packet: dict) -> list[dict]:
    aliases = dict(load_aliases())
    aliases.update({norm(k): norm(v) for k, v in (packet.get("aliases") or {}).items()})
    ledger_ids = set(load_ledger()["gmail_ids"])
    apps = store.list_applications()

    plan = []
    for record in packet.get("records", []):
        report = {"company": record["company"], "title": record["title"],
                  "confidence": record.get("confidence", "review"),
                  "action": "skip", "matched_id": None, "match_reason": "",
                  "patch": {}, "new_events": [], "dup_events": 0, "skip_reason": None}
        prov = [p for p in (record.get("provenance") or []) if p]
        if prov and all(p.split(":", 1)[-1] in ledger_ids or p in ledger_ids for p in prov):
            report["skip_reason"] = "already synced"
            plan.append(report)
            continue

        md = _flatten(record)
        existing, reason = match_record(md, apps, aliases=aliases)
        report["match_reason"] = reason
        if existing is None and ("AMBIGUOUS" in reason or "not found" in reason):
            report["skip_reason"] = reason
            plan.append(report)
            continue

        if existing is None:
            report["action"] = "add"
            rec = new_record(md)
            for k, v in (record.get("fields") or {}).items():
                if k in FIELD_KEYS and v and not rec.get(k):
                    rec[k] = v
            report["patch"] = rec
            report["new_events"], report["dup_events"] = _plan_events(store, None, record.get("events") or [])
        else:
            report["action"] = "update"
            report["matched_id"] = existing["id"]
            patch = build_patch(existing, md)
            for k, v in (record.get("fields") or {}).items():
                if k in FIELD_KEYS and v and not existing.get(k):
                    patch[k] = v
            report["patch"] = patch
            report["new_events"], report["dup_events"] = _plan_events(store, existing["id"], record.get("events") or [])
            if not patch and not report["new_events"]:
                report["action"] = "skip"
                report["skip_reason"] = "no changes"
        plan.append(report)
    return plan


# ---------- applying ----------

def upsert_employers(store, rows: list[dict]) -> int:
    """Merge incoming rules into the Employers sheet by normalized name."""
    if not rows:
        return 0
    merged = store.list_employers()
    by_name = {norm(e.get("employer")): e for e in merged}
    changed = 0
    for row in rows:
        key = norm(row.get("employer"))
        if not key:
            continue
        if key in by_name:
            target = by_name[key]
            for field in ("rule", "status"):
                if row.get(field) and row[field] != target.get(field):
                    target[field] = row[field]
                    changed += 1
        else:
            merged.append({"employer": row["employer"], "rule": row.get("rule", ""),
                           "status": row.get("status", "")})
            changed += 1
    if changed:
        store.replace_employers(merged)
    return changed


def apply_packet(store, history, packet: dict) -> dict:
    plan = plan_packet(store, packet)
    updated = added = events_added = events_deduped = 0
    applied_ids: set = set()

    for record, report in zip(packet.get("records", []), plan):
        events_deduped += report["dup_events"]
        if report["action"] == "skip" and report["skip_reason"] == "no changes":
            # Fully absorbed already — ledger the ids so future sweeps skip the fetch.
            applied_ids |= {p.split(":", 1)[-1] for p in (record.get("provenance") or []) if p}
            continue
        if report["action"] == "update":
            if report["patch"]:
                before, after = store.update_application(report["matched_id"], report["patch"])
                history.record("update", "application", report["matched_id"], before, after,
                               label=f"Sync: {after['company']} — {', '.join(sorted(report['patch']))}")
                updated += 1
            app_id = report["matched_id"]
        elif report["action"] == "add":
            rec = store.add_application(report["patch"])
            history.record("create", "application", rec["id"], None, rec,
                           label=f"Sync: added {rec['company']} — {rec['title']}")
            report["matched_id"] = rec["id"]
            app_id = rec["id"]
            added += 1
        else:
            continue
        for event in report["new_events"]:
            store.add_event(app_id, event)
            events_added += 1
        applied_ids |= {p.split(":", 1)[-1] for p in (record.get("provenance") or []) if p}

    employers_upserted = upsert_employers(store, packet.get("employers") or [])
    if packet.get("aliases"):
        merge_aliases(packet["aliases"])

    summary = {"dry_run": False, "updated": updated, "added": added,
               "skipped": sum(1 for r in plan if r["action"] == "skip"),
               "events_added": events_added, "events_deduped": events_deduped,
               "employers_upserted": employers_upserted, "records": plan}
    record_ledger(applied_ids, {
        "generated_at": packet.get("generated_at"), "source": packet.get("source"),
        "applied_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {k: v for k, v in summary.items() if k != "records"}})
    config.save_settings({"last_sync": packet.get("generated_at") or ""})
    history.record("import", "sync", packet.get("source", "manual"), None,
                   {k: v for k, v in summary.items() if k != "records"},
                   label=f"Sync ({packet.get('source', 'manual')}): {updated} updated, "
                         f"{added} added, {events_added} events",
                   undoable=False)
    return summary
