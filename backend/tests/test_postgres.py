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
from app.models.entities import Company, CompanyAlias, SourceRecord
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


async def test_global_source_ranking_precedes_pagination_and_api_preserves_order(
    session, record, metadata
):
    """Execute the generated WHERE/ORDER BY on a simulated source in real PostgreSQL.

    PostgreSQL emulates SoQL's case(boolean,value,...) function and unaccent for
    these synthetic fixtures. Filtering, sorting and LIMIT/OFFSET execute in SQL,
    rather than returning a conveniently pre-sorted mock response.
    """
    import json

    await session.execute(
        text("""
        CREATE TEMP TABLE rues_ranking_fixture (
            upstream_id text PRIMARY KEY, razon_social text, nit text,
            digito_verificacion text, payload jsonb
        ) ON COMMIT PRESERVE ROWS
    """)
    )
    await session.execute(
        text("""
        CREATE FUNCTION pg_temp.source_unaccent(value text) RETURNS text
        LANGUAGE sql IMMUTABLE AS $$
            SELECT translate(value, 'ÁÉÍÓÚÜÑáéíóúüñ', 'AEIOUUNaeiouun')
        $$
    """)
    )
    for count in (2, 6):
        arguments = ", ".join(f"c{i} boolean, v{i} integer" for i in range(count))
        branches = " ".join(f"WHEN c{i} THEN v{i}" for i in range(count))
        await session.execute(
            text(
                f"CREATE FUNCTION pg_temp.source_case({arguments}) RETURNS integer "
                f"LANGUAGE sql IMMUTABLE AS $$ SELECT CASE {branches} ELSE NULL END $$"
            )
        )
    weak = [
        dict(record, upstream_id=f"row-{i:04}", razon_social=f"AAA {i:02} AZULU SAS")
        for i in range(24)
    ]
    strong_names = [
        "ZULU",
        "Z U L U",
        "ZULU NORTE",
        "ZULU SAS",
        "A ZULU SERVICIOS",
        "ZULUAGA SAS",
        "ZULU SAS",
    ]
    strong = [
        dict(record, upstream_id=f"row-{9000 + i}", razon_social=name)
        for i, name in enumerate(strong_names)
    ]
    dv_match = dict(
        record, upstream_id="row-9900", razon_social="OTHER SYNTHETIC SAS", digito_verificacion="9"
    )
    for row in [*weak, *strong, dv_match]:
        await session.execute(
            text(
                "INSERT INTO rues_ranking_fixture "
                "VALUES (:id, :name, :nit, :dv, CAST(:payload AS jsonb))"
            ),
            {
                "id": row["upstream_id"],
                "name": row["razon_social"],
                "nit": row["nit"],
                "dv": row["digito_verificacion"],
                "payload": json.dumps(row),
            },
        )
    await session.commit()
    offsets = []

    async def handler(request):
        if "/api/views/" in request.url.path:
            return httpx.Response(200, json=metadata)
        params = request.url.params
        offsets.append(int(params["$offset"]))
        assert params["$order"].startswith("case(")
        order = (
            params["$order"]
            .replace("case(", "pg_temp.source_case(")
            .replace("unaccent(", "pg_temp.source_unaccent(")
            .replace(":id", "upstream_id")
        )
        # All query fragments come from the real adapter, including escaped literals.
        rows = await session.scalars(
            text(
                f"SELECT payload FROM rues_ranking_fixture WHERE {params['$where']} "
                f"ORDER BY {order} LIMIT :limit OFFSET :offset"
            ),
            {"limit": int(params["$limit"]), "offset": int(params["$offset"])},
        )
        return httpx.Response(200, json=list(rows))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        source = RuesDataSource(SocrataClient(upstream, retries=0))

        async def override_session():
            yield session

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[adapter] = lambda: source
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                items = []
                for page in range(1, 12):
                    response = await client.get(
                        "/api/v1/companies", params={"q": "Zulu", "page_size": 3, "page": page}
                    )
                    assert response.status_code == 200, response.text
                    data = response.json()
                    assert data["ranking_scope"] == "all matching source records"
                    assert not data["stale"]
                    if page == 1:
                        assert [i["legal_name"] for i in data["items"]] == [
                            "ZULU",
                            "Z U L U",
                            "ZULU NORTE",
                        ]
                    items.extend(data["items"])
                    if not data["has_more"]:
                        break
                names = [i["legal_name"] for i in items]
                assert names[:7] == [
                    "ZULU",
                    "Z U L U",
                    "ZULU NORTE",
                    "ZULU SAS",
                    "ZULU SAS",
                    "A ZULU SERVICIOS",
                    "ZULUAGA SAS",
                ]
                assert names[7:] == [row["razon_social"] for row in weak]
                assert len({i["id"] for i in items}) == len(items) == 31
                assert offsets == list(range(0, 31, 3))
                for i, expected in zip(items[3:5], ("row-9003", "row-9006"), strict=True):
                    sources = (await client.get(f"/api/v1/companies/{i['id']}/sources")).json()
                    assert sources[0]["external_record_id"] == expected
                    assert "search_rank" not in sources[0]["fields"]
                response = await client.get(
                    "/api/v1/companies", params={"q": "000123456-9", "page_size": 2}
                )
                assert response.status_code == 200, response.text
                nit_items = response.json()["items"]
                assert nit_items[0]["legal_name"] == "OTHER SYNTHETIC SAS"
                assert nit_items[0]["match_type"] == "exact_nit"
                assert nit_items[1]["match_type"] == "unresolved"
                source.metadata = AsyncMock(
                    side_effect=SourceError("source_timeout", "Synthetic outage")
                )
                fallback = await client.get("/api/v1/companies", params={"q": "Zulu"})
                assert fallback.json()["stale"]
                assert fallback.json()["ranking_scope"] == "current cached page"
        finally:
            app.dependency_overrides.clear()


