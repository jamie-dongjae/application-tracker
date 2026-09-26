#!/usr/bin/env python3
"""One-shot field cleanup: canonicalize source/work_type, move person names
out of `source` into `referral`, and infer missing sources from posting URLs.

    python scripts/normalize_fields.py [--data data/tracker.xlsx] [--dry-run]

Deterministic only — records without a URL keep an empty source.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracker.excel.store import ExcelStore  # noqa: E402
from tracker.importers.normalize import (  # noqa: E402
    infer_source_from_url, normalize_source, normalize_work_type,
)
from tracker.services.history import History  # noqa: E402

# Person-name / free-text sources -> Referral channel + referral person.
# Explicit by id — never guessed.
REFERRAL_FIXES = {
    133: {"source": "Referral"},  # Deloitte Tax AI (referral=Talha Amin already set)
    155: {"source": "Referral", "referral": "internal — Chanmi Kim (LG HR)"},
    156: {"source": "Referral", "referral": "Elif (bunq employee)"},
    157: {"source": "Referral", "referral": "Elif (bunq employee)"},
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data/tracker.xlsx")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    data_path = (root / args.data) if not Path(args.data).is_absolute() else Path(args.data)
    if not data_path.exists():
        raise SystemExit(f"workbook not found: {data_path}")

    backup = data_path.parent / "backups" / f"tracker-pre-normalize-{datetime.now():%Y%m%d-%H%M%S}.xlsx"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(data_path, backup)

    store = ExcelStore(data_path)
    if store.is_locked():
        raise SystemExit("workbook is open in Excel — close it and retry")

    patches: dict[int, dict] = {}
    report: list[str] = []

    for rec in store.list_applications():
        patch: dict = {}
        src = rec.get("source") or ""
        canonical = normalize_source(src)
        if canonical != src:
            patch["source"] = canonical
        wt = rec.get("work_type") or ""
        wt_c = normalize_work_type(wt)
        if wt_c != wt:
            patch["work_type"] = wt_c

        fixes = REFERRAL_FIXES.get(rec["id"], {})
        for key, value in fixes.items():
            if rec.get(key) != value and (key != "referral" or not rec.get("referral")):
                patch[key] = value

        if not (patch.get("source") or rec.get("source")) and rec["id"] not in REFERRAL_FIXES:
            inferred = infer_source_from_url(rec.get("url") or rec.get("portal_url"))
            if inferred:
                patch["source"] = inferred

        if patch:
            patches[rec["id"]] = patch
            what = ", ".join(f"{k}: {rec.get(k) or '(empty)'!r} -> {v!r}" for k, v in patch.items())
            report.append(f"  #{rec['id']:>3} {rec['company'][:24]:<24} {what}")

    print(f"backup: {backup.name}")
    print(f"plan: {len(patches)} record(s) to patch\n")
    print("\n".join(report) or "  nothing to do")
    if args.dry_run:
        return

    changed = store.bulk_update_applications(patches)
    History(data_path.parent / "history.jsonl").record(
        "import", "normalize-fields", "all", None, {"changed": changed},
        label=f"Field normalization: {changed} records", undoable=False)
    print(f"\napplied: {changed} records patched")


if __name__ == "__main__":
    main()
