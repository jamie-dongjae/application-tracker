from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from ..models import GeocodeRequest

router = APIRouter()


@router.post("/geocode")
async def geocode(request: Request, body: GeocodeRequest):
    geocoder = request.app.state.geocoder
    if geocoder.is_remote(body.query):
        return {"remote": True}
    result = await run_in_threadpool(geocoder.geocode, body.query, force=body.force)
    if not result:
        raise HTTPException(404, f"no match for '{body.query}'")
    return result


@router.post("/geocode/backfill")
def backfill(request: Request):
    return request.app.state.backfill.start()


@router.get("/geocode/backfill/status")
def backfill_status(request: Request):
    return request.app.state.backfill.status()