async def test_source_and_cached_calendar_validation_agree(session):
    from sqlalchemy import column

    from app.integrations.rues.filtering import valid_date as source_valid
    from app.services.cached_filters import valid_date as cached_valid

    await session.execute(text("CREATE TEMP TABLE filter_dates (fecha_matricula text)"))
    dates = [
        "20240229",
        "20000229",
        "24000229",
        "00010101",
        "19850319",
        "19000229",
        "21000229",
        "20230229",
        "20240431",
        "20240132",
        "20240015",
        "20241301",
        "20240100",
        "00000000",
        "0",
        "99991231",
        "00000101",
        "2024A201",
        "2024-02-01",
        "20240201 ",
        " 20240201",
        "",
        None,
    ]
    for value in dates:
        await session.execute(text("INSERT INTO filter_dates VALUES (:value)"), {"value": value})
    source = set(
        await session.scalars(
            text(
                f"SELECT fecha_matricula FROM filter_dates WHERE {source_valid('fecha_matricula')}"
            )
        )
    )
    cached = set(
        await session.scalars(
            select(column("fecha_matricula"))
            .select_from(text("filter_dates"))
            .where(cached_valid(column("fecha_matricula")))
        )
    )
    assert source == cached == set(dates[:5])


async def test_filtered_live_pages_and_cached_outage_use_same_source_constraints(
    session, record, metadata
):
    from app.integrations.rues.filtering import CIIU_FIELDS, CODE_FIELDS
    from app.models.entities import Company

    await ensure_source(session)
    rows = []
    for i in range(12):
        row = dict(
            record,
            upstream_id=f"filter-{i:02}",
            razon_social=f"TEST {i:02} SAS",
            codigo_estado_matricula="01",
            codigo_camara="04",
            codigo_organizacion_juridica="16",
            codigo_categoria_matricula="01",
            cod_ciiu_act_econ_pri="0011",
            cod_ciiu_act_econ_sec="6201",
            fecha_matricula="20240229",
            fecha_renovacion="20250101",
            ultimo_ano_renovado="2025",
        )
        if i < 6:
            row["codigo_estado_matricula"] = "03"
        if i == 6:
            row["fecha_matricula"] = "20230229"
        if i == 7:
            row["fecha_renovacion"] = "00000000"
        if i == 8:
            row["ultimo_ano_renovado"] = "9999"
        rows.append(row)
        await persist(session, row)
    await session.commit()
    fields = {
        "razon_social",
        "nit",
        "fecha_matricula",
        "fecha_renovacion",
        "ultimo_ano_renovado",
        *CODE_FIELDS.values(),
        *CIIU_FIELDS,
    }
    projection = ", ".join(f"raw_payload ->> '{f}' AS {f}" for f in sorted(fields))
    seen = []

    async def handler(request):
        if "/api/views/" in request.url.path:
            return httpx.Response(200, json=metadata)
        params = request.url.params
        seen.append(params)
        # Execute the real adapter WHERE before LIMIT/OFFSET on PostgreSQL JSONB.
        # All synthetic names have the same relevance tier; row ID is the stable tie-break.
        matches = await session.scalars(
            text(
                "WITH source AS (SELECT raw_payload AS payload, "
                "external_record_id AS upstream_id, "
                f"{projection} FROM source_records) "
                f"SELECT payload FROM source WHERE {params['$where']} ORDER BY upstream_id "
                "LIMIT :limit OFFSET :offset"
            ),
            {"limit": int(params["$limit"]), "offset": int(params["$offset"])},
        )
        return httpx.Response(200, json=list(matches))

    async def override_session():
        yield session

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as upstream:
        source = RuesDataSource(SocrataClient(upstream, retries=0))
        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[adapter] = lambda: source
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                filters = {
                    "q": "TEST",
                    "status": "01",
                    "chamber": "04",
                    "organization": "16",
                    "category": "01",
                    "ciiu": "62",
                    "ciiu_match": "prefix",
                    "ciiu_scope": "any",
                    "registration_from": "2000-01-01",
                    "registration_to": "2025-12-31",
                    "renewal_from": "2024-01-01",
                    "renewal_to": "2025-12-31",
                    "renewed_year": "2024",
                    "renewed_year_mode": "minimum",
                    "page_size": "2",
                }
                first = await client.get("/api/v1/companies", params={**filters, "page": "1"})
                assert first.status_code == 200, first.text
                data = first.json()
                assert [r["legal_name"] for r in data["items"]] == ["TEST 09 SAS", "TEST 10 SAS"]
                assert data["has_more"] and not data["stale"]
                provenance = await client.get(f"/api/v1/companies/{data['items'][0]['id']}/sources")
                public = provenance.json()[0]["fields"]
                assert public["codigo_estado_matricula"] == "01"
                assert public["codigo_categoria_matricula"] == "01"
                assert public["codigo_organizacion_juridica"] == "16"
                assert "representante_legal" not in public
                assert "num_identificacion_representante_legal" not in public
                second = await client.get("/api/v1/companies", params={**filters, "page": "2"})
                assert [r["legal_name"] for r in second.json()["items"]] == ["TEST 11 SAS"]
                assert not second.json()["has_more"]
                assert [p["$offset"] for p in seen] == ["0", "2"]
                assert all(p["$limit"] == "3" for p in seen)
                source.metadata = AsyncMock(
                    side_effect=SourceError("source_timeout", "Synthetic outage")
                )
                for page, expected in [(1, ["TEST 09 SAS", "TEST 10 SAS"]), (2, ["TEST 11 SAS"])]:
                    response = await client.get(
                        "/api/v1/companies", params={**filters, "page": str(page)}
                    )
                    assert response.status_code == 200, response.text
                    assert response.json()["stale"]
                    assert [r["legal_name"] for r in response.json()["items"]] == expected
                # A filtered outage must never return unfiltered cached records.
                response = await client.get("/api/v1/companies", params={**filters, "status": "02"})
                assert response.status_code == 503
                # Empty live responses may use normalized aliases, but still honor every filter.
                source.metadata = AsyncMock(return_value=metadata)
                source.search_by_name = AsyncMock(return_value=[])
                response = await client.get("/api/v1/companies", params=filters)
                assert response.status_code == 200 and response.json()["stale"]
                assert [r["legal_name"] for r in response.json()["items"]] == [
                    "TEST 09 SAS",
                    "TEST 10 SAS",
                ]
                assert await session.scalar(select(func.count()).select_from(Company)) == 12
        finally:
            app.dependency_overrides.clear()


