# ruff: noqa: F811
"""Disposable PostgreSQL tests reuse the project's migration/rollback fixtures."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import func, select
from test_postgres import migrated, session  # noqa: F401
from test_secop import secop_row  # noqa: F401

from app.core.errors import SourceError
from app.db.session import get_session
from app.main import app
from app.models.entities import SourceRecord
from app.models.secop import ScreeningContract, ScreeningRun, SecopContract
from app.services import secop
from app.services.companies import ensure_source, persist, profile

pytestmark = pytest.mark.postgres


async def company_and_source(session, record, rows):
    await ensure_source(session)
    company = await persist(session, record)
    await session.commit()
    source = AsyncMock()
    source.fetch.return_value = (rows, datetime.now(UTC))
    return company, source


async def age_run(session, run_id):
    run = await session.get(ScreeningRun, run_id)
    run.started_at -= timedelta(minutes=2)
    await session.commit()


async def test_persistence_cache_idempotency_and_phase1(session, record, secop_row):
    company, source = await company_and_source(
        session, record, [secop_row, dict(secop_row, source_row_id="second")]
    )
    initial = await secop.view(session, company)
    assert initial.outcome == "not_screened" and initial.summary is None
    result = await secop.refresh(session, company, source)
    assert result.outcome == "completed_with_matches" and result.summary.total_contracts == 1
    cached = await secop.view(session, company)
    assert cached.run_id == result.run_id and source.fetch.await_count == 1
    assert (await profile(session, company)).registration["registration_number"] == record[
        "matricula"
    ]
    await age_run(session, result.run_id)
    await secop.refresh(session, company, source)
    assert await session.scalar(select(func.count()).select_from(SecopContract)) == 1
    assert await session.scalar(select(func.count()).select_from(ScreeningContract)) == 2
    assert (
        await session.scalar(select(func.count()).select_from(SourceRecord)) == 2
    )  # identity + SECOP


@pytest.mark.parametrize(
    "rows,expected", [([], "completed_no_matches"), (None, "source_unavailable")]
)
async def test_no_match_vs_failed_and_preserve_success(session, record, secop_row, rows, expected):
    company, source = await company_and_source(session, record, rows or [])
    if rows is None:
        source.fetch.side_effect = SourceError("source_timeout", "Synthetic")
    result = await secop.refresh(session, company, source)
    assert result.outcome == expected
    assert (result.summary.total_contracts == 0) if rows is not None else result.summary is None
    if rows is None:
        source.fetch.side_effect = None
        source.fetch.return_value = ([secop_row], datetime.now(UTC))
        await age_run(session, result.run_id)
        result = await secop.refresh(session, company, source)
    await age_run(session, result.run_id)
    source.fetch.side_effect = SourceError("source_timeout", "Synthetic")
    failed = await secop.refresh(session, company, source)
    assert failed.outcome == "stale" and failed.summary == result.summary
    assert failed.run_id == result.run_id and failed.error_code == "source_timeout"


async def test_api_pagination_filters_details_and_company_isolation(
    session, record, secop_row, monkeypatch
):
    rows = [
        dict(
            secop_row,
            source_row_id=f"row-{i}",
            id_contrato=f"CONTRACT-{i}",
            valor_del_contrato=str(i),
        )
        for i in range(12)
    ]
    company, source = await company_and_source(session, record, rows)
    other = await persist(
        session, dict(record, nit="999999999", upstream_id="other", matricula="OTHER")
    )
    await session.commit()

    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    monkeypatch.setattr(app.state, "secop", source, raising=False)
    base = f"/api/v1/companies/{company.id}/screening/secop"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(base + "/refresh")
            assert response.status_code == 200, response.text
            assert response.json()["summary"]["total_contracts"] == 12
            assert (await client.post(base + "/refresh")).status_code == 429
            first = (await client.get(base + "/contracts?sort=value&page_size=10")).json()
            assert first["has_more"] and first["items"][0]["contract_id"] == "CONTRACT-11"
            second = (await client.get(base + "/contracts?sort=value&page_size=10&page=2")).json()
            assert len(second["items"]) == 2 and not second["has_more"]
            assert (await client.get(base + "/contracts?year=2024")).json()["total"] == 0
            assert (await client.get(base + "/contracts?status=in_execution&q=CONTRACT")).json()[
                "total"
            ] == 12
            detail = await client.get(base + "/contracts/CONTRACT-11")
            assert detail.status_code == 200 and detail.json()["match_status"] == "verified"
            assert (
                await client.get(
                    f"/api/v1/companies/{other.id}/screening/secop/contracts/CONTRACT-11"
                )
            ).status_code == 404
            assert (await client.get(base + "/contracts?page_size=100")).status_code == 422
            assert (
                await client.post(base + "/refresh", headers={"Origin": "https://evil.test"})
            ).status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_duplicate_concurrent_refresh_and_atomic_rollback(
    session, record, secop_row, migrated
):
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    company, source = await company_and_source(session, record, [secop_row])
    started, release = asyncio.Event(), asyncio.Event()

    async def fetch(*args):
        started.set()
        await release.wait()
        return [secop_row], datetime.now(UTC)

    source.fetch.side_effect = fetch
    task = asyncio.create_task(secop.refresh(session, company, source))
    await started.wait()
    engine = create_async_engine(migrated)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as second:
            with pytest.raises(Exception) as exc:
                await secop.refresh(second, company, source)
            assert exc.value.status_code == 409
        release.set()
        await task
    finally:
        release.set()
        await engine.dispose()
    await age_run(session, (await secop.view(session, company)).run_id)
    source.fetch.side_effect = RuntimeError("synthetic unexpected internal failure")
    with pytest.raises(RuntimeError):
        await secop.refresh(session, company, source)
    await session.rollback()
    assert await session.scalar(select(func.count()).select_from(ScreeningRun)) == 1
    assert await session.scalar(select(func.count()).select_from(SecopContract)) == 1


async def test_stale_cache_and_missing_verified_identity(session, record, secop_row):
    from fastapi import HTTPException

    company, source = await company_and_source(session, record, [secop_row])
    result = await secop.refresh(session, company, source)
    run_id = result.run_id
    run = await session.get(ScreeningRun, run_id)
    run.completed_at = datetime.now(UTC) - timedelta(hours=25)
    await session.commit()
    stale = await secop.view(session, company)
    assert stale.outcome == "stale" and stale.summary.total_contracts == 1
    company.identity_key = "synthetic:hash:unresolved"
    await session.commit()
    assert (await secop.refresh(session, company, source)).outcome == "missing_nit"
    assert source.fetch.await_count == 1
    with pytest.raises(HTTPException) as exc:
        await secop.contracts_page(session, company, 1, 10, run_id=run_id)
    assert exc.value.status_code == 404


async def test_timeout_rolls_back_partial_evidence_but_records_failed_attempt(
    session, record, secop_row, monkeypatch
):
    company, source = await company_and_source(session, record, [secop_row])
    original = secop.persist_contracts

    async def interrupted(*args):
        await original(*args)
        raise TimeoutError()

    monkeypatch.setattr(secop, "persist_contracts", interrupted)
    result = await secop.refresh(session, company, source)
    assert result.outcome == "source_unavailable" and result.summary is None
    assert result.error_code == "source_timeout" and result.run_status == "failed"
    assert await session.scalar(select(func.count()).select_from(SecopContract)) == 0
    assert await session.scalar(select(func.count()).select_from(ScreeningContract)) == 0
    assert await session.scalar(select(func.count()).select_from(SourceRecord)) == 1
    assert await session.scalar(select(func.count()).select_from(ScreeningRun)) == 1


async def test_legacy_cached_currency_policy_recomputes_without_source_refresh(
    session, record, secop_row
):
    company, source = await company_and_source(session, record, [secop_row])
    result = await secop.refresh(session, company, source)
    run = await session.get(ScreeningRun, result.run_id)
    run.query_metadata = {k: v for k, v in run.query_metadata.items() if k != "currency_policy"}
    run.summary = {**run.summary, "total_values": {}, "monetary_contracts": 0}
    projection = await session.scalar(select(SecopContract))
    projection.normalized = {
        **projection.normalized,
        "currency": None,
        "currency_basis": "unspecified",
    }
    await session.commit()
    cached = await secop.view(session, company)
    assert cached.summary.total_values["COP"] == projection.value
    assert cached.summary.monetary_contracts == 1 and source.fetch.await_count == 1
    assert cached.last_successful_at == result.last_successful_at
    assert (await secop.contracts_page(session, company, 1, 10)).items[0].currency == "COP"


async def test_digit_matching_policy_stales_old_cache_and_refresh_adds_full_nit(
    session, record, secop_row
):
    from app.integrations.secop.adapter import MATCHING_POLICY

    company, source = await company_and_source(session, record, [secop_row])
    initial = await secop.refresh(session, company, source)
    run = await session.get(ScreeningRun, initial.run_id)
    run.query_metadata = {k: v for k, v in run.query_metadata.items() if k != "matching_policy"}
    run.warnings = ["Solo se consultan variantes explícitas del NIT; concatenados excluidos."]
    await session.commit()
    cached = await secop.view(session, company)
    assert cached.outcome == "stale" and cached.summary.total_contracts == 1
    assert any("diez dígitos" in w for w in cached.warnings)
    assert not any("concatenados excluidos" in w for w in cached.warnings)
    await age_run(session, initial.run_id)
    source.fetch.return_value = (
        [
            secop_row,
            dict(
                secop_row,
                id_contrato="TEN-DIGITS",
                source_row_id="row-2",
                documento_proveedor=record["nit"] + record["digito_verificacion"],
            ),
        ],
        datetime.now(UTC),
    )
    refreshed = await secop.refresh(session, company, source)
    assert refreshed.outcome == "completed_with_matches" and refreshed.summary.total_contracts == 2
    assert refreshed.query_metadata["matching_policy"] == MATCHING_POLICY
    page = await secop.contracts_page(session, company, 1, 10)
    assert {c.normalized_supplier_identifier for c in page.items} == {record["nit"]}


async def test_raw_status_groups_rebuild_old_cache_and_filter_each_status(
    session, record, secop_row
):
    from app.integrations.secop.normalize import SUMMARY_POLICY

    names = ["Aprobado", "En aprobación", "Enviado proveedor", None]
    rows = [
        dict(secop_row, id_contrato=f"CONTRACT-{i}", source_row_id=f"row-{i}", estado_contrato=name)
        for i, name in enumerate(names)
    ]
    company, source = await company_and_source(session, record, rows)
    first = await secop.refresh(session, company, source)
    run = await session.get(ScreeningRun, first.run_id)
    run.query_metadata = {k: v for k, v in run.query_metadata.items() if k != "summary_policy"}
    run.summary = {**run.summary, "statuses": [{"label": "other", "count": 4, "values": {}}]}
    await session.commit()
    cached = await secop.view(session, company)
    assert {g.label: g.count for g in cached.summary.statuses} == {
        "Aprobado": 1,
        "En aprobación": 1,
        "Enviado proveedor": 1,
        "No informado": 1,
    }
    assert cached.last_successful_at == first.last_successful_at and source.fetch.await_count == 1
    assert cached.query_metadata["summary_policy"] == SUMMARY_POLICY
    for name in names:
        page = await secop.contracts_page(session, company, 1, 5, raw_status=name or "No informado")
        assert page.total == 1 and page.items[0].raw_status == name
