import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.integrations.capital_markets.types import (
    ListingStatus,
    MatchMethod,
    MatchStatus,
    RegistrationStatus,
    SecurityCategory,
)
from app.models.entities import Base


def enum_column(cls: type[enum.Enum]) -> Enum:
    return Enum(
        cls,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda values: [v.value for v in values],
        name=cls.__name__.lower(),
    )


class CapitalMarketsSourceSnapshot(Base):
    __tablename__ = "capital_markets_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"), index=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str] = mapped_column(String(1000))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    ingestion_status: Mapped[str] = mapped_column(String(30))
    error_details: Mapped[str | None] = mapped_column(String(1000))
    details: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class SecuritiesIssuer(Base):
    __tablename__ = "securities_issuers"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"))
    external_id: Mapped[str] = mapped_column(String(100))
    nit: Mapped[str | None] = mapped_column(String(30), index=True)
    source_nit: Mapped[str | None] = mapped_column(String(100))
    verification_digit: Mapped[str | None] = mapped_column(String(1))
    identity_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    issuer_name: Mapped[str] = mapped_column(String(1000))
    normalized_name: Mapped[str] = mapped_column(String(1000), index=True)
    regulator_entity_code: Mapped[str | None] = mapped_column(String(20))
    regulator_entity_type: Mapped[str | None] = mapped_column(String(20))
    registration_status: Mapped[RegistrationStatus] = mapped_column(enum_column(RegistrationStatus))
    registration_date: Mapped[date | None] = mapped_column(Date)
    cancellation_date: Mapped[date | None] = mapped_column(Date)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_source_record_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_records.id"))
    last_snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("capital_markets_snapshots.id"))


class SecurityInstrument(Base):
    __tablename__ = "security_instruments"
    __table_args__ = (UniqueConstraint("issuer_id", "source_id", "external_id"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    issuer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities_issuers.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(64))
    security_name: Mapped[str] = mapped_column(String(1000))
    security_type_raw: Mapped[str] = mapped_column(String(500))
    security_category: Mapped[SecurityCategory] = mapped_column(enum_column(SecurityCategory))
    ticker: Mapped[str | None] = mapped_column(String(100))
    isin: Mapped[str | None] = mapped_column(String(100))
    ann_code: Mapped[str | None] = mapped_column(String(100))
    issuance_number: Mapped[str | None] = mapped_column(String(100))
    exchange: Mapped[str | None] = mapped_column(String(100))
    rnve_registration_date: Mapped[date | None] = mapped_column(Date)
    bvc_registration_date: Mapped[date | None] = mapped_column(Date)
    listing_status: Mapped[ListingStatus] = mapped_column(enum_column(ListingStatus))
    authorized_amount: Mapped[Decimal | None] = mapped_column(Numeric(32, 4))
    currency: Mapped[str | None] = mapped_column(String(20))
    credit_rating: Mapped[str | None] = mapped_column(String(200))
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"))
    source_record_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("source_records.id"))
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("capital_markets_snapshots.id"))


class IssuerCompanyMatch(Base):
    __tablename__ = "issuer_company_matches"
    __table_args__ = (
        UniqueConstraint("issuer_id", "company_id"),
        Index(
            "uq_verified_issuer_match",
            "issuer_id",
            unique=True,
            postgresql_where=text("match_status = 'verified'"),
        ),
        Index(
            "uq_verified_company_match",
            "company_id",
            unique=True,
            postgresql_where=text("match_status = 'verified'"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    issuer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("securities_issuers.id"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    match_method: Mapped[MatchMethod] = mapped_column(enum_column(MatchMethod))
    match_status: Mapped[MatchStatus] = mapped_column(enum_column(MatchStatus))
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
