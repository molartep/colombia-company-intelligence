from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

MatchType = Literal[
    "exact_nit", "exact_legal_name", "normalized_name", "partial_name", "unresolved"
]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class SourceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    provider: str
    dataset_url: str
    api_url: str | None
    last_checked_at: datetime | None
    last_updated_at: datetime | None
    enabled: bool
    availability: str


class CompanyView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nit: str | None
    verification_digit: str | None
    legal_name: str
    legal_form: str | None
    registration_status: str | None
    primary_ciiu: str | None
    department: str | None
    municipality: str | None


class SearchItem(CompanyView):
    registration_number: str | None = None
    chamber: str | None = None
    chamber_code: str | None = None
    match_type: MatchType
    evidence: list[str]
    data_source: str


class SearchPage(BaseModel):
    items: list[SearchItem]
    page: int
    page_size: int
    has_more: bool
    stale: bool = False
    warning: str | None = None
    ranking_scope: str = "current bounded page"


class RecordView(BaseModel):
    id: UUID
    external_record_id: str | None
    source_id: str
    source_url: str | None
    retrieved_at: datetime
    source_updated_at: datetime | None
    payload_hash: str
    fields: dict[str, Any]
    field_mapping: dict[str, str]


class AttributeState(BaseModel):
    state: Literal[
        "present", "missing_from_record", "unavailable_in_source", "not_yet_checked", "ambiguous"
    ]
    source_field: str | None = None
    record_id: UUID | None = None
    note: str | None = None


class Profile(CompanyView):
    created_at: datetime
    updated_at: datetime
    registration: dict[str, str | None]
    attributes: dict[str, AttributeState]
    sources: list[SourceView]
    retrieved_at: datetime | None
    source_updated_at: datetime | None
    dataset_updated_at: datetime | None
    resolution_note: str
    conflicting_registration_count: int
