import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.normalization import looks_like_nit, normalize_name, normalize_nit
from app.integrations.capital_markets.automatic_details import refresh_details
from app.integrations.capital_markets.automatic_securities import refresh_securities
from app.integrations.capital_markets.ingestion import ensure_sources
from app.integrations.capital_markets.issuer_details import DETAILS_SOURCE
from app.integrations.capital_markets.matching import reconcile
from app.integrations.capital_markets.parsers import optional
from app.integrations.capital_markets.reports import SecuritiesRetriever
from app.integrations.capital_markets.summary_renderer import SummaryRetriever
from app.integrations.capital_markets.types import (
    BVC_SOURCE,
    DIRECTORY_URL,
    ISSUER_SOURCE,
    SECURITIES_SOURCE,
    ListingStatus,
    MatchStatus,
    RegistrationStatus,
    SecurityCategory,
)
from app.models.capital_markets import (
    CapitalMarketsSourceSnapshot as Snapshot,
)
from app.models.capital_markets import (
    IssuerCompanyMatch,
    SecuritiesIssuer,
    SecurityInstrument,
)
from app.models.entities import Company, DataSource, SourceRecord
from app.schemas.capital_markets import (
    CapitalMarketsProfile,
    ExchangeFinding,
    InstrumentView,
    IssuerPage,
    IssuerView,
    MarketSourceView,
    OwnershipFinding,
    RnveFinding,
    SecuritiesPage,
    SnapshotView,
)


def snapshot_stale(snapshot: Snapshot | None, now: datetime | None = None) -> bool:
    if not snapshot:
        return True
    now = now or datetime.now(UTC)
    observed = snapshot.details.get("observed_at")
    stamp = datetime.fromisoformat(observed) if observed else snapshot.retrieved_at
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return (
        now - min(stamp, snapshot.retrieved_at)
    ).total_seconds() > get_settings().capital_markets_max_age_hours * 3600


def snapshot_view(snapshot: Snapshot) -> SnapshotView:
    return SnapshotView.model_validate(
        {
            **{
                key: getattr(snapshot, key)
                for key in SnapshotView.model_fields
                if hasattr(snapshot, key)
            },
            "observed_at": snapshot.details.get("observed_at"),
            "complete_current": bool(snapshot.details.get("complete_current")),
        }
    )


async def source_views(
    session: AsyncSession, issuer_ids: list[UUID] | None = None
) -> list[MarketSourceView]:
    await ensure_sources(session)
    result = []
    for source in await session.scalars(
        select(DataSource)
        .where(DataSource.id.in_([ISSUER_SOURCE, SECURITIES_SOURCE, BVC_SOURCE, DETAILS_SOURCE]))
        .order_by(DataSource.id)
    ):
        scoped = source.id in {DETAILS_SOURCE, SECURITIES_SOURCE} and issuer_ids is not None
        conditions = [Snapshot.source_id == source.id]
        if scoped:
            conditions.append(
                Snapshot.details["issuer_id"].astext.in_([str(i) for i in issuer_ids or []])
            )
        latest = await session.scalar(
            select(Snapshot)
            .where(*conditions)
            .order_by(Snapshot.retrieved_at.desc(), Snapshot.id)
            .limit(1)
        )
        success = await session.scalar(
            select(Snapshot)
            .where(*conditions, Snapshot.ingestion_status == "success")
            .order_by(Snapshot.retrieved_at.desc(), Snapshot.id)
            .limit(1)
        )
        result.append(
            MarketSourceView(
                id=source.id,
                name=source.name,
                institution=source.provider,
                source_url=success.source_url
                if scoped and success
                else latest.source_url
                if scoped and latest
                else source.dataset_url,
                availability=(
                    "failed_to_retrieve"
                    if latest and latest.ingestion_status == "failed"
                    else "available"
                    if success
                    else "not_yet_checked"
                )
                if scoped
                else source.availability,
                last_ingestion_status=latest.ingestion_status if latest else "not_yet_checked",
                last_error=latest.error_details
                if latest and latest.ingestion_status == "failed"
                else None,
                last_attempt_at=latest.retrieved_at if latest else None,
                last_success_at=success.retrieved_at if success else None,
                refresh_interval_hours=get_settings().capital_markets_max_age_hours,
                stale=snapshot_stale(success)
                or bool(latest and latest.ingestion_status == "failed"),
                latest_snapshot=snapshot_view(success) if success else None,
            )
        )
    return result