async def test_capital_ingestion_idempotence_debt_only_and_api(
    session, record, tmp_path, monkeypatch
):
    from capital_fixtures import issuer_xlsx, security_html

    from app.core.config import get_settings
    from app.integrations.capital_markets.ingestion import ingest_issuers, ingest_securities
    from app.integrations.capital_markets.parsers import verification_digit
    from app.integrations.capital_markets.reports import securities_url
    from app.integrations.capital_markets.service import company_profile
    from app.integrations.capital_markets.types import MatchStatus
    from app.models.capital_markets import (
        CapitalMarketsSourceSnapshot,
        IssuerCompanyMatch,
        SecuritiesIssuer,
        SecurityInstrument,
    )

    monkeypatch.setattr(get_settings(), "capital_markets_storage_dir", tmp_path)
    await ensure_source(session)
    company = await persist(
        session, dict(record, digito_verificacion=verification_digit(record["nit"]))
    )
    await session.commit()
    for _ in range(2):
        await ingest_issuers(
            session,
            issuer_xlsx(),
            nit_mode="concatenated-dv",
            complete_current=True,
            expected_count=1,
        )
    issuer = await session.scalar(select(SecuritiesIssuer))
    assert issuer and issuer.company_id == company.id
    assert await session.scalar(select(func.count()).select_from(SecuritiesIssuer)) == 1
    assert (await session.scalar(select(IssuerCompanyMatch))).match_status == MatchStatus.VERIFIED
    assert company.legal_name == record["razon_social"]  # SFC never overwrites RUES identity.
    for _ in range(2):
        await ingest_securities(session, issuer, security_html(), securities_url("001", "001"))
    assert await session.scalar(select(func.count()).select_from(SecurityInstrument)) == 2
    assert await session.scalar(select(func.count()).select_from(CapitalMarketsSourceSnapshot)) == 4
    assert await session.scalar(select(func.count()).select_from(SourceRecord)) == 4
    profile = await company_profile(session, company)
    assert profile.rnve.status == "registered_active"
    assert profile.equity_listed is None and profile.exchange_listing.status == "unknown"
    assert profile.ownership.type == "unknown"
    assert "deuda" in profile.summary
    assert all(i.ticker is None and i.isin is None for i in profile.instruments)
    assert profile.instruments[0].ann_code

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/companies/{company.id}/capital-markets")
            assert response.status_code == 200, response.text
            assert response.json()["rnve"]["status"] == "registered_active"
            assert response.json()["equity_listed"] is None
            first = await client.get(
                f"/api/v1/companies/{company.id}/securities", params={"page_size": 1}
            )
            assert len(first.json()["items"]) == 1 and first.json()["has_more"]
            second = await client.get(
                f"/api/v1/companies/{company.id}/securities", params={"page_size": 1, "page": 2}
            )
            assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]
            assert not second.json()["has_more"]
            bonds = await client.get(
                f"/api/v1/companies/{company.id}/securities",
                params={"security_category": "corporate_bonds", "exchange": "BVC"},
            )
            assert len(bonds.json()["items"]) == 1
            listed = await client.get(
                f"/api/v1/companies/{company.id}/securities",
                params={"listing_status": "verified_listed"},
            )
            assert listed.json()["items"] == []
            issuers = await client.get(
                "/api/v1/capital-markets/issuers", params={"q": record["nit"]}
            )
            assert len(issuers.json()["items"]) == 1
            sources = await client.get("/api/v1/capital-markets/sources")
            assert len(sources.json()) == 3
            assert all(
                s["latest_snapshot"]["content_hash"] for s in sources.json() if s["latest_snapshot"]
            )
            assert "SYNTHETIC PRIVATE" not in response.text
            assert (
                await client.get(
                    f"/api/v1/companies/{company.id}/securities?security_category=invalid"
                )
            ).status_code == 422
    finally:
        app.dependency_overrides.clear()


