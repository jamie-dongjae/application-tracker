#!/usr/bin/env python3
"""Backfill v2 (2026-09-25): apply the Gmail-sweep categorization to the tracker.

    python scripts/backfill_v2.py [--data data/tracker.xlsx] [--dry-run]

Source of truth: ~/Desktop/tracker-backfill-v2-2026-09-25.md, hand-transcribed
into the data blocks below. Upserts on (company, role): matched records are
patched (stage_reached is monotonic — the tracker's more specific stage wins),
unmatched records are added. Run with the server stopped.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracker.excel import schema  # noqa: E402
from tracker.excel.store import ExcelStore  # noqa: E402
from tracker.services.history import History  # noqa: E402

STAMP = "2026-09-25"

# ---------------------------------------------------------------------------
# Section 1 — live records (full v4 fields + event timelines)
# ---------------------------------------------------------------------------

LIVE = [
    {
        "company": "Cummins", "title": "IT Solution Engineer",
        "track": "career", "stage_reached": "recruiter_screen",
        "current_state": "awaiting_decision",
        "gates": "ind_confirmed, commute_risk",
        "contacts": "Andy Livingston (screening)\nDenise Rückert, TA Partner Cummins Germany, denise.rueckert@cummins.com",
        "next_action": "wait for go/no-go on the new requisition; chase Denise if silent by 2026-10-01",
        "due": "2026-10-01",
        "note": "prep file: Cummins_IT_Solution_Engineer_Prep.md",
        "events": [
            ("", "applied", ""),
            ("2026-08-26", "recruiter_screen", 'call with Andy Livingston, went well, go/no-go promised "next week"'),
            ("2026-09-09", "note", "Denise asked work-authorization; replied same day (student permit to end Nov 2026, zoekjaar next)"),
            ("2026-09-17", "note", "application moved to a new requisition for the same role"),
            ("2026-09-18", "void_signal", "auto-rejection on the OLD requisition = system artifact, ignore"),
        ],
    },
    {
        "company": "LG Electronics NL", "title": "E-commerce Category Specialist",
        "match": {"title_contains": ["ecommerce"]},
        "track": "career", "stage_reached": "hiring_manager",
        "current_state": "closed", "outcome": "redirected", "closed_by": "employer",
        "gates": "onsite_5d",
        "contacts": "Chanmi Kim, HR, chanmi.kim@lge.com (out of office Wednesdays)\nYoungjun Mo, Online Brand Store team leader (hiring manager)",
        "events": [
            ("2026-08-28", "recruiter_screen", "HR call, Chanmi Kim"),
            ("2026-09-03", "hiring_manager", "on-site interview with Youngjun Mo"),
            ("2026-09-08", "redirected", "Youngjun: not a career-direction fit, referred to Media Solutions team"),
        ],
    },
    {
        "company": "LG Electronics Benelux", "title": "Assistant Product Director MS (Media Solutions, Benelux)",
        "match": {"title_contains": ["productdirector"]},
        "date_applied": "2026-09-17", "source": "internal referral (previous LG interview)",
        "track": "inbound", "stage_reached": "final",
        "current_state": "closed", "outcome": "withdrawn_by_me", "closed_by": "me",
        "gates": "onsite_5d, comp_below_target",
        "contacts": "Chanmi Kim, HR, chanmi.kim@lge.com",
        "note": "withdrawn: 4 days on-site, comp same as e-commerce role, employer ranked below bunq/Cummins",
        "events": [
            ("2026-09-17", "inbound", "Chanmi sent JD, asked if interested"),
            ("2026-09-20", "note", "replied interested, asked process / level / comp / WFH"),
            ("2026-09-21", "note", "Chanmi: one interview (Product Director + HR), ASAP start, same comp range, 1 WFH day"),
            ("2026-09-23", "final_invited", "face-to-face Sep 24 13:30 Amstelveen"),
            ("2026-09-23", "withdrawn_by_me", "declined by email, polite, door open for future data/AI roles"),
            ("2026-09-25", "closed", "Chanmi acknowledged, door left open"),
        ],
    },
    {
        "company": "bunq", "title": "Product Owner - Credit",
        "date_applied": "2026-09-02", "source": "Elif (bunq employee referral)",
        "track": "referral", "stage_reached": "recruiter_screen",
        "current_state": "closed", "outcome": "role_closed", "closed_by": "employer",
        "gates": "years_gap",
        "contacts": "Büşra Boz, recruiter, bboz@bunq.com\nVanessa Kemeny, recruiter (call)",
        "note": "not a rejection of Jamie; employer wants 5+ yrs credit-card experience",
        "events": [
            ("2026-09-02", "applied", "referral consent given"),
            ("2026-09-15", "recruiter_screen", "call with Vanessa: sees PO potential, Credit role needs 5+ yrs credit-card experience"),
            ("2026-09-15", "role_closed", "agreed it was too much of a stretch"),
        ],
    },
    {
        "company": "bunq", "title": "Product Owner (general pool, role TBD)",
        "date_applied": "2026-09-15", "source": "spun out of PO-Credit screen",
        "track": "referral", "stage_reached": "assessment",
        "current_state": "on_hold_employer",
        "contacts": "Vanessa Kemeny, recruiter\nHead of New Product (reviews all PO tests; if positive → interview with him → Get Shit Done Day)",
        "next_action": "no nudge yet; new roles decided next month, Vanessa to reach out. If nothing by 2026-10-10, ask Vanessa for test feedback",
        "due": "2026-10-10",
        "note": ("PO test = multiple choice + 3 open-ended (DreamSpace idea-to-launch incl. iOS overscope lesson; "
                 "Innovation Hub AI Transformation framework; Toss as successful product). "
                 "Told recruiter he brings Asian-app benchmarking (Toss)"),
        "events": [
            ("2026-09-15", "assessment", "PO test submitted, confirmation email sent to Vanessa same day"),
            ("2026-09-15", "on_hold_employer", "awaiting Head of New Product; no reply since"),
        ],
    },
    {
        "company": "KPMG", "title": "Microsoft AI Platform Consultant",
        "match": {"title_contains": ["microsoft"]},
        "track": "career", "stage_reached": "confirmed",
        "current_state": "action_required",
        "gates": "cap_slot",
        "contacts": "Yassine Manar, recruiter, Manar.Yassine@kpmg.nl",
        "next_action": "nudge Yassine if no decision email by 2026-09-26",
        "due": "2026-09-26",
        "note": "starred survey reminder Sep 22 mentioning a rejection most likely belongs to the Sep 8 Consultant AI rejection, not this role",
        "events": [
            ("2026-09-12", "applied", "tailored CV (Copilot Studio / Azure AI Foundry / Azure AI Search) + cover letter"),
            ("2026-09-18", "note", "Yassine: reviewing with hiring manager, selection by Sep 23 latest"),
            ("2026-09-24", "note", "no decision email received"),
        ],
    },
    {
        "company": "DogSuppy (Suppy B.V.)", "title": "Growth Associate",
        "date_applied": "2026-09-16", "source": "LinkedIn Easy Apply",
        "track": "career", "stage_reached": "confirmed",
        "current_state": "scheduling",
        "gates": "onsite_5d, ind_unknown",
        "contacts": "Daniel Okounev, Head of Growth, WhatsApp +31 6 24691886",
        "next_action": "wait for call slots; at the call ask erkend referent status + salary range",
        "note": "low enthusiasm; only if pay is good, ask high",
        "events": [
            ("2026-09-16", "applied", "Easy Apply (approx. date)"),
            ("2026-09-21", "inbound", "Daniel asked for motivation on WhatsApp, wants a call"),
            ("2026-09-21", "note", "sent motivation, confirmed read working-at page, 5 days on-site OK; not available Tuesday that week"),
        ],
    },
    {
        "company": "Uber", "title": "Sales Engineer I (Uber for Business)",
        "match": {"title_contains": ["salesengineer"]},
        "track": "career", "stage_reached": "confirmed",
        "current_state": "awaiting_response",
        "gates": "years_gap",
        "contacts": "Rishabh Devgan, Sales Engineering @ Uber (LinkedIn 2nd-degree, note drafted)",
        "next_action": "send LinkedIn connection note to Rishabh",
        "due": "2026-09-29",
        "events": [
            ("2026-09-16", "applied", "reposted role (removed after Sep 10, back Sep 16); tailored CV: client pitches with Sales, REST API design first, Korean native for APAC plus"),
            ("2026-09-16", "confirmed", ""),
        ],
    },
    {
        "company": "Paebbl", "title": "Forward Deployed Engineer",
        "track": "career", "stage_reached": "confirmed",
        "current_state": "awaiting_response",
        "gates": "ind_unknown, commute_risk, dutch_shopfloor_risk",
        "next_action": "none; small team, slow review expected. Stale check 2026-10-15",
        "due": "2026-10-15",
        "note": "assessed as closest profile match of the Sep 15 batch",
        "events": [
            ("2026-09-15", "applied", "CV only (on-site enablement / tool adoption / trained teachers / agentic AI edits) + 140-char Connect pitch"),
            ("2026-09-15", "confirmed", ""),
        ],
    },
    {
        "company": "NN Group", "title": "Digital Employee eXperience (DEX) Specialist",
        "match": {"title_contains": ["employeeexperience"]},
        "track": "lottery", "stage_reached": "confirmed",
        "current_state": "awaiting_response",
        "gates": "dutch_required",
        "contacts": "Chantal Verhagen, TA, chantal.verhagen@nn-group.com",
        "events": [
            ("2026-09-24", "applied", "tailored CV (Hub Champions / workshops / M365 Copilot / SharePoint) + cover letter, Dutch A2 named"),
            ("2026-09-24", "confirmed", "Workday confirmation (gmail:1a0d554b7d3d17c2)"),
        ],
    },
    {
        "company": "Apple", "title": "NL-Technical Specialist (Req 114438211)",
        "match": {"title_contains": ["technicalspecialist"]},
        "track": "bridge", "stage_reached": "confirmed",
        "current_state": "awaiting_response",
        "gates": "dutch_required",
        "note": "bridge job: income + keeps portfolio time free; NOT in pipeline KPIs. Part-time 24-32h preferred",
        "events": [
            ("2026-09-25", "applied", "tailored CV (MediaMarkt Apple Professional first) + short cover letter, Dutch A2 named"),
            ("2026-09-25", "confirmed", "gmail:1a0d969300c07db5"),
        ],
    },
    {
        "company": "Just Eat Takeaway.com", "title": "Junior Master Data Analyst",
        "match": {"title_contains": ["masterdata"]},
        "track": "career", "stage_reached": "applied",
        "current_state": "awaiting_response",
        "note": "off-lane stabilization application",
        "events": [
            ("2026-09-15", "applied", "CV only (data-quality / Power Automate edits), no confirmation seen"),
        ],
    },
    {
        "company": "Shell", "title": "Graduate Programme 2027 Netherlands",
        "date_applied": "2026-09-16",
        "track": "lottery", "stage_reached": "applied",
        "current_state": "awaiting_response",
        "gates": "masters_required",
        "note": "intakes May/Nov 2027",
        "events": [("2026-09-16", "applied", "no confirmation seen")],
    },
    {
        "company": "project44", "title": "Solutions Engineer",
        "date_applied": "2026-09-09",
        "track": "career", "stage_reached": "confirmed",
        "current_state": "awaiting_response",
        "next_action": "stale check 2026-10-09",
        "due": "2026-10-09",
        "events": [("2026-09-09", "confirmed", "")],
    },
    {
        "company": "Mayerfeld Consulting", "title": "AI Operations Specialist Practicum",
        "date_applied": "2026-09-07",
        "track": "nurture", "stage_reached": "applied",
        "current_state": "action_required",
        "contacts": "Isabel Herrera, isabel@mayerfeld.consulting",
        "note": ("pay-to-play / lead-gen pattern, NOT an application. 4-week practicum, list price 139 EUR "
                 '"waived", ~4-8 USD environment cost, apply.mayerfeld.consulting. Low priority, only if wanted'),
        "events": [
            ("2026-09-07", "inbound", "pitched after the Junior AI Automation Developer rejection; replied interested, has not applied"),
        ],
    },
]

# Older applications with no signal -> stale (skipped if already closed)
STALE = [
    {"company": "BJAK", "title": "Applied AI Engineer", "track": "lottery", "gates": "ind_unknown"},
    {"company": "LYNX", "title": "IT Specialist Automation & AI", "track": "career", "gates": "ind_confirmed"},
    {"company": "TomTom", "title": "Applied AI Engineer", "track": "career"},
    {"company": "Mendix", "title": "Core AI", "track": "career", "source": "LinkedIn Easy Apply",
     "match": {"title_contains": ["core"]}},
    {"company": "Amazon", "title": "AI Data Associate NL", "track": "lottery", "gates": "dutch_required",
     "match": {"title_contains": ["aidataassociate"]},
     "note": "likely ATS cut on C1 Dutch; counts toward Amazon cap (1 of 3)"},
    {"company": "SevenLab", "title": "AI Solutions Consultant", "track": "career",
     "note": "second SevenLab posting (Technisch AI Consultant, Dutch JD, via &Work, deadline Sep 30) seen Sep 25, not applied"},
]

# Non-applications to keep as records
NON_APPS = [
    {"company": "Forcyd", "title": "Starters Academy 2027", "track": "nurture",
     "note": "mailing/nurture only"},
    {"company": "(unknown, LinkedIn)", "title": "Trainee Sales Support",
     "date_applied": "2026-09-16", "track": "career", "stage_reached": "applied",
     "current_state": "closed", "outcome": "void", "closed_by": "system",
     "note": "Easy Apply submission failed 2026-09-16; re-submit only if still wanted"},
    {"company": "Cummins", "title": "IT Solution Engineer (old requisition)",
     "track": "career", "stage_reached": "applied",
     "current_state": "closed", "outcome": "void", "closed_by": "system",
     "note": "Sep 18 auto-rejection, system artifact; real application lives on the new requisition"},
]

# ---------------------------------------------------------------------------
# Section 2 — categorized closed records
# (company, title, applied, closed, stage_reached, outcome, closed_by, note, match/fix overrides)
# ---------------------------------------------------------------------------

CLOSED = [
    {"company": "Mollie", "title": "Commercial Analyst - Sales", "applied": "2026-09-14", "closed": "2026-09-22",
     "outcome": "rejected_cv", "note": "already in final stages with others; Mollie slot free again"},
    {"company": "TCC Global", "title": "Data Analyst - Entry Level", "closed": "2026-09-21",
     "outcome": "rejected_cv", "note": "high volume, not shortlisted; salary expectation 45k stated on form"},
    {"company": "Amazon", "title": "GenAI Sales Specialist EU North", "closed": "2026-09-17",
     "outcome": "rejected_cv", "match": {"title_contains": ["genai"]}},
    {"company": "Tesla", "title": "Recruiter - Sales, Service & Delivery", "closed": "2026-09-17",
     "outcome": "rejected_cv", "match": {"title_contains": ["recruiter"]}},
    {"company": "Metyis", "title": "AI Solution Engineer Analyst", "applied": "2026-09-15", "closed": "2026-09-16",
     "outcome": "rejected_ats",
     "note": "recruiter Nidhi Singh, same minute as Adaptfy; no re-apply until materially different posting"},
    {"company": "Adaptfy", "title": "AI Solutions Engineer Analyst", "applied": "2026-09-15", "closed": "2026-09-16",
     "outcome": "rejected_ats", "match": {"id": 149},
     "set_company": "Adaptfy", "note": "same-minute template rejection as Metyis (was logged under Metyis AG)"},
    {"company": "DataSnipper", "title": "Technical Support Specialist", "closed": "2026-09-16",
     "outcome": "rejected_cv"},
    {"company": "Lenovo", "title": "Mid Market Inside Sales Specialist", "closed": "2026-09-16",
     "outcome": "rejected_cv"},
    {"company": "PwC", "title": "Forward Deployed AI Engineer", "closed": "2026-09-15",
     "outcome": "rejected_cv", "match": {"title_contains": ["forwarddeployed"]},
     "note": "had been assessed as strongest recent match"},
    {"company": "Mendix", "title": "Solutions Engineer Data/Graph", "closed": "2026-09-14",
     "outcome": "role_closed", "match": {"title_contains": ["graph"]}, "note": "position filled"},
    {"company": "Forcyd", "title": "(graduate role)", "closed": "2026-09-14",
     "outcome": "rejected_language"},
    {"company": "Adyen", "title": "Technical Support Engineer", "closed": "2026-09-11",
     "outcome": "rejected_cv", "match": {"title_contains": ["technicalsupport"]},
     "note": "Adyen cap reached; all 3 Adyen apps rejected"},
    {"company": "Aon", "title": "Associate, Strategy & Technology Group EMEA", "closed": "2026-09-11",
     "outcome": "rejected_cv"},
    {"company": "Swisscom", "title": "Junior AI Platform Engineer", "closed": "2026-09-09",
     "outcome": "rejected_cv"},
    {"company": "NIKE", "title": "People Solutions Advisor I EMEA", "closed": "2026-09-09",
     "outcome": "rejected_cv"},
    {"company": "KPMG", "title": "Consultant AI", "closed": "2026-09-08",
     "outcome": "rejected_cv", "match": {"title": "Consultant AI"}, "note": "slot re-used Sep 12"},
    {"company": "Adyen", "title": "Tech Enablement Specialist", "closed": "2026-09-07",
     "outcome": "rejected_cv", "match": {"title_contains": ["enablement"]}},
    {"company": "Adyen", "title": "Business Analyst Payments Pricing", "closed": "2026-09-07",
     "outcome": "rejected_cv", "match": {"title_contains": ["paymentspricing"]}},
    {"company": "Ahold Delhaize", "title": "Technical Integration Consultant", "closed": "2026-09-04",
     "outcome": "rejected_cv"},
    {"company": "Pearl Abyss", "title": "Business Development Assistant", "closed": "2026-09-04",
     "outcome": "rejected_cv", "match": {"title_contains": ["businessdevelopment"]}},
    {"company": "Amazon", "title": "Program Manager Customs & Trade", "closed": "2026-09-03",
     "outcome": "rejected_cv", "match": {"title_contains": ["customs"]}},
    {"company": "Booking.com", "title": "Solution Engineer I", "closed": "2026-09-03",
     "outcome": "rejected_cv", "match": {"title_contains": ["solutionengineer"]}},
    {"company": "adidas", "title": "Junior Data Scientist Supply Chain", "closed": "2026-09-03",
     "outcome": "rejected_cv", "match": {"id": 138},
     "set_company": "adidas"},
    {"company": "Tangent", "title": "(2nd round)", "closed": "2026-09-02",
     "stage_reached": "assessment", "outcome": "rejected_visa",
     "note": "reached 2nd round (1-min motivation video via web.jointangent.com, due ~Aug 28); cannot proceed with sponsorship candidates"},
    {"company": "Mayerfeld Consulting", "title": "Junior AI Automation Developer", "closed": "2026-08-31",
     "stage_reached": "recruiter_screen", "outcome": "rejected_after_screen",
     "match": {"id": 130}, "set_company": "Mayerfeld Consulting",
     "note": "written Q&A (4 questions) stage reached, replied ~Sep 1 (was logged as Gulf Associates)"},
    {"company": "Deloitte", "title": "Product Analyst - Tax AI", "closed": "2026-08-27",
     "outcome": "rejected_cv", "track": "referral", "match": {"title_contains": ["taxai"]},
     "note": "via Talha referral; Deloitte = referral route only"},
    {"company": "ING", "title": "Agentic Automation & AI Consultant", "closed": "2026-08-29",
     "outcome": "rejected_cv"},
    {"company": "Sensorfact", "title": "SDR Benelux", "closed": "2026-08-29",
     "outcome": "rejected_cv"},
    {"company": "HSO", "title": "Trainee Consultant Integration & AI", "closed": "2026-08-29",
     "outcome": "rejected_cv"},
    {"company": "Keylane", "title": "AI Solutions Engineer", "closed": "2026-08-27",
     "outcome": "role_closed", "note": "invited to reapply"},
    {"company": "Dwelly", "title": "Applied AI Engineer", "closed": "2026-08-27",
     "outcome": "rejected_cv"},
    {"company": "Booking.com", "title": "Junior Business Controller", "closed": "2026-08-27",
     "outcome": "rejected_cv", "match": {"title_contains": ["controller"]}},
    {"company": "Booking.com", "title": "Data Scientist I", "closed": "2026-08-27",
     "outcome": "rejected_cv", "match": {"title_contains": ["datascientist"]}},
    {"company": "Accenture", "title": "Junior Consultant AI Strategy", "outcome": "rejected_cv",
     "match": {"id": 152}, "note": "found Sep 24 on LinkedIn; Accenture slot free, one at a time"},
    {"company": "Amazon", "title": "Insights & Measurement Consultant", "outcome": "rejected_cv",
     "match": {"title_contains": ["insights"]}},
    {"company": "Flow Traders", "title": "AI Engineer", "outcome": "rejected_cv"},
    {"company": "ML6", "title": "AI Deployment Engineer", "outcome": "rejected_cv"},
    {"company": "Alpine", "title": "Data & AI Specialist", "outcome": "rejected_cv"},
    {"company": "Arrow Electronics", "title": "Microsoft AI Engineer", "outcome": "rejected_cv"},
    {"company": "Google Cloud", "title": "Customer Engineer", "outcome": "rejected_cv",
     "match": {"id": 38}, "set_company": "Google Cloud"},
    {"company": "Keepit", "title": "(role)", "stage_reached": "recruiter_screen",
     "outcome": "void", "closed_by": "system", "match": {"title_contains": ["solutions"]},
     "note": "call cancelled / void"},
    {"company": "Microsoft", "title": "ISD Technology Consultant", "closed": "2026-08-11",
     "outcome": "rejected_cv", "note": "re-apply target only"},
]

# ---------------------------------------------------------------------------
# Section 3 — considered, not applied (Wishlist decision records; always added
# unless an exact title match exists)
# ---------------------------------------------------------------------------

CONSIDERED = [
    {"company": "Solvimon", "title": "Junior Solution Engineer (Utrecht)", "date": "2026-09-25",
     "track": "career", "gates": "no_sponsorship",
     "reason": "best match of the day; portal states no visa sponsorship (matters for HSM conversion after zoekjaar)",
     "revisit": "no"},
    {"company": "Rewire", "title": "Cloud Eng / Jr Data Eng / Jr Data Scientist", "date": "2026-09-15",
     "track": "career", "gates": "masters_required, dutch_required",
     "reason": "Master's transcript mandatory + Dutch fluency", "revisit": "after Dutch B2"},
    {"company": "AWS", "title": "Associate Solutions Architect Benelux", "date": "2026-09-12",
     "track": "career", "gates": "dutch_required",
     "reason": "Dutch/French basic qualification", "revisit": "no"},
    {"company": "Cognizant", "title": "Frontier Engineer (Amsterdam)", "date": "2026-09-25",
     "track": "career", "gates": "years_gap",
     "reason": "3-10 yrs; LangChain/LangGraph/LLMOps",
     "revisit": "re-apply when portfolio project 1 is live (~2026-10-15)",
     "next_action": "re-apply when portfolio project 1 is live", "due": "2026-10-15"},
    {"company": "SevenLab", "title": "Technisch AI Consultant (via &Work)", "date": "2026-09-25",
     "track": "career", "gates": "dutch_required",
     "reason": "Dutch JD, on-site, deadline Sep 30", "revisit": "undecided"},
]

# ---------------------------------------------------------------------------
# Section 4 — employer-level rules (+ section 5 global constraints)
# ---------------------------------------------------------------------------

EMPLOYERS = [
    {"employer": "KPMG", "rule": "one active application at a time",
     "status": "slot in use (MS AI Platform Consultant)"},
    {"employer": "Amazon", "rule": "cap 3 active", "status": "1 active; on hold since 2026-09-12"},
    {"employer": "Adyen", "rule": "cap reached",
     "status": "no further applications; genuinely wanted employer, use future slots carefully"},
    {"employer": "ABN AMRO", "rule": "frozen >=3 months from ~Sep 2026", "status": "spray flag in ATS"},
    {"employer": "Accenture", "rule": "one active at a time",
     "status": "slot free; prefer English-only Technology / MBG Analyst postings"},
    {"employer": "Capgemini Group (frog, Sogeti, Invent)", "rule": "frozen at one", "status": ""},
    {"employer": "Deloitte", "rule": "referral route (Talha) only", "status": ""},
    {"employer": "Microsoft", "rule": "re-apply target only", "status": "no active"},
    {"employer": "Metyis / Adaptfy", "rule": "no re-apply until materially different posting", "status": ""},
    {"employer": "LG Electronics NL", "rule": "door open for data/AI roles", "status": "not a top-choice employer"},
    {"employer": "(global)",
     "rule": "student permit expires 2026-11; zoekjaar activation planned; CV carries 'eligible for zoekjaar, no sponsorship required'",
     "status": "hard blockers seen: no-sponsorship portals (Solvimon, Tangent), Master's gates (Shell, Rewire), Dutch gates (NN, Apple, Amazon AI Data Associate)"},
]

# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# normalized MD company -> normalized tracker company
COMPANY_ALIASES = {
    "lgelectronicsnl": "lgelectronicsbenelux",
    "metyis": "metyisag",
    "arrowelectronics": "arrow",
    "lynx": "lynxamsterdam",
    "aholddelhaize": "albertheijn",
    "ing": "ingbank",
    "googlecloud": "goolge",  # tracker row has the typo
}

_STOP_TOKENS = {"the", "and", "for", "with"}


def _tokens(title: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (title or "").lower()) if len(t) >= 3 and t not in _STOP_TOKENS}


def match_record(md: dict, apps: list[dict], *, exact_title_only: bool = False):
    """Return (app or None, reason). Never guesses: ambiguity returns None with a reason."""
    m = md.get("match") or {}
    if "id" in m:
        for a in apps:
            if a["id"] == m["id"]:
                return a, f"explicit id {m['id']}"
        return None, f"explicit id {m['id']} not found"

    company_md = norm(m.get("company") or md["company"])
    company_md = COMPANY_ALIASES.get(company_md, company_md)
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


# ---------------------------------------------------------------------------
# Patch building
# ---------------------------------------------------------------------------

V4_FIELDS = ("track", "stage_reached", "current_state", "outcome", "closed_by",
             "gates", "contacts", "next_action", "due")


def build_patch(existing: dict, md: dict) -> dict:
    """Merge MD values onto an existing record. MD wins when non-empty, except
    stage_reached which is monotonic (the further stage wins)."""
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data/tracker.xlsx")
    ap.add_argument("--dry-run", action="store_true", help="print the match plan and exit")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    data_path = (root / args.data) if not Path(args.data).is_absolute() else Path(args.data)
    if not data_path.exists():
        raise SystemExit(f"workbook not found: {data_path}")

    # Belt-and-braces backup before anything touches the file.
    backup = data_path.parent / "backups" / f"tracker-pre-backfill-{datetime.now():%Y%m%d-%H%M%S}.xlsx"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(data_path, backup)

    store = ExcelStore(data_path)  # opening runs the v3 -> v4 migration
    if store.is_locked():
        raise SystemExit("workbook is open in Excel — close it and retry")
    apps = store.list_applications()

    # ---- build plan ----
    updates: list[tuple[dict, dict, dict]] = []   # (existing, md, patch)
    adds: list[dict] = []                          # md records to add
    problems: list[str] = []

    def plan(md: dict, *, stale: bool = False, add_if_missing: bool = True,
             exact_title_only: bool = False) -> None:
        if md.get("force_add"):
            adds.append(md)
            return
        existing, reason = match_record(md, apps, exact_title_only=exact_title_only)
        if existing is None:
            if "AMBIGUOUS" in reason or "not found" in reason:
                problems.append(f"SKIP  {md['company']} — {md['title']}: {reason}")
            elif add_if_missing:
                if stale:
                    md = {"current_state": "stale", **md}
                adds.append(md)
            else:
                problems.append(f"SKIP  {md['company']} — {md['title']}: {reason}")
            return
        md = dict(md)
        if stale and (existing.get("current_state") or "") != "closed":
            md["current_state"] = "stale"
        patch = build_patch(existing, md)
        updates.append((existing, md, patch))

    for md in LIVE:
        plan(md)
    for md in STALE:
        plan({"stage_reached": "applied", **md}, stale=True)
    for md in NON_APPS:
        plan(md, exact_title_only=True)
    for md in CLOSED:
        base = {"track": "career", "stage_reached": "applied",
                "current_state": "closed", "closed_by": "employer"}
        plan({**base, **md})
    for md in CONSIDERED:
        rec = {**md, "note": f"considered, not applied — {md['reason']} (revisit: {md['revisit']})"}
        plan(rec, exact_title_only=True)

    # ---- report ----
    print(f"backup: {backup.name}")
    print(f"schema: v{store.info()['schema_version']}, {len(apps)} applications before backfill")
    print(f"\nplan: {len(updates)} update(s), {len(adds)} add(s), {len(problems)} problem(s)\n")
    for existing, md, patch in updates:
        keys = ", ".join(sorted(patch)) or "no field changes"
        print(f"  update #{existing['id']:>3}  {existing['company']} — {existing['title']}  [{keys}]")
    for md in adds:
        print(f"  add          {md.get('set_company') or md['company']} — {md['title']}")
    for p in problems:
        print(f"  !! {p}")
    if problems:
        print("\nresolve the problems above before applying.")
    if args.dry_run:
        return
    if problems:
        raise SystemExit(1)

    # ---- apply ----
    patches = {existing["id"]: patch for existing, _, patch in updates if patch}
    changed = store.bulk_update_applications(patches)

    added_ids: dict[int, dict] = {}
    for md in adds:
        rec = store.add_application(new_record(md))
        added_ids[id(md)] = rec

    events_written = 0
    for md in LIVE + NON_APPS:
        events = md.get("events")
        if not events:
            continue
        target = None
        if id(md) in added_ids:
            target = added_ids[id(md)]["id"]
        else:
            existing, _ = match_record(md, store.list_applications())
            target = existing["id"] if existing else None
        if target is None:
            print(f"  !! events skipped, no target row: {md['company']} — {md['title']}")
            continue
        rows = [{"date": d, "event": e, "note": n} for d, e, n in events]
        events_written += store.replace_events_for_app(target, rows)

    store.replace_employers(EMPLOYERS)

    history = History(data_path.parent / "history.jsonl")
    history.record(
        "import", "backfill-v2", STAMP, None,
        {"updated": changed, "added": len(adds), "events": events_written,
         "employers": len(EMPLOYERS)},
        label=f"Backfill v2 ({STAMP}): {changed} updated, {len(adds)} added, "
              f"{events_written} events, {len(EMPLOYERS)} employer rules",
        undoable=False)

    info = store.info()
    print(f"\napplied: {changed} updated, {len(adds)} added, {events_written} events, "
          f"{len(EMPLOYERS)} employer rules")
    print(f"workbook now: {info['app_count']} applications, {info['event_count']} events, "
          f"schema v{info['schema_version']}")


if __name__ == "__main__":
    main()
