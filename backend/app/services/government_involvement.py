"""Snapshot-pinned Rae evaluations; source evidence is never mutated."""

import asyncio
import math
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.rainbird.client import RaeClient, RaeError
from app.integrations.rainbird.mapper import (
    DECISIONS,
    ContractDiagnostics,
    fingerprint,
    lookback_start,
    map_facts,
)
from app.integrations.secop.adapter import MATCHING_POLICY, SOURCE_ID
from app.integrations.secop.normalize import source_link, supplier_matches
from app.models.entities import Company, SourceRecord
from app.models.government_involvement import InvolvementEvaluation
from app.models.secop import ScreeningContract, ScreeningRun, SecopContract
from app.schemas.government_involvement import (
    Decision,
    EvaluationContext,
    EvidenceNode,
    InvolvementView,
)
from app.schemas.secop import ContractView
from app.services import secop

_inference_slots = asyncio.Semaphore(2)


def context(as_of: date | None = None, *, lookback_months: int | None = None) -> EvaluationContext:
    today = as_of or datetime.now(ZoneInfo("America/Bogota")).date()
    months = (
        lookback_months
        if lookback_months is not None
        else get_settings().government_involvement_lookback_months
    )
    if not 1 <= months <= 120:
        raise HTTPException(422, "Lookback must be between 1 and 120 calendar months.")
    return EvaluationContext(
        evaluated_at=datetime.now(UTC),
        as_of_date=today,
        lookback_months=months,
        lookback_start_date=lookback_start(today, months),
    )


async def snapshot_contracts(
    session: AsyncSession,
    company: Company,
    run: ScreeningRun,
) -> tuple[list[ContractView], list[str], bool]:
    rows = (
        await session.execute(
            select(SecopContract, SourceRecord)
            .join(ScreeningContract, ScreeningContract.contract_id == SecopContract.id)
            .join(SourceRecord, SourceRecord.id == SecopContract.evidence_id)
            .where(ScreeningContract.run_id == run.id, SourceRecord.source_id == SOURCE_ID)
            .order_by(SecopContract.contract_id)
        )
    ).all()
    contracts = []
    hashes = []
    invalid = False
    for stored, evidence in rows:
        # Reuse existing exact supplier attribution, including NIT document type and
        # explicit non-group supplier. Never trust a normalized flag in isolation.
        if (
            not company.nit
            or not supplier_matches(evidence.raw_payload, company.nit, company.verification_digit)
            or stored.contract_id != evidence.raw_payload.get("id_contrato")
        ):
            invalid = True
            continue
        contract = ContractView.model_validate(stored.normalized)
        if contract.evidence_id != stored.evidence_id or contract.contract_id != stored.contract_id:
            invalid = True
            continue
        # Identical evidence versions may predate this run; the successful run proves
        # they were observed again. Keep the underlying evidence timestamp unchanged.
        if run.completed_at:
            contract = contract.model_copy(update={"retrieved_at": run.completed_at})
        contract = contract.model_copy(update={"source_url": source_link(evidence.raw_payload)[0]})
        contracts.append(contract)
        hashes.append(evidence.payload_hash)
    expected = (run.summary or {}).get("total_contracts")
    complete = (
        not invalid
        and expected == len(contracts)
        and isinstance(run.query_metadata.get("source_rows"), int)
    )
    return contracts, hashes, complete


def cached_failure(previous: InvolvementView | None, failure: InvolvementView) -> InvolvementView:
    if previous is None:
        return failure
    result = previous.model_copy(deep=True)
    result.source["evaluation_is_stale"] = True
    result.source["is_stale"] = failure.source.get("is_stale", result.source.get("is_stale", False))
    result.source["last_evaluation_error"] = failure.diagnostics[-1]
    result.diagnostics = list(
        dict.fromkeys([*result.diagnostics, "previous_evaluation_retained", *failure.diagnostics])
    )
    return result


