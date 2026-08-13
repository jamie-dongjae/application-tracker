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

SOURCES = ["LinkedIn", "Company site", "Referral", "Indeed", "Otta"]
SPONSOR = ["Mentioned", "Not offered", ""]
STATUS_WEIGHTED = (["Applied"] * 9 + ["Interview"] * 5 + ["Offer"] * 1 +
                   ["Rejected"] * 12 + ["Withdrawn"] * 1 + ["Wishlist"] * 2)

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
        rec = {
            "company": company if i < len(COMPANIES) else company + " (NL)",
            "title": title,
            "status": status,
            "date_applied": "" if status == "Wishlist" else applied.isoformat(),
            "location": "Remote (EU)" if remote else city,
            "work_type": "Remote" if remote else rng.choice(["Hybrid", "Hybrid", "Onsite", ""]),
            "source": rng.choice(SOURCES),
            "sponsorship": rng.choice(SPONSOR),
            "url": f"https://boards.greenhouse.io/{company.split()[0].lower()}/jobs/{4000000 + i}",
            "notes": "",
            "latitude": "" if remote else lat,
            "longitude": "" if remote else lng,
            "geo_status": "remote" if remote else "ok",
        }
        apps.append(rec)
    prep = [{"category": c, "question": q, "answer": a} for c, q, a in PREP]
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
