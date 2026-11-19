"""Secondary quotes with strict identity matching and separate provenance."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.integrations.capital_markets.quote_provider import QuoteProvider
from uuid import UUID
from weakref import WeakValueDictionary

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import SourceError
from app.integrations.capital_markets.equity_identity import (
    common_equity_counts,
    former_legal_names,
)
from app.integrations.capital_markets.ingestion import ensure_sources, raw_record, record_failure
from app.integrations.capital_markets.lr_discovery import discover_quote
from app.integrations.capital_markets.reports import store_artifact
from app.integrations.capital_markets.secondary_quotes import (
    LR_INDEX_URL,
    LR_SOURCE,
    DirectoryRetriever,
    SecondaryQuote,
    SecondaryRetriever,
    exact_match,
    parse_la_republica,
    validate_lr_url,
)
from app.integrations.capital_markets.types import SECURITIES_SOURCE, SecurityCategory
from app.models.capital_markets import CapitalMarketsSourceSnapshot as Snapshot
from app.models.capital_markets import SecurityInstrument
from app.models.entities import Company, DataSource, SourceRecord
from app.schemas.capital_markets import BvcQuoteView

_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


async def attempt_for(
    session: AsyncSession, issuer_id: str, ann: str, source_id: str = LR_SOURCE
) -> Snapshot | None:
    return await session.scalar(
        select(Snapshot)
        .where(
            Snapshot.source_id == source_id,
            Snapshot.details["issuer_id"].astext == issuer_id,
            Snapshot.details["ann_code"].astext == ann,
        )
        .order_by(Snapshot.retrieved_at.desc(), Snapshot.id)
        .limit(1)
    )


async def secondary_quotes(
    session: AsyncSession,
    company: Company,
    issuer_ids: list[UUID],
    retriever: SecondaryRetriever | None,
    refresh_after: datetime | None = None,
    provider: "QuoteProvider | None" = None,
) -> list[BvcQuoteView]:
    from app.integrations.capital_markets.quote_provider import QuoteProvider

    discovery = provider is None
    if discovery:
        provider = QuoteProvider(
            LR_SOURCE, "La República", lambda ann: LR_INDEX_URL, validate_lr_url, parse_la_republica
        )
    assert provider is not None
    source_id = provider.source_id
    count, _ = await common_equity_counts(session, issuer_ids)
    if count > 1:
        return []
    common = list(
        await session.scalars(
            select(SecurityInstrument)
            .where(
                SecurityInstrument.issuer_id.in_(issuer_ids),
                SecurityInstrument.source_id == SECURITIES_SOURCE,
                SecurityInstrument.security_category == SecurityCategory.COMMON,
                SecurityInstrument.ann_code.is_not(None),
            )
            .order_by(SecurityInstrument.id)
            .limit(20)
        )
    )
    codes = {i.ann_code for i in common if i.ann_code}
    company_nit, legal_name, dv = company.nit, company.legal_name, company.verification_digit
    legal_names = [legal_name]
    if len(common) == 1 and (common[0].exchange or "").strip().upper() == "BVC":
        legal_names.extend(former_legal_names(common[0].security_name))
    pages = {
        i.ann_code: url for i in common if i.ann_code and (url := provider.url_for(i.ann_code))
    }
    selected = [
        i for i in common if i.ann_code in pages and (i.exchange or "").strip().upper() == "BVC"
    ][:2]
    for instrument in selected:
        await session.refresh(instrument)
        ann, issuer_id = instrument.ann_code or "", str(instrument.issuer_id)
        key, url = issuer_id + ":" + ann, pages[ann]
        lock_key = source_id + ":" + key
        if retriever:
            lock = _locks.setdefault(lock_key, asyncio.Lock())
            async with lock:
                recent = await attempt_for(session, issuer_id, ann, source_id)
                fresh = bool(
                    recent
                    and (
                        recent.retrieved_at >= refresh_after
                        if refresh_after
                        else datetime.now(UTC) - recent.retrieved_at < timedelta(minutes=15)
                    )
                )
                if not fresh and await session.scalar(
                    text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 770213))"),
                    {"key": lock_key},
                ):
                    recent = await attempt_for(session, issuer_id, ann, source_id)
                    fresh = bool(
                        recent
                        and (
                            recent.retrieved_at >= refresh_after
                            if refresh_after
                            else datetime.now(UTC) - recent.retrieved_at < timedelta(minutes=15)
                        )
                    )
                    if not fresh:
                        digest = None
                        try:
                            discovery_details = {}
                            async with asyncio.timeout(get_settings().capital_markets_timeout):
                                if discovery:
                                    if not isinstance(retriever, DirectoryRetriever):
                                        raise SourceError(
                                            "lr_directory_unavailable",
                                            "The directory connector is unavailable.",
                                        )
                                    previous = await session.scalar(
                                        select(SourceRecord)
                                        .where(
                                            SourceRecord.source_id == source_id,
                                            SourceRecord.external_record_id == key,
                                        )
                                        .order_by(SourceRecord.retrieved_at.desc())
                                        .limit(1)
                                    )
                                    found = await discover_quote(
                                        session,
                                        retriever,
                                        company_nit,
                                        legal_names,
                                        codes,
                                        dv,
                                        previous.source_url if previous else None,
                                    )
                                    content, quote, url = found.content, found.quote, found.url
                                    discovery_details = {
                                        "directory_url": LR_INDEX_URL,
                                        "directory_hash": found.directory_hash,
                                        "discovered_at": found.discovered_at,
                                        "verified_at": datetime.now(UTC).isoformat(),
                                    }
                                else:
                                    provider.validate_url(url)
                                    content = await retriever.fetch(url)
                                    quote = provider.parse(content)
                            digest = store_artifact(
                                content, get_settings().capital_markets_storage_dir
                            )
                            match = exact_match(quote, company_nit, legal_names, codes, dv)
                            if not match or match[2] != ann:
                                raise SourceError(
                                    "quote_no_exact_match",
                                    "No exact NIT, ANN or legal-name match was established.",
                                )
                            await ensure_sources(session)
                            payload = {
                                **quote.model_dump(mode="json"),
                                "match_type": match[0],
                                "matched_value": match[1],
                                "linked_ann": ann,
                                **discovery_details,
                            }
                            await raw_record(session, source_id, key, payload, url)
                            session.add(
                                Snapshot(
                                    source_id=source_id,
                                    source_url=url,
                                    retrieved_at=datetime.now(UTC),
                                    content_hash=digest,
                                    record_count=1,
                                    ingestion_status="success",
                                    details={
                                        "issuer_id": issuer_id,
                                        "ann_code": ann,
                                        "observed_at": quote.price_as_of.isoformat()
                                        if quote.price_as_of
                                        else None,
                                        "match_type": match[0],
                                        "matched_value": match[1],
                                        "coverage": "one_secondary_stock_quote",
                                        **discovery_details,
                                    },
                                )
                            )
                            source = await session.get(DataSource, source_id)
                            assert source
                            source.last_checked_at, source.availability = (
                                datetime.now(UTC),
                                "available",
                            )
                            await session.commit()
                        except (SourceError, ValueError, TimeoutError) as exc:
                            await record_failure(
                                session,
                                source_id,
                                url,
                                exc,
                                digest,
                                {"issuer_id": issuer_id, "ann_code": ann},
                            )
    for instrument in common:
        await session.refresh(instrument)
    result = []
    for instrument in selected:
        key = str(instrument.issuer_id) + ":" + (instrument.ann_code or "")
        record = await session.scalar(
            select(SourceRecord)
            .where(
                SourceRecord.source_id == source_id,
                SourceRecord.external_record_id == key,
            )
            .order_by(SourceRecord.retrieved_at.desc())
            .limit(1)
        )
        if not record:
            continue
        quote = SecondaryQuote.model_validate(record.raw_payload)
        # Recheck a cached identity against today's company/registration, not only on fetch.
        match = exact_match(quote, company_nit, legal_names, codes, dv)
        if not match or match[2] != instrument.ann_code:
            continue
        recent = await attempt_for(
            session, str(instrument.issuer_id), instrument.ann_code, source_id
        )
        if recent and recent.error_details == "lr_ambiguous_match":
            continue
        stale = bool(recent and recent.ingestion_status == "failed") or datetime.now(
            UTC
        ) - record.retrieved_at > timedelta(minutes=15)
        result.append(
            BvcQuoteView(
                instrument_id=instrument.id,
                superfinanciera_code=instrument.ann_code,
                ticker=quote.ticker,
                last_price=quote.last_price,
                raw_price=quote.raw_price,
                currency=quote.currency,
                price_kind=quote.price_kind,
                price_date=quote.price_date,
                source_note=quote.source_note,
                reported_state=quote.reported_listing,
                retrieved_at=record.retrieved_at,
                price_as_of=quote.price_as_of,
                source_url=record.source_url or pages[instrument.ann_code],
                stale=stale,
                source_id=source_id,
                source_name=provider.name,
                match_type=match[0],
                matched_value=match[1],
                reported_legal_name=quote.legal_name,
                reported_nit=quote.nit,
                reported_ann=quote.ann_code,
                variation_percent=quote.variation_percent,
                volume=quote.volume,
            )
        )
    return result
