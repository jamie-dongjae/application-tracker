"""Record matching + merge engine shared by importers (backfill script, sync API).

Matches an incoming (company, title) record against existing applications and
builds merge patches. Deliberately conservative: ambiguity is reported, never
guessed. Company aliases are caller-supplied — the repo ships no personal data.
"""
from __future__ import annotations

import re

from ..excel import schema

V4_FIELDS = ("track", "stage_reached", "current_state", "outcome", "closed_by",
             "gates", "contacts", "next_action", "due")

_STOP_TOKENS = {"the", "and", "for", "with"}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _tokens(title: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (title or "").lower()) if len(t) >= 3 and t not in _STOP_TOKENS}


def match_record(md: dict, apps: list[dict], *, aliases: dict[str, str] | None = None,
                 exact_title_only: bool = False):
    """Return (app or None, reason). Never guesses: ambiguity returns None with a reason.

    `md` needs `company` and `title`; optional `match` dict supports
    {"id": N} (explicit row), {"company": ..., "title": ...} (override the
    values used for matching) and {"title_contains": [normalized keywords]}.
    `aliases` maps normalized incoming company names to normalized tracker names.
    """
    m = md.get("match") or {}
    if "id" in m:
        for a in apps:
            if a["id"] == m["id"]:
                return a, f"explicit id {m['id']}"
        return None, f"explicit id {m['id']} not found"

    company_md = norm(m.get("company") or md["company"])
    company_md = (aliases or {}).get(company_md, company_md)
    candidates = []
    for a in apps:
        ca = norm(a.get("company"))
        if ca == company_md:
            candidates.append(a)
        elif len(company_md) >= 4 and len(ca) >= 4 and (company_md in ca or ca in company_md):
            candidates.append(a)
    if not candidates:
        return None, "no company match"

    title_md = norm(m.get("title") or md["title"])
    exact = [a for a in candidates if norm(a.get("title")) == title_md]
    if len(exact) == 1:
        return exact[0], "exact title"
    if len(exact) > 1:
        return None, f"AMBIGUOUS exact title x{len(exact)}"
    if exact_title_only:
        return None, "no exact title (exact-only mode)"

    contains = m.get("title_contains")
    if contains:
        hits = [a for a in candidates if all(kw in norm(a.get("title")) for kw in contains)]
        if len(hits) == 1:
            return hits[0], f"title_contains {contains}"
        if len(hits) > 1:
            return None, f"AMBIGUOUS title_contains {contains} x{len(hits)}"
        return None, "no title_contains match"

    if len(candidates) == 1:
        if _tokens(md["title"]) & _tokens(candidates[0].get("title")):
            return candidates[0], "single company row, token overlap (warn)"
        return None, "single company row but titles unrelated"
    return None, f"AMBIGUOUS {len(candidates)} company rows, no title rule"


def build_patch(existing: dict, md: dict) -> dict:
    """Merge incoming values onto an existing record. Incoming wins when
    non-empty, except stage_reached which is monotonic (the further stage wins)."""
    patch = {}
    for key in V4_FIELDS:
        value = md.get(key, "")
        if not value:
            continue
        if key == "stage_reached":
            current = existing.get("stage_reached") or ""
            if schema.STAGE_IDX.get(value, -1) > schema.STAGE_IDX.get(current, -1):
                patch[key] = value
        elif value != existing.get(key):
            patch[key] = value
    if md.get("set_company") and md["set_company"] != existing.get("company"):
        patch["company"] = md["set_company"]
    note = md.get("note") or ""
    if md.get("closed"):
        note = f"closed {md['closed']}" + (f": {note}" if note else "")
    if note and note not in (existing.get("notes") or ""):
        patch["notes"] = ((existing.get("notes") or "") + "\n" + note).strip()
    if md.get("applied") and not existing.get("date_applied"):
        patch["date_applied"] = md["applied"]
    return patch


def new_record(md: dict) -> dict:
    rec = {
        "company": md.get("set_company") or md["company"],
        "title": md["title"],
        "date_applied": md.get("date_applied") or md.get("applied") or md.get("date") or "",
        "source": md.get("source", ""),
        "notes": md.get("note", ""),
    }
    for key in V4_FIELDS:
        rec[key] = md.get(key, "")
    if md.get("closed"):
        rec["notes"] = (rec["notes"] + f"\nclosed {md['closed']}").strip()
    return rec