def issuer_view(
    issuer: SecuritiesIssuer,
    match: IssuerCompanyMatch | None = None,
    record: SourceRecord | None = None,
    details: SourceRecord | None = None,
) -> IssuerView:
    raw = record.raw_payload if record else {}
    detail_raw = details.raw_payload if details else {}
    contact: dict[str, Any] = {
        "institutional_email": optional(raw.get("Correo electronico", "")),
        "address": optional(raw.get("Direccion", "")),
        "city": optional(raw.get("Ciudad", "")),
        "phone": optional(raw.get("Teléfono", "")),
        "website": optional(raw.get("Página web", "")),
        "social_networks": [],
    }
    if details:
        for key, field in [
            ("institutional_email", "Correo institucional"),
            ("address", "Dirección"),
            ("city", "Ciudad"),
            ("phone", "Teléfono"),
            ("website", "Web"),
        ]:
            contact[key] = optional(detail_raw.get(field, ""))
        social = detail_raw.get("social_urls") or (
            [detail_raw["Redes Sociales"]] if optional(detail_raw.get("Redes Sociales", "")) else []
        )
        contact["social_networks"] = social
    board = detail_raw.get("Nro. Miembros Junta Directiva", "")
    administration = {
        "board_members_count": int(board)
        if board.isascii() and board.isdigit() and int(board) <= 1000
        else None,
        "legal_representative": optional(detail_raw.get("Representante Legal principal", "")),
        "rnve_information_representative": optional(
            detail_raw.get(
                "Representante Legal principal responsable de la informacion presentada al RNVE", ""
            )
        ),
    }
    return IssuerView.model_validate(
        {
            **{k: getattr(issuer, k) for k in IssuerView.model_fields if hasattr(issuer, k)},
            "source_url": DIRECTORY_URL,
            "snapshot_id": issuer.last_snapshot_id,
            "regulator_entity_type_description": optional(
                raw.get("Descripción tipo de entidad", "")
                or re.sub(r"^[0-9]{1,3}\s*[-–]\s*", "", detail_raw.get("Tipo Entidad:", ""))
            ),
            "contacts": contact,
            "administration": administration,
            "administration_source_url": details.source_url if details else None,
            "administration_retrieved_at": details.retrieved_at if details else None,
            "contacts_source_url": details.source_url
            if details
            else record.source_url
            if record
            else None,
            "contacts_retrieved_at": details.retrieved_at
            if details
            else record.retrieved_at
            if record
            else None,
            "match_method": match.match_method if match else None,
            "match_status": match.match_status if match else None,
        }
    )


async def issuer_views(
    session: AsyncSession, links: list[tuple[SecuritiesIssuer, IssuerCompanyMatch | None]]
) -> list[IssuerView]:
    ids = [issuer.raw_source_record_id for issuer, _ in links if issuer.raw_source_record_id]
    records = (
        {
            r.id: r
            for r in await session.scalars(select(SourceRecord).where(SourceRecord.id.in_(ids)))
        }
        if ids
        else {}
    )
    ranked = (
        select(
            SourceRecord.id,
            func.row_number()
            .over(
                partition_by=SourceRecord.external_record_id,
                order_by=(SourceRecord.retrieved_at.desc(), SourceRecord.id),
            )
            .label("position"),
        )
        .where(
            SourceRecord.source_id == DETAILS_SOURCE,
            SourceRecord.external_record_id.in_([i.external_id for i, _ in links]),
        )
        .subquery()
    )
    detail_rows = await session.scalars(
        select(SourceRecord)
        .join(ranked, SourceRecord.id == ranked.c.id)
        .where(ranked.c.position == 1)
    )
    details: dict[str | None, SourceRecord] = {}
    for detail_row in detail_rows:
        details.setdefault(detail_row.external_record_id, detail_row)
    ranked_attempts = (
        select(
            Snapshot.id,
            func.row_number()
            .over(
                partition_by=Snapshot.details["issuer_id"].astext,
                order_by=(Snapshot.retrieved_at.desc(), Snapshot.id),
            )
            .label("position"),
        )
        .where(
            Snapshot.source_id == DETAILS_SOURCE,
            Snapshot.details["issuer_id"].astext.in_([str(i.id) for i, _ in links]),
        )
        .subquery()
    )
    attempts = {
        row.details["issuer_id"]: row
        for row in await session.scalars(
            select(Snapshot)
            .join(ranked_attempts, Snapshot.id == ranked_attempts.c.id)
            .where(ranked_attempts.c.position == 1)
        )
    }
    result = []
    for issuer, match in links:
        detail = details.get(issuer.external_id)
        attempt = attempts.get(str(issuer.id))
        view = issuer_view(
            issuer,
            match,
            records.get(issuer.raw_source_record_id) if issuer.raw_source_record_id else None,
            detail,
        )
        failed = bool(attempt and attempt.ingestion_status == "failed")
        view.details_last_attempt_at = attempt.retrieved_at if attempt else None
        view.details_last_attempt_failed = failed
        if detail:
            old = (datetime.now(UTC) - detail.retrieved_at).total_seconds() > (
                get_settings().capital_markets_max_age_hours * 3600
            )
            view.details_availability = "stale" if old or failed else "available"
        elif failed:
            view.details_availability = "failed_to_retrieve"
        result.append(view)
    return result


