import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast
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
from starlette.responses import Response

from app.core.config import get_settings
from app.core.errors import DatabaseUnavailable, SourceError
from app.core.logging import configure_logging
from app.core.normalization import InvalidIdentifier, looks_like_nit, normalize_name, normalize_nit
from app.db.session import engine, get_session
from app.integrations.rues.adapter import RuesDataSource
from app.integrations.socrata import SocrataClient
from app.models.entities import Company, DataSource
from app.schemas.api import ErrorResponse, Profile, RecordView, SearchPage, SourceView
from app.services.companies import (
    ensure_source,
    profile,
    records_for,
    search_companies,
    serialize_record,
)

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
        app.state.rues = RuesDataSource(
            SocrataClient(client, settings.socrata_retries, settings.upstream_concurrency)
        )
        yield
    await engine.dispose()


app = FastAPI(
    title="Colombia Company Intelligence",
    version="0.1.0",
    lifespan=lifespan,
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET"],
    allow_headers=["Accept", "Content-Type"],
)
DB = Annotated[AsyncSession, Depends(get_session)]


def adapter(request: Request) -> RuesDataSource:
    return cast(RuesDataSource, request.app.state.rues)


@app.middleware("http")
async def constrain_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
    if len(request.scope.get("query_string", b"")) > 2048:
        return error(414, "request_too_large", "Query string is too long.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        return error(405, "method_not_allowed", "This API accepts read requests only.")
    if (
        request.headers.get("transfer-encoding")
        or request.headers.get("content-length", "0") != "0"
    ):
        return error(413, "request_too_large", "Request bodies are not accepted.")
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
    return error(422, "invalid_request", "Check query length, pagination, and UUID format.")


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
    session: DB,
    source: Annotated[RuesDataSource, Depends(adapter)],
    q: Annotated[str, Query(min_length=2, max_length=160)],
    page: Annotated[int, Query(ge=1, le=100)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchPage:
    q = q.strip()
    nit = normalize_nit(q) if looks_like_nit(q) else None
    if not nit and (
        len(normalize_name(q)) < 2 or len(q.replace("%", "").replace("_", "").strip()) < 2
    ):
        raise HTTPException(422, "Enter at least two searchable characters.")
    return await search_companies(session, source, q, nit, page, page_size)


async def get_company(session: AsyncSession, company_id: UUID) -> Company:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "Company not found. Search the official source first.")
    return company


@app.get("/api/v1/companies/{company_id}", response_model=Profile)
async def company_profile(company_id: UUID, session: DB) -> Profile:
    return await profile(session, await get_company(session, company_id))


@app.get("/api/v1/companies/{company_id}/sources", response_model=list[RecordView])
async def company_sources(company_id: UUID, session: DB) -> list[RecordView]:
    await get_company(session, company_id)
    return [serialize_record(r) for r in await records_for(session, company_id)]


@app.get("/api/v1/sources", response_model=list[SourceView])
async def sources(session: DB) -> list[DataSource]:
    await ensure_source(session)
    await session.commit()
    return list(await session.scalars(select(DataSource).order_by(DataSource.id)))
