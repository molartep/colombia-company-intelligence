"""Factual preprocessing only: never computes involvement outcomes."""

import calendar
import hashlib
import json
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, StrictBool

from app.schemas.secop import ContractView


class ContractDiagnostics(BaseModel):
    """Explicit upstream diagnostics; omission means unknown, never false."""

    model_config = ConfigDict(extra="forbid")
    signature_conflict: StrictBool | None = None
    execution_status_conflict: StrictBool | None = None
    value_conflict: StrictBool | None = None


POLICY_VERSION = "government_involvement_v1"
DECISIONS = (
    "direct_participation",
    "historical_participation",
    "recent_participation",
    "currently_reported_execution",
)


def lookback_start(as_of: date, months: int) -> date:
    index = as_of.year * 12 + as_of.month - 1 - months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(as_of.day, calendar.monthrange(year, month + 1)[1]))


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def map_facts(
    contracts: list[ContractView],
    *,
    as_of: date,
    months: int,
    complete: bool,
    stale: bool,
    identity_verified: bool,
    exclusions: bool = False,
    diagnostics: dict[str, ContractDiagnostics] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]], list[str]]:
    """Accept only existing verified snapshot members; preserve local provenance.

    Pseudonyms are session-local. No names, NITs, money, descriptions or URLs leave CCI.
    CCI's current deduplication excludes all tied conflicting versions; exclusions therefore
    block negative coverage instead of assuming which fields were contradictory.
    """
    facts: list[dict[str, Any]] = []
    references: dict[str, dict[str, str]] = {}
    warnings: list[str] = []

    def add(subject: str, relationship: str, value: str | int | bool) -> None:
        facts.append(dict(subject=subject, relationship=relationship, object=value, certainty=100))

    add("evaluation", "identity_verified", identity_verified)
    add("evaluation", "query_complete", complete and not exclusions)
    add("evaluation", "source_stale", stale)
    add("evaluation", "lookback_months", months)
    add("evaluation", "as_of_date", as_of.isoformat())
    add("evaluation", "lookback_start_date", lookback_start(as_of, months).isoformat())
    add("evaluation", "contract_count", len({c.contract_id for c in contracts}))
    boundary = lookback_start(as_of, months)
    seen: set[str] = set()
    for contract in contracts:
        if contract.contract_id in seen:
            continue
        seen.add(contract.contract_id)
        alias = f"contract_{len(references) + 1}"
        references[alias] = {
            "contract_id": contract.contract_id,
            "evidence_id": str(contract.evidence_id or ""),
            "source_url": contract.source_url,
            "observed_at": contract.retrieved_at.isoformat(),
        }
        add("evaluation", "contains_contract", alias)
        add(
            alias,
            "attribution_verified",
            identity_verified
            and contract.match_status == "verified"
            and contract.match_method == "exact_supplier_nit"
            and bool(contract.evidence_id),
        )
        signature = contract.signature_date
        band = (
            "missing"
            if signature is None
            else "future"
            if signature > as_of
            else "historical"
            if signature < boundary
            else "recent"
        )
        add(alias, "signature_band", band)
        if signature:
            add(alias, "signature_date", signature.isoformat())
        if band in ("missing", "future"):
            warnings.append(f"signature_{band}")
        add(alias, "reported_status", contract.raw_status or "unknown")
        # Validated positive mapping: official SECOP 'En ejecución'. Other existing
        # normalized statuses are preserved; unknowns cannot establish a negative.
        add(
            alias,
            "execution_status",
            "execution"
            if contract.status == "in_execution"
            else "unknown"
            if contract.status == "other"
            else "non_execution",
        )
        add(alias, "observation_available", True)
        if contract.end_date:
            add(alias, "scheduled_end_date", contract.end_date.isoformat())
        diagnostic = (diagnostics or {}).get(contract.contract_id)
        if diagnostic:
            for field, value in diagnostic.model_dump(exclude_none=True).items():
                add(alias, field, value)
        if contract.status == "in_execution" and contract.end_date and contract.end_date < as_of:
            warnings.append("execution_past_scheduled_end")
    if exclusions:
        warnings.append("excluded_conflicting_or_ineligible_rows")
    if stale:
        warnings.append("source_stale")
    return facts, references, sorted(set(warnings))
