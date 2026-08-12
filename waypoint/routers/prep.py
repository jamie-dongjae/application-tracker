from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..excel.store import NotFoundError
from ..models import PrepIn, PrepPatch

router = APIRouter()


@router.get("/prep")
def list_prep(request: Request):
    return {"prep": request.app.state.store.list_prep()}


@router.post("/prep", status_code=201)
def create_prep(request: Request, body: PrepIn):
    rec = request.app.state.store.add_prep(body.model_dump())
    request.app.state.history.record("create", "prep", rec["id"], None, rec,
                                     label=f"Added prep: {rec['question'][:60]}")
    return rec


@router.patch("/prep/{prep_id}")
def update_prep(request: Request, prep_id: int, body: PrepPatch):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(400, "empty patch")
    try:
        before, after = request.app.state.store.update_prep(prep_id, patch)
    except NotFoundError:
        raise HTTPException(404, f"prep {prep_id} not found")
    request.app.state.history.record("update", "prep", prep_id, before, after,
                                     label=f"Updated prep: {after['question'][:60]}")
    return after


@router.delete("/prep/{prep_id}")
def delete_prep(request: Request, prep_id: int):
    try:
        removed = request.app.state.store.delete_prep(prep_id)
    except NotFoundError:
        raise HTTPException(404, f"prep {prep_id} not found")
    request.app.state.history.record("delete", "prep", prep_id, removed, None,
                                     label=f"Deleted prep: {removed['question'][:60]}")
    return {"deleted": prep_id}