async def company_view(
    session: AsyncSession,
    company: Company,
    run_id: UUID | None,
    *,
    force: bool = False,
    lookback_months: int | None = None,
) -> InvolvementView:
    settings = get_settings()
    if run_id:
        run = await session.scalar(
            select(ScreeningRun).where(
                ScreeningRun.id == run_id,
                ScreeningRun.company_id == company.id,
                ScreeningRun.source_id == SOURCE_ID,
                ScreeningRun.canonical_nit == company.nit,
                ScreeningRun.query_metadata["verification_digit"].astext
                == company.verification_digit,
            )
        )
        if run is None:
            raise HTTPException(404, "Screening run not found for this company.")
        latest, _ = await secop.runs(session, company)
    else:
        latest, run = await secop.runs(session, company)
    result = InvolvementView(
        company_id=company.id,
        screening_run_id=run.id if run else None,
        status="blocked",
        engine={
            "provider": "Rainbird AI",
            "product": "Rae",
            "model_id": settings.rae_model_id,
            "model_version": settings.rae_model_version,
            "execution_mode": settings.rae_execution_mode,
            "reasoning_engine": settings.rae_engine,
            "model_reference_mode": settings.rae_model_reference_mode,
        },
        evaluation=context(lookback_months=lookback_months),
        source={
            "dataset": "SECOP II",
            "dataset_id": "jbjy-vk9h",
            "snapshot_completed_at": run.completed_at.isoformat()
            if run and run.completed_at
            else None,
        },
    )
    if not settings.rae_enabled or settings.rae_execution_mode != "live":
        result.status = "disabled"
        result.diagnostics = ["company_reasoning_disabled"]
        return result
    if not settings.rae_company_processing_authorized:
        result.diagnostics = ["real_company_processing_not_authorized"]
        return result
    if not (settings.rae_api_key and settings.rae_model_id):
        result.diagnostics = ["rae_not_configured"]
        return result
    if not company.nit or len(company.nit) != 9 or ":hash:" in company.identity_key:
        result.diagnostics = ["identity_unverified"]
        return result
    if run is None or run.status != "completed" or run.completed_at is None:
        result.diagnostics = ["source_snapshot_required"]
        return result
    if run.query_metadata.get("matching_policy") != MATCHING_POLICY:
        result.diagnostics = ["source_snapshot_requires_refresh"]
        return result
    now = datetime.now(UTC)
    stale = now - run.completed_at >= timedelta(hours=settings.secop_cache_hours) or bool(
        latest and latest.id != run.id and latest.status in ("completed", "failed")
    )
    result.source["is_stale"] = stale
    contracts, hashes, complete = await snapshot_contracts(session, company, run)
    # All admitted contracts passed SECOP's whole-version conflict exclusion policy.
    # These false flags describe that validation result, not absent upstream diagnostics.
    diagnostics = {
        c.contract_id: ContractDiagnostics(
            signature_conflict=False, execution_status_conflict=False, value_conflict=False
        )
        for c in contracts
    }
    facts, references, warnings = map_facts(
        contracts,
        as_of=result.evaluation.as_of_date,
        months=result.evaluation.lookback_months,
        complete=complete,
        stale=stale,
        identity_verified=True,
        exclusions=bool(run.query_metadata.get("excluded_rows_or_conflicts", 0)),
        diagnostics=diagnostics,
    )
    result.source["conflict_validation"] = "verified_snapshot_admission_v1"
    key = fingerprint(
        dict(
            company=str(company.id),
            run=str(run.id),
            facts=facts,
            evidence_hashes=hashes,
            references=references,
            model=settings.rae_model_id,
            version=settings.rae_model_version,
            reference_mode=settings.rae_model_reference_mode,
            engine=settings.rae_engine,
            base=settings.rae_api_base_url,
            policy=result.evaluation.policy_version,
            mode="live",
        )
    )
    result.engine["configuration_fingerprint"] = fingerprint(
        dict(
            model=settings.rae_model_id,
            version=settings.rae_model_version,
            reference_mode=settings.rae_model_reference_mode,
            engine=settings.rae_engine,
            base=settings.rae_api_base_url,
            policy=result.evaluation.policy_version,
            months=result.evaluation.lookback_months,
        )
    )
    result.input_fingerprint = key
    result.diagnostics = warnings
    query = (
        select(InvolvementEvaluation)
        .where(
            InvolvementEvaluation.company_id == company.id,
            InvolvementEvaluation.screening_run_id == run.id,
            InvolvementEvaluation.input_fingerprint == key,
        )
        .order_by(InvolvementEvaluation.created_at.desc(), InvolvementEvaluation.id.desc())
    )
    recent = await session.scalar(query.limit(1))
    successful = await session.scalar(
        query.where(InvolvementEvaluation.payload["status"].astext == "completed").limit(1)
    )
    if successful is None:
        successful = await session.scalar(
            select(InvolvementEvaluation)
            .where(
                InvolvementEvaluation.company_id == company.id,
                InvolvementEvaluation.screening_run_id == run.id,
                InvolvementEvaluation.payload["status"].astext == "completed",
                InvolvementEvaluation.payload["engine"]["configuration_fingerprint"].astext
                == result.engine["configuration_fingerprint"],
            )
            .order_by(InvolvementEvaluation.created_at.desc())
            .limit(1)
        )
    previous = InvolvementView.model_validate(successful.payload) if successful else None
    if not force and recent:
        age = now - recent.created_at
        if recent.payload.get("status") == "completed" and age < timedelta(
            hours=settings.rae_cache_hours
        ):
            return InvolvementView.model_validate(recent.payload)
        if recent.payload.get("status") == "failed" and age < timedelta(seconds=60):
            return cached_failure(previous, InvolvementView.model_validate(recent.payload))
    locked = await session.scalar(
        text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": "rae-company:" + str(company.id)},
    )
    if not locked:
        result.status = "running"
        return result
    # Recheck under the cross-process lock: another request may have just committed.
    under_lock = await session.scalar(query.limit(1))
    if not force and under_lock and under_lock.id != (recent.id if recent else None):
        payload = InvolvementView.model_validate(under_lock.payload)
        if payload.status == "completed":
            return payload
        if payload.status == "failed" and now - under_lock.created_at < timedelta(seconds=60):
            return cached_failure(previous, payload)
    if (
        force
        and recent
        and now - recent.created_at < timedelta(seconds=settings.refresh_min_interval_seconds)
    ):
        remaining = (
            settings.refresh_min_interval_seconds - (now - recent.created_at).total_seconds()
        )
        raise HTTPException(
            429,
            "Wait before refreshing reasoning again.",
            headers={"Retry-After": str(max(1, math.ceil(remaining)))},
        )
    try:
        async with asyncio.timeout(settings.rae_request_timeout_seconds):
            async with _inference_slots:
                async with httpx.AsyncClient() as http:
                    decisions, version = await RaeClient(settings, http).evaluate_company(facts)
        for decision in decisions:
            if any(alias not in references for alias in decision.supporting_aliases):
                raise RaeError("invalid_evidence_reference")
            decision.source_references = [
                references[alias] for alias in dict.fromkeys(decision.supporting_aliases)
            ]
            decision.supporting_contract_ids = [
                r["contract_id"] for r in decision.source_references
            ]
            decision.supporting_evidence_ids = [
                r["evidence_id"] for r in decision.source_references
            ]
        result.status = "completed"
        result.decisions = decisions
        result.engine["model_version"] = version
        result.source["evaluation_is_stale"] = False
    except (RaeError, TimeoutError) as exc:
        result.status = "failed"
        result.diagnostics = [*warnings, str(exc) if isinstance(exc, RaeError) else "timeout"]
    session.add(
        InvolvementEvaluation(
            company_id=company.id,
            screening_run_id=run.id,
            input_fingerprint=key,
            execution_mode="live",
            payload=result.model_dump(mode="json"),
        )
    )
    await session.commit()
    return cached_failure(previous, result) if result.status == "failed" else result


