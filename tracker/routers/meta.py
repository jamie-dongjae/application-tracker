from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from .. import config
from ..models import ImportRequest, SettingsPatch

router = APIRouter()


@router.get("/health")
def health(request: Request):
    info = request.app.state.store.info()
    return {"ok": True, **info}


@router.get("/settings")
def get_settings():
    return config.load_settings()


@router.put("/settings")
def put_settings(body: SettingsPatch):
    return config.save_settings({k: v for k, v in body.model_dump().items() if v is not None})


@router.post("/import/legacy")
def import_legacy(request: Request, body: ImportRequest):
    from ..excel.legacy import import_legacy_workbook

    src = Path(body.path).expanduser()
    if not src.exists():
        raise HTTPException(404, f"file not found: {src}")
    summary = import_legacy_workbook(src, request.app.state.store)
    request.app.state.history.record(
        "import", "workbook", str(src), None, summary,
        label=f"Imported {summary['applications']} applications, {summary['prep']} prep rows",
        undoable=False)
    return summary