async def company_links(
    session: AsyncSession, company: Company
) -> list[tuple[SecuritiesIssuer, IssuerCompanyMatch]]:
    await reconcile(session, company)
    result = await session.execute(
        select(SecuritiesIssuer, IssuerCompanyMatch)
        .join(IssuerCompanyMatch, IssuerCompanyMatch.issuer_id == SecuritiesIssuer.id)
        .where(
            IssuerCompanyMatch.company_id == company.id,
            IssuerCompanyMatch.match_status != MatchStatus.REJECTED,
        )
        .order_by(SecuritiesIssuer.issuer_name, SecuritiesIssuer.id)
    )
    return [(issuer, match) for issuer, match in result.all()]


async def instrument_views(
    session: AsyncSession,
    issuer_ids: list[UUID],
    page: int = 1,
    page_size: int = 10,
    category: SecurityCategory | None = None,
    exchange: str | None = None,
    listing_status: ListingStatus | None = None,
) -> SecuritiesPage:
    query = (
        select(SecurityInstrument, Snapshot, SourceRecord)
        .join(Snapshot, Snapshot.id == SecurityInstrument.last_snapshot_id)
        .join(SourceRecord, SourceRecord.id == SecurityInstrument.source_record_id)
        .where(SecurityInstrument.issuer_id.in_(issuer_ids))
    )
    unfiltered_total = int(
        await session.scalar(
            select(func.count()).select_from(
                query.with_only_columns(SecurityInstrument.id).subquery()
            )
        )
        or 0
    )
    if category:
        query = query.where(SecurityInstrument.security_category == category)
    if exchange:
        query = query.where(SecurityInstrument.exchange == exchange.upper())
    if listing_status:
        query = query.where(SecurityInstrument.listing_status == listing_status)
    total = int(
        await session.scalar(
            select(func.count()).select_from(
                query.with_only_columns(SecurityInstrument.id).subquery()
            )
        )
        or 0
    )
    records = (
        await session.execute(
            query.order_by(SecurityInstrument.security_name, SecurityInstrument.id)
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        )
    ).all()
    checked = (
        await session.scalar(
            select(Snapshot)
            .where(
                Snapshot.source_id == SECURITIES_SOURCE,
                Snapshot.ingestion_status == "success",
                Snapshot.details["issuer_id"].astext.in_([str(i) for i in issuer_ids]),
            )
            .order_by(Snapshot.retrieved_at.desc())
            .limit(1)
        )
        if issuer_ids
        else None
    )
    attempt = (
        await session.scalar(
            select(Snapshot)
            .where(
                Snapshot.source_id == SECURITIES_SOURCE,
                Snapshot.details["issuer_id"].astext.in_([str(i) for i in issuer_ids]),
            )
            .order_by(Snapshot.retrieved_at.desc(), Snapshot.id)
            .limit(1)
        )
        if issuer_ids
        else None
    )
    failed = bool(attempt and attempt.ingestion_status == "failed")
    items = [
        InstrumentView.model_validate(
            {
                **{
                    k: getattr(instrument, k)
                    for k in InstrumentView.model_fields
                    if hasattr(instrument, k)
                },
                "source_url": record.source_url,
                "snapshot_id": snapshot.id,
                "source_values": record.raw_payload,
                "stale": snapshot_stale(snapshot)
                or failed
                or bool(checked and snapshot.id != checked.id),
                "observation_status": "previously_observed"
                if checked and snapshot.id != checked.id
                else "present_in_latest_report",
                "quality_notes": [
                    f"Revisar valor original de fuente: {raw_field}"
                    for raw_field, normalized_field in (
                        ("Monto Autorizado", "authorized_amount"),
                        ("Inscrito RNVE Fecha", "rnve_registration_date"),
                        ("Inscrito BVC Fecha", "bvc_registration_date"),
                    )
                    if optional(record.raw_payload.get(raw_field, ""))
                    and getattr(instrument, normalized_field) is None
                ],
            }
        )
        for instrument, snapshot, record in records[:page_size]
    ]
    return SecuritiesPage(
        total=total,
        unfiltered_total=unfiltered_total,
        items=items,
        page=page,
        page_size=page_size,
        has_more=len(records) > page_size,
        availability="stale"
        if checked and (snapshot_stale(checked) or failed)
        else "available"
        if checked
        else "failed_to_retrieve"
        if failed
        else "not_yet_checked",
    )


