from datetime import date, datetime

import pytest
from openpyxl import load_workbook

from waypoint.excel.store import ExcelStore, WorkbookLockedError, coerce_date


def test_creates_workbook_on_first_run(tmp_path):
    path = tmp_path / "tracker.xlsx"
    ExcelStore(path)
    wb = load_workbook(path)
    assert set(wb.sheetnames) == {"Applications", "Interview Prep", "Meta"}
    assert wb["Applications"]["A1"].value == "ID"
    assert wb["Meta"].sheet_state == "hidden"


def test_roundtrip_add_update_delete(store):
    rec = store.add_application({"company": "Acme", "title": "Analyst",
                                 "status": "Applied", "date_applied": "2026-08-01",
                                 "salary_min": 55000})
    assert rec["id"] == 1
    assert rec["date_applied"] == date(2026, 8, 1)

    before, after = store.update_application(1, {"status": "Phone Screen"})
    assert before["status"] == "Applied" and after["status"] == "Phone Screen"

    # Reload from disk: a fresh store must see the same data.
    fresh = ExcelStore(store.path)
    rows = fresh.list_applications()
    assert len(rows) == 1
    assert rows[0]["status"] == "Phone Screen"
    assert rows[0]["salary_min"] == 55000.0

    fresh.delete_application(1)
    assert fresh.list_applications() == []
    # IDs are never reused.
    rec2 = fresh.add_application({"company": "Beta", "title": "Engineer"})
    assert rec2["id"] == 2


def test_atomic_save_leaves_no_tmp(store):
    store.add_application({"company": "Acme", "title": "Analyst"})
    assert not list(store.path.parent.glob("*.tmp"))


def test_lock_sentinel_blocks_writes(store):
    sentinel = store.path.parent / f"~${store.path.name}"
    sentinel.write_text("locked by excel")
    with pytest.raises(WorkbookLockedError):
        store.add_application({"company": "Acme", "title": "Analyst"})
    sentinel.unlink()
    rec = store.add_application({"company": "Acme", "title": "Analyst"})
    assert rec["id"] >= 1


def test_backup_created(tmp_path):
    store = ExcelStore(tmp_path / "tracker.xlsx")
    store.add_application({"company": "Acme", "title": "Analyst"})
    backups = list((tmp_path / "backups").glob("tracker-*.xlsx"))
    assert len(backups) == 1  # throttled to at most one per hour


def test_external_edit_is_picked_up(store):
    store.add_application({"company": "Acme", "title": "Analyst"})
    # Simulate the user editing the workbook directly in Excel.
    wb = load_workbook(store.path)
    ws = wb["Applications"]
    headers = [c.value for c in ws[1]]
    row = [""] * len(headers)
    row[headers.index("ID")] = 99
    row[headers.index("Company")] = "HandEdited"
    row[headers.index("Job Title")] = "CFO"
    row[headers.index("Status")] = "Applied"
    ws.append(row)
    wb.save(store.path)

    companies = {r["company"] for r in store.list_applications()}
    assert "HandEdited" in companies


def test_bulk_update(store):
    a = store.add_application({"company": "Acme", "title": "Analyst"})
    b = store.add_application({"company": "Beta", "title": "Engineer"})
    changed = store.bulk_update_applications({
        a["id"]: {"latitude": 52.1, "longitude": 5.1, "geo_status": "ok"},
        b["id"]: {"geo_status": "failed"},
    })
    assert changed == 2
    rows = {r["id"]: r for r in store.list_applications()}
    assert rows[a["id"]]["latitude"] == 52.1
    assert rows[b["id"]]["geo_status"] == "failed"


@pytest.mark.parametrize("value,expected", [
    ("2026-04-08T00:00:00.000Z", date(2026, 4, 8)),   # SheetJS ISO string
    (datetime(2026, 4, 8, 0, 0), date(2026, 4, 8)),
    (45000, date(2023, 3, 15)),                        # Excel serial
    ("08/04/2026", date(2026, 4, 8)),                  # d/m/Y wins for EU data
    ("", None),
    (None, None),
    ("not a date", None),
])
def test_coerce_date(value, expected):
    assert coerce_date(value) == expected
