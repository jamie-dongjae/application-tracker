"""Pydantic request/response models."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .excel import schema as xl_schema

_ENUM_FIELDS = {
    "track": xl_schema.TRACKS,
    "stage_reached": xl_schema.STAGES,
    "current_state": xl_schema.CURRENT_STATES,
    "outcome": xl_schema.OUTCOMES,
    "closed_by": xl_schema.CLOSED_BY,
}


class _V4EnumMixin:
    @field_validator("track", "stage_reached", "current_state", "outcome", "closed_by",
                     mode="before", check_fields=False)
    @classmethod
    def _check_enum(cls, value, info):
        if value in (None, ""):
            return value
        allowed = _ENUM_FIELDS[info.field_name]
        if str(value) not in allowed:
            raise ValueError(f"{info.field_name} must be one of {allowed} (got {value!r})")
        return value


class ApplicationIn(_V4EnumMixin, BaseModel):
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
    track: str = ""
    stage_reached: str = ""
    current_state: str = ""
    outcome: str = ""
    closed_by: str = ""
    gates: str = ""
    contacts: str = ""
    next_action: str = ""
    due: Optional[str] = None  # yyyy-mm-dd
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geo_status: str = ""


class ApplicationPatch(_V4EnumMixin, BaseModel):
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
    track: Optional[str] = None
    stage_reached: Optional[str] = None
    current_state: Optional[str] = None
    outcome: Optional[str] = None
    closed_by: Optional[str] = None
    gates: Optional[str] = None
    contacts: Optional[str] = None
    next_action: Optional[str] = None
    due: Optional[str] = None
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


class EventIn(BaseModel):
    date: Optional[str] = None  # yyyy-mm-dd
    event: str = Field(min_length=1)
    note: str = ""


class EmployerIn(BaseModel):
    employer: str = Field(min_length=1)
    rule: str = ""
    status: str = ""


class SyncPatch(_V4EnumMixin, BaseModel):
    track: Optional[str] = None
    stage_reached: Optional[str] = None
    current_state: Optional[str] = None
    outcome: Optional[str] = None
    closed_by: Optional[str] = None
    gates: Optional[str] = None
    contacts: Optional[str] = None
    next_action: Optional[str] = None
    due: Optional[str] = None


class SyncEventIn(BaseModel):
    date: Optional[str] = None
    event: str = Field(min_length=1)
    note: str = ""
    provenance: str = ""  # e.g. "gmail:<message-id>"


class SyncRecord(BaseModel):
    company: str = Field(min_length=1)
    title: str = Field(min_length=1)
    match: dict = Field(default_factory=dict)      # {"id": N} | {"title": ...} | {"title_contains": [...]}
    confidence: str = "review"                     # "high" | "review" — gated client-side
    reason: str = ""
    fields: dict = Field(default_factory=dict)     # base columns for adds / fill-if-empty
    patch: SyncPatch = Field(default_factory=SyncPatch)
    note: str = ""
    events: list[SyncEventIn] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)


class SyncPacket(BaseModel):
    packet_version: int = 1
    source: str = "manual"
    generated_at: str = Field(min_length=1)        # ISO timestamp; becomes last_sync on apply
    since: str = ""
    records: list[SyncRecord] = Field(default_factory=list)
    employers: list[EmployerIn] = Field(default_factory=list)
    aliases: dict = Field(default_factory=dict)    # normalized name -> normalized tracker name


class SyncImportRequest(BaseModel):
    packet: SyncPacket
    dry_run: bool = True


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