def demo() -> InvolvementView:
    """Fixed synthetic output: explicitly NOT native Rae reasoning or company findings."""
    decisions = []
    for dimension in DECISIONS:
        contract = (
            "SYNTHETIC-HISTORICAL"
            if dimension == "historical_participation"
            else "SYNTHETIC-RECENT"
        )
        decisions.append(
            Decision.model_validate(
                dict(
                    id=dimension,
                    outcome="reported"
                    if dimension == "currently_reported_execution"
                    else "documented",
                    evidence_status="sufficient",
                    supporting_contract_ids=[contract],
                    supporting_evidence_ids=["synthetic-observation"],
                    evidence_tree_id=f"demo-{dimension}",
                    evidence_tree=EvidenceNode(
                        id=f"demo-{dimension}",
                        kind="decision",
                        label=dimension,
                        children=[
                            EvidenceNode(
                                id="rule",
                                kind="rule",
                                label=f"rule_{dimension}",
                                children=[
                                    EvidenceNode(
                                        id="identity", kind="fact", label="verified_identity"
                                    ),
                                    EvidenceNode(id="contract", kind="fact", label=contract),
                                    EvidenceNode(
                                        id="observation", kind="source", label="synthetic_source"
                                    ),
                                ],
                            )
                        ],
                    ),
                    warnings=[],
                )
            )
        )
    return InvolvementView(
        status="demo",
        engine={
            "provider": "Rainbird AI",
            "product": "Rae",
            "model_id": "government_involvement_profile",
            "model_version": "synthetic-fixture-v1",
            "execution_mode": "demo",
        },
        evaluation=EvaluationContext(
            evaluated_at=datetime(2026, 11, 26, 15, tzinfo=UTC),
            as_of_date=date(2026, 11, 26),
            lookback_months=24,
            lookback_start_date=date(2024, 11, 26),
        ),
        decisions=decisions,
        source={
            "dataset": "Synthetic SECOP II example",
            "dataset_id": "jbjy-vk9h",
            "snapshot_completed_at": "2026-11-26T15:00:00Z",
            "is_stale": False,
        },
        diagnostics=["synthetic_not_rae_inference"],
    )
