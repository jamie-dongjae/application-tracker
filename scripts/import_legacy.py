#!/usr/bin/env python3
"""Import a legacy (JAMIE-era) tracker workbook into a fresh Application Tracker workbook.

    python scripts/import_legacy.py --in "/path/to/Old_Tracker.xlsx" [--out data/tracker.xlsx] [--force]

The source file is opened read-only and never modified.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracker.excel.legacy import import_legacy_workbook  # noqa: E402
from tracker.excel.store import ExcelStore  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="src", required=True, help="legacy workbook to read")
    ap.add_argument("--out", default="data/tracker.xlsx", help="Application Tracker workbook to create/extend")
    ap.add_argument("--force", action="store_true", help="allow importing into an existing workbook")
    args = ap.parse_args()

    src = Path(args.src).expanduser()
    out = Path(args.out).expanduser()
    if not src.exists():
        raise SystemExit(f"source not found: {src}")
    if out.exists() and not args.force:
        raise SystemExit(f"{out} already exists — pass --force to import into it anyway")

    store = ExcelStore(out)
    summary = import_legacy_workbook(src, store)

    print(f"imported {summary['applications']} applications, {summary['prep']} prep rows")
    print(f"  from {src}")
    print(f"  into {out}")
    for warning in summary["warnings"]:
        print(f"  warning: {warning}")
    pending = sum(1 for r in store.list_applications() if r.get("geo_status") == "pending")
    if pending:
        print(f"  {pending} rows have a location but no coordinates — run the geocode "
              f"backfill from the Map view (or the command palette).")


if __name__ == "__main__":
    main()
