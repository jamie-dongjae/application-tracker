from __future__ import annotations

import html as html_lib
import re

from selectolax.parser import HTMLParser


def html_to_text(markup: str) -> str:
    """Strip tags/scripts and collapse whitespace; tolerant of fragments and
    of entity-escaped HTML (Greenhouse ships `&lt;p&gt;…` in its API)."""
    if not markup:
        return ""
    text = html_lib.unescape(markup)
    if "<" not in text:
        return clean_ws(text)
    tree = HTMLParser(text)
    for node in tree.css("script,style,noscript"):
        node.decompose()
    root = tree.body or tree.root
    return clean_ws(root.text(separator=" ")) if root else ""


def clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


WORK_TYPE_PATTERNS = [
    ("Remote", r"\bfully\s+remote\b|\bremote[- ]first\b|\b100%\s*remote\b|\bwork\s+from\s+anywhere\b"),
    ("Hybrid", r"\bhybrid"),  # also matches Dutch "hybride"
    ("Remote", r"\bremote\b"),
    ("Onsite", r"\bon[- ]?site\b|\bin[- ]office\b"),
]


def detect_work_type(text: str) -> str:
    for label, pattern in WORK_TYPE_PATTERNS:
        if re.search(pattern, text or "", re.I):
            return label
    return ""
