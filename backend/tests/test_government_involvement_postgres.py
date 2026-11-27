# ruff: noqa: F811
"""Real persistence/snapshot scope; vendor inference remains mocked."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from test_postgres import migrated, session  # noqa: F401
from test_secop import secop_row  # noqa: F401
from test_secop_postgres import company_and_source

from app.models.government_involvement import InvolvementEvaluation
from app.schemas.government_involvement import Decision, EvidenceNode
from app.services import government_involvement as service
from app.services import secop

pytestmark = pytest.mark.postgres


async def test_company_snapshot_evaluation_persists_and_caches(
    session, record, secop_row, monkeypatch
):
    company, source = await company_and_source(session, record, [secop_row])
    screening = await secop.refresh(session, company, source)
    settings = service.get_settings().model_copy(
        update={
            "rae_enabled": True,
            "rae_execution_mode": "live",
            "rae_company_processing_authorized": True,
            "rae_api_key": "TEST",
            "rae_model_id": "test-model",
        }
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    decisions = [
        Decision(
            id=id,
            outcome="reported" if id == "currently_reported_execution" else "documented",
            evidence_status="sufficient",
            supporting_aliases=["contract_1"],
            evidence_tree=EvidenceNode(id="native", kind="rule", label="native fact"),
        )
        for id in service.DECISIONS
    ]
    inference = AsyncMock(return_value=(decisions, "version"))
    monkeypatch.setattr(service.RaeClient, "evaluate_company", inference)
    result = await service.company_view(session, company, screening.run_id)
    assert result.status == "completed"
    assert result.screening_run_id == screening.run_id
    assert result.decisions[0].supporting_contract_ids == [secop_row["id_contrato"]]
    cached = await service.company_view(session, company, screening.run_id)
    assert cached.evaluation.evaluated_at == result.evaluation.evaluated_at
    assert inference.await_count == 1
    assert await session.scalar(select(func.count()).select_from(InvolvementEvaluation)) == 1
    # A model change invalidates the cache without changing official source evidence.
    settings.rae_model_id = "another-model"
    await service.company_view(session, company, screening.run_id)
    assert inference.await_count == 2
    second_record = dict(record, upstream_id="other-row", nit="000111222")
    other, _ = await company_and_source(session, second_record, [])
    with pytest.raises(HTTPException) as exc:
        await service.company_view(session, other, screening.run_id)
    assert exc.value.status_code == 404
