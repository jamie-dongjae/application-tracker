"""Field normalization: canonical sources, work types, URL inference."""
from tracker.importers.normalize import (
    infer_source_from_url, normalize_source, normalize_work_type,
)


def test_normalize_source_variants():
    assert normalize_source("Linkedin") == "LinkedIn"
    assert normalize_source("LinkedIn Easy Apply") == "LinkedIn"
    assert normalize_source("linkedin") == "LinkedIn"
    assert normalize_source("Join") == "Job board"
    assert normalize_source("Indeed") == "Job board"
    assert normalize_source("company site") == "Company site"
    assert normalize_source("Referral") == "Referral"


def test_normalize_source_preserves_unknowns_and_empty():
    assert normalize_source("") == ""
    assert normalize_source(None) == ""
    assert normalize_source("Weird Custom Source") == "Weird Custom Source"


def test_normalize_work_type():
    assert normalize_work_type("On-site") == "Onsite"
    assert normalize_work_type("on site") == "Onsite"
    assert normalize_work_type("REMOTE") == "Remote"
    assert normalize_work_type("") == ""
    assert normalize_work_type("4 days office") == "4 days office"  # preserved


def test_infer_source_from_url():
    assert infer_source_from_url("https://www.linkedin.com/jobs/view/1") == "LinkedIn"
    assert infer_source_from_url("https://join.com/companies/acme/1") == "Job board"
    assert infer_source_from_url("https://nl.indeed.com/viewjob?jk=1") == "Job board"
    assert infer_source_from_url("https://wellfound.com/jobs/1") == "Job board"
    assert infer_source_from_url("https://jobs.lever.co/acme/1") == "Company site"
    assert infer_source_from_url("https://acme.wd12.myworkdayjobs.com/x") == "Company site"
    assert infer_source_from_url("https://careers.acme.example/jobs/1") == "Company site"
    assert infer_source_from_url("careers.acme.example/jobs/1") == "Company site"  # schemeless
    assert infer_source_from_url("") == ""
    assert infer_source_from_url(None) == ""


def test_store_clean_normalizes_on_write(store):
    rec = store.add_application({"company": "Acme Corp", "title": "Analyst",
                                 "source": "Linkedin", "work_type": "On-site"})
    assert rec["source"] == "LinkedIn"
    assert rec["work_type"] == "Onsite"
