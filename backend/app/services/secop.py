import asyncio
import logging
import math
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Text, extract, func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import SourceError
from app.integrations.rues.adapter import payload_hash
from app.integrations.secop.adapter import (
    API_PATH,
    DATASET_URL,
    MATCHING_POLICY,
    SOURCE_ID,
    SecopSource,
    supplier_variants,
)
from app.integrations.secop.normalize import (
    CURRENCY_POLICY,
    CURRENCY_WARNING,
    MATCHING_WARNING,
    SUMMARY_POLICY,
    WARNINGS,
    aggregate,
    apply_currency_policy,
    verified_contracts,
)
from app.models.entities import Company, DataSource, SourceRecord
from app.models.secop import ScreeningContract, ScreeningRun, SecopContract
from app.schemas.secop import ContractPage, ContractView, ScreeningSummary, ScreeningView

logger = logging.getLogger(__name__)


async def runs(
    session: AsyncSession, company: Company
) -> tuple[ScreeningRun | None, ScreeningRun | None]:
    query = (
        select(ScreeningRun)
        .where(
            ScreeningRun.company_id == company.id,
            ScreeningRun.source_id == SOURCE_ID,
            ScreeningRun.canonical_nit == company.nit,
            ScreeningRun.query_metadata["verification_digit"].astext == company.verification_digit,
        )
        .order_by(ScreeningRun.started_at.desc(), ScreeningRun.id.desc())
    )
    latest = await session.scalar(query.limit(1))
    success = await session.scalar(query.where(ScreeningRun.status == "completed").limit(1))
    return latest, success


async def view(session: AsyncSession, company: Company) -> ScreeningView:
    settings = get_settings()
    latest, success = await runs(session, company)
    age = (
        max(0, int((datetime.now(UTC) - success.completed_at).total_seconds()))
        if success and success.completed_at
        else None
    )
    ttl = settings.secop_cache_hours * 3600
    outcome = "not_screened"
    if not company.nit or len(company.nit) != 9 or ":hash:" in company.identity_key:
        outcome = "missing_nit"
        success = None
    elif latest:
        if success:
            outcome = (
                "stale"
                if (age is not None and (age >= ttl or latest.status == "failed"))
                or success.query_metadata.get("matching_policy") != MATCHING_POLICY
                else (
                    "completed_with_matches"
                    if success.summary and success.summary["total_contracts"]
                    else "completed_no_matches"
                )
            )
        elif latest.status == "failed":
            outcome = (
                "failed"
                if latest.error_code
                in ("source_schema_changed", "secop_limit_exceeded", "source_invalid_response")
                else "source_unavailable"
            )
        else:
            outcome = "running"
    in_progress = False
    if company.nit and outcome != "missing_nit":
        in_progress = not await session.scalar(
            text("SELECT pg_try_advisory_xact_lock_shared(hashtextextended(:key, 0))"),
            {"key": "secop:" + str(company.id)},
        )
        if in_progress:
            outcome = "running"
    summary = ScreeningSummary.model_validate(success.summary) if success else None
    if success and (
        success.query_metadata.get("currency_policy") != CURRENCY_POLICY
        or success.query_metadata.get("summary_policy") != SUMMARY_POLICY
    ):
        # Reinterpret existing verified local evidence without requerying the source or
        # altering the original run/raw payload/freshness timestamps.
        cached = await session.scalars(
            select(SecopContract)
            .join(ScreeningContract)
            .where(ScreeningContract.run_id == success.id)
        )
        summary = aggregate(
            [apply_currency_policy(ContractView.model_validate(c.normalized)) for c in cached]
        )
    warnings = [
        CURRENCY_WARNING
        if w.startswith("La fuente no publica moneda.")
        else MATCHING_WARNING
        if w.startswith("Solo se consultan variantes explícitas")
        else w
        for w in (success.warnings if success else WARNINGS)
    ]
    if success and success.query_metadata.get("matching_policy") != MATCHING_POLICY:
        warnings.append(
            "Actualiza la consulta para incluir NIT de diez dígitos con DV; "
            "la caché usa la regla anterior."
        )
    if latest and latest.error_code == "secop_limit_exceeded":
        warnings.append(
            "La consulta supera el límite seguro de filas. No se publican totales parciales."
        )
    if latest and latest.error_code == "source_changed":
        warnings.append("La fuente cambió durante la consulta; el resultado no se pudo completar.")
    return ScreeningView(
        company_id=company.id,
        company_name=company.legal_name,
        nit=company.nit,
        source_id=SOURCE_ID,
        source_url=DATASET_URL,
        outcome=outcome,
        run_id=success.id if success else (latest.id if latest else None),
        run_status="running" if in_progress else (latest.status if latest else None),
        last_attempted_at=latest.started_at if latest else None,
        last_successful_at=success.completed_at if success else None,
        source_updated_at=success.source_updated_at if success else None,
        cache_age_seconds=age,
        cache_ttl_seconds=ttl,
        summary=summary,
        warnings=warnings,
        error_code=latest.error_code if latest else None,
        query_metadata={
            **(success.query_metadata if success else {}),
            "currency_policy": CURRENCY_POLICY,
            "summary_policy": SUMMARY_POLICY,
        },
    )