async def test_capital_atomic_failure_history_and_ambiguous_registration(
    session, record, tmp_path, monkeypatch
):
    from capital_fixtures import SYNTHETIC_NIT, issuer_xlsx, security_html

    from app.core.config import get_settings
    from app.integrations.capital_markets import ingestion
    from app.integrations.capital_markets.parsers import verification_digit
    from app.integrations.capital_markets.service import company_profile
    from app.integrations.capital_markets.types import MatchStatus
    from app.models.capital_markets import (
        CapitalMarketsSourceSnapshot,
        IssuerCompanyMatch,
        SecuritiesIssuer,
        SecurityInstrument,
    )

    monkeypatch.setattr(get_settings(), "capital_markets_storage_dir", tmp_path)
    await ensure_source(session)
    original = await persist(
        session, dict(record, digito_verificacion=verification_digit(record["nit"]))
    )
    await session.commit()
    await ingestion.ingest_issuers(session, issuer_xlsx(), nit_mode="concatenated-dv")
    issuer = await session.scalar(select(SecuritiesIssuer))
    await ingestion.ingest_securities(
        session, issuer, security_html(), "https://www.superfinanciera.gov.co/report"
    )
    original_id, issuer_id = original.id, issuer.id
    original_raw = ingestion.raw_record

    async def fail_second(session, source, external_id, raw, url):
        if external_id == "001:002":
            raise ValueError("Synthetic failure after one upsert")
        return await original_raw(session, source, external_id, raw, url)

    monkeypatch.setattr(ingestion, "raw_record", fail_second)
    nit = SYNTHETIC_NIT + verification_digit(SYNTHETIC_NIT)
    with pytest.raises(ValueError):
        await ingestion.ingest_issuers(
            session,
            issuer_xlsx(
                [
                    ("SYNTHETIC CHANGED NAME", nit, "001", "001"),
                    ("SYNTHETIC SECOND", "0009999990", "001", "002"),
                ]
            ),
            nit_mode="concatenated-dv",
        )
    monkeypatch.setattr(ingestion, "raw_record", original_raw)
    issuer = await session.get(SecuritiesIssuer, issuer_id)
    original = await session.get(Company, original_id)
    assert issuer.issuer_name == "SYNTHETIC EMISOR SAS"
    assert await session.scalar(select(func.count()).select_from(SecuritiesIssuer)) == 1
    assert await session.scalar(select(func.count()).select_from(SecurityInstrument)) == 2
    assert (
        await session.scalar(
            select(func.count())
            .select_from(CapitalMarketsSourceSnapshot)
            .where(CapitalMarketsSourceSnapshot.ingestion_status == "failed")
        )
        == 1
    )
    assert (await company_profile(session, original)).stale
    # A later duplicate RUES registration with the same NIT invalidates automatic uniqueness.
    duplicate = await persist(
        session,
        dict(
            record,
            upstream_id="synthetic-duplicate-registration",
            digito_verificacion=verification_digit(record["nit"]),
        ),
    )
    await session.commit()
    duplicate_profile = await company_profile(session, duplicate)
    assert duplicate_profile.rnve.match_status == "potential"
    assert duplicate_profile.instruments == []
    original_profile = await company_profile(session, original)
    assert original_profile.rnve.match_status == "potential"
    assert all(
        m.match_status != MatchStatus.VERIFIED
        for m in await session.scalars(select(IssuerCompanyMatch))
    )


