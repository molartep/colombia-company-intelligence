import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal, cast
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from app.api.exports import router as exports_router
from app.api.operations import IMPORT_PATH, authorize_import
from app.api.operations import router as operations_router
from app.core.config import get_settings
from app.core.errors import DatabaseUnavailable, SourceError
from app.core.logging import configure_logging
from app.core.normalization import InvalidIdentifier, looks_like_nit, normalize_name, normalize_nit
from app.core.rate_limits import RequestLimiter
from app.db.session import engine, get_session

# Issuer summaries and securities reports refresh into snapshots on Capital Markets access.
from app.integrations.capital_markets import service as capital
from app.integrations.capital_markets.bvc import BvcPublicPages
from app.integrations.capital_markets.parsers import MAX_BYTES
from app.integrations.capital_markets.reports import OfficialReports
from app.integrations.capital_markets.secondary_quotes import LaRepublicaPublicPages
from app.integrations.capital_markets.sfc_quotes import SfcQuotePages
from app.integrations.capital_markets.summary_renderer import RnveSummaryRenderer
from app.integrations.capital_markets.types import ListingStatus, MatchStatus, SecurityCategory
from app.integrations.rues.adapter import RuesDataSource
from app.integrations.rues.parameters import parameter_catalog
from app.integrations.secop.adapter import SecopSource
from app.integrations.socrata import SocrataClient
from app.models.entities import Company, DataSource
from app.schemas.api import ErrorResponse, Profile, RecordView, SearchPage, SourceView
from app.schemas.capital_markets import (
    CapitalMarketsProfile,
    IssuerPage,
    MarketSourceView,
    SecuritiesPage,
)
from app.schemas.filters import CompanySearchRequest, SearchFilters
from app.schemas.parameters import ParameterCatalog
from app.schemas.secop import ContractPage, ContractStatus, ContractView, ScreeningView
from app.services import secop
from app.services.companies import (
    ensure_source,
    profile,
    records_for,
    refresh_registration,
    search_companies,
    serialize_record,
)
from app.services.currency import Rate, ReferenceRates

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    headers = {"X-App-Token": settings.socrata_app_token} if settings.socrata_app_token else {}
    async with httpx.AsyncClient(
        timeout=settings.socrata_timeout,
        headers=headers,
        limits=httpx.Limits(max_connections=settings.upstream_concurrency),
        follow_redirects=False,
    ) as client:
        app.state.reference_rates = ReferenceRates(SocrataClient(client, retries=0))
        app.state.rues = RuesDataSource(
            SocrataClient(client, settings.socrata_retries, settings.upstream_concurrency)
        )
        app.state.secop = SecopSource(
            SocrataClient(client, settings.socrata_retries, settings.upstream_concurrency)
        )
        app.state.rnve_summary = RnveSummaryRenderer(settings.capital_markets_timeout)
        # Dedicated transport: Socrata app-token headers must never reach SFC.
        async with httpx.AsyncClient(
            timeout=settings.capital_markets_timeout,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
            follow_redirects=False,
        ) as reports_client:
            app.state.bvc_pages = BvcPublicPages(reports_client)
            app.state.sfc_quote_pages = SfcQuotePages(reports_client)
            app.state.secondary_quotes = LaRepublicaPublicPages()
            app.state.rnve_securities = OfficialReports(
                reports_client, settings.capital_markets_retries
            )
            try:
                yield
            finally:
                await app.state.rnve_summary.close()
    await engine.dispose()


app = FastAPI(
    title="Colombia Company Intelligence",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if get_settings().public_api_docs else None,
    redoc_url="/redoc" if get_settings().public_api_docs else None,
    openapi_url="/openapi.json" if get_settings().public_api_docs else None,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_settings().allowed_hosts)
limiter = RequestLimiter(get_settings())
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type"],
)
DB = Annotated[AsyncSession, Depends(get_session)]
app.include_router(operations_router)
app.include_router(exports_router)


def adapter(request: Request) -> RuesDataSource:
    return cast(RuesDataSource, request.app.state.rues)


