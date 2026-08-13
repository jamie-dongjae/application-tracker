from tests.conftest import fixture_text
from tracker.services.parser import jsonld


def test_extract_jobposting_from_graph():
    fields = jsonld.extract(fixture_text("jsonld_page.html"))
    assert fields is not None
    assert fields["title"] == "Quantitative Analyst"
    assert fields["company"] == "Acme Fintech"
    assert fields["location"] == "Amsterdam, North Holland, NL"
    assert fields["work_type"] == "Remote"           # TELECOMMUTE
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