async def refresh(session: AsyncSession, company: Company, source: SecopSource) -> ScreeningView:
    settings = get_settings()
    if not company.nit or len(company.nit) != 9 or ":hash:" in company.identity_key:
        return await view(session, company)
    # Cross-process, nonblocking lock held until transaction commit/rollback. Separate sources
    # can use this same lifecycle with their own lock namespace and source ID.
    key = "secop:" + str(company.id)
    locked = await session.scalar(
        text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
    )
    if not locked:
        raise HTTPException(409, "SECOP screening already in progress.")
    latest, _ = await runs(session, company)
    now = datetime.now(UTC)
    if latest and now - latest.started_at < timedelta(
        seconds=settings.refresh_min_interval_seconds
    ):
        remaining = (
            settings.refresh_min_interval_seconds - (now - latest.started_at).total_seconds()
        )
        raise HTTPException(
            429,
            "Wait before refreshing SECOP again.",
            headers={"Retry-After": str(max(1, math.ceil(remaining)))},
        )
    await session.execute(
        insert(DataSource)
        .values(
            id=SOURCE_ID,
            name="SECOP II — Contratos Electrónicos",
            provider="Colombia Compra Eficiente",
            description="Official electronic contracts; exact supplier NIT screening.",
            dataset_url=DATASET_URL,
            api_url="https://www.datos.gov.co" + API_PATH,
            availability="not_yet_checked",
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    run = ScreeningRun(
        company_id=company.id,
        source_id=SOURCE_ID,
        canonical_nit=company.nit,
        status="running",
        started_at=now,
        warnings=list(WARNINGS),
        query_metadata={
            "match_method": "exact_supplier_nit",
            "matching_policy": MATCHING_POLICY,
            "currency_policy": CURRENCY_POLICY,
            "summary_policy": SUMMARY_POLICY,
            "verification_digit": company.verification_digit,
            "variants": supplier_variants(company.nit, company.verification_digit),
            "row_cap": settings.secop_max_rows,
            "deduplication": "id_contrato/latest_ultima_actualizacion",
        },
    )
    session.add(run)
    await session.flush()
    try:
        async with asyncio.timeout(settings.secop_run_timeout):
            rows, updated = await source.fetch(
                company.nit, company.verification_digit, settings.secop_max_rows
            )
            contracts, excluded = verified_contracts(
                rows, company.nit, company.verification_digit, now
            )
            async with session.begin_nested():
                await persist_contracts(session, run.id, contracts, now)
        run.summary = aggregate([c for c, _ in contracts]).model_dump(mode="json")
        run.source_updated_at = updated
        run.query_metadata = {
            **run.query_metadata,
            "source_rows": len(rows),
            "excluded_rows_or_conflicts": excluded,
        }
        if excluded:
            run.warnings = [
                *run.warnings,
                f"Se excluyeron {excluded} filas o contratos ambiguos "
                "de los resultados verificados.",
            ]
        run.status = "completed"
    except (SourceError, TimeoutError) as exc:
        run.status = "failed"
        run.error_code = exc.code if isinstance(exc, SourceError) else "source_timeout"
        logger.warning("secop_screening_failed", extra={"error_code": run.error_code})
    run.completed_at = datetime.now(UTC)
    ds = await session.get(DataSource, SOURCE_ID)
    assert ds is not None
    ds.last_checked_at = run.completed_at
    ds.availability = "available" if run.status == "completed" else "failed_to_retrieve"
    if run.status == "completed":
        ds.last_updated_at = run.source_updated_at
    await session.commit()
    return await view(session, company)


async def contracts_page(
    session: AsyncSession,
    company: Company,
    page: int,
    page_size: int,
    status: str | None = None,
    entity: str | None = None,
    year: int | None = None,
    modality: str | None = None,
    q: str = "",
    sort: Literal["date", "value"] = "date",
    direction: Literal["asc", "desc"] = "desc",
    contract_id: str | None = None,
    run_id: UUID | None = None,
    raw_status: str | None = None,
    missing_signature_date: bool = False,
) -> ContractPage:
    _, run = await runs(session, company)
    if not company.nit or len(company.nit) != 9 or ":hash:" in company.identity_key:
        run = None
        if run_id:
            raise HTTPException(404, "A verified company identity is required for this snapshot.")
    if run_id:
        pinned = await session.get(ScreeningRun, run_id)
        if (
            not pinned
            or pinned.company_id != company.id
            or pinned.source_id != SOURCE_ID
            or pinned.canonical_nit != company.nit
            or pinned.query_metadata.get("verification_digit") != company.verification_digit
            or pinned.status != "completed"
        ):
            raise HTTPException(404, "Screening snapshot not found.")
        run = pinned
    if not run:
        return ContractPage(items=[], page=page, page_size=page_size, total=0, has_more=False)
    query = select(SecopContract).join(ScreeningContract).where(ScreeningContract.run_id == run.id)
    if contract_id:
        query = query.where(SecopContract.contract_id == contract_id)
    if status:
        query = query.where(SecopContract.status == status)
    if raw_status is not None:
        reported_status = func.coalesce(
            func.nullif(func.trim(SecopContract.normalized["raw_status"].astext), ""),
            "No informado",
        )
        query = query.where(reported_status == raw_status)
    if entity:
        query = query.where(SecopContract.buyer == entity)
    if missing_signature_date:
        query = query.where(SecopContract.signature_date.is_(None))
    elif year:
        query = query.where(extract("year", SecopContract.signature_date) == year)
    if modality:
        query = query.where(SecopContract.modality == modality)
    if q:
        query = query.where(
            func.strpos(func.lower(SecopContract.normalized.cast(Text)), q.lower()) > 0
        )
    count = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    col = SecopContract.value if sort == "value" else SecopContract.signature_date
    order = col.asc() if direction == "asc" else col.desc()
    items = await session.scalars(
        query.order_by(order.nulls_last(), SecopContract.contract_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    views = [
        apply_currency_policy(ContractView.model_validate(c.normalized)).model_copy(
            update={"retrieved_at": run.started_at}
        )
        for c in items
    ]
    return ContractPage(
        items=views,
        page=page,
        page_size=page_size,
        total=count,
        has_more=page * page_size < count,
        run_id=run.id,
    )


async def persist_contracts(
    session: AsyncSession,
    run_id: UUID,
    contracts: list[tuple[ContractView, dict[str, Any]]],
    retrieved: datetime,
) -> None:
    # Bounded bulk writes; repeated snapshots reuse both raw and normalized evidence.
    for offset in range(0, len(contracts), 200):
        batch = contracts[offset : offset + 200]
        await session.execute(
            insert(SourceRecord)
            .values(
                [
                    dict(
                        source_id=SOURCE_ID,
                        external_record_id=c.contract_id,
                        company_id=None,
                        source_nit=c.original_supplier_identifier,
                        raw_payload=row,
                        retrieved_at=retrieved,
                        source_updated_at=c.source_updated_at,
                        source_url=c.source_url,
                        payload_hash=payload_hash(row),
                    )
                    for c, row in batch
                ]
            )
            .on_conflict_do_nothing()
        )
        evidence = {
            (r.external_record_id, r.payload_hash): r.id
            for r in await session.scalars(
                select(SourceRecord).where(
                    SourceRecord.source_id == SOURCE_ID,
                    tuple_(SourceRecord.external_record_id, SourceRecord.payload_hash).in_(
                        [(c.contract_id, payload_hash(row)) for c, row in batch]
                    ),
                )
            )
        }
        projections = []
        for c, row in batch:
            c.evidence_id = evidence[(c.contract_id, payload_hash(row))]
            projections.append(
                dict(
                    evidence_id=c.evidence_id,
                    contract_id=c.contract_id,
                    buyer=c.buyer,
                    status=c.status,
                    modality=c.modality,
                    signature_date=c.signature_date,
                    value=c.value,
                    normalized=c.model_dump(mode="json"),
                )
            )
        await session.execute(insert(SecopContract).values(projections).on_conflict_do_nothing())
        ids = list(
            await session.scalars(
                select(SecopContract.id).where(
                    SecopContract.evidence_id.in_([c.evidence_id for c, _ in batch])
                )
            )
        )
        await session.execute(
            insert(ScreeningContract).values([dict(run_id=run_id, contract_id=cid) for cid in ids])
        )
