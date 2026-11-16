"""Summarize scoped attempts without claiming unconfigured sources were queried."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.capital_markets.bvc import DEFAULT_PAGES
from app.integrations.capital_markets.secondary_quotes import LR_DEFAULT_PAGES, LR_SOURCE
from app.integrations.capital_markets.sfc_quotes import SFC_PROVIDER
from app.integrations.capital_markets.types import BVC_SOURCE, SECURITIES_SOURCE, SecurityCategory
from app.models.capital_markets import CapitalMarketsSourceSnapshot as Snapshot
from app.models.capital_markets import SecurityInstrument
from app.schemas.capital_markets import QuoteAttemptView


async def quote_attempts(
    session: AsyncSession, issuer_ids: list[UUID], verified_sources: set[str]
) -> list[QuoteAttemptView]:
    rows = list(
        await session.scalars(
            select(SecurityInstrument)
            .where(
                SecurityInstrument.issuer_id.in_(issuer_ids),
                SecurityInstrument.source_id == SECURITIES_SOURCE,
                SecurityInstrument.security_category == SecurityCategory.COMMON,
            )
            .limit(2)
        )
    )
    if len(rows) != 1 or (rows[0].exchange or "").strip().upper() != "BVC":
        return []
    instrument = rows[0]
    ann, issuer_id = instrument.ann_code or "", str(instrument.issuer_id)
    settings = get_settings()
    providers = [
        (
            BVC_SOURCE,
            "Bolsa de Valores de Colombia",
            {**DEFAULT_PAGES, **settings.bvc_page_urls}.get(ann),
        ),
        (
            LR_SOURCE,
            "La República",
            {**LR_DEFAULT_PAGES, **settings.la_republica_page_urls}.get(ann),
        ),
        (SFC_PROVIDER.source_id, SFC_PROVIDER.name, SFC_PROVIDER.url_for(ann)),
    ]
    result = []
    for source_id, name, url in providers:
        latest = await session.scalar(
            select(Snapshot)
            .where(
                Snapshot.source_id == source_id,
                Snapshot.details["issuer_id"].astext == issuer_id,
                Snapshot.details["ann_code"].astext == ann,
            )
            .order_by(Snapshot.retrieved_at.desc(), Snapshot.id)
            .limit(1)
        )
        status = "not_checked"
        detail: str | None = "No fue necesario consultar esta fuente."
        if latest:
            status = (
                "matched"
                if latest.ingestion_status == "success" and source_id in verified_sources
                else "no_exact_match"
                if latest.ingestion_status == "success"
                or latest.error_details in {"quote_no_exact_match", "quote_identity_missing"}
                else "unavailable"
            )
            detail = (
                latest.error_details
                if latest.ingestion_status != "success"
                else (None if source_id in verified_sources else "quote_no_exact_match")
            )
        elif not url:
            status, detail = (
                "not_configured",
                "No hay una página de consulta verificada para este ANN.",
            )
        result.append(
            QuoteAttemptView(
                source_id=source_id,
                source_name=name,
                source_url=latest.source_url if latest else url,
                status=status,
                last_attempt_at=latest.retrieved_at if latest else None,
                detail=detail,
            )
        )
    return result