async def test_capital_negative_requires_complete_fresh_source_and_name_only_is_potential(
    session, record, tmp_path, monkeypatch
):
    from capital_fixtures import issuer_xlsx

    from app.core.config import get_settings
    from app.integrations.capital_markets.ingestion import ingest_issuers
    from app.integrations.capital_markets.service import company_profile
    from app.models.capital_markets import SecuritiesIssuer

    monkeypatch.setattr(get_settings(), "capital_markets_storage_dir", tmp_path)
    await ensure_source(session)
    company = await persist(session, dict(record, nit="000999999"))
    await session.commit()
    assert (await company_profile(session, company)).rnve.status == "unknown"
    await ingest_issuers(session, issuer_xlsx(), nit_mode="concatenated-dv")
    assert (await company_profile(session, company)).rnve.status == "unknown"
    await ingest_issuers(
        session, issuer_xlsx(), nit_mode="concatenated-dv", complete_current=True, expected_count=1
    )
    result = await company_profile(session, company)
    assert result.rnve.status == "not_found_in_checked_source"
    assert "no descarta registros históricos" in result.summary
    with pytest.raises(ValueError):
        await ingest_issuers(session, b"broken spreadsheet")
    result = await company_profile(session, company)
    assert result.rnve.status == "unknown" and result.stale
    # Source has no NIT: exact name may suggest a candidate, never a verified link.
    await ingest_issuers(
        session, issuer_xlsx([(company.legal_name, "", "001", "002")]), nit_mode="concatenated-dv"
    )
    result = await company_profile(session, company)
    assert result.rnve.match_status == "potential" and result.rnve.status == "unknown"
    assert result.instruments == []
    # Similar subsidiary name is not linked to its parent.
    parent = await persist(
        session,
        dict(
            record,
            upstream_id="synthetic-parent",
            razon_social="SYNTHETIC PARENT SAS",
            nit="000888888",
        ),
    )
    await session.commit()
    await ingest_issuers(
        session, issuer_xlsx([("SYNTHETIC PARENT SUBSIDIARY SAS", "", "001", "003")])
    )
    assert (await company_profile(session, parent)).issuers == []
    assert await session.scalar(select(func.count()).select_from(SecuritiesIssuer)) == 3


