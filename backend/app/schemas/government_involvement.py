from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

DecisionId = Literal[
    "direct_participation",
    "historical_participation",
    "recent_participation",
    "currently_reported_execution",
]
EvidenceStatus = Literal[
    "sufficient",
    "limited",
    "missing",
    "stale",
    "contradictory",
    "incomplete",
]


class EvidenceNode(BaseModel):
    id: str
    kind: Literal["decision", "rule", "fact", "source", "unresolved"]
    label: str
    children: list["EvidenceNode"] = Field(default_factory=list)


class Decision(BaseModel):
    id: DecisionId
    outcome: Literal[
        "documented", "reported", "no_scoped_matches", "not_observed_in_scope", "undetermined"
    ]
    evidence_status: EvidenceStatus
    supporting_aliases: list[str] = Field(default_factory=list)
    source_references: list[dict[str, str]] = Field(default_factory=list)
    supporting_contract_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    evidence_tree_id: str | None = None
    evidence_tree: EvidenceNode | None = None
    native_diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    native_evidence: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class EvaluationContext(BaseModel):
    evaluated_at: datetime
    as_of_date: date
    lookback_months: int
    lookback_start_date: date
    policy_version: str = "government_involvement_v1"


class InvolvementView(BaseModel):
    company_id: UUID | None = None
    screening_run_id: UUID | None = None
    status: Literal["disabled", "demo", "completed", "blocked", "failed", "running"]
    engine: dict[str, Any]
    evaluation: EvaluationContext
    decisions: list[Decision] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
    input_fingerprint: str | None = None