@app.middleware("http")
async def constrain_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
    if len(request.scope.get("query_string", b"")) > 8192:
        return error(414, "request_too_large", "Query string is too long.")
    secop_refresh = (
        request.method == "POST"
        and request.url.path.startswith("/api/v1/companies/")
        and request.url.path.endswith("/screening/secop/refresh")
    )
    importing = request.method == "POST" and request.url.path == IMPORT_PATH
    if importing:
        try:
            authorize_import(request)
        except SourceError as exc:
            return error(exc.status, exc.code, exc.message)
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > MAX_BYTES:
            return error(413, "import_too_large", "The XLSX limit is 10 MiB.")
    if request.method not in ("GET", "HEAD", "OPTIONS") and not importing and not secop_refresh:
        return error(405, "method_not_allowed", "This API accepts read requests only.")
    if not importing and (
        request.headers.get("transfer-encoding")
        or request.headers.get("content-length", "0") != "0"
    ):
        return error(413, "request_too_large", "Request bodies are not accepted.")
    retry_after = limiter.check(request)
    if retry_after:
        response: Response = error(
            429, "rate_limited", "Too many requests. Please try again later."
        )
        response.headers["Retry-After"] = str(retry_after)
    else:
        response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(SourceError)
async def source_error(request: Request, exc: SourceError) -> JSONResponse:
    return error(exc.status, exc.code, exc.message)


@app.exception_handler(InvalidIdentifier)
async def identifier_error(request: Request, exc: InvalidIdentifier) -> JSONResponse:
    return error(422, "invalid_identifier", str(exc))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error(
        422,
        "invalid_request",
        "Check search filters, date ranges, query length, pagination, and UUID format.",
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error(
        exc.status_code,
        "not_found" if exc.status_code == 404 else "invalid_request",
        str(exc.detail),
    )


@app.exception_handler(DatabaseUnavailable)
@app.exception_handler(SQLAlchemyError)
async def database_error(
    request: Request, exc: SQLAlchemyError | DatabaseUnavailable
) -> JSONResponse:
    logger.error("database_unavailable", extra={"exception_type": type(exc).__name__})
    return error(503, "database_unavailable", "Database is temporarily unavailable.")


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unexpected_error", extra={"exception_type": type(exc).__name__})
    return error(500, "internal_error", "An unexpected error occurred.")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(session: DB) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/api/v1/companies", response_model=SearchPage)
async def companies(
    request: Request,
    session: DB,
    source: Annotated[RuesDataSource, Depends(adapter)],
    params: Annotated[CompanySearchRequest, Query()],
) -> SearchPage:
    q = params.q.strip()
    nit = normalize_nit(q) if looks_like_nit(q) else None
    if not nit and (
        len(normalize_name(q)) < 2 or len(q.replace("%", "").replace("_", "").strip()) < 2
    ):
        raise HTTPException(422, "Enter at least two searchable characters.")
    return await search_companies(
        session,
        source,
        q,
        nit,
        params.page,
        params.page_size,
        SearchFilters.model_validate(params.model_dump(exclude={"q", "page", "page_size"})),
        securities_retriever=getattr(request.app.state, "rnve_securities", None),
    )


async def get_company(session: AsyncSession, company_id: UUID) -> Company:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "Company not found. Search the official source first.")
    return company


@app.get("/api/v1/companies/{company_id}", response_model=Profile)
async def company_profile(
    company_id: UUID,
    session: DB,
    request: Request,
    refresh: bool = False,
) -> Profile:
    company = await get_company(session, company_id)
    if refresh:
        await refresh_registration(session, company, adapter(request))
    return await profile(session, company)


@app.get("/api/v1/companies/{company_id}/sources", response_model=list[RecordView])
async def company_sources(company_id: UUID, session: DB) -> list[RecordView]:
    await get_company(session, company_id)
    return [serialize_record(r) for r in await records_for(session, company_id)]


@app.get("/api/v1/sources", response_model=list[SourceView])
async def sources(session: DB) -> list[DataSource]:
    await ensure_source(session)
    await session.commit()
    return list(await session.scalars(select(DataSource).order_by(DataSource.id)))


@app.get("/api/v1/parameters", response_model=ParameterCatalog)
async def parameters() -> ParameterCatalog:
    return ParameterCatalog.model_validate(parameter_catalog())


@app.get("/api/v1/companies/{company_id}/capital-markets", response_model=CapitalMarketsProfile)
async def company_capital_markets(
    company_id: UUID,
    session: DB,
    request: Request,
    refresh: bool = False,
    refresh_source: Literal[
        "sfc_rnve_issuer_details",
        "sfc_rnve_securities",
        "bvc_listings",
        "la_republica_quotes",
        "sfc_daily_quotes",
    ]
    | None = None,
) -> CapitalMarketsProfile:
    if refresh_source and not refresh:
        raise HTTPException(422, "A source-specific refresh requires refresh=true.")
    return await capital.company_profile(
        session,
        await get_company(session, company_id),
        getattr(request.app.state, "rnve_summary", None),
        getattr(request.app.state, "rnve_securities", None),
        force_refresh=refresh,
        refresh_source=refresh_source,
        bvc_retriever=getattr(request.app.state, "bvc_pages", None),
        secondary_retriever=getattr(request.app.state, "secondary_quotes", None),
        sfc_quote_retriever=getattr(request.app.state, "sfc_quote_pages", None),
    )


