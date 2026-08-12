"""HTTP fetching with block/authwall classification.

Job boards behind login walls or bot protection (LinkedIn, Indeed) are
detected and reported as `blocked` so the UI can offer the paste-description
fallback instead of showing a raw error.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 waypoint-tracker/1.0")

TIMEOUT = httpx.Timeout(12.0, connect=6.0)

_BLOCK_MARKERS = [
    "/authwall", "login.microsoftonline", "cf-chl", "cf_chl", "challenge-platform",
    "just a moment", "attention required", "captcha", "verify you are human",
    "signup?trk", "please log in", "sign in to continue",
]


@dataclass
class FetchResult:
    url: str
    final_url: str = ""
    status: int = 0
    text: str = ""
    blocked: bool = False
    error: str = ""
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocked and not self.error and 200 <= self.status < 300


def classify_blocked(status: int, final_url: str, text: str) -> bool:
    if status in (401, 403, 407, 429, 451, 999):
        return True
    haystack = (final_url + " " + text[:4000]).lower()
    return any(marker in haystack for marker in _BLOCK_MARKERS)


def fetch(url: str) -> FetchResult:
    result = FetchResult(url=url)
    try:
        with httpx.Client(follow_redirects=True, timeout=TIMEOUT,
                          headers={"User-Agent": USER_AGENT,
                                   "Accept-Language": "en"}) as client:
            resp = client.get(url)
        result.status = resp.status_code
        result.final_url = str(resp.url)
        result.text = resp.text
        result.blocked = classify_blocked(resp.status_code, result.final_url, resp.text)
        if result.blocked:
            result.warnings.append("The site blocks automated access — paste the job description instead.")
        elif resp.status_code >= 400:
            result.error = f"HTTP {resp.status_code}"
    except httpx.HTTPError as exc:
        result.error = type(exc).__name__
        result.warnings.append(f"Could not reach the page ({type(exc).__name__}).")
    return result


def fetch_json(url: str) -> dict | list | None:
    try:
        with httpx.Client(follow_redirects=True, timeout=TIMEOUT,
                          headers={"User-Agent": USER_AGENT, "Accept": "application/json"}) as client:
            resp = client.get(url)
        if resp.status_code == 200:
            return resp.json()
    except (httpx.HTTPError, ValueError):
        pass
    return None
