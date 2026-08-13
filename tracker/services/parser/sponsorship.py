"""Visa-sponsorship signal scan. Returns the verdict plus the matched snippet
as evidence — never a bare guess."""
from __future__ import annotations

import re

_NEGATIVE = [
    r"(?:do(?:es)? not|don't|doesn't|cannot|can't|unable to|will not|won't|no)\s+(?:currently\s+)?(?:provide|offer|support|sponsor)\w*\s+(?:visa|work permit|sponsorship|immigration)",
    r"no\s+(?:visa\s+)?sponsorship",
    r"sponsorship\s+is\s+not\s+(?:available|provided|offered)",
    r"without\s+(?:the\s+)?need\s+for\s+(?:visa\s+)?sponsorship",
    r"must\s+(?:already\s+)?(?:have|hold|possess)\s+(?:the\s+)?(?:right|authori[sz]ation|permit|eligibility)\s+to\s+work",
    r"(?:right|authori[sz]ed?|eligib\w+)\s+to\s+work\s+in\s+\w+(?:\s+\w+)?\s+(?:is\s+)?required",
    r"(?:eu|e\.u\.|european)\s+(?:work\s+)?(?:citizens?(?:hip)?|nationals?|passport)\s+(?:only|required)",
]

_POSITIVE = [
    r"visa\s+sponsorship\s+(?:is\s+)?(?:available|provided|offered|possible)",
    r"(?:provide|offer|support)\w*\s+(?:visa\s+)?sponsorship",
    r"(?:can|willing to|able to)\s+sponsor",
    r"sponsorship\s+(?:for\s+)?(?:a\s+)?(?:work\s+)?(?:visa|permit)",
    r"highly\s+skilled\s+migrant",
    r"kennismigrant",
    r"30%\s*(?:tax\s+)?ruling",
    r"recogni[sz]ed\s+sponsor",
    r"relocation\s+(?:support|assistance|package|budget)",
    r"work\s+permit\s+(?:support|assistance|sponsorship)",
]


def _find(text: str, patterns: list) -> tuple[str, str] | None:
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            start = max(0, m.start() - 40)
            snippet = re.sub(r"\s+", " ", text[start:m.end() + 60]).strip()
            return m.group(0), ("…" + snippet + "…")
    return None


def scan(text: str) -> dict | None:
    """Return {value: 'Mentioned'|'Not offered', snippet} or None if silent."""
    if not text:
        return None
    negative = _find(text, _NEGATIVE)
    if negative:
        return {"value": "Not offered", "snippet": negative[1]}
    positive = _find(text, _POSITIVE)
    if positive:
        return {"value": "Mentioned", "snippet": positive[1]}
    return None
