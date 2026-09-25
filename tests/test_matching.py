"""Unit tests for the extracted matching engine (tracker/importers/matching.py)."""
from tracker.importers.matching import build_patch, match_record, new_record, norm


APPS = [
    {"id": 1, "company": "Acme Corp", "title": "Data Analyst"},
    {"id": 2, "company": "Acme Corp", "title": "Data Engineer"},
    {"id": 3, "company": "Beta B.V.", "title": "Product Manager"},
    {"id": 4, "company": "Gamma", "title": "Solutions Engineer I"},
]


def test_norm():
    assert norm("Acme Corp!") == "acmecorp"
    assert norm("Béta B.V.") == "btabv"


def test_explicit_id_match():
    app, reason = match_record({"company": "x", "title": "y", "match": {"id": 3}}, APPS)
    assert app["id"] == 3 and "explicit" in reason
    app, reason = match_record({"company": "x", "title": "y", "match": {"id": 99}}, APPS)
    assert app is None and "not found" in reason


def test_exact_title_beats_everything():
    app, reason = match_record({"company": "acme corp", "title": "Data Engineer"}, APPS)
    assert app["id"] == 2 and reason == "exact title"


def test_title_contains_disambiguates_and_flags_ambiguity():
    app, _ = match_record({"company": "Acme Corp", "title": "Engineer role",
                           "match": {"title_contains": ["engineer"]}}, APPS)
    assert app["id"] == 2
    app, reason = match_record({"company": "Acme Corp", "title": "Data role",
                                "match": {"title_contains": ["data"]}}, APPS)
    assert app is None and "AMBIGUOUS" in reason


def test_single_row_needs_token_overlap():
    app, _ = match_record({"company": "Gamma", "title": "Solutions Engineer"}, APPS)
    assert app["id"] == 4  # overlapping tokens
    app, reason = match_record({"company": "Gamma", "title": "Recruiter"}, APPS)
    assert app is None and "unrelated" in reason


def test_aliases_are_a_parameter():
    md = {"company": "Acme NL", "title": "Data Engineer"}
    app, _ = match_record(md, APPS)
    assert app is None or app["id"] == 2  # substring may match; force distinct alias case
    md = {"company": "Zeta", "title": "Product Manager"}
    assert match_record(md, APPS)[0] is None
    app, _ = match_record(md, APPS, aliases={"zeta": "betabv"})
    assert app["id"] == 3


def test_build_patch_stage_monotonic_and_note_append():
    existing = {"stage_reached": "recruiter_screen", "notes": "old line", "track": "career"}
    patch = build_patch(existing, {"stage_reached": "applied", "note": "new line"})
    assert "stage_reached" not in patch          # never downgrade
    assert patch["notes"] == "old line\nnew line"
    patch = build_patch(existing, {"stage_reached": "final", "note": "old line"})
    assert patch["stage_reached"] == "final"     # upgrade ok
    assert "notes" not in patch                  # already contained


def test_new_record_carries_v4_fields():
    rec = new_record({"company": "Zeta", "title": "PM", "track": "career",
                      "stage_reached": "applied", "date": "2026-09-01"})
    assert rec["track"] == "career" and rec["date_applied"] == "2026-09-01"
