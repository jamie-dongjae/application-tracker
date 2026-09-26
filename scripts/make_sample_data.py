#!/usr/bin/env python3
"""Generate a fictional demo workbook and demo/sample-data.json.

Companies are invented; cities are real with pre-resolved coordinates so the
demo map needs no geocoding calls. Deterministic (seeded) so screenshots are
reproducible. Records are authored in v4 terms (track / stage_reached /
current_state / outcome) and the legacy kanban status is DERIVED by the store
— the same sync rule the real app uses — so demo data can never contradict
itself.

    python scripts/make_sample_data.py [--out data/tracker.xlsx] [--force]
    python scripts/make_sample_data.py --json-only     # refresh the demo only,
                                                       # never touches a workbook
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracker.excel.store import ExcelStore  # noqa: E402

CITIES = {
    "Amsterdam, Netherlands": (52.3728, 4.8936),
    "Rotterdam, Netherlands": (51.9225, 4.4792),
    "Utrecht, Netherlands": (52.0907, 5.1214),
    "Eindhoven, Netherlands": (51.4416, 5.4697),
    "The Hague, Netherlands": (52.0705, 4.3007),
    "Berlin, Germany": (52.5200, 13.4050),
    "Munich, Germany": (48.1351, 11.5820),
    "London, United Kingdom": (51.5072, -0.1276),
    "Dublin, Ireland": (53.3498, -6.2603),
    "Paris, France": (48.8566, 2.3522),
    "Copenhagen, Denmark": (55.6761, 12.5683),
    "Stockholm, Sweden": (59.3293, 18.0686),
    "Zurich, Switzerland": (47.3769, 8.5417),
    "Barcelona, Spain": (41.3874, 2.1686),
    "Warsaw, Poland": (52.2297, 21.0122),
}

COMPANIES = [
    ("Northwind Analytics", "Data Analyst"),
    ("Bluefjord", "Data Engineer"),
    ("Cobalt Labs", "Machine Learning Engineer"),
    ("Meridian Pay", "Product Analyst"),
    ("Arcline Systems", "Backend Engineer"),
    ("Statmill", "Quantitative Analyst"),
    ("Vector & Vine", "BI Developer"),
    ("Halcyon Grid", "Data Scientist"),
    ("Pinebrook", "Analytics Engineer"),
    ("Quartzline", "Research Analyst"),
    ("Delta Verge", "Platform Engineer"),
    ("Lumen Forge", "Software Engineer"),
    ("Osprey Cloud", "DevOps Engineer"),
    ("Tidewater AI", "ML Ops Engineer"),
    ("Redshift Labs", "Data Analyst"),
]

SPONSOR = ["Mentioned", "Not offered", ""]

# Archetypes tell a legible story in the Insights charts: referrals convert,
# cold company-site applications mostly die at the CV screen, and rejection
# speed clusters at the same-batch ATS cut. Each entry:
# (weight, track, stage, state, outcome, closed_by, source, gates)
ARCHETYPES = [
    (6, "career", "applied", "awaiting_response", "", "", "Company site", ""),
    (2, "career", "confirmed", "awaiting_response", "", "", "LinkedIn", ""),
    (1, "career", "confirmed", "action_required", "", "", "Company site", "cap_slot"),
    (1, "career", "recruiter_screen", "scheduling", "", "", "LinkedIn", ""),
    (1, "referral", "assessment", "on_hold_employer", "", "", "Referral", ""),
    (1, "referral", "hiring_manager", "awaiting_decision", "", "", "Referral", ""),
    (1, "career", "offer", "awaiting_decision", "", "", "Referral", ""),
    (1, "career", "offer", "closed", "", "me", "LinkedIn", ""),          # Accepted
    (1, "career", "offer", "closed", "withdrawn_by_me", "me", "Company site", ""),  # Declined
    (7, "career", "applied", "closed", "rejected_cv", "employer", "Company site", ""),
    (2, "career", "applied", "closed", "rejected_ats", "employer", "Company site", ""),
    (1, "career", "recruiter_screen", "closed", "rejected_after_screen", "employer", "LinkedIn", ""),
    (1, "career", "hiring_manager", "closed", "rejected_after_interview", "employer", "Referral", ""),
    (1, "lottery", "applied", "closed", "rejected_visa", "employer", "Job board", "no_sponsorship"),
    (1, "career", "applied", "closed", "withdrawn_by_me", "me", "LinkedIn", ""),
    (1, "career", "applied", "stale", "", "", "Company site", ""),
    (1, "bridge", "confirmed", "awaiting_response", "", "", "Company site", "dutch_required"),
    (1, "career", "", "", "", "", "", ""),                                # Wishlist
]

NEXT_ACTIONS = [
    ("nudge the recruiter if no decision email arrives", -1),   # overdue
    ("prepare the case study before the panel", 2),
    ("send a thank-you note and ask about timeline", 4),
    ("follow up on the take-home feedback", 6),
]

PREP = [
    ("Behavioral", "Tell me about a time you resolved a conflict in a team.",
     "Two analysts disagreed on metric definitions mid-sprint. I facilitated a working "
     "session, wrote the definition doc, and got both to co-own it. The review shipped "
     "on time and the doc became the team standard. Tips: name the disagreement "
     "neutrally; focus on the process."),
    ("Behavioral", "Describe a project you drove end to end.",
     "A churn dashboard leadership wanted but nobody owned. Scoped it with stakeholders, "
     "built the pipeline, automated QA checks. Adopted in the weekly business review and "
     "it caught a billing bug. Tips: quantify the result."),
    ("Behavioral", "Tell me about a time you missed a deadline.",
     "Underestimated a migration during a dashboard rebuild. Flagged it early, cut scope "
     "with the stakeholder, delivered the core a week late. Trust preserved; the process "
     "now includes a migration checklist. Tips: own it — no blame-shifting."),
    ("Technical", "How would you find duplicate users in a table?",
     "GROUP BY email HAVING COUNT(*) > 1, or ROW_NUMBER() over a window to keep the "
     "first occurrence. Tips: mention the trade-offs between the two."),
    ("Technical", "Explain p-values to a non-technical stakeholder.",
     "The probability of seeing data this extreme if there were truly no effect. "
     "Tips: avoid saying 'probability the hypothesis is true'."),
    ("Case", "Signups dropped 15% week over week — walk me through your investigation.",
     "Segment by platform, geo, and channel; check tracking changes, seasonality, and "
     "funnel step deltas before hypothesizing. Tips: structure first, hypotheses second."),
    ("Motivation", "Why this company?",
     "Tie one product decision they made to your own experience; be specific. "
     "Tips: research one recent launch."),
    ("Motivation", "Where do you see yourself in five years?",
     "Growing from IC excellence toward owning a problem space. Tips: keep it honest, "
     "not rehearsed."),
]

EMPLOYERS = [
    {"employer": "Northwind Analytics", "rule": "one active application at a time",
     "status": "slot in use (Data Analyst)"},
    {"employer": "Halcyon Grid", "rule": "cap 2 active", "status": "1 active"},
    {"employer": "Meridian Pay", "rule": "re-apply target only",
     "status": "invited to reapply next quarter"},
    {"employer": "Osprey Cloud", "rule": "referral route only", "status": ""},
    {"employer": "(global)", "rule": "relocation budget capped; prefer roles within the EU",
     "status": "hard gates seen: sponsorship (Statmill), language (Bluefjord)"},
]


def _weighted(rng: random.Random):
    pool = []
    for row in ARCHETYPES:
        pool.extend([row[1:]] * row[0])
    rng.shuffle(pool)
    return pool


def build(out: Path, *, seed: int = 7) -> tuple[ExcelStore, list]:
    rng = random.Random(seed)
    store = ExcelStore(out)
    today = date.today()
    pool = _weighted(rng)
    apps = []
    for i, (company, title) in enumerate((COMPANIES * 2)[:30]):
        track, stage, state, outcome, closed_by, source, gates = pool[i % len(pool)]
        # Spread across the last 12 weeks so the cohort chart has a full axis.
        applied = today - timedelta(days=rng.randint(0, 83))
        remote = rng.random() < 0.12
        city = rng.choice(list(CITIES))
        lat, lng = CITIES[city]
        notes = ""
        if state in ("closed",) and outcome:
            # Close date drives the rejection-speed histogram: ATS cuts land
            # same-day/next-day, human reviews take one to five weeks.
            gap = rng.randint(0, 1) if outcome == "rejected_ats" else rng.randint(3, 35)
            notes = f"closed {(applied + timedelta(days=gap)).isoformat()}"
        rec = {
            "company": company if i < len(COMPANIES) else company + " (NL)",
            "title": title,
            "date_applied": "" if not stage else applied.isoformat(),
            "location": "Remote (EU)" if remote else city,
            "work_type": "Remote" if remote else rng.choice(["Hybrid", "Hybrid", "Onsite", ""]),
            "source": source,
            "sponsorship": rng.choice(SPONSOR),
            "url": f"https://boards.greenhouse.io/{company.split()[0].lower()}/jobs/{4000000 + i}",
            "notes": notes,
            "track": track,
            "stage_reached": stage,
            "current_state": state,
            "outcome": outcome,
            "closed_by": closed_by,
            "gates": gates,
            "latitude": "" if remote else lat,
            "longitude": "" if remote else lng,
            "geo_status": "remote" if remote else "ok",
        }
        apps.append(rec)

    # Next actions with due dates for the dashboard panel (one overdue).
    live = [a for a in apps if a["current_state"] not in ("closed", "stale", "")]
    for a, (action, delta) in zip(live[:len(NEXT_ACTIONS)], NEXT_ACTIONS):
        a["next_action"] = action
        a["due"] = (today + timedelta(days=delta)).isoformat()
    for a in live[:2]:
        a["contacts"] = "Alex Winter, recruiter, alex@" + a["company"].split()[0].lower() + ".example"

    prep = [{"category": c, "question": q, "answer": a} for c, q, a in PREP]
    store.bulk_add(apps, prep)  # store derives the kanban status from v4 fields
    return store, apps


def synth_events(apps: list, *, seed: int = 13) -> list:
    """Timelines for the detail drawer, consistent with each record's stage."""
    rng = random.Random(seed)
    order = ["applied", "confirmed", "recruiter_screen", "assessment", "hiring_manager", "final", "offer"]
    notes = {"applied": "submitted via careers portal", "confirmed": "ATS confirmation received",
             "recruiter_screen": "intro call with the recruiter", "assessment": "take-home submitted",
             "hiring_manager": "interview with the hiring manager", "final": "panel round",
             "offer": "offer received"}
    out, eid = [], 1
    for a in apps:
        stage = a.get("stage_reached")
        if not stage or not a.get("date_applied") or stage not in order:
            continue
        if rng.random() < 0.4 and order.index(stage) < 2:
            continue  # not every early-stage record needs a timeline
        day = date.fromisoformat(str(a["date_applied"]))
        for s in order[: order.index(stage) + 1]:
            out.append({"id": eid, "app_id": a["id"], "date": day.isoformat(),
                        "event": s, "note": notes[s]})
            eid += 1
            day = day + timedelta(days=rng.randint(2, 9))
    return out


