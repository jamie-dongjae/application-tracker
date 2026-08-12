import pytest

from waypoint.services.parser import sponsorship


@pytest.mark.parametrize("text", [
    "Visa sponsorship is available for this role.",
    "We can sponsor a highly skilled migrant visa.",
    "Wij zijn een recognised sponsor (kennismigrant).",
    "Eligible employees benefit from the 30% ruling.",
    "We offer relocation support and work permit assistance.",
])
def test_positive(text):
    result = sponsorship.scan(text)
    assert result and result["value"] == "Mentioned"
    assert result["snippet"]


@pytest.mark.parametrize("text", [
    "We do not provide visa sponsorship.",
    "No visa sponsorship for this position.",
    "Unfortunately we are unable to sponsor visas.",
    "You must have the right to work in the Netherlands.",
    "Sponsorship is not available at this time.",
])
def test_negative(text):
    result = sponsorship.scan(text)
    assert result and result["value"] == "Not offered"


def test_negative_wins_over_positive():
    text = "We value visa sponsorship questions, however we do not provide visa sponsorship."
    assert sponsorship.scan(text)["value"] == "Not offered"


def test_silent_returns_none():
    assert sponsorship.scan("A normal job description about dashboards.") is None
    assert sponsorship.scan("") is None
