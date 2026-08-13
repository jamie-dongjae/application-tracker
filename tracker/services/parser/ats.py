"""ATS detection and structured parsing.

Most applicant-tracking systems expose free, unauthenticated JSON for public
postings. `detect()` is pure (URL → AtsRef) so it is trivially testable; each
`parse_*` is pure (payload dict → fields dict). Network access happens only in
the orchestrator via fetcher.fetch_json.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from .textutil import clean_ws, detect_work_type, html_to_text


@dataclass
class AtsRef:
    kind: str          # greenhouse | lever | ashby | workable | recruitee | smartrecruiters | workday
    api_url: str
    company_hint: str = ""
    job_hint: str = ""  # id/slug used to select the right posting in board-wide payloads


def _prettify(slug: str) -> str:
    return clean_ws(unquote(slug).replace("-", " ").replace("_", " ")).title()


def detect(url: str) -> AtsRef | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.rstrip("/")

    m = re.match(r"(?:boards|job-boards)(\.eu)?\.greenhouse\.io$", host)
    if m:
        parts = [p for p in path.split("/") if p]
        # /{board}/jobs/{id}  (embedded boards use the same shape)
        if len(parts) >= 3 and parts[-2] == "jobs":
            eu = ".eu" if m.group(1) else ""
            board, job_id = parts[0], parts[-1]
            return AtsRef("greenhouse",
                          f"https://boards-api{eu}.greenhouse.io/v1/boards/{board}/jobs/{job_id}",
                          company_hint=_prettify(board))

    m = re.match(r"jobs(\.eu)?\.lever\.co$", host)
    if m:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            eu = ".eu" if m.group(1) else ""
            org, posting = parts[0], parts[1]
            return AtsRef("lever", f"https://api{eu}.lever.co/v0/postings/{org}/{posting}",
                          company_hint=_prettify(org))

    if host == "jobs.ashbyhq.com":
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            org = parts[0]
            return AtsRef("ashby",
                          f"https://api.ashbyhq.com/posting-api/job-board/{org}",
                          company_hint=_prettify(org), job_hint=parts[1])

    if host == "apply.workable.com":
        m = re.match(r"^/([^/]+)/j/([^/]+)", path + "/")
        if m:
            org, shortcode = m.group(1), m.group(2)
            return AtsRef("workable",
                          f"https://apply.workable.com/api/v2/accounts/{org}/jobs/{shortcode}",
                          company_hint=_prettify(org))

    if host.endswith(".recruitee.com"):
        m = re.match(r"^/o/([^/]+)", path)
        if m:
            org = host.split(".")[0]
            return AtsRef("recruitee", f"https://{org}.recruitee.com/api/offers/{m.group(1)}",
                          company_hint=_prettify(org))

    if host in ("jobs.smartrecruiters.com", "careers.smartrecruiters.com"):
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            org = parts[0]
            job_id = re.match(r"^(\d+)", parts[1])
            if job_id:
                return AtsRef("smartrecruiters",
                              f"https://api.smartrecruiters.com/v1/companies/{org}/postings/{job_id.group(1)}",
                              company_hint=_prettify(org))

    m = re.match(r"^([\w-]+)\.(wd\d+)\.myworkdayjobs\.com$", host)
    if m:
        tenant, wd = m.group(1), m.group(2)
        parts = [p for p in path.split("/") if p]
        if "job" in parts:
            job_idx = parts.index("job")
            # /{lang?}/{site}/job/{location...}/{slug}
            site_parts = parts[:job_idx]
            slug = parts[-1]
            if site_parts:
                site = site_parts[-1]
                return AtsRef("workday",
                              f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/job/{slug}",
                              company_hint=_prettify(tenant))
    return None


# ---------- per-ATS payload parsers (pure) ----------

def parse_greenhouse(payload: dict, ref: AtsRef) -> dict:
    fields = {
        "title": clean_ws(payload.get("title") or ""),
        "company": clean_ws((payload.get("company_name") or ref.company_hint)),
        "location": clean_ws(((payload.get("location") or {}).get("name") or "")),
    }
    description = html_to_text(payload.get("content") or "")
    if description:
        fields["_description_text"] = description
        fields["work_type"] = detect_work_type(fields["location"] + " " + description[:2000])
    return fields


def parse_lever(payload: dict, ref: AtsRef) -> dict:
    categories = payload.get("categories") or {}
    workplace = str(payload.get("workplaceType") or "").lower()
    work_type = {"remote": "Remote", "hybrid": "Hybrid", "on-site": "Onsite", "onsite": "Onsite"}.get(workplace, "")
    fields = {
        "title": clean_ws(payload.get("text") or ""),
        "company": ref.company_hint,
        "location": clean_ws(categories.get("location") or ""),
        "work_type": work_type,
        "_description_text": clean_ws(payload.get("descriptionPlain") or "") or
                             html_to_text(payload.get("description") or ""),
    }
    return fields


def parse_ashby(payload: dict, ref: AtsRef) -> dict | None:
    jobs = payload.get("jobs") or []
    target = None
    for job in jobs:
        haystack = " ".join(str(job.get(k) or "") for k in ("id", "jobUrl", "applyUrl", "title"))
        if ref.job_hint and ref.job_hint in haystack:
            target = job
            break
    if target is None:
        target = jobs[0] if len(jobs) == 1 else None
    if target is None:
        return None
    fields = {
        "title": clean_ws(target.get("title") or ""),
        "company": ref.company_hint,
        "location": clean_ws(target.get("location") or ""),
        "work_type": "Remote" if target.get("isRemote") else "",
        "_description_text": html_to_text(target.get("descriptionHtml") or "") or
                             clean_ws(target.get("descriptionPlain") or ""),
    }
    return fields


def parse_workable(payload: dict, ref: AtsRef) -> dict:
    location = payload.get("location") or {}
    parts = [location.get("city"), location.get("country")]
    workplace = str(payload.get("workplace") or "").lower()
    work_type = {"remote": "Remote", "hybrid": "Hybrid", "on_site": "Onsite"}.get(workplace, "")
    return {
        "title": clean_ws(payload.get("title") or ""),
        "company": clean_ws(payload.get("company_name") or ref.company_hint),
        "location": ", ".join(clean_ws(str(p)) for p in parts if p),
        "work_type": work_type,
        "_description_text": html_to_text(payload.get("description") or ""),
    }


def parse_recruitee(payload: dict, ref: AtsRef) -> dict:
    offer = payload.get("offer") or payload
    parts = [offer.get("city"), offer.get("country")]
    return {
        "title": clean_ws(offer.get("title") or ""),
        "company": clean_ws(offer.get("company_name") or ref.company_hint),
        "location": clean_ws(offer.get("location") or "") or
                    ", ".join(clean_ws(str(p)) for p in parts if p),
        "work_type": "Remote" if offer.get("remote") else "",
        "_description_text": html_to_text(offer.get("description") or ""),
    }


def parse_smartrecruiters(payload: dict, ref: AtsRef) -> dict:
    location = payload.get("location") or {}
    parts = [location.get("city"), location.get("country")]
    company = (payload.get("company") or {}).get("name") or ref.company_hint
    description = ""
    sections = ((payload.get("jobAd") or {}).get("sections") or {})
    for section in sections.values():
        if isinstance(section, dict) and section.get("text"):
            description += html_to_text(section["text"]) + " "
    return {
        "title": clean_ws(payload.get("name") or ""),
        "company": clean_ws(company),
        "location": ", ".join(clean_ws(str(p)) for p in parts if p),
        "work_type": "Remote" if location.get("remote") else "",
        "_description_text": clean_ws(description),
    }


def parse_workday(payload: dict, ref: AtsRef) -> dict | None:
    info = payload.get("jobPostingInfo")
    if not isinstance(info, dict):
        return None
    location = clean_ws(info.get("location") or "")
    country = clean_ws(info.get("country") or "")
    if country and country.lower() not in location.lower():
        location = f"{location}, {country}" if location else country
    return {
        "title": clean_ws(info.get("title") or ""),
        "company": ref.company_hint,
        "location": location,
        "work_type": "Remote" if str(info.get("remoteType") or "").lower().startswith("remote") else "",
        "_description_text": html_to_text(info.get("jobDescription") or ""),
    }


PARSERS = {
    "greenhouse": parse_greenhouse,
    "lever": parse_lever,
    "ashby": parse_ashby,
    "workable": parse_workable,
    "recruitee": parse_recruitee,
    "smartrecruiters": parse_smartrecruiters,
    "workday": parse_workday,
}
