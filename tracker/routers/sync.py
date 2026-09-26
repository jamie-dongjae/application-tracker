from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from .. import config
from ..importers import review_queue
from ..importers.sync_packet import apply_packet, plan_packet, record_ledger
from ..models import MailCredentialsIn, SyncImportRequest, SyncRecord
from ..services import mailbox
from ..services.mail_sync import run_mail_sync
from ..services.pipeline_state import render_pipeline_state

router = APIRouter()

_MAILBOX_HTTP = {"no_credentials": 428, "auth_failed": 401, "network": 502}


def _mailbox_http(exc: mailbox.MailboxError) -> HTTPException:
    return HTTPException(_MAILBOX_HTTP.get(exc.code, 500),
                         detail={"error": exc.code, "message": str(exc)})


@router.post("/import/sync")
def import_sync(request: Request, body: SyncImportRequest):
    packet = body.packet.model_dump()
    if body.dry_run:
        plan = plan_packet(request.app.state.store, packet)
        return {"dry_run": True,
                "updated": sum(1 for r in plan if r["action"] == "update"),
                "added": sum(1 for r in plan if r["action"] == "add"),
                "skipped": sum(1 for r in plan if r["action"] == "skip"),
                "records": plan}
    return apply_packet(request.app.state.store, request.app.state.history, packet)


@router.post("/sync/mail")
def sync_mail(request: Request):
    try:
        return run_mail_sync(request.app.state.store, request.app.state.history)
    except mailbox.MailboxError as exc:
        raise _mailbox_http(exc)


@router.get("/sync/mail/credentials")
def get_mail_credentials():
    return mailbox.credentials_status()


@router.post("/sync/mail/credentials")
def set_mail_credentials(body: MailCredentialsIn):
    try:
        mailbox.verify_login(body.email, body.app_password)
    except mailbox.MailboxError as exc:
        raise _mailbox_http(exc)
    mailbox.save_credentials(body.email, body.app_password)
    return {"ok": True}


@router.delete("/sync/mail/credentials")
def delete_mail_credentials():
    return {"ok": True, "deleted": mailbox.delete_credentials()}


@router.get("/sync/review")
def list_review(request: Request):
    return {"items": review_queue.pending()}


@router.post("/sync/review/{item_id}/apply")
def apply_review(request: Request, item_id: str):
    items = {i["id"]: i for i in review_queue.load_queue()}
    item = items.get(item_id)
    if item is None:
        raise HTTPException(404, f"review item {item_id} not found")
    if item["status"] != "pending":
        raise HTTPException(409, f"review item already {item['status']}")
    try:
        record = SyncRecord.model_validate(item["proposed"]).model_dump()
    except ValidationError as exc:
        raise HTTPException(422, f"stored proposal invalid: {exc}")
    # Pin generated_at to the current watermark so a queue apply never rewinds
    # (or falsely advances) last_sync — see sync_packet.apply_packet.
    watermark = config.load_settings().get("last_sync") \
        or datetime.now().isoformat(timespec="seconds")
    packet = {"packet_version": 1, "source": "mail-review",
              "generated_at": watermark, "since": "", "records": [record],
              "employers": [], "aliases": {}}
    summary = apply_packet(request.app.state.store, request.app.state.history, packet)
    review_queue.resolve(item_id, "applied")
    return summary


@router.post("/sync/review/{item_id}/dismiss")
def dismiss_review(item_id: str):
    try:
        item = review_queue.resolve(item_id, "dismissed")
    except KeyError:
        raise HTTPException(404, f"review item {item_id} not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    # Ledger the id, else the same mail re-queues on every future sweep.
    record_ledger({item_id}, {"source": "mail-review-dismiss",
                              "generated_at": item.get("added_at"),
                              "applied_at": datetime.now().isoformat(timespec="seconds"),
                              "summary": {"dismissed": 1}})
    return {"ok": True, "dismissed": item_id}


@router.get("/export/pipeline-state")
def pipeline_state(request: Request):
    store = request.app.state.store
    markdown = render_pipeline_state(store.list_applications(), store.list_employers(),
                                     config.load_settings())
    return {"generated_at": datetime.now().isoformat(timespec="seconds"),
            "markdown": markdown}
