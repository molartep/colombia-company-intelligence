import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from rainbird_reference import evaluate

from app.core.config import Settings
from app.integrations.rainbird.client import RaeClient, RaeError, normalize_evidence
from app.integrations.rainbird.mapper import (
    DECISIONS,
    ContractDiagnostics,
    fingerprint,
    lookback_start,
    map_facts,
)
from app.schemas.secop import ContractView
from app.services.government_involvement import company_view, demo

SCENARIOS = json.loads((Path(__file__).parent / "fixtures/rainbird/scenarios.json").read_text())


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s["id"])
def test_explicit_truth_table(scenario):
    assert evaluate(scenario) == scenario["expected"]
    assert len(scenario["expected"]["outcomes"]) == len(DECISIONS)
    assert len(scenario["expected"]["sufficiency"]) == len(DECISIONS)


@pytest.mark.parametrize(
    "value,months,expected",
    [
        ("2026-11-26", 24, "2024-11-26"),
        ("2024-02-29", 12, "2023-02-28"),
        ("2026-03-31", 1, "2026-02-28"),
        ("2024-03-31", 1, "2024-02-29"),
    ],
)
def test_calendar_boundaries(value, months, expected):
    assert lookback_start(date.fromisoformat(value), months).isoformat() == expected


def test_mapper_minimizes_and_preserves():
    c = ContractView(
        contract_id="local-contract",
        original_supplier_identifier="PRIVATE-NIT",
        normalized_supplier_identifier="PRIVATE-NIT",
        supplier_document_type="NIT",
        source_identifier="private-row",
        status="in_execution",
        raw_status="En ejecución",
        source_url="https://www.datos.gov.co/d/jbjy-vk9h",
        source_link_label="official",
        retrieved_at=datetime(2026, 11, 26, tzinfo=UTC),
        evidence_id=uuid4(),
        signature_date=date(2024, 11, 26),
        end_date=date(2025, 1, 1),
        description="PRIVATE-TEXT",
    )
    before = c.model_dump_json()
    facts, refs, warnings = map_facts(
        [c, c],
        as_of=date(2026, 11, 26),
        months=24,
        complete=True,
        stale=False,
        identity_verified=True,
    )
    payload = json.dumps(facts)
    assert (
        "PRIVATE" not in payload and "https://" not in payload and "local-contract" not in payload
    )
    assert any(f["relationship"] == "signature_band" and f["object"] == "recent" for f in facts)
    assert len(refs) == 1 and warnings == ["execution_past_scheduled_end"]
    assert c.model_dump_json() == before
    assert not any(f["relationship"] in DECISIONS for f in facts)


def test_native_evidence_expression_and_missing():
    tree = normalize_evidence(
        {
            "factID": "root",
            "source": "rule",
            "rule": {
                "conditions": [
                    {"factID": "a", "evidenceError": "absent"},
                    {
                        "expression": {
                            "functions": {"count": {"facts": [{"factID": "b", "repeated": True}]}}
                        }
                    },
                ]
            },
        }
    )
    assert tree.kind == "rule"
    assert tree.children[0].kind == "unresolved"
    assert tree.children[1].id == "b"
    with pytest.raises(RaeError):
        normalize_evidence({"fact": {}})


def test_fingerprint_invalidation():
    base = dict(
        run="a", evidence=["v1"], model="m", version=1, policy="v1", as_of="2026-11-26", months=24
    )
    for key in base:
        assert fingerprint(base) != fingerprint({**base, key: "changed"})


def settings(**kwargs):
    return Settings(
        _env_file=None,
        rae_enabled=True,
        rae_execution_mode="live_experimental",
        rae_api_key="SECRET",
        rae_evidence_key="EVIDENCE",
        rae_model_id="test-model",
        rae_model_version=1,
        rae_model_reference_mode="version",
        **kwargs,
    )


