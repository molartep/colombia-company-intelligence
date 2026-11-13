import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index(
            "ix_companies_name_prefix",
            "normalized_name",
            postgresql_ops={"normalized_name": "text_pattern_ops"},
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    identity_key: Mapped[str] = mapped_column(String(300), unique=True)
    nit: Mapped[str | None] = mapped_column(String(15), index=True)
    verification_digit: Mapped[str | None] = mapped_column(String(1))
    legal_name: Mapped[str] = mapped_column(String(1000))
    normalized_name: Mapped[str] = mapped_column(String(1000), index=True)
    legal_form: Mapped[str | None] = mapped_column(String(300))
    registration_status: Mapped[str | None] = mapped_column(String(100))
    primary_ciiu: Mapped[str | None] = mapped_column(String(20))
    department: Mapped[str | None] = mapped_column(String(200))
    municipality: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataSource(Base):
    __tablename__ = "data_sources"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(String(2000))
    provider: Mapped[str] = mapped_column(String(300))
    dataset_url: Mapped[str] = mapped_column(String(1000))
    api_url: Mapped[str | None] = mapped_column(String(1000))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    availability: Mapped[str] = mapped_column(String(40), default="not_yet_checked")


class CompanyAlias(Base):
    __tablename__ = "company_aliases"
    __table_args__ = (
        UniqueConstraint("company_id", "normalized_name", "alias_type"),
        Index(
            "ix_aliases_name_prefix",
            "normalized_name",
            postgresql_ops={"normalized_name": "text_pattern_ops"},
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(1000))
    normalized_name: Mapped[str] = mapped_column(String(1000), index=True)
    alias_type: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"))


class SourceRecord(Base):
    __tablename__ = "source_records"
    __table_args__ = (
        UniqueConstraint("source_id", "external_record_id", "payload_hash"),
        Index("ix_source_records_company_retrieved", "company_id", "retrieved_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id"))
    external_record_id: Mapped[str | None] = mapped_column(String(300))
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    source_nit: Mapped[str | None] = mapped_column(String(100))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    payload_hash: Mapped[str] = mapped_column(String(64))
