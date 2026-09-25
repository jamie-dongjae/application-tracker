"""Workbook schema v4: sheet layout, columns, and styling for a fresh tracker file.

The app owns this format (headers on row 1, no emoji sheet names). Legacy
Legacy-format workbooks are converted once by `tracker.excel.legacy`.

v4 adds the categorization model (track / stage_reached / current_state /
outcome / closed_by / gates / contacts / next_action / due), an Events sheet
(per-application timeline) and an Employers sheet (per-employer rules).
The legacy `status` column stays authoritative for the kanban board and is
derived from the v4 fields via `derive_status`.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

SCHEMA_VERSION = 4

SHEET_APPS = "Applications"
SHEET_PREP = "Interview Prep"
SHEET_EVENTS = "Events"
SHEET_EMPLOYERS = "Employers"
SHEET_META = "Meta"

STATUSES = [
    "Wishlist",
    "Applied",
    "Interview",
    "Offer",
    "Accepted",
    "Declined",
    "Rejected",
    "Withdrawn",
]
ACTIVE_STATUSES = ["Applied", "Interview", "Offer"]
# Pre-v3 stage names collapse into "Interview" (also used by the legacy importer).
STATUS_MIGRATE = {"Phone Screen": "Interview", "Technical": "Interview", "Onsite": "Interview"}
WORK_TYPES = ["Onsite", "Hybrid", "Remote"]
GEO_STATUSES = ["ok", "pending", "failed", "remote", "manual"]

# ---------- v4 categorization enums ----------

TRACKS = ["career", "bridge", "lottery", "referral", "inbound", "nurture"]

# Furthest point in the funnel; index = order, never goes backwards.
STAGES = [
    "applied",
    "confirmed",
    "recruiter_screen",
    "assessment",
    "hiring_manager",
    "final",
    "offer",
]
STAGE_IDX = {s: i for i, s in enumerate(STAGES)}

CURRENT_STATES = [
    "awaiting_response",
    "awaiting_decision",
    "scheduling",
    "action_required",
    "on_hold_employer",
    "stale",
    "closed",
]

OUTCOMES = [
    "rejected_ats",
    "rejected_cv",
    "rejected_after_screen",
    "rejected_after_interview",
    "rejected_visa",
    "rejected_language",
    "redirected",
    "withdrawn_by_me",
    "role_closed",
    "void",
]
REJECTED_OUTCOMES = {
    "rejected_ats",
    "rejected_cv",
    "rejected_after_screen",
    "rejected_after_interview",
    "rejected_visa",
    "rejected_language",
}

CLOSED_BY = ["employer", "me", "system"]

# Known gate flags; `gates` is a comma-separated free string so ad-hoc flags
# (comp_below_target, dutch_shopfloor_risk, ...) survive round-trips.
GATES = [
    "ind_confirmed",
    "ind_unknown",
    "no_sponsorship",
    "dutch_required",
    "masters_required",
    "years_gap",
    "onsite_5d",
    "commute_risk",
    "cap_slot",
]

STALE_AFTER_DAYS = 30  # applied/confirmed with no signal this long -> stale

# (header, key, width, number_format)
APP_COLUMNS = [
    ("ID", "id", 6, "0"),
    ("Company", "company", 22, None),
    ("Job Title", "title", 32, None),
    ("Status", "status", 13, None),
    ("Date Applied", "date_applied", 13, "yyyy-mm-dd"),
    ("Location", "location", 24, None),
    ("Work Type", "work_type", 10, None),
    ("Source", "source", 14, None),
    ("Sponsorship", "sponsorship", 16, None),
    ("Referral", "referral", 14, None),
    ("Job URL", "url", 40, None),
    ("Portal URL", "portal_url", 28, None),
    ("Notes", "notes", 40, None),
    ("Track", "track", 10, None),
    ("Stage Reached", "stage_reached", 15, None),
    ("Current State", "current_state", 16, None),
    ("Outcome", "outcome", 18, None),
    ("Closed By", "closed_by", 10, None),
    ("Gates", "gates", 24, None),
    ("Contacts", "contacts", 36, None),
    ("Next Action", "next_action", 36, None),
    ("Due", "due", 12, "yyyy-mm-dd"),
    ("Latitude", "latitude", 10, "0.00000"),
    ("Longitude", "longitude", 10, "0.00000"),
    ("Geo Status", "geo_status", 10, None),
    ("Last Updated", "last_updated", 19, None),
]

PREP_COLUMNS = [
    ("ID", "id", 6, "0"),
    ("Category", "category", 18, None),
    ("Question", "question", 50, None),
    ("Answer", "answer", 90, None),
]

EVENT_COLUMNS = [
    ("ID", "id", 6, "0"),
    ("App ID", "app_id", 7, "0"),
    ("Date", "date", 12, "yyyy-mm-dd"),
    ("Event", "event", 18, None),
    ("Note", "note", 60, None),
]

EMPLOYER_COLUMNS = [
    ("ID", "id", 6, "0"),
    ("Employer", "employer", 24, None),
    ("Rule", "rule", 40, None),
    ("Status", "status", 40, None),
]

APP_KEYS = [k for _, k, _, _ in APP_COLUMNS]
PREP_KEYS = [k for _, k, _, _ in PREP_COLUMNS]
EVENT_KEYS = [k for _, k, _, _ in EVENT_COLUMNS]
EMPLOYER_KEYS = [k for _, k, _, _ in EMPLOYER_COLUMNS]
NUMERIC_KEYS = {"latitude", "longitude"}

_HEADER_FILL = PatternFill("solid", start_color="FF101828")
_HEADER_FONT = Font(name="Calibri", bold=True, color="FFE8EEF9", size=11)


def _style_sheet(ws: Worksheet, columns: list) -> None:
    for idx, (header, _key, width, _fmt) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=idx, value=header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(vertical="center")
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}1"


def write_rows(ws: Worksheet, columns: list, rows: list) -> None:
    """Replace all data rows (row 2+) with `rows` (list of dicts)."""
    if ws.max_row > 1:
        ws.delete_rows(2, ws.max_row - 1)
    for r, rec in enumerate(rows, start=2):
        for c, (_header, key, _width, fmt) in enumerate(columns, start=1):
            value = rec.get(key)
            if value in ("", None):
                continue
            cell = ws.cell(row=r, column=c, value=value)
            if fmt:
                cell.number_format = fmt
            if isinstance(value, (date, datetime)):
                cell.number_format = "yyyy-mm-dd"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{max(1, len(rows) + 1)}"


def init_workbook() -> Workbook:
    wb = Workbook()
    ws_apps = wb.active
    ws_apps.title = SHEET_APPS
    _style_sheet(ws_apps, APP_COLUMNS)

    ws_prep = wb.create_sheet(SHEET_PREP)
    _style_sheet(ws_prep, PREP_COLUMNS)

    ws_events = wb.create_sheet(SHEET_EVENTS)
    _style_sheet(ws_events, EVENT_COLUMNS)

    ws_employers = wb.create_sheet(SHEET_EMPLOYERS)
    _style_sheet(ws_employers, EMPLOYER_COLUMNS)

    ws_meta = wb.create_sheet(SHEET_META)
    ws_meta.sheet_state = "hidden"
    set_meta(
        ws_meta,
        {
            "schema_version": SCHEMA_VERSION,
            "next_app_id": 1,
            "next_prep_id": 1,
            "next_event_id": 1,
            "next_employer_id": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "generator": "application-tracker",
        },
    )
    return wb


def read_meta(ws: Worksheet) -> dict:
    meta = {}
    for row in ws.iter_rows(min_row=1, max_col=2, values_only=True):
        if row and row[0]:
            meta[str(row[0])] = row[1]
    return meta


def set_meta(ws: Worksheet, meta: dict) -> None:
    if ws.max_row >= 1:
        ws.delete_rows(1, ws.max_row)
    for r, (k, v) in enumerate(sorted(meta.items()), start=1):
        ws.cell(row=r, column=1, value=k)
        ws.cell(row=r, column=2, value=v)


def header_map(ws: Worksheet, columns: list) -> dict:
    """Map column index -> record key based on the actual header row (order-tolerant)."""
    by_header = {h: k for h, k, _, _ in columns}
    mapping = {}
    for idx, cell in enumerate(ws[1], start=1):
        if cell.value and str(cell.value).strip() in by_header:
            mapping[idx] = by_header[str(cell.value).strip()]
    return mapping


# ---------- v4 <-> legacy status sync ----------

def _stage_max(current: str, floor: str) -> str:
    """Stage is monotonic: return whichever of the two is further along."""
    if current not in STAGE_IDX:
        return floor
    if floor not in STAGE_IDX:
        return current
    return current if STAGE_IDX[current] >= STAGE_IDX[floor] else floor


def derive_status(rec: dict) -> str:
    """Map (track, stage_reached, current_state, outcome) -> legacy status.

    First match wins; keeps the kanban board consistent with the v4 fields.
    """
    track = rec.get("track") or ""
    stage = rec.get("stage_reached") or ""
    state = rec.get("current_state") or ""
    outcome = rec.get("outcome") or ""

    if track == "nurture":
        return "Wishlist"
    if not stage:  # considered-not-applied / plain wishlist
        return "Wishlist"
    if state == "closed":
        if outcome in REJECTED_OUTCOMES or outcome in ("role_closed", "redirected"):
            return "Rejected"
        if outcome == "withdrawn_by_me":
            return "Declined" if stage == "offer" else "Withdrawn"
        if outcome == "void":
            return "Withdrawn"
        if stage == "offer":  # closed with no outcome at offer = accepted
            return "Accepted"
        return "Withdrawn"  # defensive fallback: closed without outcome
    if stage == "offer":
        return "Offer"
    if STAGE_IDX.get(stage, 0) >= STAGE_IDX["recruiter_screen"]:
        return "Interview"
    return "Applied"


def apply_status_forward(rec: dict, new_status: str) -> dict:
    """Patch for the v4 fields when only the legacy status changed (board drag).

    Never lowers stage_reached; round-trips through derive_status.
    """
    stage = rec.get("stage_reached") or ""
    patch: dict = {}
    if new_status == "Wishlist":
        return patch
    if new_status == "Applied":
        patch = {"stage_reached": _stage_max(stage, "applied"),
                 "current_state": "awaiting_response", "outcome": "", "closed_by": ""}
    elif new_status == "Interview":
        patch = {"stage_reached": _stage_max(stage, "recruiter_screen"),
                 "current_state": "awaiting_response", "outcome": "", "closed_by": ""}
    elif new_status == "Offer":
        patch = {"stage_reached": "offer", "current_state": "awaiting_decision",
                 "outcome": "", "closed_by": ""}
    elif new_status == "Accepted":
        patch = {"stage_reached": "offer", "current_state": "closed",
                 "closed_by": "me", "outcome": ""}
    elif new_status == "Declined":
        patch = {"stage_reached": "offer", "current_state": "closed",
                 "closed_by": "me", "outcome": "withdrawn_by_me"}
    elif new_status == "Rejected":
        effective = _stage_max(stage, "applied")
        if STAGE_IDX[effective] >= STAGE_IDX["hiring_manager"]:
            outcome = "rejected_after_interview"
        elif STAGE_IDX[effective] >= STAGE_IDX["recruiter_screen"]:
            outcome = "rejected_after_screen"
        else:
            outcome = "rejected_cv"
        patch = {"stage_reached": effective, "current_state": "closed",
                 "closed_by": "employer", "outcome": outcome}
    elif new_status == "Withdrawn":
        patch = {"stage_reached": _stage_max(stage, "applied"), "current_state": "closed",
                 "closed_by": "me", "outcome": "withdrawn_by_me"}
    if not (rec.get("track") or "") and new_status != "Wishlist":
        patch["track"] = "career"
    return patch


def apply_v4_defaults(rec: dict, today: date | None = None) -> dict:
    """Derive v4 fields for a pre-v4 record (migration pass). Returns a patch."""
    if rec.get("track") or rec.get("stage_reached"):
        return {}  # already categorized
    status = rec.get("status") or "Applied"
    if status == "Wishlist":
        return {"track": "career"}
    patch = {"track": "career"}
    patch.update(apply_status_forward({**rec, **patch}, status))
    if status == "Applied" and patch.get("current_state") == "awaiting_response":
        today = today or date.today()
        anchor = None
        last = rec.get("last_updated")
        if last:
            try:
                anchor = datetime.fromisoformat(str(last)).date()
            except ValueError:
                anchor = None
        if anchor is None:
            applied = rec.get("date_applied")
            anchor = applied if isinstance(applied, date) else None
        if anchor and (today - anchor) >= timedelta(days=STALE_AFTER_DAYS):
            patch["current_state"] = "stale"
    return patch
