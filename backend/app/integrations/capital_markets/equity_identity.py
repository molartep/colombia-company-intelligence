"""Registration-scoped quote eligibility and explicitly reported former names."""

import re
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.capital_markets.types import SECURITIES_SOURCE, MatchStatus, SecurityCategory
from app.models.capital_markets import IssuerCompanyMatch, SecurityInstrument


async def common_equity_counts(session: AsyncSession, issuer_ids: list[UUID]) -> tuple[int, int]:
    row = (
        await session.execute(
            select(
                func.count(SecurityInstrument.id),
                func.count(SecurityInstrument.id).filter(
                    func.upper(func.trim(SecurityInstrument.exchange)) == "BVC"
                ),
            ).where(
                SecurityInstrument.issuer_id.in_(issuer_ids),
                SecurityInstrument.source_id == SECURITIES_SOURCE,
                SecurityInstrument.security_category == SecurityCategory.COMMON,
            )
        )
    ).one()
    return int(row[0]), int(row[1])


def former_legal_names(security_name: str) -> list[str]:
    # Only explicit ANTES clauses in an ordinary-share title; never strip legal suffixes.
    parts = re.split(r"\s+-\s+ANTES\s+", security_name, flags=re.IGNORECASE)
    if len(parts) < 2 or not re.match(r"^AO\s+", parts[0], flags=re.IGNORECASE):
        return []
    return [part.strip() for part in parts[1:] if part.strip()]


def registered_bvc_company_ids() -> Select[UUID]:
    """Positive registration evidence only; no inference from prices or absent records."""
    return (
        select(IssuerCompanyMatch.company_id)
        .join(SecurityInstrument, SecurityInstrument.issuer_id == IssuerCompanyMatch.issuer_id)
        .where(
            IssuerCompanyMatch.match_status == MatchStatus.VERIFIED,
            SecurityInstrument.source_id == SECURITIES_SOURCE,
            SecurityInstrument.security_category == SecurityCategory.COMMON,
            func.upper(func.trim(SecurityInstrument.exchange)) == "BVC",
        )
        .distinct()
    )