def synth_review_queue(apps: list) -> list:
    """Two pending mail-review items so the dashboard panel has something to show."""
    live = [a for a in apps if a.get("current_state") in ("awaiting_response", "confirmed", "scheduling")
            or a.get("status") == "Applied"]
    items = []
    templates = [
        ("Interview invitation — {title}", "We would love to schedule a 30-minute intro call next week…",
         {"stage_reached": "recruiter_screen", "current_state": "scheduling"}),
        ("Update on your application", "After careful consideration we have decided to move forward with other candidates…",
         {"current_state": "closed", "closed_by": "employer", "outcome": "rejected_cv"}),
    ]
    for i, a in enumerate(live[:2]):
        subject, snippet, patch = templates[i]
        items.append({
            "id": f"demo-review-{i + 1}",
            "added_at": f"{date.today().isoformat()}T09:0{i}:00",
            "email": {"gmail_id": f"demo-review-{i + 1}",
                      "from": "talent@" + a["company"].split()[0].lower() + ".example",
                      "subject": subject.format(title=a["title"]),
                      "date": date.today().isoformat(), "snippet": snippet},
            "proposed": {"company": a["company"], "title": a["title"], "match": {"id": a["id"]},
                         "confidence": "review", "reason": "needs a human eye", "fields": {},
                         "patch": patch, "note": "", "events": [], "provenance": []},
            "status": "pending", "resolved_at": None,
        })
    return items


