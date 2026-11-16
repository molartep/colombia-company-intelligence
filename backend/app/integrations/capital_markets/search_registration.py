"""Discover BVC registration evidence before requesting a bounded RUES page."""

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import SourceError
from app.core.normalization import Nit, compact_name
from app.integrations.capital_markets.automatic_securities import refresh_securities
from app.integrations.capital_markets.reports import SecuritiesRetriever
from app.integrations.capital_markets.types import (
    ISSUER_SOURCE,
    SECURITIES_SOURCE,
    SecurityCategory,
)
from app.models.capital_markets import CapitalMarketsSourceSnapshot as Snapshot
from app.models.capital_markets import SecuritiesIssuer, SecurityInstrument

MAX_DISCOVERY_ISSUERS = 10
MAX_FILTER_NITS = 500


async def registration_nits(
    session: AsyncSession, query: str, nit: Nit | None, retriever: SecuritiesRetriever
) -> list[str]:
    condition = (
        SecuritiesIssuer.nit == nit.number
        if nit
        else func.replace(SecuritiesIssuer.normalized_name, " ", "").contains(
            compact_name(query), autoescape=True
        )
    )
    candidates = list(
        await session.scalars(
            select(SecuritiesIssuer)
            .where(
                SecuritiesIssuer.source_id == ISSUER_SOURCE,
                SecuritiesIssuer.identity_eligible.is_(True),
                condition,
            )
            .order_by(SecuritiesIssuer.id)
            .limit(MAX_DISCOVERY_ISSUERS + 1)
        )
    )
    if len(candidates) > MAX_DISCOVERY_ISSUERS:
        raise SourceError(
            "bvc_search_too_broad",
            "Too many RNVE issuers match. Use a more specific name or NIT.",
            422,
        )
    if not await session.scalar(select(SecuritiesIssuer.id).limit(1)):
        raise SourceError(
            "bvc_directory_unavailable",
            "Import the official RNVE issuer directory before using Registrado BVC.",
        )
    candidate_ids = [issuer.id for issuer in candidates]
    await session.commit()  # Do not hold identity-resolution locks during network I/O.
    try:
        async with asyncio.timeout(get_settings().capital_markets_timeout):
            for issuer_id in candidate_ids:
                issuer = await session.get(SecuritiesIssuer, issuer_id)
                assert issuer
                await session.refresh(issuer)
                await refresh_securities(session, issuer, retriever)
                attempt = await session.scalar(
                    select(Snapshot)
                    .where(
                        Snapshot.source_id == SECURITIES_SOURCE,
                        Snapshot.details["issuer_id"].astext == str(issuer_id),
                    )
                    .order_by(Snapshot.retrieved_at.desc(), Snapshot.id)
                    .limit(1)
                )
                if not attempt or attempt.ingestion_status != "success":
                    raise SourceError(
                        "bvc_registration_unavailable",
                        "RNVE securities evidence could not be verified. Retry this search; "
                        "this is not a finding of no BVC registration.",
                    )
    except TimeoutError as exc:
        raise SourceError(
            "bvc_registration_timeout",
            "RNVE registration discovery timed out. Retry with a more specific name or NIT.",
        ) from exc
    # Identity is established after RUES returns, without depending on previously visited pages.
    nits = list(
        await session.scalars(
            select(SecuritiesIssuer.nit)
            .join(SecurityInstrument, SecurityInstrument.issuer_id == SecuritiesIssuer.id)
            .where(
                SecuritiesIssuer.source_id == ISSUER_SOURCE,
                SecuritiesIssuer.identity_eligible.is_(True),
                SecuritiesIssuer.nit.is_not(None),
                SecurityInstrument.source_id == SECURITIES_SOURCE,
                SecurityInstrument.security_category == SecurityCategory.COMMON,
                func.upper(func.trim(SecurityInstrument.exchange)) == "BVC",
            )
            .distinct()
            .order_by(SecuritiesIssuer.nit)
            .limit(MAX_FILTER_NITS + 1)
        )
    )
    if len(nits) > MAX_FILTER_NITS:
        raise SourceError(
            "bvc_registration_limit",
            "BVC registration index exceeds the bounded query limit; adapter review is required.",
        )
    return [value for value in nits if value]
