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


def _extract_salary(node: dict) -> dict | None:
    base = node.get("baseSalary")
    if not isinstance(base, dict):
        return None
    value = base.get("value")
    if not isinstance(value, dict):
        value = base
    low = value.get("minValue") or value.get("value")
    high = value.get("maxValue")
    unit = str(value.get("unitText") or "YEAR").upper()
    try:
        low = float(low) if low is not None else None
        high = float(high) if high is not None else None
    except (TypeError, ValueError):
        return None
    if low is None:
        return None
    warnings = []
    if unit == "MONTH":
        low, high = low * 12, high * 12 if high else None
        warnings.append("Salary was listed per month — converted to yearly (×12).")
    elif unit == "HOUR":
        return None
    currency = str(base.get("currency") or node.get("salaryCurrency") or "").upper()
    return {"salary_min": round(low), "salary_max": round(high) if high else None,
            "currency": currency, "warnings": warnings}


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

    salary = _extract_salary(node)
    if salary:
        warnings.extend(salary.pop("warnings"))
        fields.update({k: v for k, v in salary.items() if v})

    description = html_to_text(str(node.get("description") or ""))
    if description:
        fields["_description_text"] = description

    fields["_warnings"] = warnings
    return fields
