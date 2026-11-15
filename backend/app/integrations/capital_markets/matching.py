from datetime import UTC, datetime

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.capital_markets.types import MatchMethod, MatchStatus
from app.models.capital_markets import IssuerCompanyMatch, SecuritiesIssuer
from app.models.entities import Company, CompanyAlias


async def eligible(session: AsyncSession, company: Company, issuer: SecuritiesIssuer) -> bool:
    if not company.nit or company.nit != issuer.nit or not issuer.identity_eligible:
        return False
    if (
        company.verification_digit
        and issuer.verification_digit
        and company.verification_digit != issuer.verification_digit
    ):
        return False
    companies = await session.scalar(
        select(func.count()).select_from(Company).where(Company.nit == company.nit)
    )
    issuers = await session.scalar(
        select(func.count())
        .select_from(SecuritiesIssuer)
        .where(SecuritiesIssuer.nit == issuer.nit, SecuritiesIssuer.identity_eligible.is_(True))
    )
    return companies == issuers == 1


async def reconcile(session: AsyncSession, company: Company | None = None) -> None:
    """Verify only a unique eligible exact NIT. Names/aliases remain potential.

    Demote obsolete machine links before assigning new ones. A weaker name
    candidate must never invalidate another company's valid exact-NIT link.
    Reviewed/rejected decisions are preserved; no partial NIT or brand matching.
    """
    await session.execute(text("SELECT pg_advisory_xact_lock(770209)"))
    companies = [company] if company else list(await session.scalars(select(Company)))
    for candidate in companies:
        aliases = list(
            await session.scalars(
                select(CompanyAlias.normalized_name).where(CompanyAlias.company_id == candidate.id)
            )
        )
        issuers = list(
            await session.scalars(
                select(SecuritiesIssuer).where(
                    or_(
                        SecuritiesIssuer.nit == candidate.nit if candidate.nit else False,
                        SecuritiesIssuer.normalized_name.in_([candidate.normalized_name, *aliases]),
                        SecuritiesIssuer.id.in_(
                            select(IssuerCompanyMatch.issuer_id).where(
                                IssuerCompanyMatch.company_id == candidate.id
                            )
                        ),
                    )
                )
            )
        )
        for issuer in issuers:
            match = await session.scalar(
                select(IssuerCompanyMatch).where(
                    IssuerCompanyMatch.issuer_id == issuer.id,
                    IssuerCompanyMatch.company_id == candidate.id,
                )
            )
            if match and (match.reviewed_at or match.match_status == MatchStatus.REJECTED):
                if match.match_status != MatchStatus.VERIFIED and issuer.company_id == candidate.id:
                    issuer.company_id = None
                continue
            verified = await eligible(session, candidate, issuer)
            conflicts = list(
                await session.scalars(
                    select(IssuerCompanyMatch).where(
                        IssuerCompanyMatch.match_status == MatchStatus.VERIFIED,
                        or_(
                            IssuerCompanyMatch.issuer_id == issuer.id,
                            IssuerCompanyMatch.company_id == candidate.id,
                        ),
                    )
                )
            )
            for conflict in conflicts:
                if conflict.issuer_id == issuer.id and conflict.company_id == candidate.id:
                    continue
                other_company = await session.get(Company, conflict.company_id)
                other_issuer = await session.get(SecuritiesIssuer, conflict.issuer_id)
                if conflict.reviewed_at or (
                    other_company
                    and other_issuer
                    and await eligible(session, other_company, other_issuer)
                ):
                    verified = False
                else:
                    conflict.match_status = MatchStatus.POTENTIAL
                    if other_issuer and other_issuer.company_id == conflict.company_id:
                        other_issuer.company_id = None
                    await session.flush()
            exact = bool(candidate.nit and candidate.nit == issuer.nit and issuer.identity_eligible)
            method = (
                MatchMethod.NIT
                if exact
                else (
                    MatchMethod.NAME
                    if candidate.legal_name.strip().upper() == issuer.issuer_name.strip().upper()
                    else MatchMethod.NORMALIZED
                )
            )
            if not match:
                match = IssuerCompanyMatch(
                    issuer_id=issuer.id, company_id=candidate.id, matched_at=datetime.now(UTC)
                )
                session.add(match)
            match.match_method = method
            match.match_status = MatchStatus.VERIFIED if verified else MatchStatus.POTENTIAL
            if verified:
                issuer.company_id = candidate.id
            elif issuer.company_id == candidate.id:
                issuer.company_id = None
            await session.flush()
