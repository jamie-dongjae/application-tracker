from tests.conftest import fixture_text
from waypoint.services.parser import jsonld


def test_extract_jobposting_from_graph():
    fields = jsonld.extract(fixture_text("jsonld_page.html"))
    assert fields is not None
    assert fields["title"] == "Quantitative Analyst"
    assert fields["company"] == "Acme Fintech"
    assert fields["location"] == "Amsterdam, North Holland, NL"
    assert fields["work_type"] == "Remote"           # TELECOMMUTE
    assert fields["salary_min"] == 4500 * 12          # MONTH → yearly
    assert fields["salary_max"] == 6000 * 12
    assert fields["currency"] == "EUR"
    assert any("month" in w.lower() for w in fields["_warnings"])
    assert "visa sponsorship" in fields["_description_text"].lower()


def test_no_jobposting_returns_none():
    assert jsonld.extract("<html><body><p>hello</p></body></html>") is None


def test_malformed_block_is_skipped():
    html = """<script type="application/ld+json">{not json at all</script>
    <script type="application/ld+json">{"@type":"JobPosting","title":"X",
      "hiringOrganization":{"name":"Y"},}</script>"""
    fields = jsonld.extract(html)
    assert fields["title"] == "X"
    assert fields["company"] == "Y"
