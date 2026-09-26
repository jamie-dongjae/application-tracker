"""Mail sync orchestrator: one button click = fetch → classify → apply → queue."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .. import config
from ..importers.mail_rules import classify_messages
from ..importers.review_queue import add_items, pending_gmail_ids
from ..importers.sync_packet import apply_packet, load_aliases, load_ledger
from . import mailbox

DEFAULT_WINDOW_DAYS = 14


def _since() -> date:
    last = config.load_settings().get("last_sync") or ""
    try:
        anchor = date.fromisoformat(str(last)[:10])
    except ValueError:
        anchor = date.today() - timedelta(days=DEFAULT_WINDOW_DAYS)
    return anchor - timedelta(days=1)  # overlap absorbed by ledger + dedup


def run_mail_sync(store, history) -> dict:
    creds = mailbox.load_credentials()
    messages, warnings = mailbox.fetch_messages(creds, _since())

    known = set(load_ledger()["gmail_ids"]) | pending_gmail_ids()
    fresh = [m for m in messages if m["gmail_id"] not in known]
    already_known = len(messages) - len(fresh)

    high, review, ignored = classify_messages(
        fresh, store.list_applications(), load_aliases())

    # Apply even with zero records: advances last_sync uniformly and ledgers
    # the packet, so the next click starts from now.
    packet = {"packet_version": 1, "source": "mail-button",
              "generated_at": datetime.now().isoformat(timespec="seconds"),
              "since": _since().isoformat(), "records": high,
              "employers": [], "aliases": {}}
    summary = apply_packet(store, history, packet)
    queued = add_items(review)

    return {"fetched": len(messages), "already_known": already_known,
            "applied": {k: summary[k] for k in ("updated", "added", "skipped",
                                                "events_added", "events_deduped")},
            "queued": queued, "ignored": ignored, "warnings": warnings,
            "records": summary["records"]}
