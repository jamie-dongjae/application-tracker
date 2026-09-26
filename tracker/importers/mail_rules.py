"""Deterministic mail classifier for the in-app sync button.

Mirrors the HIGH tier of the judgment rubric: only mechanically certain
signals (ATS confirmations, template rejections) on unambiguous company/role
matches are auto-applied; everything else that looks job-related becomes a
review item for a human (or a smarter agent) to decide. Matching is lowercase
substring on normalized text — never sentence structure, since bodies may be
tag-stripped HTML.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .matching import norm

ATS_DOMAINS = ("myworkday", "greenhouse", "lever.co", "ashbyhq", "smartrecruiters",
               "icims", "workable", "recruitee", "teamtailor", "successfactors",
               "jobvite")

CONFIRM_PATTERNS = (
    "received your application", "we have received your application",
    "thank you for applying", "thanks for applying", "thank you for your application",
    "successfully received", "application has been submitted",
    "sollicitatie ontvangen", "bedankt voor je sollicitatie",
    "bedankt voor jouw sollicitatie", "we hebben je sollicitatie",
)

REJECT_PATTERNS = (
    "unfortunately", "regret to inform", "not to proceed", "will not be moving",
    "not moving forward", "other candidates", "decided to pursue other",
    "not been selected", "unsuccessful",
    "helaas", "niet verder", "andere kandidaten", "niet geselecteerd",
)

# Signals that need judgment even when a rejection/confirmation matched.
FORCE_REVIEW_KEYWORDS = ("visa", "sponsorship", "work permit", "werkvergunning",
                         "dutch", "nederlands", "other role", "another role",
                         "different position", "andere functie")

_STOP_COMPANIES = {"apple"}  # common words: only match these via sender domain


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _companies(apps: list[dict]) -> dict:
    """normalized company -> list of apps, aliases folded in by the caller."""
    out: dict[str, list[dict]] = {}
    for a in apps:
        key = norm(a.get("company"))
        if key:
            out.setdefault(key, []).append(a)
    return out


def _find_company(msg: dict, companies: dict, aliases: dict) -> tuple[str | None, bool]:
    """Return (normalized company key, multiple_hits). Sender fields count more
    than the body; short/common names only match through the sender domain."""
    sender_text = norm(msg.get("from_name", "")) + " " + norm(msg.get("from_domain", ""))
    body_text = norm((msg.get("subject") or "") + " " + (msg.get("body") or "")[:1500])
    hits = set()
    for key in companies:
        target = aliases.get(key, key)
        probes = {key, target} | {a for a, t in aliases.items() if t == key}
        for probe in probes:
            if len(probe) < 4 or probe in _STOP_COMPANIES:
                if probe and probe in norm(msg.get("from_domain", "")):
                    hits.add(key)
                continue
            if probe in sender_text or probe in body_text:
                hits.add(key)
                break
    if len(hits) == 1:
        return hits.pop(), False
    return None, len(hits) > 1


def _find_role(msg: dict, rows: list[dict]) -> dict | None:
    """Within one company's applications, pick the row this mail is about."""
    open_rows = [a for a in rows if (a.get("current_state") or "") not in ("closed",)]
    pool = open_rows or rows
    if len(pool) == 1:
        return pool[0]
    text = norm((msg.get("subject") or "") + " " + (msg.get("body") or "")[:1500])
    titled = [a for a in pool if norm(a.get("title"))[:24] and norm(a.get("title"))[:24] in text]
    if len(titled) == 1:
        return titled[0]
    return None


def _mentions(text: str, patterns) -> bool:
    low = " ".join((text or "").lower().split())
    return any(p in low for p in patterns)


def _base_record(msg: dict, app: dict | None, confidence: str, reason: str) -> dict:
    from_ats = any(d in (msg.get("from_domain") or "") for d in ATS_DOMAINS)
    rec = {
        "company": app["company"] if app else (msg.get("from_name") or msg.get("from_domain") or "unknown"),
        "title": app["title"] if app else (msg.get("subject") or "")[:60],
        "match": {"id": app["id"]} if app else {},
        "confidence": confidence,
        "reason": reason,
        "fields": {} if app else ({"source": "Company site"} if from_ats else {}),
        "patch": {},
        "note": "",
        "events": [],
        "provenance": [f"gmail:{msg['gmail_id']}"],
    }
    return rec


def classify_messages(messages: list[dict], apps: list[dict], aliases: dict
                      ) -> tuple[list[dict], list[dict], int]:
    """-> (high_records, review_items, ignored_count). Review items carry the
    email metadata the queue needs alongside the proposed record."""
    companies = _companies(apps)
    high: list[dict] = []
    review: list[dict] = []
    ignored = 0

    for msg in messages:
        text = (msg.get("subject") or "") + "\n" + (msg.get("body") or "")
        from_ats = any(d in (msg.get("from_domain") or "") for d in ATS_DOMAINS)
        company_key, multi = _find_company(msg, companies, aliases)
        app = _find_role(msg, companies[company_key]) if company_key else None

        is_confirm = _mentions(text, CONFIRM_PATTERNS)
        is_reject = _mentions(text, REJECT_PATTERNS)
        needs_judgment = _mentions(text, FORCE_REVIEW_KEYWORDS)

        if not company_key and not multi and not from_ats:
            ignored += 1
            continue

        if is_confirm and app and not needs_judgment and not multi:
            rec = _base_record(msg, app, "high", "ATS/template application confirmation")
            rec["patch"] = {"stage_reached": "confirmed"}
            rec["events"] = [{"date": msg.get("date") or "", "event": "confirmed",
                              "note": (msg.get("subject") or "confirmation")[:60],
                              "provenance": f"gmail:{msg['gmail_id']}"}]
            high.append(rec)
            continue

        if is_reject and app and not needs_judgment and not multi:
            applied = _to_date(app.get("date_applied"))
            mail_day = _to_date(msg.get("date"))
            same_batch = applied and mail_day and (mail_day - applied) <= timedelta(days=1)
            outcome = "rejected_ats" if same_batch else "rejected_cv"
            rec = _base_record(msg, app, "high", "template rejection")
            rec["patch"] = {"current_state": "closed", "closed_by": "employer",
                            "outcome": outcome}
            rec["events"] = [{"date": msg.get("date") or "", "event": "rejected",
                              "note": (msg.get("subject") or "rejection")[:60],
                              "provenance": f"gmail:{msg['gmail_id']}"}]
            high.append(rec)
            continue

        # Everything else job-shaped goes to review with a best guess attached.
        if is_confirm:
            reason = "confirmation, but match/keywords need review"
            guess_patch = {"stage_reached": "confirmed"}
        elif is_reject:
            reason = "rejection, but match/keywords need review"
            guess_patch = {"current_state": "closed", "closed_by": "employer",
                           "outcome": "rejected_cv"}
        else:
            reason = "job-related mail, no template match"
            guess_patch = {}
        rec = _base_record(msg, app, "review", reason)
        rec["patch"] = guess_patch
        review.append({
            "email": {"gmail_id": msg["gmail_id"],
                      "from": msg.get("from_addr") or msg.get("from_name") or "",
                      "subject": msg.get("subject") or "",
                      "date": msg.get("date") or "",
                      "snippet": (msg.get("body") or "")[:300]},
            "proposed": rec,
        })

    return high, review, ignored
