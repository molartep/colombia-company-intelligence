import os
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.core.errors import SourceError
from app.db.session import get_session
from app.integrations.rues.adapter import RuesDataSource
from app.integrations.socrata import SocrataClient
from app.main import adapter, app
from app.models.entities import CompanyAlias, SourceRecord
from app.services.companies import ensure_source, persist

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def migrated():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set TEST_DATABASE_URL to a disposable PostgreSQL database to run persistence tests"
        )
    if not url.startswith("postgresql+asyncpg://"):
        pytest.fail("PostgreSQL asyncpg test URL required")
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    from app.core.config import get_settings

    get_settings.cache_clear()
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")
    # Verify full downgrade/re-upgrade, not just ORM create_all.
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    command.check(cfg)
    yield url
    if previous is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def session(migrated):
    engine = create_async_engine(migrated)
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE source_records, company_aliases, companies, data_sources CASCADE")
        )
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


async def test_duplicate_versions_and_relationships(session, record):
    await ensure_source(session)
    first = await persist(session, record)
    same = await persist(session, record)
    assert first.id == same.id
    assert await session.scalar(select(func.count()).select_from(SourceRecord)) == 1
    record["estado_matricula"] = "CANCELADA"
    await persist(session, record)
    assert await session.scalar(select(func.count()).select_from(SourceRecord)) == 2
    record["upstream_id"] = "row-synthetic-002"
    record["matricula"] = "TEST002"
    second = await persist(session, record)
    assert first.id != second.id  # Identical NIT is never a row key.
    assert await session.scalar(select(func.count()).select_from(CompanyAlias)) == 2
    assert (await session.scalars(select(SourceRecord.company_id))).all().count(first.id) == 2
    await session.commit()


async def test_end_to_end_and_pagination(session, record, metadata):
    rows = [dict(record, upstream_id=f"row-synthetic-{i}", matricula=f"TEST{i}") for i in range(3)]

    def handler(request):
        if "/api/views/" in request.url.path:
            return httpx.Response(200, json=metadata)
        start, limit = int(request.url.params["$offset"]), int(request.url.params["$limit"])
        return httpx.Response(200, json=rows[start : start + limit])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        source = RuesDataSource(SocrataClient(upstream))

        async def override_session():
            yield session

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[adapter] = lambda: source
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                assert (await client.get("/ready")).status_code == 200
                result = await client.get("/api/v1/companies?q=000123456&page_size=2")
                assert result.status_code == 200, result.text
                data = result.json()
                assert len(data["items"]) == 2 and data["has_more"]
                assert data["items"][0]["match_type"] == "exact_nit"
                assert data["items"][0]["chamber"] == "SYNTHETIC CHAMBER"
                assert data["items"][0]["registration_date"] == "20200115"
                assert data["items"][0]["renewal_date"] == "20250120"
                company_id = data["items"][0]["id"]
                profile = (await client.get(f"/api/v1/companies/{company_id}")).json()
                assert profile["primary_ciiu"] == "0011"
                assert profile["attributes"]["municipality"]["state"] == "unavailable_in_source"
                assert profile["attributes"]["securities_listing"]["state"] == "not_yet_checked"
                assert profile["conflicting_registration_count"] == 1
                records = (await client.get(f"/api/v1/companies/{company_id}/sources")).json()
                assert records[0]["fields"]["nit"] == "000123456"
                assert "representante_legal" not in records[0]["fields"]
                assert "num_identificacion_representante_legal" not in records[0]["fields"]
                assert (await client.get("/api/v1/sources")).json()[0][
                    "availability"
                ] == "available"
                page2 = (
                    await client.get("/api/v1/companies?q=000123456&page_size=2&page=2")
                ).json()
                assert len(page2["items"]) == 1 and not page2["has_more"]
                named = await client.get("/api/v1/companies?q=andina")
                assert named.json()["items"][0]["match_type"] == "partial_name"
                assert (
                    await client.get("/api/v1/companies/00000000-0000-0000-0000-000000000000")
                ).status_code == 404
                source.metadata = AsyncMock(
                    side_effect=SourceError("source_timeout", "Synthetic outage")
                )
                cached = (await client.get("/api/v1/companies?q=000123456")).json()
                assert cached["stale"] and cached["warning"]
                failed = await client.get("/api/v1/companies?q=999999999")
                assert (
                    failed.status_code == 503 and failed.json()["error"]["code"] == "source_timeout"
                )
        finally:
            app.dependency_overrides.clear()


