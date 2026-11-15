from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.integrations.capital_markets.types import (
    ListingStatus,
    MatchMethod,
    MatchStatus,
    RegistrationStatus,
    SecurityCategory,
)


class SnapshotView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_id: str
    retrieved_at: datetime
    published_at: datetime | None
    source_url: str
    content_hash: str | None
    record_count: int
    ingestion_status: str
    error_details: str | None
    observed_at: datetime | None = None
    complete_current: bool = False


class MarketSourceView(BaseModel):
    id: str
    name: str
    institution: str
    source_url: str
    availability: str
    last_ingestion_status: str
    last_error: str | None
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    refresh_interval_hours: int
    stale: bool
    latest_snapshot: SnapshotView | None


class IssuerContacts(BaseModel):
    institutional_email: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    website: str | None = None
    social_networks: list[str] = Field(default_factory=list)


class IssuerAdministration(BaseModel):
    board_members_count: int | None = None
    legal_representative: str | None = None
    rnve_information_representative: str | None = None


class IssuerView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nit: str | None
    source_nit: str | None
    verification_digit: str | None
    issuer_name: str
    regulator_entity_code: str | None
    regulator_entity_type: str | None
    registration_status: RegistrationStatus
    registration_date: date | None
    cancellation_date: date | None
    last_verified_at: datetime
    raw_source_record_id: UUID | None
    source_id: str
    source_url: str
    snapshot_id: UUID
    regulator_entity_type_description: str | None = None
    contacts: IssuerContacts = Field(default_factory=IssuerContacts)
    administration: IssuerAdministration = Field(default_factory=IssuerAdministration)
    contacts_source_url: str | None = None
    contacts_retrieved_at: datetime | None = None
    administration_source_url: str | None = None
    administration_retrieved_at: datetime | None = None
    details_availability: Literal["available", "not_yet_checked", "failed_to_retrieve", "stale"] = (
        "not_yet_checked"
    )
    details_last_attempt_at: datetime | None = None
    details_last_attempt_failed: bool = False
    match_method: MatchMethod | None = None
    match_status: MatchStatus | None = None


class IssuerPage(BaseModel):
    items: list[IssuerView]
    page: int
    page_size: int
    has_more: bool


class InstrumentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    issuer_id: UUID
    security_name: str
    security_type_raw: str
    security_category: SecurityCategory
    ticker: str | None
    isin: str | None
    ann_code: str | None
    issuance_number: str | None
    exchange: str | None
    rnve_registration_date: date | None
    bvc_registration_date: date | None
    listing_status: ListingStatus
    authorized_amount: Decimal | None
    currency: str | None
    credit_rating: str | None
    source_id: str
    source_record_id: UUID | None
    last_verified_at: datetime
    source_url: str
    snapshot_id: UUID
    source_values: dict[str, str]
    stale: bool
    observation_status: str = "present_in_latest_report"
    quality_notes: list[str] = Field(default_factory=list)


class SecuritiesPage(BaseModel):
    total: int
    unfiltered_total: int
    items: list[InstrumentView]
    page: int
    page_size: int
    has_more: bool
    availability: str


class RnveFinding(BaseModel):
    status: RegistrationStatus
    issuer_name: str | None = None
    issuer_code: str | None = None
    source: str = "sfc_rnve"
    match_status: str = "unresolved"
    checked_snapshot_id: UUID | None = None


class ExchangeFinding(BaseModel):
    status: ListingStatus = ListingStatus.UNKNOWN
    exchange: str = "BVC"
    verified_as_of: datetime | None = None
    availability: str = "requires_authorized_source"
    explanation: str = (
        "No se ha verificado una fuente BVC autorizada y reproducible. Una "
        "fecha de inscripción BVC reportada por SFC no demuestra "
        "negociación vigente."
    )


class OwnershipFinding(BaseModel):
    type: str = "unknown"
    verification_status: str = "not_assessed"


class CapitalMarketsProfile(BaseModel):
    company_id: UUID
    rnve: RnveFinding
    exchange_listing: ExchangeFinding
    equity_listed: bool | None = None
    ownership: OwnershipFinding
    issuers: list[IssuerView]
    instruments: list[InstrumentView]
    securities_availability: str
    sources: list[MarketSourceView]
    last_checked_at: datetime | None
    stale: bool
    summary: str
    limitations: list[str]
