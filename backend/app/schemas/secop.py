from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ContractStatus = Literal[
    "in_execution",
    "signed",
    "closed",
    "terminated",
    "liquidated",
    "suspended",
    "cancelled",
    "draft",
    "other",
]


class ContractView(BaseModel):
    contract_id: str
    process_id: str | None = None
    reference: str | None = None
    original_supplier_identifier: str
    normalized_supplier_identifier: str
    supplier_document_type: str
    source_identifier: str
    match_method: Literal["exact_supplier_nit"] = "exact_supplier_nit"
    match_status: Literal["verified"] = "verified"
    buyer: str | None = None
    buyer_nit: str | None = None
    description: str | None = None
    value: Decimal | None = None
    currency: str | None = None
    currency_basis: Literal["application_policy", "unspecified"] = "unspecified"
    raw_status: str | None = None
    status: ContractStatus
    contract_type: str | None = None
    modality: str | None = None
    signature_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    department: str | None = None
    city: str | None = None
    source_url: str
    source_link_label: str
    retrieved_at: datetime
    source_updated_at: datetime | None = None
    evidence_id: UUID | None = None


class ActivityGroup(BaseModel):
    label: str
    count: int
    values: dict[str, Decimal] = Field(default_factory=dict)


class ScreeningSummary(BaseModel):
    total_contracts: int
    total_values: dict[str, Decimal]
    monetary_contracts: int
    missing_or_invalid_values: int
    unknown_currency_contracts: int
    zero_value_contracts: int
    distinct_buyers: int
    latest_signature_date: date | None
    annual: list[ActivityGroup]
    statuses: list[ActivityGroup]
    top_buyers: list[ActivityGroup]
    modalities: list[ActivityGroup]
    departments: list[ActivityGroup]
    executive_summary: str


class ScreeningView(BaseModel):
    company_id: UUID
    company_name: str
    nit: str | None
    source_id: str
    source_url: str
    publisher: str = "Agencia Nacional de Contratación Pública — Colombia Compra Eficiente"
    outcome: Literal[
        "completed_with_matches",
        "completed_no_matches",
        "source_unavailable",
        "failed",
        "stale",
        "not_screened",
        "missing_nit",
        "running",
    ]
    run_id: UUID | None = None
    run_status: Literal["pending", "running", "completed", "failed"] | None = None
    last_attempted_at: datetime | None = None
    last_successful_at: datetime | None = None
    source_updated_at: datetime | None = None
    cache_age_seconds: int | None = None
    cache_ttl_seconds: int
    summary: ScreeningSummary | None = None
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    query_metadata: dict[str, Any] = Field(default_factory=dict)


class ContractPage(BaseModel):
    items: list[ContractView]
    page: int
    page_size: int
    total: int
    has_more: bool
    run_id: UUID | None = None