def summary(status: RegistrationStatus, potential: bool, debt: bool, stale: bool) -> str:
    if potential:
        value = (
            "Se identificó una posible coincidencia con un emisor, pendiente "
            "de verificación de identidad."
        )
    elif status == RegistrationStatus.ACTIVE:
        value = "La empresa figura como emisor vigente en la fuente RNVE consultada."
        if debt:
            value += " Se identificaron valores de deuda registrados."
    elif status == RegistrationStatus.CANCELLED:
        value = (
            "La fuente consultada reporta una inscripción cancelada en RNVE; "
            "no es una conclusión sobre todos los registros históricos."
        )
    elif status == RegistrationStatus.HISTORICAL:
        value = (
            "Existe evidencia histórica de registro; no se ha confirmado una "
            "inscripción vigente en el directorio actual."
        )
    elif status == RegistrationStatus.NOT_FOUND:
        value = (
            "La empresa no fue encontrada por NIT en la última consulta "
            "completa del directorio vigente RNVE. Esto no descarta registros "
            "históricos ni estructuras con identificadores especiales."
        )
    else:
        value = "No hay evidencia suficiente para determinar el registro RNVE de esta empresa."
    value += " No se ha verificado un listado vigente de acciones en la BVC."
    return value


async def company_profile(
    session: AsyncSession,
    company: Company,
    retriever: SummaryRetriever | None = None,
    securities_retriever: SecuritiesRetriever | None = None,
    force_refresh: bool = False,
    refresh_source: str | None = None,
) -> CapitalMarketsProfile:
    refresh_after = datetime.now(UTC) if force_refresh else None
    links = await company_links(session, company)
    if retriever or securities_retriever:
        verified_issuers = [i for i, m in links if m.match_status == MatchStatus.VERIFIED]
        # Release reconciliation's global lock before any network wait.
        await session.commit()
        for issuer in verified_issuers[:2]:
            await session.refresh(issuer)
            if retriever and refresh_source in (None, DETAILS_SOURCE):
                await refresh_details(session, issuer, retriever, refresh_after)
            if securities_retriever and refresh_source in (None, SECURITIES_SOURCE):
                await session.refresh(issuer)
                await refresh_securities(session, issuer, securities_retriever, refresh_after)
        # A failed import rolls back and expires ORM objects; reload before serialization.
        await session.refresh(company)
        links = await company_links(session, company)
    sources = await source_views(
        session, [i.id for i, m in links if m.match_status == MatchStatus.VERIFIED]
    )
    directory = await session.scalar(
        select(Snapshot)
        .where(Snapshot.source_id == ISSUER_SOURCE, Snapshot.ingestion_status == "success")
        .order_by(Snapshot.retrieved_at.desc(), Snapshot.id)
        .limit(1)
    )
    issuer_source = next(s for s in sources if s.id == ISSUER_SOURCE)
    verified = [(i, m) for i, m in links if m.match_status == MatchStatus.VERIFIED]
    potential = bool(links and not verified)
    status = verified[0][0].registration_status if verified else RegistrationStatus.UNKNOWN
    source_nit_present = (
        bool(
            await session.scalar(
                select(func.count())
                .select_from(SecuritiesIssuer)
                .where(SecuritiesIssuer.nit == company.nit)
            )
        )
        if company.nit
        else False
    )
    # No false current negatives from incomplete/stale/failed snapshots or special identifiers.
    if (
        not links
        and not source_nit_present
        and directory
        and directory.details.get("complete_current")
        and directory.details.get("corporate_nits_validated")
        and not issuer_source.stale
        and company.nit
        and len(company.nit) == 9
        and not any(
            word in normalize_name(company.legal_form or "")
            for word in ("FIDUC", "FONDO", "PATRIMON", "EXTRANJ")
        )
    ):
        status = RegistrationStatus.NOT_FOUND
    instruments = await instrument_views(session, [i.id for i, _ in verified])
    # Compute summary from all stored instruments, not just the first displayed page.
    debt = bool(
        await session.scalar(
            select(func.count())
            .select_from(SecurityInstrument)
            .where(
                SecurityInstrument.issuer_id.in_([i.id for i, _ in verified]),
                SecurityInstrument.security_category.in_(
                    [
                        SecurityCategory.BONDS,
                        SecurityCategory.PAPER,
                        SecurityCategory.DEBT,
                        SecurityCategory.SECURITIZED,
                    ]
                ),
            )
        )
    )
    stale = bool(directory and issuer_source.stale) or any(
        [snapshot_stale(await session.get(Snapshot, i.last_snapshot_id)) for i, _ in verified]
    )
    stale = stale or instruments.availability == "stale"
    result = CapitalMarketsProfile(
        company_id=company.id,
        rnve=RnveFinding(
            status=status,
            issuer_name=verified[0][0].issuer_name if verified else None,
            issuer_code=verified[0][0].regulator_entity_code if verified else None,
            match_status="verified" if verified else "potential" if potential else "unresolved",
            checked_snapshot_id=verified[0][0].last_snapshot_id
            if verified
            else directory.id
            if directory
            else None,
        ),
        exchange_listing=ExchangeFinding(),
        ownership=OwnershipFinding(),
        issuers=await issuer_views(session, [(i, m) for i, m in links]),
        instruments=instruments.items,
        securities_availability=instruments.availability,
        sources=sources,
        last_checked_at=verified[0][0].last_verified_at
        if verified
        else directory.retrieved_at
        if directory
        else None,
        stale=stale,
        summary=summary(status, potential, debt, stale),
        limitations=[
            "La forma jurídica proviene de RUES y no determina propiedad pública o privada.",
            (
                "RNVE no equivale a acciones listadas. Los códigos ANN no se "
                "convierten en ticker o ISIN."
            ),
            (
                "Las fechas BVC de SFC son eventos de inscripción, no verificación "
                "de negociación vigente."
            ),
            "Los candidatos por nombre y las matrículas con NIT compartido requieren revisión.",
        ],
    )
    await session.commit()
    return result


async def issuer_search(session: AsyncSession, query: str, page: int, page_size: int) -> IssuerPage:
    statement = select(SecuritiesIssuer)
    if query:
        if looks_like_nit(query):
            statement = statement.where(SecuritiesIssuer.nit == normalize_nit(query).number)
        else:
            statement = statement.where(
                SecuritiesIssuer.normalized_name.contains(normalize_name(query), autoescape=True)
            )
    rows = list(
        await session.scalars(
            statement.order_by(SecuritiesIssuer.normalized_name, SecuritiesIssuer.id)
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        )
    )
    return IssuerPage(
        items=await issuer_views(session, [(i, None) for i in rows[:page_size]]),
        page=page,
        page_size=page_size,
        has_more=len(rows) > page_size,
    )
