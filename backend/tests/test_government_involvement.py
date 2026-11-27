"""Company lifecycle tests; all inference is mocked."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.integrations.rainbird.client import RaeError
from app.integrations.secop.adapter import MATCHING_POLICY
from app.schemas.government_involvement import Decision, EvidenceNode
from app.schemas.secop import ContractView
from app.services import government_involvement as service


@pytest.fixture
def setup(monkeypatch):
    settings = Settings(
        _env_file=None,
        rae_enabled=True,
        rae_execution_mode="live",
        rae_company_processing_authorized=True,
        rae_api_key="TEST-ONLY",
        rae_model_id="model",
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    company = SimpleNamespace(
        id=uuid4(), nit="000000001", verification_digit=None, identity_key="rues:row"
    )
    run = SimpleNamespace(
        id=uuid4(),
        company_id=company.id,
        status="completed",
        completed_at=datetime.now(UTC),
        query_metadata={"matching_policy": MATCHING_POLICY, "excluded_rows_or_conflicts": 0},
    )
    monkeypatch.setattr(service.secop, "runs", AsyncMock(return_value=(run, run)))
    contract = ContractView(
        contract_id="LOCAL-CONTRACT",
        original_supplier_identifier="000000001",
        normalized_supplier_identifier="000000001",
        supplier_document_type="NIT",
        source_identifier="row",
        status="in_execution",
        raw_status="En ejecución",
        signature_date=datetime.now(UTC).date(),
        retrieved_at=run.completed_at,
        evidence_id=uuid4(),
        source_url="https://www.datos.gov.co/d/jbjy-vk9h",
        source_link_label="Official",
    )
    snapshot = AsyncMock(return_value=([contract], ["immutable-hash"], True))
    monkeypatch.setattr(service, "snapshot_contracts", snapshot)
    decisions = [
        Decision(
            id=id,
            outcome="reported" if id == "currently_reported_execution" else "documented",
            evidence_status="sufficient",
            supporting_aliases=["contract_1"],
            evidence_tree=EvidenceNode(id="native", kind="rule", label="native rule"),
        )
        for id in service.DECISIONS
    ]
    inference = AsyncMock(return_value=(decisions, "native-version"))
    monkeypatch.setattr(service.RaeClient, "evaluate_company", inference)
    session = AsyncMock()
    session.add = lambda value: None
    return settings, company, run, contract, snapshot, inference, session


def records(session, recent=None, success=None, locked=True, under_lock=None):
    values = [recent, success]
    if success is None:
        values.append(None)
    values.extend([locked, under_lock])
    session.scalar.side_effect = values


async def test_live_minimized_facts_and_local_provenance(setup):
    _, company, run, contract, _, inference, session = setup
    records(session)
    stored = []
    session.add = stored.append
    result = await service.company_view(session, company, None)
    assert result.status == "completed" and result.screening_run_id == run.id
    assert result.engine["model_version"] == "native-version"
    assert all(d.supporting_contract_ids == ["LOCAL-CONTRACT"] for d in result.decisions)
    assert result.decisions[0].source_references[0]["evidence_id"] == str(contract.evidence_id)
    facts = inference.call_args.args[0]
    assert any(f["relationship"] == "signature_conflict" and f["object"] is False for f in facts)
    assert all(
        company.nit not in str(f) and "LOCAL-CONTRACT" not in str(f) and "https://" not in str(f)
        for f in facts
    )
    assert len(stored) == 1 and stored[0].screening_run_id == run.id
    session.commit.assert_awaited_once()


async def test_repeat_visits_use_cache(setup):
    _, company, _, _, _, inference, session = setup
    records(session)
    result = await service.company_view(session, company, None)
    inference.reset_mock()
    cached = SimpleNamespace(
        id=uuid4(), created_at=datetime.now(UTC), payload=result.model_dump(mode="json")
    )
    records(session, recent=cached, success=cached)
    second = await service.company_view(session, company, None)
    assert second.evaluation.evaluated_at == result.evaluation.evaluated_at
    inference.assert_not_awaited()


@pytest.mark.parametrize(
    "change,diagnostic",
    [
        ({"rae_company_processing_authorized": False}, "real_company_processing_not_authorized"),
        ({"rae_api_key": None}, "rae_not_configured"),
        ({"rae_enabled": False}, "company_reasoning_disabled"),
        ({"rae_execution_mode": "live_experimental"}, "company_reasoning_disabled"),
    ],
)
async def test_configuration_gates(setup, change, diagnostic):
    settings, company, _, _, _, inference, session = setup
    for key, value in change.items():
        setattr(settings, key, value)
    result = await service.company_view(session, company, None)
    assert result.diagnostics == [diagnostic] and not result.decisions
    inference.assert_not_awaited()


@pytest.mark.parametrize("status", ["failed", "running"])
async def test_unsuccessful_snapshot_never_becomes_negative(setup, status):
    _, company, run, _, _, inference, session = setup
    run.status = status
    result = await service.company_view(session, company, None)
    assert result.status == "blocked" and result.decisions == []
    assert result.diagnostics == ["source_snapshot_required"]
    inference.assert_not_awaited()


async def test_stale_source_and_exclusions_are_explicit_facts(setup):
    _, company, run, _, _, inference, session = setup
    run.completed_at -= timedelta(days=3)
    run.query_metadata["excluded_rows_or_conflicts"] = 1
    records(session)
    result = await service.company_view(session, company, None)
    facts = {
        f["relationship"]: f["object"]
        for f in inference.call_args.args[0]
        if f["subject"] == "evaluation"
    }
    assert facts["source_stale"] is True and facts["query_complete"] is False
    assert result.source["is_stale"] is True


async def test_outage_preserves_native_prior_findings(setup):
    _, company, _, _, _, inference, session = setup
    records(session)
    result = await service.company_view(session, company, None)
    previous = SimpleNamespace(
        id=uuid4(),
        created_at=datetime.now(UTC) - timedelta(days=2),
        payload=result.model_dump(mode="json"),
    )
    records(session, recent=previous, success=previous)
    inference.side_effect = RaeError("api_unavailable")
    retained = await service.company_view(session, company, None, force=True)
    assert retained.status == "completed" and retained.source["evaluation_is_stale"] is True
    assert "previous_evaluation_retained" in retained.diagnostics
    assert retained.evaluation.evaluated_at == result.evaluation.evaluated_at
    assert retained.decisions == result.decisions
    assert not result.source["evaluation_is_stale"]


async def test_first_failure_cooldown(setup):
    _, company, _, _, _, inference, session = setup
    records(session)
    inference.side_effect = RaeError("timeout")
    result = await service.company_view(session, company, None)
    assert result.status == "failed" and not result.decisions
    failed = SimpleNamespace(
        id=uuid4(), created_at=datetime.now(UTC), payload=result.model_dump(mode="json")
    )
    inference.reset_mock()
    records(session, recent=failed)
    second = await service.company_view(session, company, None)
    assert second.status == "failed"
    inference.assert_not_awaited()


async def test_concurrency_protection(setup):
    _, company, _, _, _, inference, session = setup
    records(session, locked=False)
    result = await service.company_view(session, company, None)
    assert result.status == "running"
    inference.assert_not_awaited()


async def test_unknown_witness_rejected(setup):
    _, company, _, _, _, inference, session = setup
    decisions, _ = inference.return_value
    decisions[0].supporting_aliases = ["contract_from_another_company"]
    records(session)
    result = await service.company_view(session, company, None)
    assert result.status == "failed" and not result.decisions
    assert "invalid_evidence_reference" in result.diagnostics


async def test_refresh_throttled(setup):
    _, company, _, _, _, inference, session = setup
    recent = SimpleNamespace(id=uuid4(), created_at=datetime.now(UTC), payload={"status": "failed"})
    records(session, recent=recent)
    with pytest.raises(HTTPException) as exc:
        await service.company_view(session, company, None, force=True)
    assert exc.value.status_code == 429
    inference.assert_not_awaited()


async def test_source_freshness_change_keeps_prior_findings_qualified_on_outage(setup):
    _, company, run, _, _, inference, session = setup
    records(session)
    original = await service.company_view(session, company, None)
    previous = SimpleNamespace(
        id=uuid4(), created_at=datetime.now(UTC), payload=original.model_dump(mode="json")
    )
    run.completed_at -= timedelta(days=3)
    # New input key has no result; find prior successful evaluation for the same run/configuration.
    session.scalar.side_effect = [None, None, previous, True, None]
    inference.side_effect = RaeError("api_unavailable")
    retained = await service.company_view(session, company, None)
    assert retained.source["is_stale"] is True
    assert retained.source["evaluation_is_stale"] is True
    assert retained.decisions == original.decisions


async def test_user_lookback_is_injected_and_invalidates_policy_cache(setup):
    _, company, _, _, _, inference, session = setup
    records(session)
    first = await service.company_view(session, company, None, lookback_months=1)
    records(session)
    second = await service.company_view(session, company, None, lookback_months=120)
    assert first.evaluation.lookback_months == 1 and second.evaluation.lookback_months == 120
    assert first.input_fingerprint != second.input_fingerprint
    facts = inference.call_args.args[0]
    assert any(f["relationship"] == "lookback_months" and f["object"] == 120 for f in facts)
    assert any(
        f["relationship"] == "lookback_start_date"
        and f["object"] == second.evaluation.lookback_start_date.isoformat()
        for f in facts
    )
