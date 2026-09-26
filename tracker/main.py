from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .excel.store import ExcelStore, WorkbookLockedError
from .routers import applications, geocode, meta, prefill, prep, sync
from .services.geocoder import BackfillJob, Geocoder
from .services.history import History

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(store: ExcelStore | None = None, history: History | None = None,
               geocoder: Geocoder | None = None) -> FastAPI:
    app = FastAPI(title="Application Tracker", version="1.0.0",
                  description="Local-first job application tracker with an Excel backend.")

    app.state.store = store or ExcelStore(config.xlsx_path())
    app.state.history = history or History(config.history_path())
    app.state.geocoder = geocoder or Geocoder(config.geocode_cache_path())
    app.state.backfill = BackfillJob(app.state.geocoder, app.state.store)

    for router in (meta.router, applications.router, prep.router,
                   prefill.router, geocode.router, sync.router):
        app.include_router(router, prefix="/api")

    @app.exception_handler(WorkbookLockedError)
    async def locked_handler(_request: Request, exc: WorkbookLockedError):
        return JSONResponse(status_code=409,
                            content={"error": "workbook_locked", "detail": str(exc)})

    @app.middleware("http")
    async def cache_policy(request: Request, call_next):
        # Local-first app: heuristic browser caching only ever serves stale
        # modules after an update. ETag revalidation stays (304s are cheap).
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/vendor/"):
            response.headers["Cache-Control"] = "max-age=86400"
        elif path.startswith(("/js/", "/css/")):
            response.headers["Cache-Control"] = "no-cache"
        elif response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-store"
        return response

    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app


app = create_app()
