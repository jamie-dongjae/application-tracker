"""Nominatim (OpenStreetMap) geocoding with a persistent cache.

Etiquette per the Nominatim usage policy: identifying User-Agent, at most one
request per 1.1 s (global gate), cache everything including misses. Results
are written back to the workbook so each location is resolved once, ever.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

import httpx

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "waypoint-job-tracker/1.0 (https://github.com/waypoint-tracker)"
RATE_SECONDS = 1.1

_REMOTE = re.compile(r"^\s*(fully\s+)?remote\b|\bwork\s+from\s+(home|anywhere)\b|^\s*wfh\s*$", re.I)
_NOISE = re.compile(r"\b(remote|hybrid|on[- ]?site|flexible|hq|headquarters)\b|\(.*?\)", re.I)


class Geocoder:
    def __init__(self, cache_path: Path):
        self.cache_path = Path(cache_path)
        self._lock = threading.Lock()
        self._last_request = 0.0
        self._cache: dict = {}
        try:
            self._cache = json.loads(self.cache_path.read_text())
        except (OSError, ValueError):
            pass

    @staticmethod
    def is_remote(location: str) -> bool:
        return bool(_REMOTE.search(location or ""))

    @staticmethod
    def normalize(location: str) -> str:
        text = _NOISE.sub(" ", location or "")
        text = re.sub(r"\s+", " ", text).strip(" ,;-·|")
        return text

    def _persist(self) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=1))
        except OSError:
            pass

    def cached(self, query: str) -> dict | None:
        entry = self._cache.get(self.normalize(query).lower())
        if entry and not entry.get("miss"):
            return entry
        return None

    def geocode(self, query: str, *, force: bool = False) -> dict | None:
        """Return {lat, lng, display_name, cached} or None. Blocking (rate-gated)."""
        normalized = self.normalize(query)
        if len(normalized) < 2:
            return None
        key = normalized.lower()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and not force:
                return None if entry.get("miss") else {**entry, "cached": True}
            wait = RATE_SECONDS - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            result = self._request(normalized)
            self._last_request = time.monotonic()
            self._cache[key] = result if result else {"miss": True, "ts": time.time()}
            self._persist()
            return {**result, "cached": False} if result else None

    def _request(self, query: str) -> dict | None:
        try:
            resp = httpx.get(NOMINATIM_URL,
                             params={"q": query, "format": "jsonv2", "limit": 1,
                                     "accept-language": "en"},
                             headers={"User-Agent": USER_AGENT},
                             timeout=10.0)
            if resp.status_code != 200:
                return None
            rows = resp.json()
            if not rows:
                return None
            top = rows[0]
            return {"lat": round(float(top["lat"]), 5),
                    "lng": round(float(top["lon"]), 5),
                    "display_name": top.get("display_name", ""),
                    "ts": time.time()}
        except (httpx.HTTPError, ValueError, KeyError):
            return None


class BackfillJob:
    """Background geocoding over rows that have a location but no coordinates."""

    def __init__(self, geocoder: Geocoder, store):
        self.geocoder = geocoder
        self.store = store
        self._thread: threading.Thread | None = None
        self.state = {"running": False, "done": 0, "total": 0, "ok": 0,
                      "failed": [], "current": ""}

    def start(self) -> dict:
        if self._thread and self._thread.is_alive():
            return self.status()
        rows = [r for r in self.store.list_applications()
                if (r.get("location") or "").strip()
                and (r.get("latitude") in ("", None) or r.get("longitude") in ("", None))
                and r.get("geo_status") != "remote"]
        self.state = {"running": True, "done": 0, "total": len(rows), "ok": 0,
                      "failed": [], "current": ""}
        self._thread = threading.Thread(target=self._run, args=(rows,), daemon=True)
        self._thread.start()
        return self.status()

    def _run(self, rows: list) -> None:
        patches: dict = {}
        try:
            for rec in rows:
                location = rec["location"]
                self.state["current"] = location
                if self.geocoder.is_remote(location):
                    patches[rec["id"]] = {"geo_status": "remote"}
                    self.state["ok"] += 1
                else:
                    result = self.geocoder.geocode(location)
                    if result:
                        patches[rec["id"]] = {"latitude": result["lat"],
                                              "longitude": result["lng"],
                                              "geo_status": "ok"}
                        self.state["ok"] += 1
                    else:
                        patches[rec["id"]] = {"geo_status": "failed"}
                        self.state["failed"].append(rec["id"])
                self.state["done"] += 1
                if len(patches) >= 10:
                    self.store.bulk_update_applications(patches)
                    patches = {}
            if patches:
                self.store.bulk_update_applications(patches)
        finally:
            self.state["running"] = False
            self.state["current"] = ""

    def status(self) -> dict:
        return dict(self.state)