def synth_transitions(apps: list, *, seed: int = 11) -> list:
    """Plausible stage-history chains for the history-aware KPIs."""
    rng = random.Random(seed)
    out = []
    for a in apps:
        status = a["status"]
        if status in ("Wishlist", "Applied") or not a["date_applied"]:
            continue
        path = ["Applied"]
        if status in ("Interview", "Offer", "Accepted", "Declined"):
            path.append("Interview")
        if status in ("Offer", "Accepted", "Declined"):
            path.append("Offer")
        if status in ("Accepted", "Declined"):
            path.append(status)
        if status in ("Rejected", "Withdrawn"):
            if rng.random() < 0.35:
                path.append("Interview")
            path.append(status)
        day = a["date_applied"]
        for frm, to in zip(path, path[1:]):
            day = day + timedelta(days=rng.randint(3, 12))
            out.append({"ts": f"{day.isoformat()}T10:00:00", "id": a["id"], "from": frm, "to": to})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tracker.xlsx")
    ap.add_argument("--json", default="demo/sample-data.json")
    ap.add_argument("--json-only", action="store_true",
                    help="refresh demo/sample-data.json without touching any workbook")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.json_only:
        tmp = Path(tempfile.mkdtemp(prefix="tracker-sample-")) / "tracker.xlsx"
        store, _ = build(tmp)
    else:
        out = Path(args.out)
        if out.exists() and not args.force:
            raise SystemExit(f"{out} exists — pass --force to overwrite (or use --json-only)")
        if out.exists():
            out.unlink()
        store, _ = build(out)

    apps = store.list_applications()
    prep = store.list_prep()
    employer_rows = store.replace_employers(EMPLOYERS) and store.list_employers()

    json_path = Path(args.json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(
        {"applications": [{**a, "date_applied": str(a["date_applied"]), "due": str(a.get("due") or "")} for a in apps],
         "prep": prep,
         "transitions": synth_transitions(apps),
         "events": synth_events(apps),
         "employers": employer_rows or [],
         "review_queue": synth_review_queue(apps),
         "settings": {"weekly_goal": 5, "stale_days": 14}},
        indent=1, default=str))
    target = "(temp workbook, json only)" if args.json_only else str(args.out)
    print(f"wrote {target} ({len(apps)} applications, {len(prep)} prep) and {json_path}")


if __name__ == "__main__":
    main()