async def test_documented_session_contract():
    calls = []

    def handler(request):
        calls.append(request)
        path = request.url.path
        if path.startswith("/start/"):
            assert request.headers["X-API-Key"] == "SECRET"
            assert request.url.params["version"] == "1"
            return httpx.Response(200, json={"id": "session", "kmVersion": {"id": "immutable"}})
        if path.endswith("/inject"):
            return httpx.Response(200, json={"result": "OK"})
        if path.endswith("/query"):
            query = json.loads(request.content)
            relation = query["relationship"]
            if relation == "common_diagnostic" or relation.endswith("_diagnostics"):
                return httpx.Response(200, json={"result": []})
            outcome = (
                "sufficient"
                if relation.endswith("_sufficiency")
                else "reported"
                if relation == "currently_reported_execution"
                else "documented"
            )
            return httpx.Response(
                200,
                json={
                    "sid": "session",
                    "result": [
                        {
                            "subject": "evaluation",
                            "relationship": relation,
                            "object": outcome,
                            "certainty": 100,
                            "factID": "WA:RF:" + relation,
                        }
                    ],
                },
            )
        assert request.headers["x-evidence-key"] == "EVIDENCE"
        return httpx.Response(
            200, json={"factID": path.split("/")[-2], "source": "rule", "rule": {"conditions": []}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        decisions, version = await RaeClient(settings(), http).evaluate_synthetic([])
    assert version == "immutable" and len(decisions) == 4 and len(calls) == 22
    assert all(d.evidence_tree is not None for d in decisions)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "invalid_credentials"),
        (403, "access_denied"),
        (404, "model_not_found"),
        (429, "rate_limited"),
        (500, "api_unavailable"),
    ],
)
async def test_safe_failures(status, code):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, json={"secret": "private"}))
    ) as http:
        with pytest.raises(RaeError, match=code):
            await RaeClient(settings(), http).evaluate_synthetic([])


async def test_disabled_no_calls_and_fixed_hosts():
    with pytest.raises(ValueError):
        Settings(_env_file=None, rae_api_base_url="https://evil.invalid")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: pytest.fail("No calls permitted"))
    ) as http:
        with pytest.raises(RaeError, match="not_configured"):
            await RaeClient(Settings(_env_file=None), http).evaluate_synthetic([])


async def test_company_scope():
    session = AsyncMock()
    session.scalar.return_value = None
    company = type("Company", (), {"id": uuid4(), "nit": "000000001", "verification_digit": None})()
    with pytest.raises(HTTPException) as exc:
        await company_view(session, company, uuid4())
    assert exc.value.status_code == 404


def test_demo_is_unambiguously_synthetic():
    output = demo()
    assert output.company_id is None and output.screening_run_id is None
    assert output.status == "demo" and output.engine["execution_mode"] == "demo"
    assert output.diagnostics == ["synthetic_not_rae_inference"]


@pytest.mark.parametrize("payload", [[], {}, {"id": "s", "kmVersion": {}}, {"id": None}])
async def test_incompatible_start(payload):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    ) as http:
        with pytest.raises(RaeError):
            await RaeClient(settings(), http).evaluate_synthetic([])


