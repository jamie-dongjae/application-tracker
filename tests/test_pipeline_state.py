"""Pipeline-state markdown renderer."""
from datetime import date

from tracker.services.pipeline_state import render_pipeline_state

TODAY = date(2026, 9, 26)


def _app(**over):
    base = {"id": 1, "company": "Acme Corp", "title": "Data Analyst", "status": "Applied",
            "track": "career", "stage_reached": "applied", "current_state": "awaiting_response",
            "outcome": "", "closed_by": "", "gates": "", "next_action": "", "due": "",
            "date_applied": "2026-09-22", "last_updated": "2026-09-22T10:00:00", "notes": ""}
    base.update(over)
    return base


def test_all_sections_render():
    apps = [
        _app(id=1, current_state="action_required", next_action="nudge recruiter",
             due="2026-09-27"),
        _app(id=2, company="Beta B.V.", title="PM", current_state="on_hold_employer",
             gates="years_gap"),
        _app(id=3, company="Gamma", title="SE", current_state="stale"),
        _app(id=4, company="Delta", title="Analyst", current_state="closed",
             outcome="rejected_cv", closed_by="employer", last_updated="2026-09-20T09:00:00"),
        _app(id=5, company="Epsilon", title="Lead", current_state="awaiting_decision",
             stage_reached="final"),
    ]
    employers = [{"employer": "Acme Corp", "rule": "one at a time", "status": "slot used"}]
    md = render_pipeline_state(apps, employers, {"weekly_goal": 5}, TODAY)

    assert "# FY26 Pipeline State" in md
    assert "5 applications · 3 live · 1 closed · 1 stale" in md
    assert "## Due / action required" in md and "nudge recruiter" in md
    assert "### Awaiting decision (1)" in md and "Epsilon — Lead" in md
    assert "### On hold (employer) (1)" in md and "gates: years_gap" in md
    assert "## Recent outcomes (14 days)" in md and "rejected_cv" in md
    assert "## Stale (1)" in md and "Gamma — SE" in md
    assert "| Acme Corp | one at a time | slot used |" in md
    assert "## KPIs" in md and "this week:" in md


def test_overdue_flagged():
    apps = [_app(current_state="awaiting_response", next_action="chase", due="2026-09-20")]
    md = render_pipeline_state(apps, [], {}, TODAY)
    assert "OVERDUE" in md


def test_empty_store_does_not_crash():
    md = render_pipeline_state([], [], {}, TODAY)
    assert "# FY26 Pipeline State" in md
    assert "- nothing due" in md and "- pipeline is empty" in md
