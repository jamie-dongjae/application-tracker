"""Pydantic request/response models."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ApplicationIn(BaseModel):
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: str = "Applied"
    date_applied: Optional[str] = None  # yyyy-mm-dd
    location: str = ""
    work_type: str = ""
    source: str = ""
    sponsorship: str = ""
    referral: str = ""
    url: str = ""
    portal_url: str = ""
    notes: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geo_status: str = ""


class ApplicationPatch(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    date_applied: Optional[str] = None
    location: Optional[str] = None
    work_type: Optional[str] = None
    source: Optional[str] = None
    sponsorship: Optional[str] = None
    referral: Optional[str] = None
    url: Optional[str] = None
    portal_url: Optional[str] = None
    notes: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geo_status: Optional[str] = None


class PrepIn(BaseModel):
    category: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str = ""


class PrepPatch(BaseModel):
    category: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None


class PrefillRequest(BaseModel):
    url: str = Field(min_length=4)


class PrefillTextRequest(BaseModel):
    text: str = Field(min_length=10)
    url: str = ""


class GeocodeRequest(BaseModel):
    query: str = Field(min_length=2)
    force: bool = False


class SettingsPatch(BaseModel):
    weekly_goal: Optional[int] = Field(default=None, ge=1, le=100)
    stale_days: Optional[int] = Field(default=None, ge=1, le=365)
    theme: Optional[str] = None


class ImportRequest(BaseModel):
    path: str = Field(min_length=1)