@app.get("/api/v1/companies/{company_id}/securities", response_model=SecuritiesPage)
async def company_securities(
    company_id: UUID,
    session: DB,
    security_category: SecurityCategory | None = None,
    exchange: Annotated[str | None, Query(max_length=100)] = None,
    listing_status: ListingStatus | None = None,
    page: Annotated[int, Query(ge=1, le=100)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SecuritiesPage:
    links = await capital.company_links(session, await get_company(session, company_id))
    result = await capital.instrument_views(
        session,
        [i.id for i, m in links if m.match_status == MatchStatus.VERIFIED],
        page,
        page_size,
        security_category,
        exchange,
        listing_status,
    )
    await session.commit()
    return result


@app.get("/api/v1/capital-markets/issuers", response_model=IssuerPage)
async def capital_issuers(
    session: DB,
    q: Annotated[str, Query(max_length=160)] = "",
    page: Annotated[int, Query(ge=1, le=100)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> IssuerPage:
    return await capital.issuer_search(session, q.strip(), page, page_size)


@app.get("/api/v1/capital-markets/sources", response_model=list[MarketSourceView])
async def capital_sources(session: DB) -> list[MarketSourceView]:
    result = await capital.source_views(session)
    await session.commit()
    return result


@app.get("/api/v1/companies/{company_id}/screening/secop", response_model=ScreeningView)
async def secop_screening(company_id: UUID, session: DB) -> ScreeningView:
    return await secop.view(session, await get_company(session, company_id))


@app.post("/api/v1/companies/{company_id}/screening/secop/refresh", response_model=ScreeningView)
async def secop_refresh(company_id: UUID, session: DB, request: Request) -> ScreeningView:
    origin = request.headers.get("origin")
    settings = get_settings()
    allowed = {f"{request.url.scheme}://{request.url.netloc}"}
    allowed.update(settings.cors_origins)
    if request.headers.get("sec-fetch-site") == "cross-site" or (origin and origin not in allowed):
        raise HTTPException(403, "SECOP refresh requires a same-origin request.")
    return await secop.refresh(
        session, await get_company(session, company_id), request.app.state.secop
    )


@app.get("/api/v1/companies/{company_id}/screening/secop/contracts", response_model=ContractPage)
async def secop_contracts(
    company_id: UUID,
    session: DB,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
    status: ContractStatus | None = None,
    raw_status: Annotated[str | None, Query(max_length=300)] = None,
    entity: Annotated[str | None, Query(max_length=1000)] = None,
    year: Annotated[int | None, Query(ge=1990, le=2100)] = None,
    missing_signature_date: bool = False,
    modality: Annotated[str | None, Query(max_length=500)] = None,
    q: Annotated[str, Query(max_length=160)] = "",
    sort: Literal["date", "value"] = "date",
    direction: Literal["asc", "desc"] = "desc",
    run_id: UUID | None = None,
) -> ContractPage:
    if year is not None and missing_signature_date:
        raise HTTPException(422, "Choose a signature year or missing signature dates, not both.")
    return await secop.contracts_page(
        session,
        await get_company(session, company_id),
        page,
        page_size,
        status,
        entity,
        year,
        modality,
        q,
        sort,
        direction,
        run_id=run_id,
        raw_status=raw_status,
        missing_signature_date=missing_signature_date,
    )


@app.get(
    "/api/v1/companies/{company_id}/screening/secop/contracts/{contract_id}",
    response_model=ContractView,
)
async def secop_contract_detail(
    company_id: UUID, contract_id: str, session: DB, run_id: UUID | None = None
) -> ContractView:
    result = await secop.contracts_page(
        session,
        await get_company(session, company_id),
        1,
        1,
        contract_id=contract_id,
        run_id=run_id,
    )
    if not result.items:
        raise HTTPException(404, "Contract not found in this company's verified screening.")
    return result.items[0]


@app.get("/api/v1/presentation/usd-rate", response_model=Rate)
async def reference_rate(request: Request) -> Rate:
    return await cast(ReferenceRates, request.app.state.reference_rates).get()
