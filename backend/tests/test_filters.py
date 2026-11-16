from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from app.db.session import get_session
from app.integrations.rues.adapter import RuesDataSource
from app.integrations.rues.filtering import filter_clauses
from app.integrations.rues.parameters import parameter_catalog
from app.integrations.socrata import SocrataClient
from app.main import app
from app.schemas.filters import SearchFilters
from app.schemas.parameters import ParameterCatalog


@pytest.mark.parametrize(
    "values",
    [
        {"status": ["ACTIVA"]},
        {"chamber": ["04' OR true"]},
        {"category": ["02"]},
        {"organization": ["99"]},
        {"ciiu": "1%"},
        {"ciiu": "001"},
        {"ciiu": "00001"},
        {"ciiu_match": "arbitrary"},
        {"ciiu_scope": "unknown"},
        {"registration_from": "2023-02-29"},
        {"renewal_to": "00000000"},
        {"registration_from": "2025-01-01", "registration_to": "2024-01-01"},
        {"renewal_from": "2025-01-01", "renewal_to": "2024-01-01"},
        {"renewal_to": "9999-12-31"},
        {"renewed_year": 9999},
        {"renewed_year_mode": "after"},
    ],
)
def test_reject_invalid_filters(values):
    with pytest.raises(ValidationError):
        SearchFilters.model_validate(values)


def test_preserve_source_codes_and_catalog_provenance():
    catalog = ParameterCatalog.model_validate(parameter_catalog())
    statuses = {o.value: o for g in catalog.groups if g.key == "status" for o in g.options}
    assert statuses["04"].label == "NO COMPETENCIA DE LA CAMARA"
    assert statuses["4"].label is None
    assert statuses["__missing__"].code is None
    assert statuses["07"].label != statuses["09"].label
    assert catalog.verified_at and catalog.source_url
    filters = SearchFilters(status=["4", "04", "4"], category=["00"])
    assert filters.status == ["04", "4"]
    assert "codigo_estado_matricula in ('04', '4')" in filter_clauses(filters)[0]
    assert not SearchFilters().active


async def test_compose_all_filters_before_source_pagination(record):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=[record])

    filters = SearchFilters(
        status=["01", "03", "__missing__"],
        chamber=["04"],
        organization=["16"],
        category=["01"],
        ciiu="62",
        ciiu_match="prefix",
        ciiu_scope="any",
        registration_from="2000-02-29",
        registration_to="2024-02-29",
        renewal_from="2024-01-01",
        renewal_to="2025-12-31",
        renewed_year=2024,
        renewed_year_mode="minimum",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        source = RuesDataSource(SocrataClient(http))
        await source.search_by_name("TEST", limit=21, offset=20, filters=filters)
        await source.search_by_nit("000123456", limit=21, offset=20, filters=filters)
    for request in requests:
        where = request.url.params["$where"]
        for clause in filter_clauses(filters):
            assert f"({clause})" in where
        assert " OR " in where and " AND " in where
        assert "ciiu4 like '62%'" in where
        assert "codigo_estado_matricula is null" in where
        assert request.url.params["$limit"] == "21"
        assert request.url.params["$offset"] == "20"
        assert request.url.params["$order"].endswith(":id ASC")


def test_exact_ciiu_primary_and_year():
    where = " AND ".join(filter_clauses(SearchFilters(ciiu="0011", renewed_year=2024)))
    assert "cod_ciiu_act_econ_pri = '0011'" in where
    assert "cod_ciiu_act_econ_sec" not in where
    assert "ultimo_ano_renovado = '2024'" in where
    assert "like '____'" in where


async def test_parameters_endpoint_is_offline_and_search_api_validates_filters():
    async def no_db():
        yield None

    app.dependency_overrides[get_session] = no_db
    app.state.rues = None
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/parameters")
            assert response.status_code == 200
            assert len(response.json()["groups"]) == 4
            assert "record_count" not in response.text
            assert "numero_identificacion" not in response.text
            for params in [
                {"status": "99"},
                {"ciiu": "0"},
                {"renewed_year": 9999},
                {"registration_from": "2025-01-02", "registration_to": "2025-01-01"},
                {"where": "true"},
            ]:
                response = await client.get("/api/v1/companies", params={"q": "TEST", **params})
                assert response.status_code == 422, response.text
            from unittest.mock import AsyncMock

            from app.schemas.api import SearchPage

            with patch("app.main.search_companies", new_callable=AsyncMock) as search:
                search.return_value = SearchPage(items=[], page=2, page_size=1, has_more=False)
                response = await client.get(
                    "/api/v1/companies",
                    params=[
                        ("q", "TEST"),
                        ("status", "01"),
                        ("status", "03"),
                        ("chamber", "04"),
                        ("page", "2"),
                        ("page_size", "1"),
                    ],
                )
                assert response.status_code == 200, response.text
                assert search.call_args.args[-1].status == ["01", "03"]
                assert search.call_args.args[-1].chamber == ["04"]
                assert search.call_args.args[4:6] == (2, 1)
    finally:
        app.dependency_overrides.clear()


async def test_nit_allowlist_is_bounded_and_applied_before_source_pagination(record):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=[record])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        source = RuesDataSource(SocrataClient(http))
        await source.search_by_name("SYNTHETIC", offset=20, nit_allowlist=["000123456"])
        await source.search_by_nit("000123456", nit_allowlist=["000123456"])
        assert await source.search_by_name("SYNTHETIC", nit_allowlist=[]) == []
        for invalid in [["1' OR true"], ["１２３"], ["123"] * 501]:
            with pytest.raises(ValueError):
                await source.search_by_name("SYNTHETIC", nit_allowlist=invalid)
    assert len(requests) == 2
    assert requests[0].url.params["$offset"] == "20"
    assert all("nit in ('000123456')" in r.url.params["$where"] for r in requests)
