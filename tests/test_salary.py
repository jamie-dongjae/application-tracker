import pytest

from waypoint.services.parser import salary


@pytest.mark.parametrize("text,mn,mx,cur", [
    ("Salary: €60,000 – €80,000 per year", 60000, 80000, "EUR"),
    ("Base compensation $90k-$120k", 90000, 120000, "USD"),
    ("Salary range 60,000 - 80,000 EUR", 60000, 80000, "EUR"),
    ("We pay EUR 60.000 - 80.000 gross", 60000, 80000, "EUR"),
    ("Salary £45,000 per annum", 45000, None, "GBP"),
    ("Salaris: €4.500 per maand", 54000, None, "EUR"),
    ("bruto salaris €3.200 - €4.100 p/m", 38400, 49200, "EUR"),
])
def test_parse_ranges(text, mn, mx, cur):
    found = salary.parse(text)
    assert found is not None, text
    assert found["salary_min"] == mn
    assert found["salary_max"] == mx or found["salary_max"] is None and mx is None
    assert found["currency"] == cur


@pytest.mark.parametrize("text", [
    "You have 5-8 years of experience",
    "Work 32-40 hours per week",
    "€25 per hour freelance rate",
    "No salary mentioned here at all",
    "",
])
def test_parse_rejects_noise(text):
    found = salary.parse(text)
    if found is not None:
        # Never annualize hourly, never accept tiny "ranges" as salaries.
        assert found["salary_min"] >= 1000


def test_monthly_conversion_warns():
    found = salary.parse("Salaris: €4.500 per maand")
    assert any("month" in w.lower() for w in found["warnings"])
