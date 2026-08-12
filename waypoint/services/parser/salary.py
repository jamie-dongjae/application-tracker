"""Salary extraction from free text. Returns yearly-normalized min/max + currency."""
from __future__ import annotations

import re

CURRENCY_SIGNS = {"€": "EUR", "$": "USD", "£": "GBP", "₩": "KRW", "¥": "JPY", "₹": "INR"}
CURRENCY_CODES = ["EUR", "USD", "GBP", "CHF", "SEK", "DKK", "NOK", "PLN", "KRW", "JPY", "SGD", "AUD", "CAD"]

_NUM = r"(\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?\s?[kK]?)"
_SIGN = r"[€$£₩¥₹]"
_RANGE_SEP = r"\s*(?:-|–|—|to|t/m|~)\s*"

_PATTERNS = [
    # €60,000 – €80,000  |  $90k-$120k
    re.compile(rf"(?P<sign>{_SIGN})\s?(?P<min>{_NUM}){_RANGE_SEP}(?:{_SIGN})?\s?(?P<max>{_NUM})"),
    # 60,000 - 80,000 EUR  |  60k–80k EUR
    re.compile(rf"(?P<min>{_NUM}){_RANGE_SEP}(?P<max>{_NUM})\s?(?P<code>{'|'.join(CURRENCY_CODES)})\b", re.I),
    # EUR 60.000 - 80.000
    re.compile(rf"(?P<code>{'|'.join(CURRENCY_CODES)})\s?(?P<min>{_NUM})(?:{_RANGE_SEP}(?P<max>{_NUM}))?", re.I),
    # single value: €65.000
    re.compile(rf"(?P<sign>{_SIGN})\s?(?P<min>{_NUM})"),
]

_PER_MONTH = re.compile(r"per\s+m(?:onth|aand)|/\s*m(?:onth|o|aand)\b|monthly|p/m|\bpm\b", re.I)
_PER_HOUR = re.compile(r"per\s+(?:hour|uur)|/\s*h(?:our|r)?\b|hourly", re.I)
_SALARY_CONTEXT = re.compile(r"salar|compensat|loon|salaris|pay\b|remunerat|бруто|gross|bruto|base", re.I)


def _to_number(raw: str) -> float | None:
    text = raw.strip().replace(" ", "")
    mult = 1000 if text[-1:] in ("k", "K") else 1
    if mult == 1000:
        text = text[:-1]
    # "60.000" / "60,000" thousand separators vs "60.5" decimal
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", text):
        text = re.sub(r"[.,]", "", text)
    else:
        text = text.replace(",", ".")
    try:
        return float(text) * mult
    except ValueError:
        return None


def parse(text: str) -> dict | None:
    """Return {salary_min, salary_max, currency, warnings} or None."""
    if not text:
        return None
    for match in _iter_candidates(text):
        low = _to_number(match["min"])
        high = _to_number(match["max"]) if match.get("max") else None
        if low is None:
            continue
        window = text[max(0, match["start"] - 60):match["end"] + 60]
        warnings = []
        if _PER_HOUR.search(window):
            continue  # hourly rates: too ambiguous to annualize
        if _PER_MONTH.search(window):
            low *= 12
            high = high * 12 if high else None
            warnings.append("Salary was listed per month — converted to yearly (×12).")
        if low < 1000:  # "5-8 years experience" style false positives
            continue
        if high is not None and high < low:
            low, high = high, low
        return {
            "salary_min": round(low),
            "salary_max": round(high) if high else None,
            "currency": match["currency"],
            "warnings": warnings,
        }
    return None


def _iter_candidates(text: str):
    scored = []
    for pattern in _PATTERNS:
        for m in pattern.finditer(text):
            gd = m.groupdict()
            currency = CURRENCY_SIGNS.get(gd.get("sign") or "", "") or (gd.get("code") or "").upper()
            window = text[max(0, m.start() - 80):m.end() + 80]
            score = 2 if _SALARY_CONTEXT.search(window) else 0
            score += 1 if gd.get("max") else 0
            scored.append((score, m.start(), {
                "min": gd.get("min"), "max": gd.get("max"),
                "currency": currency or "EUR",
                "start": m.start(), "end": m.end(),
            }))
    # Highest score first, then earliest occurrence.
    for _, _, cand in sorted(scored, key=lambda t: (-t[0], t[1])):
        yield cand
