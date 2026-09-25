from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request

from .. import config
from ..importers.sync_packet import apply_packet, plan_packet
from ..models import SyncImportRequest
from ..services.pipeline_state import render_pipeline_state

router = APIRouter()


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


@router.get("/export/pipeline-state")
def pipeline_state(request: Request):
    store = request.app.state.store
    markdown = render_pipeline_state(store.list_applications(), store.list_employers(),
                                     config.load_settings())
    return {"generated_at": datetime.now().isoformat(timespec="seconds"),
            "markdown": markdown}
