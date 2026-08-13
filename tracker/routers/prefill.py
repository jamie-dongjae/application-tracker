from __future__ import annotations

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from ..models import PrefillRequest, PrefillTextRequest
from ..services import parser

router = APIRouter()


@router.post("/prefill")
async def prefill(body: PrefillRequest):
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return await run_in_threadpool(parser.parse_job_posting, url)


@router.post("/prefill/text")
async def prefill_text(body: PrefillTextRequest):
    return await run_in_threadpool(parser.parse_pasted, body.text, body.url.strip())