async def test_capital_status_history_and_stale_complete_snapshot(
    session, record, tmp_path, monkeypatch
):
    from datetime import UTC, datetime, timedelta

    from capital_fixtures import SYNTHETIC_NIT, issuer_xlsx

    from app.core.config import get_settings
    from app.integrations.capital_markets.ingestion import ingest_issuers
    from app.integrations.capital_markets.parsers import verification_digit
    from app.integrations.capital_markets.service import company_profile
    from app.integrations.capital_markets.types import ISSUER_SOURCE, RegistrationStatus
    from app.models.capital_markets import CapitalMarketsSourceSnapshot, SecuritiesIssuer

    monkeypatch.setattr(get_settings(), "capital_markets_storage_dir", tmp_path)
    await ensure_source(session)
    company = await persist(
        session, dict(record, digito_verificacion=verification_digit(record["nit"]))
    )
    await session.commit()
    first = await ingest_issuers(session, issuer_xlsx(), nit_mode="concatenated-dv")
    await ingest_issuers(
        session,
        issuer_xlsx(
            [
                (
                    "SYNTHETIC RENAMED ISSUER",
                    SYNTHETIC_NIT + verification_digit(SYNTHETIC_NIT),
                    "001",
                    "001",
                )
            ]
        ),
        nit_mode="concatenated-dv",
        registration_status=RegistrationStatus.CANCELLED,
    )
    assert (await company_profile(session, company)).rnve.status == "registered_cancelled"
    raw = list(
        await session.scalars(select(SourceRecord).where(SourceRecord.source_id == ISSUER_SOURCE))
    )
    assert {r.raw_payload["Nombre entidad"] for r in raw} == {
        "SYNTHETIC EMISOR SAS",
        "SYNTHETIC RENAMED ISSUER",
    }
    assert company.legal_name == record["razon_social"]
    await ingest_issuers(session, issuer_xlsx(), nit_mode="concatenated-dv")
    other = "000999999"
    newest = await ingest_issuers(
        session,
        issuer_xlsx([("SYNTHETIC OTHER", other + verification_digit(other), "001", "002")]),
        nit_mode="concatenated-dv",
        complete_current=True,
        expected_count=1,
    )
    assert (await company_profile(session, company)).rnve.status == "historical"
    assert await session.scalar(select(func.count()).select_from(SecuritiesIssuer)) == 2
    absent = await persist(session, dict(record, upstream_id="synthetic-absent", nit="000888888"))
    await session.commit()
    newest.details = {
        **newest.details,
        "observed_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
    }
    await session.commit()
    result = await company_profile(session, absent)
    assert result.rnve.status == "unknown" and result.stale
    assert await session.get(CapitalMarketsSourceSnapshot, first.id) is not None


