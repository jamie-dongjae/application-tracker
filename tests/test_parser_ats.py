import json

import pytest

from tests.conftest import fixture_text
from waypoint.services.parser import ats


@pytest.mark.parametrize("url,kind,api_fragment", [
    ("https://boards.greenhouse.io/acme/jobs/4021775008",
     "greenhouse", "boards-api.greenhouse.io/v1/boards/acme/jobs/4021775008"),
    ("https://job-boards.eu.greenhouse.io/acme/jobs/999",
     "greenhouse", "boards-api.eu.greenhouse.io/v1/boards/acme/jobs/999"),
    ("https://jobs.lever.co/acme/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
     "lever", "api.lever.co/v0/postings/acme/a1b2c3d4"),
    ("https://jobs.eu.lever.co/acme/a1b2c3d4",
     "lever", "api.eu.lever.co/v0/postings/acme/a1b2c3d4"),
    ("https://jobs.ashbyhq.com/acme/f47ac10b-58cc-4372-a567-0e02b2c3d479",
     "ashby", "api.ashbyhq.com/posting-api/job-board/acme"),
    ("https://apply.workable.com/acme/j/12AB34C/",
     "workable", "apply.workable.com/api/v2/accounts/acme/jobs/12AB34C"),
    ("https://acme.recruitee.com/o/devops-engineer",
     "recruitee", "acme.recruitee.com/api/offers/devops-engineer"),
    ("https://jobs.smartrecruiters.com/Acme1/744000060000000-product-manager",
     "smartrecruiters", "api.smartrecruiters.com/v1/companies/Acme1/postings/744000060000000"),
    ("https://acme.wd3.myworkdayjobs.com/en-US/External/job/Amsterdam/Financial-Analyst_JR-1234",
     "workday", "acme.wd3.myworkdayjobs.com/wday/cxs/acme/External/job/Financial-Analyst_JR-1234"),
])
def test_detect(url, kind, api_fragment):
    ref = ats.detect(url)
    assert ref is not None, url
    assert ref.kind == kind
    assert api_fragment in ref.api_url


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/1234567890",
    "https://careers.example.com/openings/data-analyst",
    "https://boards.greenhouse.io/acme",  # board root, not a job
])
def test_detect_non_ats(url):
    assert ats.detect(url) is None


def test_parse_greenhouse():
    payload = json.loads(fixture_text("greenhouse_job.json"))
    ref = ats.AtsRef("greenhouse", "", company_hint="Acme")
    fields = ats.parse_greenhouse(payload, ref)
    assert fields["title"] == "Data Analyst"
    assert fields["location"] == "Amsterdam, Netherlands"
    assert "recognised sponsor" in fields["_description_text"].lower()
    assert "&lt;" not in fields["_description_text"]  # entity-escaped HTML unwrapped


def test_parse_lever():
    payload = json.loads(fixture_text("lever_posting.json"))
    ref = ats.AtsRef("lever", "", company_hint="Acme")
    fields = ats.parse_lever(payload, ref)
    assert fields["title"] == "Machine Learning Engineer"
    assert fields["work_type"] == "Hybrid"
    assert fields["salary_min"] == 65000
    assert fields["salary_max"] == 85000
    assert fields["currency"] == "EUR"


def test_parse_ashby_selects_right_job():
    payload = json.loads(fixture_text("ashby_board.json"))
    ref = ats.AtsRef("ashby", "", company_hint="Acme",
                     job_hint="f47ac10b-58cc-4372-a567-0e02b2c3d479")
    fields = ats.parse_ashby(payload, ref)
    assert fields["title"] == "Backend Engineer"
    assert fields["salary_min"] == 70000
    assert fields["currency"] == "EUR"


def test_parse_workable():
    payload = json.loads(fixture_text("workable_job.json"))
    ref = ats.AtsRef("workable", "", company_hint="Acme")
    fields = ats.parse_workable(payload, ref)
    assert fields["company"] == "Acme B.V."
    assert fields["location"] == "Eindhoven, Netherlands"
    assert fields["work_type"] == "Hybrid"


def test_parse_workday():
    payload = json.loads(fixture_text("workday_cxs.json"))
    ref = ats.AtsRef("workday", "", company_hint="Acme")
    fields = ats.parse_workday(payload, ref)
    assert fields["title"] == "Financial Analyst"
    assert fields["location"] == "Amsterdam, Netherlands"
    assert "30% ruling" in fields["_description_text"]


def test_parse_smartrecruiters():
    payload = json.loads(fixture_text("smartrecruiters.json"))
    ref = ats.AtsRef("smartrecruiters", "", company_hint="Acme1")
    fields = ats.parse_smartrecruiters(payload, ref)
    assert fields["title"] == "Product Manager"
    assert fields["company"] == "Acme"
    assert "Visa sponsorship available" in fields["_description_text"]


def test_parse_recruitee():
    payload = json.loads(fixture_text("recruitee_offer.json"))
    ref = ats.AtsRef("recruitee", "", company_hint="Acme")
    fields = ats.parse_recruitee(payload, ref)
    assert fields["title"] == "DevOps Engineer"
    assert fields["location"] == "Utrecht, Netherlands"
