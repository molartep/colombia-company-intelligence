"""Read-only company availability and isolated synthetic demonstration.

Real-company external processing is intentionally blocked in every execution mode.
No Python evaluator runs in this service. Demo outputs are authored fixtures.
"""

from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.rainbird.mapper import DECISIONS, lookback_start
from app.integrations.secop.adapter import SOURCE_ID
from app.models.entities import Company
from app.models.secop import ScreeningRun
from app.schemas.government_involvement import (
    Decision,
    EvaluationContext,
    EvidenceNode,
    InvolvementView,
)
from app.services import secop


def context(as_of: date | None = None) -> EvaluationContext:
    today = as_of or datetime.now(ZoneInfo("America/Bogota")).date()
    months = get_settings().government_involvement_lookback_months
    return EvaluationContext(
        evaluated_at=datetime.now(UTC),
        as_of_date=today,
        lookback_months=months,
        lookback_start_date=lookback_start(today, months),
    )


async def company_view(
    session: AsyncSession,
    company: Company,
    run_id: UUID | None,
) -> InvolvementView:
    if run_id:
        run = await session.scalar(
            select(ScreeningRun).where(
                ScreeningRun.id == run_id,
                ScreeningRun.company_id == company.id,
                ScreeningRun.source_id == SOURCE_ID,
                ScreeningRun.canonical_nit == company.nit,
            )
        )
        if run is None:
            raise HTTPException(404, "Screening run not found for this company.")
    else:
        _, run = await secop.runs(session, company)
    settings = get_settings()
    return InvolvementView(
        company_id=company.id,
        screening_run_id=run.id if run else None,
        status="blocked" if settings.rae_enabled else "disabled",
        engine={
            "provider": "Rainbird AI",
            "product": "Rae",
            "model_id": settings.rae_model_id,
            "model_version": settings.rae_model_version,
            "execution_mode": "disabled",
        },
        evaluation=context(),
        diagnostics=["real_company_processing_not_authorized"],
        source={
            "dataset": "SECOP II",
            "dataset_id": "jbjy-vk9h",
            "snapshot_completed_at": run.completed_at.isoformat()
            if run and run.completed_at
            else None,
        },
    )


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
