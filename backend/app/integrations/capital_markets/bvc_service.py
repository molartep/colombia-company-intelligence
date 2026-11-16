"""Cache public BVC observations without changing SFC source records or inventing prices."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID
from weakref import WeakValueDictionary

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import SourceError
from app.integrations.capital_markets.bvc import (
    DEFAULT_PAGES,
    BvcQuote,
    BvcRetriever,
    parse_quote,
    validate_page,
)
from app.integrations.capital_markets.equity_identity import common_equity_counts
from app.integrations.capital_markets.ingestion import ensure_sources, raw_record, record_failure
from app.integrations.capital_markets.reports import store_artifact
from app.integrations.capital_markets.types import (
    BVC_SOURCE,
    SECURITIES_SOURCE,
    ListingStatus,
    SecurityCategory,
)
from app.models.capital_markets import CapitalMarketsSourceSnapshot as Snapshot
from app.models.capital_markets import SecurityInstrument
from app.models.entities import DataSource, SourceRecord
from app.schemas.capital_markets import BvcQuoteView, ExchangeFinding

_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


async def latest_attempt(session: AsyncSession, issuer_id: str, code: str) -> Snapshot | None:
    return await session.scalar(
        select(Snapshot)
        .where(
            Snapshot.source_id == BVC_SOURCE,
            Snapshot.details["issuer_id"].astext == issuer_id,
            Snapshot.details["ann_code"].astext == code,
        )
        .order_by(Snapshot.retrieved_at.desc(), Snapshot.id)
        .limit(1)
    )


async def refresh_quote(
    session: AsyncSession,
    instrument: SecurityInstrument,
    retriever: BvcRetriever,
    url: str,
    refresh_after: datetime | None,
) -> None:
    code, issuer_id = instrument.ann_code or "", str(instrument.issuer_id)
    key = issuer_id + ":" + code
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        for acquire in (False, True):
            attempt = await latest_attempt(session, issuer_id, code)
            if attempt:
                recent = (
                    attempt.retrieved_at >= refresh_after
                    if refresh_after
                    else (
                        datetime.now(UTC) - attempt.retrieved_at
                        < timedelta(
                            minutes=15
                            if attempt.ingestion_status == "failed"
                            else get_settings().bvc_cache_minutes
                        )
                    )
                )
                if recent:
                    return
            if not acquire and not await session.scalar(
                text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 770212))"),
                {"key": key},
            ):
                return
        try:
            validate_page(url)
            async with asyncio.timeout(get_settings().capital_markets_timeout):
                content = await retriever.fetch(url, code)
            quote = parse_quote(content, code)
            digest = store_artifact(content, get_settings().capital_markets_storage_dir)
            await ensure_sources(session)
            await raw_record(session, BVC_SOURCE, key, quote.model_dump(mode="json"), url)
            session.add(
                Snapshot(
                    source_id=BVC_SOURCE,
                    source_url=url,
                    retrieved_at=datetime.now(UTC),
                    content_hash=digest,
                    record_count=1,
                    ingestion_status="success",
                    details={
                        "issuer_id": issuer_id,
                        "ann_code": code,
                        "coverage": "one_public_common_equity_page",
                        "observed_at": None,
                    },
                )
            )
            source = await session.get(DataSource, BVC_SOURCE)
            assert source
            source.availability, source.last_checked_at = "available", datetime.now(UTC)
            await session.commit()
        except (SourceError, ValueError, TimeoutError) as exc:
            await record_failure(
                session, BVC_SOURCE, url, exc, details={"issuer_id": issuer_id, "ann_code": code}
            )


async def bvc_finding(
    session: AsyncSession,
    issuer_ids: list[UUID],
    retriever: BvcRetriever | None = None,
    refresh_after: datetime | None = None,
) -> ExchangeFinding:
    count, _ = await common_equity_counts(session, issuer_ids)
    if count > 1:
        return ExchangeFinding(availability="not_yet_checked")
    common = list(
        await session.scalars(
            select(SecurityInstrument)
            .where(
                SecurityInstrument.issuer_id.in_(issuer_ids),
                SecurityInstrument.security_category == SecurityCategory.COMMON,
                SecurityInstrument.source_id == SECURITIES_SOURCE,
                SecurityInstrument.ann_code.is_not(None),
            )
            .order_by(SecurityInstrument.id)
            .limit(20)
        )
    )
    pages = {**DEFAULT_PAGES, **get_settings().bvc_page_urls}
    # Source URLs are routing hints; code matching still gates every displayed observation.
    selected = [i for i in common if i.ann_code in pages][:2]
    if retriever:
        for instrument in selected:
            await session.refresh(instrument)
            await refresh_quote(
                session, instrument, retriever, pages[instrument.ann_code or ""], refresh_after
            )
        # Failed refresh rolls back and expires tracked objects.
        for instrument in common:
            await session.refresh(instrument)
    quotes = []
    failed = False
    for instrument in selected:
        code, issuer_id = instrument.ann_code or "", str(instrument.issuer_id)
        attempt = await latest_attempt(session, issuer_id, code)
        failed = failed or bool(attempt and attempt.ingestion_status == "failed")
        record = await session.scalar(
            select(SourceRecord)
            .where(
                SourceRecord.source_id == BVC_SOURCE,
                SourceRecord.external_record_id == issuer_id + ":" + code,
            )
            .order_by(SourceRecord.retrieved_at.desc())
            .limit(1)
        )
        if not record:
            continue
        quote = BvcQuote.model_validate(record.raw_payload)
        if quote.code != code:
            continue
        stale = bool(attempt and attempt.ingestion_status == "failed") or (
            datetime.now(UTC) - record.retrieved_at
            > timedelta(minutes=get_settings().bvc_cache_minutes)
        )
        quotes.append(
            BvcQuoteView(
                instrument_id=instrument.id,
                superfinanciera_code=quote.code,
                ticker=quote.ticker,
                last_price=quote.last_price,
                raw_price=quote.raw_price,
                currency=quote.currency,
                isin=quote.isin,
                reported_state=quote.state,
                retrieved_at=record.retrieved_at,
                source_url=record.source_url or pages[code],
                stale=stale,
            )
        )
    active = any(
        q.reported_state and q.reported_state.upper() == "ACTIVO" and not q.stale for q in quotes
    )
    return ExchangeFinding(
        quotes=quotes,
        status=ListingStatus.LISTED if active else ListingStatus.UNKNOWN,
        verified_as_of=max((q.retrieved_at for q in quotes), default=None),
        availability="stale"
        if quotes and (failed or any(q.stale for q in quotes))
        else "available"
        if quotes
        else "failed_to_retrieve"
        if failed
        else "not_yet_checked",
        explanation=(
            (
                "Coincidencia exacta entre Código Superfinanciera BVC y ANN "
                "de acciones ordinarias RNVE. "
                "El precio es el último reportado por la página; "
                "no es una cotización en tiempo real."
            )
            if quotes
            else (
                "No se pudo recuperar la página pública BVC. "
                "No implica ausencia de listado ni de precio."
            )
            if failed
            else (
                "La consulta BVC requiere una página pública configurada para el código ANN de las "
                "acciones ordinarias; esta cobertura aún no se ha verificado."
            )
        ),
    )
