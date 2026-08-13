"""OpenGraph / <title> heuristics — the last resort for plain career pages."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from selectolax.parser import HTMLParser

from .textutil import clean_ws

SOURCE_BY_DOMAIN = {
    "linkedin.com": "LinkedIn",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "greenhouse.io": "Company site",
    "lever.co": "Company site",
    "ashbyhq.com": "Company site",
    "workable.com": "Company site",
    "recruitee.com": "Company site",
    "smartrecruiters.com": "Company site",
    "myworkdayjobs.com": "Company site",
    "join.com": "Join",
    "otta.com": "Otta",
    "welcometothejungle.com": "WTTJ",
    "wellfound.com": "Wellfound",
    "iamexpat.nl": "IamExpat",
    "magnet.me": "Magnet.me",
}

_TITLE_SPLIT = re.compile(r"\s+[|–—·]\s+|\s+-\s+")


def source_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for needle, label in SOURCE_BY_DOMAIN.items():
        if needle in host:
            return label
    return "Company site" if host else ""


def company_from_host(url: str) -> str:
    """`careers.acme.com` → `Acme` — a weak but honest guess."""
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    generic = {"careers", "jobs", "apply", "boards", "job-boards", "work", "join"}
    parts = [p for p in host.split(".")[:-1] if p not in generic]
    if not parts:
        return ""
    return parts[-1].replace("-", " ").title()


def _meta(tree: HTMLParser, *names: str) -> str:
    for name in names:
        node = tree.css_first(f'meta[property="{name}"], meta[name="{name}"]')
        if node:
            content = node.attributes.get("content") or ""
            if clean_ws(content):
                return clean_ws(content)
    return ""


def extract(html: str, url: str) -> dict:
    tree = HTMLParser(html)
    fields: dict = {}

    og_title = _meta(tree, "og:title", "twitter:title")
    page_title = clean_ws(tree.css_first("title").text()) if tree.css_first("title") else ""
    site_name = _meta(tree, "og:site_name")
    raw = og_title or page_title

    if raw:
        parts = [clean_ws(p) for p in _TITLE_SPLIT.split(raw) if clean_ws(p)]
        # "Senior Analyst at Acme" pattern
        at_match = re.match(r"^(?P<title>.{4,80}?)\s+(?:at|@)\s+(?P<company>.{2,60})$", raw, re.I)
        if at_match:
            fields["title"] = clean_ws(at_match.group("title"))
            fields["company"] = clean_ws(at_match.group("company"))
        elif parts:
            fields["title"] = parts[0]
            if len(parts) > 1:
                fields["company"] = parts[-1]
    if site_name and not fields.get("company"):
        fields["company"] = site_name

    description = _meta(tree, "og:description", "description")
    if description:
        fields["_description_text"] = description

    fields["source"] = source_from_url(url)
    if not fields.get("company"):
        guess = company_from_host(url)
        if guess:
            fields["company"] = guess
    fields["_warnings"] = []
    return fields
