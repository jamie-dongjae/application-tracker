from tests.conftest import fixture_text
from tracker.services.fetcher import classify_blocked
from tracker.services.parser import meta_tags


def test_og_title_at_pattern():
    fields = meta_tags.extract(fixture_text("og_only.html"), "https://careers.bluewater.example/jobs/1")
    assert fields["title"] == "Senior Data Analyst"
    assert fields["company"] == "Bluewater"
    assert "visa sponsorship" in fields["_description_text"].lower()


def test_source_from_url():
    assert meta_tags.source_from_url("https://www.linkedin.com/jobs/view/1") == "LinkedIn"
    assert meta_tags.source_from_url("https://nl.indeed.com/viewjob?jk=1") == "Indeed"
    assert meta_tags.source_from_url("https://boards.greenhouse.io/acme/jobs/1") == "Company site"
    assert meta_tags.source_from_url("https://careers.acme.com/jobs/1") == "Company site"


def test_company_from_host():
    assert meta_tags.company_from_host("https://careers.acme-corp.com/jobs/1") == "Acme Corp"
    assert meta_tags.company_from_host("https://jobs.bluewater.io/x") == "Bluewater"


def test_authwall_classification():
    text = fixture_text("linkedin_authwall.html")
    assert classify_blocked(200, "https://www.linkedin.com/authwall?return=1", text)
    assert classify_blocked(999, "https://www.linkedin.com/jobs/view/1", "")
    assert classify_blocked(403, "https://nl.indeed.com/viewjob", "")
    assert classify_blocked(200, "https://example.com/challenge", "Just a moment...")
    assert not classify_blocked(200, "https://careers.acme.com/jobs/1", "<html><title>Data Analyst</title></html>")
