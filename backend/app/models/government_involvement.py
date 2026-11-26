"""Append-only evaluation envelope; never alter SECOP runs or evidence."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base


class InvolvementEvaluation(Base):
    __tablename__ = "government_involvement_evaluations"
    __table_args__ = (Index("ix_involvement_cache", "input_fingerprint", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"))
    screening_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("screening_runs.id"))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    execution_mode: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