async def test_capital_migration_preserves_existing_phase1_data(session, record, migrated):
    import asyncio

    from app.models.entities import Company

    await ensure_source(session)
    company = await persist(session, record)
    company_id = company.id
    await session.commit()
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    await asyncio.to_thread(command.downgrade, cfg, "a4e58b192f70")
    await asyncio.to_thread(command.upgrade, cfg, "head")
    await asyncio.to_thread(command.check, cfg)
    session.expire_all()
    preserved = await session.get(Company, company_id)
    assert preserved and preserved.nit == record["nit"]
    assert preserved.legal_name == record["razon_social"]


async def test_capital_name_collision_cannot_displace_verified_nit_or_turn_rejection_into_absence(
    session, record, tmp_path, monkeypatch
):
    from capital_fixtures import issuer_xlsx

    from app.core.config import get_settings
    from app.integrations.capital_markets.ingestion import ingest_issuers
    from app.integrations.capital_markets.parsers import verification_digit
    from app.integrations.capital_markets.service import company_profile
    from app.integrations.capital_markets.types import MatchStatus
    from app.models.capital_markets import IssuerCompanyMatch, SecuritiesIssuer

    monkeypatch.setattr(get_settings(), "capital_markets_storage_dir", tmp_path)
    await ensure_source(session)
    original = await persist(
        session, dict(record, digito_verificacion=verification_digit(record["nit"]))
    )
    await session.commit()
    await ingest_issuers(
        session, issuer_xlsx(), nit_mode="concatenated-dv", complete_current=True, expected_count=1
    )
    unrelated = await persist(
        session,
        dict(
            record,
            upstream_id="synthetic-name-collision",
            nit="000999999",
            razon_social="SYNTHETIC EMISOR SAS",
            digito_verificacion=verification_digit("000999999"),
        ),
    )
    await session.commit()
    assert (await company_profile(session, unrelated)).rnve.match_status == "potential"
    assert (await company_profile(session, original)).rnve.match_status == "verified"
    issuer = await session.scalar(select(SecuritiesIssuer))
    assert issuer.company_id == original.id
    # Simulate a changed regulatory identity before either company's next local reconciliation.
    issuer.nit = "000999999"
    issuer.verification_digit = verification_digit("000999999")
    await session.commit()
    assert (await company_profile(session, unrelated)).rnve.match_status == "verified"
    assert (await company_profile(session, original)).rnve.match_status == "potential"
    match = await session.scalar(
        select(IssuerCompanyMatch).where(IssuerCompanyMatch.company_id == unrelated.id)
    )
    match.match_status = MatchStatus.REJECTED
    await session.commit()
    result = await company_profile(session, unrelated)
    assert result.rnve.status == "unknown"  # A rejected identity is not a negative source lookup.
    assert match.match_status == MatchStatus.REJECTED


