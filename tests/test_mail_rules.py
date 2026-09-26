"""Deterministic mail classifier — table-driven, fictional companies only."""
from datetime import date

from tracker.importers.mail_rules import classify_messages

APPS = [
    {"id": 1, "company": "Acme Corp", "title": "Data Analyst",
     "current_state": "awaiting_response", "date_applied": date(2026, 9, 20)},
    {"id": 2, "company": "Beta B.V.", "title": "Product Manager",
     "current_state": "awaiting_response", "date_applied": date(2026, 9, 1)},
    {"id": 3, "company": "Gamma", "title": "Solutions Engineer",
     "current_state": "awaiting_response", "date_applied": date(2026, 9, 10)},
    {"id": 4, "company": "Gamma", "title": "Account Executive",
     "current_state": "awaiting_response", "date_applied": date(2026, 9, 10)},
]


def _msg(**over):
    base = {"gmail_id": "abc1", "from_name": "Acme Corp Careers",
            "from_addr": "no-reply@acmecorp.example", "from_domain": "acmecorp.example",
            "subject": "Your application", "date": "2026-09-25", "body": ""}
    base.update(over)
    return base


def test_confirmation_high():
    msgs = [_msg(body="Thank you for applying! We received your application for Data Analyst.")]
    high, review, ignored = classify_messages(msgs, APPS, {})
    assert len(high) == 1 and not review and not ignored
    rec = high[0]
    assert rec["match"] == {"id": 1}
    assert rec["patch"] == {"stage_reached": "confirmed"}
    assert rec["events"][0]["provenance"] == "gmail:abc1"


def test_rejection_next_day_is_ats_later_is_cv():
    fast = [_msg(gmail_id="r1", body="Unfortunately we will not be moving forward.",
                 date="2026-09-21")]  # applied 09-20 -> within 1 day
    high, _, _ = classify_messages(fast, APPS, {})
    assert high[0]["patch"]["outcome"] == "rejected_ats"

    slow = [_msg(gmail_id="r2", from_name="Beta B.V.", from_domain="betabv.example",
                 body="Helaas gaan we niet verder met je sollicitatie.", date="2026-09-25")]
    high, _, _ = classify_messages(slow, APPS, {})
    assert high[0]["match"] == {"id": 2}
    assert high[0]["patch"]["outcome"] == "rejected_cv"


def test_visa_keyword_forces_review():
    msgs = [_msg(body="Unfortunately we cannot proceed with candidates requiring visa sponsorship.")]
    high, review, _ = classify_messages(msgs, APPS, {})
    assert not high and len(review) == 1
    assert review[0]["proposed"]["confidence"] == "review"
    assert review[0]["email"]["gmail_id"] == "abc1"


def test_two_open_roles_forces_review():
    msgs = [_msg(from_name="Gamma Recruiting", from_domain="gamma.example",
                 body="Unfortunately we decided to pursue other candidates.")]
    high, review, _ = classify_messages(msgs, APPS, {})
    assert not high and len(review) == 1  # Gamma has 2 open roles, no title in mail


def test_title_disambiguates_multi_role_company():
    msgs = [_msg(from_name="Gamma Recruiting", from_domain="gamma.example",
                 subject="Solutions Engineer application",
                 body="We received your application for Solutions Engineer.")]
    high, review, _ = classify_messages(msgs, APPS, {})
    assert len(high) == 1 and high[0]["match"] == {"id": 3}


def test_unknown_company_non_ats_ignored():
    msgs = [_msg(from_name="Random Newsletter", from_domain="news.example",
                 subject="Weekly digest", body="jobs jobs jobs")]
    high, review, ignored = classify_messages(msgs, APPS, {})
    assert not high and not review and ignored == 1


def test_ats_domain_without_match_goes_to_review():
    msgs = [_msg(from_name="Recruiting", from_domain="mail.greenhouse.io",
                 subject="Interview invitation", body="We'd love to schedule a call.")]
    high, review, ignored = classify_messages(msgs, APPS, {})
    assert not high and len(review) == 1 and not ignored
    assert review[0]["proposed"]["match"] == {}


def test_aliases_bridge_company_names():
    msgs = [_msg(gmail_id="al1", from_name="Acme NL", from_domain="acmenl.example",
                 body="Thank you for applying. We received your application.")]
    # without alias: from_name "acmenl" contains "acmecorp"? no -> review/ignore path
    high, review, _ = classify_messages(msgs, APPS, {})
    assert not high
    high, review, _ = classify_messages(msgs, APPS, {"acmenl": "acmecorp"})
    assert len(high) == 1 and high[0]["match"] == {"id": 1}