async def test_timeout_sanitized():
    def handler(request):
        raise httpx.ReadTimeout("private input", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(RaeError, match="^timeout$"):
            await RaeClient(settings(), http).evaluate_synthetic([])


@pytest.mark.parametrize("outcome", ["risk_high", "corruption", None, 100])
async def test_unexpected_decision_rejected(outcome):
    def handler(request):
        if request.url.path.startswith("/start/"):
            return httpx.Response(200, json={"id": "s", "kmVersion": {"id": "v"}})
        return httpx.Response(
            200,
            json={
                "sid": "s",
                "result": [
                    {
                        "subject": "evaluation",
                        "relationship": "direct_participation",
                        "object": outcome,
                        "certainty": 100,
                        "factID": "f",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(RaeError):
            await RaeClient(settings(), http).evaluate_synthetic([])


def rbx_settings(**kwargs):
    return Settings(
        _env_file=None,
        rae_enabled=True,
        rae_execution_mode="live_experimental",
        rae_api_base_url="https://enterprise-api.rainbird.ai",
        rae_api_key="PRIVATE",
        rae_model_id="738e8674-b78f-4eee-9ad7-c7d13dfa7221",
        **kwargs,
    )


def rbx_handler(request):
    assert request.headers["x-rainbird-engine"] == "rbx"
    assert request.headers["X-API-Key"] == "PRIVATE"
    path = request.url.path
    if path.startswith("/start/"):
        assert "version" not in request.url.params and "useDraft" not in request.url.params
        return httpx.Response(200, json={"id": "rbx-session"})
    if path.endswith("/inject"):
        return httpx.Response(200, json={"result": "OK"})
    if path.endswith("/query"):
        relation = json.loads(request.content)["relationship"]
        value = (
            "source_observation_missing"
            if relation == "common_diagnostic"
            else "signature_date_missing"
            if relation.endswith("_diagnostics")
            else "sufficient"
            if relation.endswith("_sufficiency")
            else "reported"
            if relation == "currently_reported_execution"
            else "documented"
        )
        return httpx.Response(
            200,
            json={
                "result": [
                    {
                        "subject": "evaluation",
                        "relationshipType": relation,
                        "object": value,
                        "factID": "WA:RF:" + relation,
                        "certainty": 100,
                    }
                ]
            },
        )
    assert path.startswith("/analysis/evidence/")
    return httpx.Response(
        200, json={"factID": path.split("/")[-2], "source": "rule", "rule": {"conditions": []}}
    )


async def test_published_rbx_build_without_legacy_metadata_or_sid():
    async with httpx.AsyncClient(transport=httpx.MockTransport(rbx_handler)) as http:
        decisions, version = await RaeClient(rbx_settings(), http).evaluate_synthetic([])
    assert version == "published-build:738e8674-b78f-4eee-9ad7-c7d13dfa7221"
    assert len(decisions) == 4
    assert all(len(d.native_diagnostics) == 2 for d in decisions)
    assert all(d.evidence_tree and not d.warnings for d in decisions)
    assert decisions[0].native_diagnostics[0]["object"] == "source_observation_missing"


async def test_returned_wrong_session_rejected():
    def handler(request):
        response = rbx_handler(request)
        if request.url.path.endswith("/query"):
            return httpx.Response(200, json={**response.json(), "sid": "another-session"})
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(RaeError, match="invalid_session"):
            await RaeClient(rbx_settings(), http).evaluate_synthetic([])


async def test_missing_facts_questions_never_answered_with_guesses():
    def handler(request):
        if request.url.path.endswith("/query"):
            return httpx.Response(200, json={"question": {"relationship": "identity_verified"}})
        return rbx_handler(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(RaeError, match="unresolved_question"):
            await RaeClient(rbx_settings(), http).evaluate_synthetic([])


@pytest.mark.parametrize("failure", [400, 413])
async def test_evidence_single_fact_fallback_expands_cycles_and_missing(failure):
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.params.get("full"):
            return httpx.Response(failure)
        fact_id = request.url.path.split("/")[-2]
        if fact_id == "WA:RF:root":
            return httpx.Response(
                200,
                json={
                    "factID": fact_id,
                    "source": "rule",
                    "rule": {
                        "conditions": [
                            {"factID": "WA:RF:child"},
                            {
                                "expression": {
                                    "functions": {"count": {"facts": [{"factID": "WA:KF:missing"}]}}
                                }
                            },
                        ]
                    },
                },
            )
        if fact_id == "WA:RF:child":
            return httpx.Response(
                200,
                json={
                    "factID": fact_id,
                    "source": "rule",
                    "rule": {"conditions": [{"factID": "WA:RF:root"}]},
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        raw = await RaeClient(rbx_settings(), http)._evidence("WA:RF:root", "session", {})
    tree = normalize_evidence(raw)
    assert tree.children[0].children[0].id == "WA:RF:root"
    assert tree.children[1].kind == "unresolved"
    assert len(calls) == 4
    # Retained native JSON is serializable even when references cycle.
    json.dumps(raw)


async def test_non_inferred_answer_has_no_fabricated_tree():
    def handler(request):
        response = rbx_handler(request)
        if request.url.path.endswith("/query"):
            data = response.json()
            for fact in data["result"]:
                fact["factID"] = "WA:KF:injected"
            return httpx.Response(200, json=data)
        assert not request.url.path.startswith("/analysis/evidence/")
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        decisions, _ = await RaeClient(rbx_settings(), http).evaluate_synthetic([])
    assert all(
        d.evidence_tree is None and d.warnings == ["native_evidence_not_available"]
        for d in decisions
    )


def test_boolean_and_conflict_mapping_never_defaults_unknown_to_false():
    c = ContractView(
        contract_id="synthetic",
        original_supplier_identifier="000000001",
        normalized_supplier_identifier="000000001",
        supplier_document_type="NIT",
        source_identifier="synthetic",
        status="in_execution",
        raw_status="En ejecución",
        source_url="https://www.datos.gov.co/d/jbjy-vk9h",
        source_link_label="Synthetic",
        retrieved_at=datetime(2026, 11, 26, tzinfo=UTC),
        evidence_id=uuid4(),
        signature_date=date(2026, 5, 14),
        end_date=date(2027, 5, 14),
    )
    options = dict(
        as_of=date(2026, 11, 26), months=24, complete=True, stale=False, identity_verified=True
    )
    unknown, _, _ = map_facts([c], **options)
    assert not any(f["relationship"].endswith("_conflict") for f in unknown)
    known, _, _ = map_facts(
        [c],
        **options,
        diagnostics={
            "synthetic": ContractDiagnostics(
                signature_conflict=False, execution_status_conflict=True, value_conflict=False
            )
        },
    )
    values = {f["relationship"]: f["object"] for f in known}
    assert values["identity_verified"] is True and values["source_stale"] is False
    assert values["signature_conflict"] is False and values["execution_status_conflict"] is True
    assert values["observation_available"] is True
    assert values["scheduled_end_date"] == "2027-05-14"
    with pytest.raises(ValueError):
        ContractDiagnostics(signature_conflict="false")


async def test_terminal_overrides_never_transmitted():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: pytest.fail("No calls"))
    ) as http:
        with pytest.raises(RaeError, match="derived_input_forbidden"):
            await RaeClient(rbx_settings(), http).evaluate_synthetic(
                [
                    {
                        "subject": "evaluation",
                        "relationship": "recent_participation",
                        "object": "documented",
                        "certainty": 100,
                    }
                ]
            )


async def test_company_inference_requires_explicit_live_authorization():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: pytest.fail("No calls"))
    ) as http:
        with pytest.raises(RaeError, match="company_processing_not_authorized"):
            await RaeClient(rbx_settings(), http).evaluate_company([])


async def test_authorized_company_results_include_native_witness_aliases():
    settings = Settings(
        _env_file=None,
        rae_enabled=True,
        rae_execution_mode="live",
        rae_company_processing_authorized=True,
        rae_api_base_url="https://enterprise-api.rainbird.ai",
        rae_api_key="PRIVATE",
        rae_model_id="738e8674-b78f-4eee-9ad7-c7d13dfa7221",
    )

    def handler(request):
        if request.url.path.endswith("/query"):
            relation = json.loads(request.content)["relationship"]
            if relation in (
                "eligible_contract",
                "historical_witness",
                "recent_witness",
                "execution_witness",
            ):
                return httpx.Response(
                    200,
                    json={
                        "result": [
                            {
                                "subject": "evaluation",
                                "relationship": relation,
                                "object": "contract_1",
                                "factID": "WA:RF:witness",
                                "certainty": 100,
                            }
                        ]
                    },
                )
        return rbx_handler(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        decisions, _ = await RaeClient(settings, http).evaluate_company([])
    assert all(d.supporting_aliases == ["contract_1"] for d in decisions)
