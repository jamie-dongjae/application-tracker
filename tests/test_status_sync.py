"""v4 <-> legacy status sync: the two representations must never diverge."""
from datetime import date

from tracker.excel import schema


def _blank():
    return {"track": "", "stage_reached": "", "current_state": "", "outcome": "", "closed_by": ""}


def test_forward_map_round_trips_every_status():
    for status in schema.STATUSES:
        rec = _blank()
        rec.update(schema.apply_status_forward(rec, status))
        if status == "Wishlist":
            assert schema.derive_status(rec) == "Wishlist"
        else:
            assert schema.derive_status(rec) == status, status


def test_stage_is_monotonic_on_downgrade():
    rec = {"track": "career", "stage_reached": "final", "current_state": "closed",
           "outcome": "rejected_after_interview", "closed_by": "employer"}
    patch = schema.apply_status_forward(rec, "Interview")
    assert patch["stage_reached"] == "final"
    rec.update(patch)
    assert schema.derive_status(rec) == "Interview"  # revived, stage preserved


def test_reject_outcome_depends_on_stage():
    for stage, expected in [("applied", "rejected_cv"), ("confirmed", "rejected_cv"),
                            ("recruiter_screen", "rejected_after_screen"),
                            ("assessment", "rejected_after_screen"),
                            ("hiring_manager", "rejected_after_interview"),
                            ("final", "rejected_after_interview")]:
        rec = {**_blank(), "stage_reached": stage}
        assert schema.apply_status_forward(rec, "Rejected")["outcome"] == expected


def test_derive_status_terminal_outcomes():
    base = {"track": "career", "stage_reached": "applied", "current_state": "closed", "closed_by": "employer"}
    assert schema.derive_status({**base, "outcome": "role_closed"}) == "Rejected"
    assert schema.derive_status({**base, "outcome": "redirected"}) == "Rejected"
    assert schema.derive_status({**base, "outcome": "void"}) == "Withdrawn"
    assert schema.derive_status({**base, "outcome": "withdrawn_by_me"}) == "Withdrawn"
    assert schema.derive_status({**base, "stage_reached": "offer", "outcome": "withdrawn_by_me"}) == "Declined"
    assert schema.derive_status({**base, "stage_reached": "offer", "outcome": ""}) == "Accepted"


def test_derive_status_nurture_and_considered_are_wishlist():
    assert schema.derive_status({**_blank(), "track": "nurture", "stage_reached": "applied"}) == "Wishlist"
    assert schema.derive_status({**_blank(), "track": "career"}) == "Wishlist"  # no stage


def test_v4_defaults_by_status():
    today = date(2026, 9, 25)
    d = schema.apply_v4_defaults({"status": "Rejected", "track": "", "stage_reached": ""}, today)
    assert (d["current_state"], d["outcome"], d["closed_by"]) == ("closed", "rejected_cv", "employer")
    d = schema.apply_v4_defaults({"status": "Withdrawn", "track": "", "stage_reached": ""}, today)
    assert (d["current_state"], d["outcome"], d["closed_by"]) == ("closed", "withdrawn_by_me", "me")
    d = schema.apply_v4_defaults({"status": "Interview", "track": "", "stage_reached": ""}, today)
    assert (d["stage_reached"], d["current_state"]) == ("recruiter_screen", "awaiting_response")
    # already-categorized records are left alone
    assert schema.apply_v4_defaults({"status": "Applied", "track": "bridge", "stage_reached": "confirmed"}, today) == {}


def test_v4_defaults_stale_rule():
    today = date(2026, 9, 25)
    old = {"status": "Applied", "track": "", "stage_reached": "",
           "last_updated": "2026-08-01T10:00:00", "date_applied": date(2026, 7, 30)}
    assert schema.apply_v4_defaults(old, today)["current_state"] == "stale"
    fresh = {"status": "Applied", "track": "", "stage_reached": "",
             "last_updated": "2026-09-20T10:00:00", "date_applied": date(2026, 9, 15)}
    assert schema.apply_v4_defaults(fresh, today)["current_state"] == "awaiting_response"


def test_store_syncs_v4_fields_on_status_patch(store):
    rec = store.add_application({"company": "Acme", "title": "Analyst", "status": "Applied"})
    assert rec["stage_reached"] == "applied"
    assert rec["current_state"] == "awaiting_response"

    _, after = store.update_application(rec["id"], {"status": "Rejected"})
    assert after["current_state"] == "closed"
    assert after["outcome"] == "rejected_cv"
    assert after["closed_by"] == "employer"


def test_store_syncs_status_on_v4_patch(store):
    rec = store.add_application({"company": "Acme", "title": "Analyst", "status": "Applied"})
    _, after = store.update_application(rec["id"], {"stage_reached": "hiring_manager"})
    assert after["status"] == "Interview"
    _, after = store.update_application(rec["id"], {"current_state": "closed", "outcome": "rejected_visa"})
    assert after["status"] == "Rejected"
