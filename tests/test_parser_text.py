from tests.conftest import fixture_text
from waypoint.services.parser import parse_pasted


def test_pasted_english_jd():
    result = parse_pasted(fixture_text("pasted_jd_en.txt"))
    fields = result["fields"]
    assert fields["title"] == "Senior Data Analyst"
    assert fields["company"] == "Acme Analytics"
    assert fields["location"] == "Amsterdam, Netherlands"
    assert fields["work_type"] == "Hybrid"
    assert fields["salary_min"] == 55000
    assert fields["salary_max"] == 70000
    assert fields["currency"] == "EUR"
    assert fields["sponsorship"] == "Mentioned"
    assert result["evidence"]["sponsorship_snippet"]
    assert result["method"] == "Pasted text"


def test_pasted_dutch_jd_monthly_salary():
    result = parse_pasted(fixture_text("pasted_jd_nl.txt"))
    fields = result["fields"]
    assert fields["title"] == "Data Engineer"
    assert fields["location"] == "Rotterdam, Zuid-Holland"
    assert fields["work_type"] == "Hybrid"
    assert fields["salary_min"] == 4500 * 12
    assert fields["sponsorship"] == "Not offered"
    assert any("month" in w.lower() for w in result["warnings"])


def test_pasted_with_url_source():
    result = parse_pasted("Data Analyst\nSome Company\nGreat role.",
                          url="https://www.linkedin.com/jobs/view/123")
    assert result["fields"]["source"] == "LinkedIn"
