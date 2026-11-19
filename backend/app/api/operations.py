"""Live diagnostics and narrowly scoped, authorized directory imports."""

import asyncio
import secrets
import time
from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import SourceError
from app.db.session import get_session
from app.integrations.capital_markets.directory_download import download_directory
from app.integrations.capital_markets.ingestion import ingest_issuers, record_failure
from app.integrations.capital_markets.parsers import MAX_BYTES
from app.integrations.capital_markets.service import source_views
from app.integrations.capital_markets.types import DIRECTORY_URL, ISSUER_SOURCE, MatchStatus
from app.integrations.rues.parameters import parameter_catalog
from app.integrations.secop.adapter import SOURCE_ID as SECOP_SOURCE
from app.models.capital_markets import (
    CapitalMarketsSourceSnapshot,
    IssuerCompanyMatch,
    SecuritiesIssuer,
    SecurityInstrument,
)
from app.models.entities import Company, SourceRecord
from app.models.secop import ScreeningRun, SecopContract
from app.schemas.api import SourceView
from app.schemas.capital_markets import MarketSourceView
from app.services.companies import ensure_source

IMPORT_PATH = "/api/v1/admin/imports/rnve"
router = APIRouter(prefix="/api/v1")
DB = Annotated[AsyncSession, Depends(get_session)]
_import_lock = asyncio.Lock()
_last_download: float | None = None


def local_operator(request: Request) -> bool:
    return (
        get_settings().environment == "development"
        and request.client is not None
        and request.client.host in {"127.0.0.1", "::1"}
        and request.url.hostname in {"127.0.0.1", "localhost", "::1"}
    )


def authorize_import(request: Request) -> None:
    settings = get_settings()
    origin = request.headers.get("origin")
    allowed = {f"{request.url.scheme}://{request.url.netloc}"}
    if settings.environment == "development":
        # Vite's proxy can rewrite Host to the API target; allow only configured loopback origins.
        allowed.update(
            value
            for value in settings.cors_origins
            if urlparse(value).hostname in {"127.0.0.1", "localhost", "::1"}
        )
    if settings.environment == "production":
        allowed = {f"https://{settings.public_hostname}"}
    if origin not in allowed:
        raise SourceError("import_origin_denied", "Import requires a same-origin request.", 403)
    if local_operator(request):
        return
    expected = settings.admin_import_token
    supplied = request.headers.get("x-cci-admin-token", "")
    if not expected or not secrets.compare_digest(supplied, expected):
        raise SourceError(
            "import_unauthorized", "An administrator import key is required on this server.", 403
        )


class SecopReadiness(BaseModel):
    status: Literal["not_yet_checked", "pending", "running", "completed", "failed"]
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    source_updated_at: datetime | None
    cache_hours: int
    max_rows: int


class PlatformStatus(BaseModel):
    checked_at: datetime
    counts: dict[str, int]
    rues: SourceView
    sources: list[MarketSourceView]
    directory_missing: bool
    import_access: Literal["local", "admin_key", "disabled"]
    parameter_verified_at: str
    parameter_options: int
    secop: SecopReadiness


class ImportResult(BaseModel):
    snapshot_id: str
    record_count: int
    retrieved_at: datetime
    content_hash: str | None
    complete_current: bool = False


@router.get("/platform", response_model=PlatformStatus)
async def platform_status(request: Request, session: DB) -> PlatformStatus:
    rues = await ensure_source(session)
    sources = await source_views(session)
    counts = {}
    for key, model in (
        ("registrations", Company),
        ("source_records", SourceRecord),
        ("issuers", SecuritiesIssuer),
        ("instruments", SecurityInstrument),
        ("snapshots", CapitalMarketsSourceSnapshot),
    ):
        counts[key] = int(await session.scalar(select(func.count()).select_from(model)) or 0)
    counts["verified_links"] = int(
        await session.scalar(
            select(func.count())
            .select_from(IssuerCompanyMatch)
            .where(IssuerCompanyMatch.match_status == MatchStatus.VERIFIED)
        )
        or 0
    )
    counts["screening_runs"] = int(
        await session.scalar(
            select(func.count())
            .select_from(ScreeningRun)
            .where(ScreeningRun.source_id == SECOP_SOURCE)
        )
        or 0
    )
    # Evidence versions may repeat an ID. This is a global historical count, not a portfolio total.
    counts["secop_contracts"] = int(
        await session.scalar(select(func.count(func.distinct(SecopContract.contract_id)))) or 0
    )
    latest_run = await session.scalar(
        select(ScreeningRun)
        .where(ScreeningRun.source_id == SECOP_SOURCE)
        .order_by(ScreeningRun.started_at.desc(), ScreeningRun.id.desc())
        .limit(1)
    )
    last_success = await session.scalar(
        select(ScreeningRun)
        .where(ScreeningRun.source_id == SECOP_SOURCE, ScreeningRun.status == "completed")
        .order_by(ScreeningRun.completed_at.desc(), ScreeningRun.id.desc())
        .limit(1)
    )
    settings = get_settings()
    readiness = SecopReadiness(
        status=latest_run.status if latest_run else "not_yet_checked",
        last_attempt_at=latest_run.started_at if latest_run else None,
        last_success_at=last_success.completed_at if last_success else None,
        source_updated_at=last_success.source_updated_at if last_success else None,
        cache_hours=settings.secop_cache_hours,
        max_rows=settings.secop_max_rows,
    )
    catalog = parameter_catalog()
    result = PlatformStatus(
        checked_at=datetime.now(UTC),
        counts=counts,
        secop=readiness,
        rues=SourceView.model_validate(rues),
        sources=sources,
        directory_missing=counts["issuers"] == 0,
        import_access="local"
        if local_operator(request)
        else "admin_key"
        if get_settings().admin_import_token
        else "disabled",
        parameter_verified_at=catalog["verified_at"],
        parameter_options=sum(len(group["options"]) for group in catalog["groups"]),
    )
    await session.commit()
    return result


@router.post("/admin/imports/rnve", response_model=ImportResult)
async def import_directory(
    request: Request, session: DB, method: Literal["download", "upload"] = "download"
) -> ImportResult:
    global _last_download
    authorize_import(request)
    if _import_lock.locked():
        raise SourceError(
            "import_busy", "A directory import is already running. Try again later.", 409
        )
    async with _import_lock:
        if method == "download":
            now = time.monotonic()
            if _last_download is not None and now - _last_download < 60:
                raise SourceError(
                    "import_cooldown", "Wait one minute before downloading again.", 429
                )
            _last_download = now
            try:
                content = await download_directory()
            except SourceError as exc:
                await record_failure(session, ISSUER_SOURCE, DIRECTORY_URL, exc)
                raise
        else:
            # Stream raw XLSX bytes: no multipart dependency or filesystem paths from the client.
            data = bytearray()
            async for chunk in request.stream():
                if len(data) + len(chunk) > MAX_BYTES:
                    raise SourceError("import_too_large", "The XLSX limit is 10 MiB.", 413)
                data.extend(chunk)
            content = bytes(data)
        try:
            snapshot = await ingest_issuers(session, content, nit_mode="concatenated-dv")
        except (ValueError, KeyError) as exc:
            raise SourceError(
                "invalid_issuer_report",
                "The export could not be validated. Use the official issuer-only XLSX "
                "(DESCARGAR EMISORES → REPORTE EXCEL). Existing evidence is preserved.",
                422,
            ) from exc
        return ImportResult(
            snapshot_id=str(snapshot.id),
            record_count=snapshot.record_count,
            retrieved_at=snapshot.retrieved_at,
            content_hash=snapshot.content_hash,
        )
