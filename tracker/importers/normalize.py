"""Field normalization: canonical source/work_type values + URL-based inference.

Applied at input time via ExcelStore._clean, so every write path (form, sync,
importers) converges on the same vocabulary — the Insights source charts are
only meaningful when "LinkedIn", "Linkedin" and "LinkedIn Easy Apply" are one
bucket. Unknown values are preserved verbatim, never destroyed.
"""
from __future__ import annotations

from urllib.parse import urlparse

from .matching import norm

CANONICAL_SOURCES = ["LinkedIn", "Company site", "Job board", "Referral",
                     "Recruiter", "Other"]

# norm(variant) -> canonical
SOURCE_VARIANTS = {
    "linkedin": "LinkedIn",
    "linkedineasyapply": "LinkedIn",
    "easyapply": "LinkedIn",
    "companysite": "Company site",
    "companywebsite": "Company site",
    "careersite": "Company site",
    "careerspage": "Company site",
    "jobboard": "Job board",
    "join": "Job board",
    "joincom": "Job board",
    "indeed": "Job board",
    "otta": "Job board",
    "glassdoor": "Job board",
    "referral": "Referral",
    "recruiter": "Recruiter",
    "headhunter": "Recruiter",
    "other": "Other",
    # legacy parser labels for job boards
    "wttj": "Job board",
    "wellfound": "Job board",
    "iamexpat": "Job board",
    "magnetme": "Job board",
}

_JOB_BOARD_DOMAINS = ("join.com", "indeed.", "glassdoor.", "otta.com",
                      "welcometothejungle", "honeypot.io", "wellfound.com",
                      "iamexpat.nl", "magnet.me")

_WORK_TYPE_VARIANTS = {
    "onsite": "Onsite", "on-site": "Onsite", "on site": "Onsite",
    "hybrid": "Hybrid", "remote": "Remote", "fully remote": "Remote",
}


def normalize_source(value) -> str:
    """Fold known variants into the canonical vocabulary; keep unknowns as-is."""
    text = str(value or "").strip()
    if not text:
        return ""
    return SOURCE_VARIANTS.get(norm(text), text)


def normalize_work_type(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return _WORK_TYPE_VARIANTS.get(text.lower(), text)


def infer_source_from_url(url) -> str:
    """Deterministic source from a job-posting/portal URL; "" when unknowable."""
    text = str(url or "").strip()
    if not text:
        return ""
    host = urlparse(text if "//" in text else f"https://{text}").netloc.lower()
    if not host:
        return ""
    if "linkedin.com" in host:
        return "LinkedIn"
    if any(d in host for d in _JOB_BOARD_DOMAINS):
        return "Job board"
    # Anything else with a real host — company career page or the company's ATS
    # tenant (myworkdayjobs, greenhouse, lever...) — counts as applying direct.
    return "Company site"
