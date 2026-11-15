"""Bounded read-through cache for verified issuers' public RNVE summary pages."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from weakref import WeakValueDictionary

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import SourceError
from app.integrations.capital_markets.ingestion import ingest_issuer_details, record_failure
from app.integrations.capital_markets.issuer_details import DETAILS_SOURCE
from app.integrations.capital_markets.summary_renderer import SummaryRetriever, summary_url
from app.models.capital_markets import CapitalMarketsSourceSnapshot as Snapshot
from app.models.capital_markets import SecuritiesIssuer

logger = logging.getLogger(__name__)
_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


async def recent_attempt(session: AsyncSession, issuer_key: str) -> bool:
    latest = await session.scalar(
        select(Snapshot)
        .where(
            Snapshot.source_id == DETAILS_SOURCE,
            Snapshot.details["issuer_id"].astext == issuer_key,
        )
        .order_by(Snapshot.retrieved_at.desc(), Snapshot.id)
        .limit(1)
    )
    if latest is None:
        return False
    ttl = (
        timedelta(minutes=15)
        if latest.ingestion_status == "failed"
        else timedelta(hours=get_settings().capital_markets_max_age_hours)
    )
    return datetime.now(UTC) - latest.retrieved_at < ttl


async def refresh_details(
    session: AsyncSession, issuer: SecuritiesIssuer, retriever: SummaryRetriever
) -> None:
    # Lock within a worker, then use PostgreSQL to suppress duplicate fetches across workers.
    key, issuer_key = issuer.external_id, str(issuer.id)
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if await recent_attempt(session, issuer_key):
            return
        if not issuer.regulator_entity_type or not issuer.regulator_entity_code:
            return
        url = summary_url(issuer.regulator_entity_type, issuer.regulator_entity_code)
        locked = await session.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 770210))"),
            {"key": key},
        )
        if not locked:
            return
        # Another worker may have completed between our first cache read and acquiring this lock.
        if await recent_attempt(session, issuer_key):
            return
        try:
            content = await retriever.fetch(
                issuer.regulator_entity_type, issuer.regulator_entity_code, issuer.issuer_name
            )
        except (SourceError, ValueError) as exc:
            await record_failure(
                session, DETAILS_SOURCE, url, exc, details={"issuer_id": issuer_key}
            )
            logger.warning(
                "rnve_summary_retrieval_failed", extra={"exception_type": type(exc).__name__}
            )
            return
        try:
            await ingest_issuer_details(session, issuer, content, url)
        except (ValueError, SourceError):
            # Ingest has already recorded a sanitized failure and preserved the last good version.
            logger.warning("rnve_summary_validation_failed")
