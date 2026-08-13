"""Prefill orchestrator: URL (or pasted text) → structured application fields.

Priority: ATS JSON API → JSON-LD JobPosting → OG/meta heuristics. Later stages
only fill gaps. Every returned field carries provenance so the review UI can
show where each value came from.
"""
from __future__ import annotations

from datetime import date

from .. import fetcher
from . import ats, jsonld, meta_tags, sponsorship, text_heuristics

FIELD_KEYS = ["company", "title", "location", "work_type", "source", "sponsorship"]

_METHOD_LABELS = {
    "greenhouse": "Greenhouse API", "lever": "Lever API", "ashby": "Ashby API",
    "workable": "Workable API", "recruitee": "Recruitee API",
    "smartrecruiters": "SmartRecruiters API", "workday": "Workday API",
    "jsonld": "JSON-LD", "meta": "Page metadata", "pasted_text": "Pasted text",
    "url_only": "URL",
}


def _merge(dst: dict, provenance: dict, src: dict | None, label: str) -> None:
    if not src:
        return
    for key, value in src.items():
        if key.startswith("_") or value in (None, ""):
            continue
        if dst.get(key) in (None, ""):
            dst[key] = value
            provenance[key] = label


def _finish(fields: dict, provenance: dict, warnings: list, method: str,
            url: str, description: str) -> dict:
    if not fields.get("source"):
        fields["source"] = meta_tags.source_from_url(url)
        if fields["source"]:
            provenance.setdefault("source", "URL")

    if description:
        sponsor = sponsorship.scan(description)
        if sponsor and not fields.get("sponsorship"):
            fields["sponsorship"] = sponsor["value"]
            provenance["sponsorship"] = "Description scan"
            fields["_sponsorship_snippet"] = sponsor["snippet"]
        if not fields.get("work_type"):
            from .textutil import detect_work_type
            wt = detect_work_type(description[:4000])
            if wt:
                fields["work_type"] = wt
                provenance["work_type"] = "Description scan"

    evidence = {"sponsorship_snippet": fields.pop("_sponsorship_snippet", "")}
    clean = {k: v for k, v in fields.items() if not k.startswith("_") and v not in (None, "")}
    clean.setdefault("url", url)
    clean.setdefault("date_applied", date.today().isoformat())
    return {
        "fields": clean,
        "provenance": provenance,
        "method": _METHOD_LABELS.get(method, method),
        "warnings": [w for w in warnings if w],
        "evidence": evidence,
    }


def parse_job_posting(url: str) -> dict:
    fields: dict = {}
    provenance: dict = {}
    warnings: list = []
    description = ""
    method = "url_only"

    ref = ats.detect(url)
    if ref:
        payload = fetcher.fetch_json(ref.api_url)
        if payload is not None:
            parsed = ats.PARSERS[ref.kind](payload, ref)
            if parsed and parsed.get("title"):
                method = ref.kind
                description = parsed.get("_description_text", "")
                _merge(fields, provenance, parsed, _METHOD_LABELS[ref.kind])
            else:
                warnings.append(f"{ref.kind} API response had an unexpected shape — fell back to the page.")
        else:
            warnings.append(f"{ref.kind} API was unreachable — fell back to the page.")

    if not fields.get("title"):
        page = fetcher.fetch(url)
        if page.blocked:
            warnings.extend(page.warnings)
            guess = {"company": meta_tags.company_from_host(url)}
            _merge(fields, provenance, guess, "URL")
            return {**_finish(fields, provenance, warnings, "url_only", url, ""),
                    "blocked": True}
        if page.error:
            warnings.extend(page.warnings or [f"Fetch failed: {page.error}"])
            return {**_finish(fields, provenance, warnings, "url_only", url, ""),
                    "blocked": False, "fetch_error": page.error}

        structured = jsonld.extract(page.text)
        if structured:
            method = "jsonld"
            warnings.extend(structured.get("_warnings", []))
            description = description or structured.get("_description_text", "")
            _merge(fields, provenance, structured, "JSON-LD")

        fallback = meta_tags.extract(page.text, url)
        if fallback:
            if method == "url_only":
                method = "meta"
            description = description or fallback.get("_description_text", "")
            _merge(fields, provenance, fallback, "Page metadata")

    return _finish(fields, provenance, warnings, method, url, description)


def parse_pasted(text: str, url: str = "") -> dict:
    fields: dict = {}
    provenance: dict = {}
    parsed = text_heuristics.parse(text)
    description = parsed.get("_description_text", "")
    _merge(fields, provenance, parsed, "Pasted text")
    if url:
        _merge(fields, provenance, {"company": meta_tags.company_from_host(url)}, "URL")
    return _finish(fields, provenance, [], "pasted_text", url, description)
