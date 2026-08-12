"""Heuristics over a pasted job description — the fallback when the posting
URL cannot be fetched (LinkedIn authwall, Cloudflare, dead link)."""
from __future__ import annotations

import re

from .textutil import clean_ws, detect_work_type

_LOCATION_LABELS = re.compile(
    r"(?:^|\n)\s*(?:location|based in|office|standort|locatie|werkplek|plaats)\s*[:\-–]\s*(?P<loc>[^\n|•·]{2,60})",
    re.I)
_TITLE_AT_COMPANY = re.compile(r"^(?P<title>.{4,80}?)\s+(?:at|@)\s+(?P<company>.{2,60})$", re.I)
_NOISE_LINE = re.compile(
    r"^(apply|share|save|report|about|benefits|full[- ]time|part[- ]time|posted|reposted|\d+\s+(applicants|views))",
    re.I)


def parse(text: str) -> dict:
    fields: dict = {}
    lines = [clean_ws(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    for line in lines[:8]:
        if _NOISE_LINE.match(line) or len(line) > 90:
            continue
        at = _TITLE_AT_COMPANY.match(line)
        if at:
            fields["title"] = clean_ws(at.group("title"))
            fields["company"] = clean_ws(at.group("company"))
            break
        if "title" not in fields and 4 <= len(line) <= 80:
            fields["title"] = line
        elif "company" not in fields and len(line) <= 50:
            fields["company"] = line
            break

    m = _LOCATION_LABELS.search(text)
    if m:
        fields["location"] = clean_ws(m.group("loc")).strip(".,;")
    else:
        # "City, Country · Hybrid" early-line pattern (LinkedIn paste shape)
        for line in lines[:10]:
            m = re.match(r"^(?P<loc>[A-Z][\w .'-]+,\s*[A-Z][\w .'-]+?)(?:\s*[·•|]\s*|$)", line)
            if m and len(m.group("loc")) <= 60 and not _NOISE_LINE.match(line):
                fields["location"] = clean_ws(m.group("loc"))
                break

    work_type = detect_work_type(text[:4000])
    if work_type:
        fields["work_type"] = work_type

    fields["_description_text"] = clean_ws(text)
    fields["_warnings"] = []
    return fields
