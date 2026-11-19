import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base


class ScreeningRun(Base):
    __tablename__ = "screening_runs"
    __table_args__ = (
        Index("ix_screening_company_source_started", "company_id", "source_id", "started_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    source_id: Mapped[str] = mapped_column(String(100), ForeignKey("data_sources.id"))
    canonical_nit: Mapped[str] = mapped_column(String(15))
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    query_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)


class SecopContract(Base):
    __tablename__ = "secop_contracts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_records.id"), unique=True)
    contract_id: Mapped[str] = mapped_column(String(300), index=True)
    buyer: Mapped[str | None] = mapped_column(String(1000), index=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    modality: Mapped[str | None] = mapped_column(String(500), index=True)
    signature_date: Mapped[date | None] = mapped_column(Date, index=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(31, 6), index=True)
    normalized: Mapped[dict[str, Any]] = mapped_column(JSONB)


class ScreeningContract(Base):
    __tablename__ = "screening_contracts"
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("screening_runs.id"), primary_key=True)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("secop_contracts.id"), primary_key=True
    )
