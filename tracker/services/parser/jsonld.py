"""schema.org/JobPosting extraction from JSON-LD blocks — the most reliable
signal on company career pages and most job boards."""
from __future__ import annotations

import json
import re

from selectolax.parser import HTMLParser

from .textutil import clean_ws, detect_work_type, html_to_text


def _json_loads_tolerant(raw: str):
    for candidate in (raw, re.sub(r",\s*([}\]])", r"\1", raw)):
        try:
            return json.loads(candidate)
        except ValueError:
            continue
    return None


def _iter_nodes(data):
    """Yield every dict inside arbitrarily nested JSON-LD (@graph, arrays)."""
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from _iter_nodes(value)
    elif isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)


def _is_jobposting(node: dict) -> bool:
    node_type = node.get("@type", "")
    types = node_type if isinstance(node_type, list) else [node_type]
    return any("jobposting" in str(t).lower() for t in types)


def find_jobposting(html: str) -> dict | None:
    tree = HTMLParser(html)
    for script in tree.css('script[type="application/ld+json"]'):
        data = _json_loads_tolerant(script.text() or "")
        if data is None:
            continue
        for node in _iter_nodes(data):
            if _is_jobposting(node):
                return node
    return None


def _format_location(node: dict) -> str:
    locations = node.get("jobLocation") or []
    if isinstance(locations, dict):
        locations = [locations]
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        address = loc.get("address") or {}
        if isinstance(address, str):
            return clean_ws(address)
        parts = [address.get("addressLocality"), address.get("addressRegion"),
                 address.get("addressCountry")]
        parts = [clean_ws(str(p)) for p in parts if p and clean_ws(str(p))]
        # Drop region if it duplicates locality; country codes stay as-is.
        deduped = []
        for p in parts:
            if p not in deduped:
                deduped.append(p)
        if deduped:
            return ", ".join(deduped)
    return ""


def extract(html: str) -> dict | None:
    """Return prefill fields from the first JobPosting node, or None."""
    node = find_jobposting(html)
    if not node:
        return None
    fields, warnings = {}, []

    if node.get("title"):
        fields["title"] = clean_ws(str(node["title"]))
    org = node.get("hiringOrganization")
    if isinstance(org, dict) and org.get("name"):
        fields["company"] = clean_ws(str(org["name"]))
    elif isinstance(org, str):
        fields["company"] = clean_ws(org)

    location = _format_location(node)
    if location:
        fields["location"] = location
    if str(node.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        fields["work_type"] = "Remote"

    employment = node.get("employmentType")
    if employment and not fields.get("work_type"):
        as_text = " ".join(employment) if isinstance(employment, list) else str(employment)
        fields["work_type"] = detect_work_type(as_text)

    description = html_to_text(str(node.get("description") or ""))
    if description:
        fields["_description_text"] = description

    fields["_warnings"] = warnings
    return fields