async def test_capital_securities_history_review_notes_and_failed_refresh(
    session, record, tmp_path, monkeypatch
):
    from capital_fixtures import issuer_xlsx, security_html

    from app.core.config import get_settings
    from app.integrations.capital_markets.ingestion import ingest_issuers, ingest_securities
    from app.integrations.capital_markets.parsers import verification_digit
    from app.integrations.capital_markets.service import company_profile
    from app.models.capital_markets import SecuritiesIssuer, SecurityInstrument

    monkeypatch.setattr(get_settings(), "capital_markets_storage_dir", tmp_path)
    await ensure_source(session)
    company = await persist(
        session, dict(record, digito_verificacion=verification_digit(record["nit"]))
    )
    await session.commit()
    await ingest_issuers(session, issuer_xlsx(), nit_mode="concatenated-dv")
    issuer = await session.scalar(select(SecuritiesIssuer))
    await ingest_securities(
        session, issuer, security_html(), "https://www.superfinanciera.gov.co/synthetic-report"
    )
    one = [
        [
            "BO SYNTHETIC BOND",
            "SYNTHETIC-ANN",
            "001",
            "AUT",
            "BVC",
            "N/A",
            "29/02/2024",
            "31/02/2024",
            "BAD AMOUNT",
            "COP",
            "AAA",
        ]
    ]
    await ingest_securities(
        session,
        issuer,
        security_html(rows=one),
        "https://www.superfinanciera.gov.co/synthetic-report",
    )
    result = await company_profile(session, company)
    assert len(result.instruments) == 2
    current = next(i for i in result.instruments if i.security_name == "BO SYNTHETIC BOND")
    old = next(i for i in result.instruments if i.security_name == "ACE SYNTHETIC DEBT")
    assert current.authorized_amount is None and current.bvc_registration_date is None
    assert len(current.quality_notes) == 2
    assert old.observation_status == "previously_observed" and old.stale
    issuer_id, company_id = issuer.id, company.id
    with pytest.raises(ValueError):
        await ingest_securities(
            session,
            issuer,
            b"<html>schema changed</html>",
            "https://www.superfinanciera.gov.co/synthetic-report",
        )
    company = await session.get(Company, company_id)
    result = await company_profile(session, company)
    assert result.securities_availability == "stale"
    assert all(i.stale for i in result.instruments)
    assert (
        await session.scalar(
            select(func.count())
            .select_from(SecurityInstrument)
            .where(SecurityInstrument.issuer_id == issuer_id)
        )
        == 2
    )


async def test_capital_security_rename_preserves_instrument_uuid_and_raw_name_history(
    session, tmp_path, monkeypatch
):
    from capital_fixtures import issuer_xlsx, security_html

    from app.core.config import get_settings
    from app.integrations.capital_markets.ingestion import ingest_issuers, ingest_securities
    from app.integrations.capital_markets.types import SECURITIES_SOURCE
    from app.models.capital_markets import SecuritiesIssuer, SecurityInstrument

    monkeypatch.setattr(get_settings(), "capital_markets_storage_dir", tmp_path)
    await ingest_issuers(session, issuer_xlsx(), nit_mode="concatenated-dv")
    issuer = await session.scalar(select(SecuritiesIssuer))
    await ingest_securities(
        session, issuer, security_html(), "https://www.superfinanciera.gov.co/synthetic-report"
    )
    before = {i.ann_code: i.id for i in await session.scalars(select(SecurityInstrument))}
    renamed = security_html().replace(b"BO SYNTHETIC BOND", b"BO SYNTHETIC RENAMED BOND")
    await ingest_securities(
        session, issuer, renamed, "https://www.superfinanciera.gov.co/synthetic-report"
    )
    after = {i.ann_code: i.id for i in await session.scalars(select(SecurityInstrument))}
    assert before == after and len(after) == 2
    names = {
        r.raw_payload["Nombre del título"]
        for r in await session.scalars(
            select(SourceRecord).where(SourceRecord.source_id == SECURITIES_SOURCE)
        )
    }
    assert "BO SYNTHETIC BOND" in names and "BO SYNTHETIC RENAMED BOND" in names
