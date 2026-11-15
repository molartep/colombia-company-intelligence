"""Read-through cache for one verified issuer's separate SFC securities report."""

import asyncio
import logging
from weakref import WeakValueDictionary

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import SourceError
from app.integrations.capital_markets.automatic_details import recent_attempt
from app.integrations.capital_markets.ingestion import ingest_securities, record_failure
from app.integrations.capital_markets.reports import SecuritiesRetriever, securities_url
from app.integrations.capital_markets.types import SECURITIES_SOURCE
from app.models.capital_markets import SecuritiesIssuer

logger = logging.getLogger(__name__)
_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


async def refresh_securities(
    session: AsyncSession, issuer: SecuritiesIssuer, retriever: SecuritiesRetriever
) -> None:
    key, issuer_key = issuer.external_id, str(issuer.id)
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        if await recent_attempt(session, issuer_key, SECURITIES_SOURCE):
            return
        if not issuer.regulator_entity_type or not issuer.regulator_entity_code:
            return
        url = securities_url(issuer.regulator_entity_type, issuer.regulator_entity_code)
        locked = await session.scalar(
            text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 770211))"), {"key": key}
        )
        if not locked or await recent_attempt(session, issuer_key, SECURITIES_SOURCE):
            return
        try:
            # Bound the whole operation, including pooling waits, retries and Retry-After delays.
            async with asyncio.timeout(get_settings().capital_markets_timeout):
                content = await retriever.securities(
                    issuer.regulator_entity_type, issuer.regulator_entity_code
                )
        except (SourceError, ValueError, TimeoutError) as exc:
            await record_failure(
                session, SECURITIES_SOURCE, url, exc, details={"issuer_id": issuer_key}
            )
            logger.warning(
                "rnve_securities_retrieval_failed", extra={"exception_type": type(exc).__name__}
            )
            return
        try:
            await ingest_securities(session, issuer, content, url)
        except (ValueError, SourceError):
            # Ingestion has persisted a sanitized failure without discarding previous instruments.
            logger.warning("rnve_securities_validation_failed")
