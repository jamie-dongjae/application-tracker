from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Request

from ..excel.store import NotFoundError
from ..models import ApplicationIn, ApplicationPatch

router = APIRouter()


def _geocode_new_row(request: Request, fields: dict) -> dict:
    """Resolve coordinates for a new/changed location via the geocoder, if wired."""
    location = (fields.get("location") or "").strip()
    if not location:
        fields["latitude"] = fields["longitude"] = ""
        fields["geo_status"] = ""
        return fields
    geocoder = getattr(request.app.state, "geocoder", None)
    if geocoder is None:
        fields["geo_status"] = "pending"
        return fields
    if geocoder.is_remote(location):
        fields["latitude"] = fields["longitude"] = ""
        fields["geo_status"] = "remote"
        return fields
    result = geocoder.geocode(location)
    if result:
        fields["latitude"], fields["longitude"] = result["lat"], result["lng"]
        fields["geo_status"] = "ok"
    else:
        fields["latitude"] = fields["longitude"] = ""
        fields["geo_status"] = "failed"
    return fields


@router.get("/applications")
def list_applications(request: Request):
    return {"applications": request.app.state.store.list_applications()}


@router.post("/applications", status_code=201)
def create_application(request: Request, body: ApplicationIn):
    fields = body.model_dump()
    fields["date_applied"] = fields.get("date_applied") or date.today().isoformat()
    if fields.get("latitude") in (None, "") or fields.get("longitude") in (None, ""):
        fields = _geocode_new_row(request, fields)
    elif not fields.get("geo_status"):
        fields["geo_status"] = "manual"
    rec = request.app.state.store.add_application(fields)
    request.app.state.history.record(
        "create", "application", rec["id"], None, rec,
        label=f"Added {rec['company']} — {rec['title']}")
    return rec


@router.patch("/applications/{app_id}")
def update_application(request: Request, app_id: int, body: ApplicationPatch):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(400, "empty patch")
    try:
        current = request.app.state.store.get_application(app_id)
        if "location" in patch and patch["location"] != current.get("location") \
                and "latitude" not in patch:
            patch = _geocode_new_row(request, patch)
        before, after = request.app.state.store.update_application(app_id, patch)
    except NotFoundError:
        raise HTTPException(404, f"application {app_id} not found")
    label = f"Updated {after['company']}"
    if before.get("status") != after.get("status"):
        label = f"{after['company']}: {before.get('status') or '—'} → {after['status']}"
    request.app.state.history.record("update", "application", app_id, before, after, label=label)
    return after


@router.delete("/applications/{app_id}")
def delete_application(request: Request, app_id: int):
    try:
        removed = request.app.state.store.delete_application(app_id)
    except NotFoundError:
        raise HTTPException(404, f"application {app_id} not found")
    request.app.state.history.record(
        "delete", "application", app_id, removed, None,
        label=f"Deleted {removed['company']} — {removed['title']}")
    return {"deleted": app_id}


@router.post("/undo")
def undo(request: Request):
    history = request.app.state.history
    store = request.app.state.store
    entry = history.pop_undoable()
    if not entry:
        raise HTTPException(404, "nothing to undo")
    try:
        if entry["entity"] == "application":
            if entry["action"] == "create":
                store.delete_application(entry["id"])
            elif entry["action"] == "delete":
                store.add_application(entry["before"], force_id=entry["id"])
            else:
                store.update_application(entry["id"], entry["before"])
        elif entry["entity"] == "prep":
            if entry["action"] == "create":
                store.delete_prep(entry["id"])
            elif entry["action"] == "delete":
                store.add_prep(entry["before"], force_id=entry["id"])
            else:
                store.update_prep(entry["id"], entry["before"])
    except NotFoundError:
        raise HTTPException(410, "the affected row no longer exists")
    except Exception:
        history.push_back(entry)
        raise
    history.record("undo", entry["entity"], entry["id"], entry.get("after"),
                   entry.get("before"), label=f"Undid: {entry.get('label', '')}", undoable=False)
    return {"undone": entry["label"], "entity": entry["entity"], "id": entry["id"]}


@router.get("/history")
def get_history(request: Request, n: int = 100):
    return {"history": request.app.state.history.recent(n),
            "transitions": request.app.state.history.transitions()}
