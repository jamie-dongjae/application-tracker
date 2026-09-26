"""Mail review queue: ambiguous mail waiting for a human (or agent) decision.

This file (data/review_queue.json) is the cross-channel contract — the in-app
panel and any external agent both read pending items and resolve them through
the /api/sync/review endpoints. Item shape:

    {"id": "<gmail hex id>", "added_at": iso,
     "email": {"gmail_id", "from", "subject", "date", "snippet"},
     "proposed": <sync-packet SyncRecord>,
     "status": "pending" | "applied" | "dismissed",
     "resolved_at": iso | null}
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from .. import config

_PRUNE_AFTER_DAYS = 30


def load_queue() -> list[dict]:
    try:
        items = json.loads(config.review_queue_path().read_text())
    except (OSError, ValueError):
        return []
    cutoff = (datetime.now() - timedelta(days=_PRUNE_AFTER_DAYS)).isoformat(timespec="seconds")
    pruned = [i for i in items
              if i.get("status") == "pending" or (i.get("resolved_at") or "9999") > cutoff]
    if len(pruned) != len(items):
        save_queue(pruned)
    return pruned


def save_queue(items: list[dict]) -> None:
    config.review_queue_path().write_text(json.dumps(items, indent=2))


def pending() -> list[dict]:
    return [i for i in load_queue() if i.get("status") == "pending"]


def pending_gmail_ids() -> set:
    return {i["id"] for i in load_queue()}  # any status: resolved ids must not re-queue


def add_items(new_items: list[dict]) -> int:
    """new_items: [{"email": {...}, "proposed": {...}}]. Skips known gmail ids."""
    items = load_queue()
    known = {i["id"] for i in items}
    added = 0
    for entry in new_items:
        gid = entry["email"]["gmail_id"]
        if gid in known:
            continue
        items.append({"id": gid,
                      "added_at": datetime.now().isoformat(timespec="seconds"),
                      "email": entry["email"], "proposed": entry["proposed"],
                      "status": "pending", "resolved_at": None})
        known.add(gid)
        added += 1
    if added:
        save_queue(items)
    return added


def resolve(item_id: str, status: str) -> dict:
    items = load_queue()
    for item in items:
        if item["id"] == item_id:
            if item["status"] != "pending":
                raise ValueError(f"item {item_id} already {item['status']}")
            item["status"] = status
            item["resolved_at"] = datetime.now().isoformat(timespec="seconds")
            save_queue(items)
            return item
    raise KeyError(item_id)