async def test_empty_is_not_outage(session, metadata):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=metadata if "/api/views/" in r.url.path else [])
        )
    ) as http:
        from app.services.companies import search_companies

        data = await search_companies(
            session, RuesDataSource(SocrataClient(http)), "SYNTHETIC", None, 1, 20
        )
        assert data.items == [] and not data.stale


async def test_cached_name_variant_and_unstable_identity(session, record, metadata):
    from app.services.companies import search_companies

    await ensure_source(session)
    company = await persist(session, record)
    await session.commit()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=metadata if "/api/views/" in r.url.path else [])
        )
    ) as http:
        data = await search_companies(
            session,
            RuesDataSource(SocrataClient(http)),
            "compania sintetica andina sas",
            None,
            1,
            20,
        )
        assert data.stale and data.items[0].id == company.id
        assert data.items[0].match_type == "normalized_name"
    del record["upstream_id"]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json=metadata if "/api/views/" in r.url.path else [record]
            )
        )
    ) as http:
        data = await search_companies(
            session, RuesDataSource(SocrataClient(http)), "andina", None, 1, 20
        )
        assert data.items[0].match_type == "unresolved"


async def test_spacing_variants_live_cache_pagination_and_aliases(session, record, metadata):
    from app.services.companies import search_companies

    rows = [
        dict(record, upstream_id="row-synthetic-spacing-1", razon_social="TEST NORTE SAS"),
        dict(record, upstream_id="row-synthetic-spacing-2", razon_social="TESTNORTE SAS"),
    ]
    mode = "live"

    def handler(request):
        if "/api/views/" in request.url.path:
            if mode == "outage":
                return httpx.Response(503)
            return httpx.Response(200, json=metadata)
        assert (
            request.url.params["$where"]
            == "replace(upper(razon_social), ' ', '') like '%TESTNORTE%'"
        )
        start = int(request.url.params["$offset"])
        limit = int(request.url.params["$limit"])
        return httpx.Response(200, json=rows[start : start + limit] if mode == "live" else [])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        source = RuesDataSource(SocrataClient(http, retries=0))
        first = await search_companies(session, source, "testnorte", None, 1, 1)
        second = await search_companies(session, source, "test norte", None, 2, 1)
        assert first.has_more and not second.has_more
        assert first.items[0].id != second.items[0].id
        assert first.items[0].legal_name == "TEST NORTE SAS"
        assert first.items[0].match_type == "partial_name"
        assert "ignoring word spacing" in first.items[0].evidence[0]
        assert not first.stale and not second.stale
        mode = "empty"
        cached = await search_companies(session, source, "testnorte", None, 1, 20)
        assert cached.stale and len(cached.items) == 2
        assert {i.id for i in cached.items} == {first.items[0].id, second.items[0].id}
        # Earlier names remain searchable after the current legal name changes.
        await persist(session, dict(rows[0], razon_social="RENAMED SYNTHETIC SAS"))
        await session.commit()
        mode = "outage"
        cached = await search_companies(session, source, "testnorte", None, 1, 20)
        assert cached.stale and len(cached.items) == 2
        renamed = next(i for i in cached.items if i.id == first.items[0].id)
        assert renamed.legal_name == "RENAMED SYNTHETIC SAS"
        assert renamed.match_type == "unresolved"  # An alias is not the current legal name.


async def test_search_dates_use_latest_source_record_without_filling_missing_values(
    session, record, metadata
):
    from app.services.companies import search_companies

    row = dict(record)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json=metadata if "/api/views/" in r.url.path else [row])
        )
    ) as http:
        source = RuesDataSource(SocrataClient(http, retries=0))
        first = await search_companies(session, source, "SYNTHETIC", None, 1, 20)
        assert first.items[0].registration_date == "20200115"
        assert first.items[0].renewal_date == "20250120"
        row.pop("fecha_matricula")
        row["fecha_renovacion"] = ""
        row["ultimo_ano_renovado"] = "2025"  # Never substitute a renewal year for a date.
        latest = await search_companies(session, source, "SYNTHETIC", None, 1, 20)
        assert latest.items[0].id == first.items[0].id
        assert latest.items[0].registration_date is None
        assert latest.items[0].renewal_date is None
        source.metadata = AsyncMock(side_effect=SourceError("source_timeout", "Synthetic outage"))
        cached = await search_companies(session, source, "compania", None, 1, 20)
        assert cached.stale
        assert cached.items[0].registration_date is None
        assert cached.items[0].renewal_date is None
