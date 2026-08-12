#!/usr/bin/env python3
"""Generate a fictional demo workbook (and demo/sample-data.json).

Companies are invented; cities are real with pre-resolved coordinates so the
demo map needs no geocoding calls. Deterministic (seeded) so screenshots are
reproducible.

    python scripts/make_sample_data.py [--out data/tracker.xlsx] [--force]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from waypoint.excel.store import ExcelStore  # noqa: E402

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

SOURCES = ["LinkedIn", "Company site", "Referral", "Indeed", "Otta"]
SPONSOR = ["Mentioned", "Not offered", ""]
STATUS_WEIGHTED = (["Applied"] * 8 + ["Phone Screen"] * 3 + ["Technical"] * 2 +
                   ["Onsite"] * 1 + ["Offer"] * 1 + ["Rejected"] * 12 +
                   ["Withdrawn"] * 1 + ["Wishlist"] * 2)

PREP = [
    ("Behavioral", "Teamwork", "Tell me about a time you resolved a conflict in a team.",
     "Two analysts disagreed on metric definitions mid-sprint.",
     "Align the team before the stakeholder review.",
     "Facilitated a working session, wrote the definition doc, got both to co-own it.",
     "Review shipped on time; the doc became the team standard.",
     "Name the disagreement neutrally; focus on the process."),
    ("Behavioral", "Ownership", "Describe a project you drove end to end.",
     "Churn dashboard requested by leadership with no clear owner.",
     "Deliver a trustworthy weekly view of churn drivers.",
     "Scoped with stakeholders, built the pipeline, automated QA checks.",
     "Adopted in the weekly business review; caught a billing bug.",
     "Quantify the result."),
    ("Technical", "SQL", "How would you find duplicate users in a table?",
     "", "", "GROUP BY email HAVING COUNT(*) > 1, or ROW_NUMBER() OVER a window to keep the first.",
     "", "Mention trade-offs between the two."),
    ("Technical", "Statistics", "Explain p-values to a non-technical stakeholder.",
     "", "", "Probability of seeing data this extreme if there were truly no effect.",
     "", "Avoid 'probability the hypothesis is true'."),
    ("Case", "Metrics", "Signups dropped 15% week over week — walk me through your investigation.",
     "", "", "Segment (platform, geo, channel), check tracking changes, seasonality, funnel step deltas.",
     "", "Structure first, hypotheses second."),
    ("Motivation", "", "Why this company?",
     "", "", "Tie one product decision they made to your own experience; be specific.",
     "", "Research one recent launch."),
    ("Motivation", "", "Where do you see yourself in five years?",
     "", "", "Growing from IC excellence toward owning a problem space.",
     "", "Keep it honest, not rehearsed."),
    ("Behavioral", "Failure", "Tell me about a time you missed a deadline.",
     "Underestimated a migration during a dashboard rebuild.",
     "Ship without breaking downstream reports.",
     "Flagged early, cut scope with the stakeholder, delivered the core a week late.",
     "Trust preserved; process now includes a migration checklist.",
     "Own it — no blame-shifting."),
]


def build(out: Path, *, seed: int = 7) -> ExcelStore:
    rng = random.Random(seed)
    store = ExcelStore(out)
    today = date.today()
    apps = []
    for i, (company, title) in enumerate(COMPANIES * 2):
        if i >= 30:
            break
        status = rng.choice(STATUS_WEIGHTED)
        applied = today - timedelta(days=rng.randint(0, 84))
        remote = rng.random() < 0.12
        city = rng.choice(list(CITIES))
        lat, lng = CITIES[city]
        has_salary = rng.random() < 0.4
        lo = rng.randrange(45, 75) * 1000 if has_salary else None
        rec = {
            "company": company if i < len(COMPANIES) else company + " (NL)",
            "title": title,
            "status": status,
            "date_applied": "" if status == "Wishlist" else applied.isoformat(),
            "location": "Remote (EU)" if remote else city,
            "work_type": "Remote" if remote else rng.choice(["Hybrid", "Hybrid", "Onsite", ""]),
            "salary_min": lo,
            "salary_max": (lo + rng.randrange(8, 20) * 1000) if lo else None,
            "currency": "EUR" if lo else "",
            "source": rng.choice(SOURCES),
            "sponsorship": rng.choice(SPONSOR),
            "url": f"https://boards.greenhouse.io/{company.split()[0].lower()}/jobs/{4000000 + i}",
            "notes": "",
            "latitude": "" if remote else lat,
            "longitude": "" if remote else lng,
            "geo_status": "remote" if remote else "ok",
        }
        apps.append(rec)
    prep = [{"category": c, "subcategory": s, "question": q, "situation": sit,
             "task": t, "action": a, "result": r, "tips": tip}
            for c, s, q, sit, t, a, r, tip in PREP]
    store.bulk_add(apps, prep)
    return store


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/tracker.xlsx")
    ap.add_argument("--json", default="demo/sample-data.json")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists() and not args.force:
        raise SystemExit(f"{out} exists — pass --force to overwrite")
    if out.exists():
        out.unlink()

    store = build(out)
    apps = store.list_applications()
    prep = store.list_prep()

    json_path = Path(args.json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(
        {"applications": [{**a, "date_applied": str(a["date_applied"])} for a in apps],
         "prep": prep,
         "settings": {"weekly_goal": 5, "stale_days": 14}},
        indent=1, default=str))
    print(f"wrote {out} ({len(apps)} applications, {len(prep)} prep) and {json_path}")


if __name__ == "__main__":
    main()
