import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import SourceError
from app.core.normalization import Nit, compact_name, normalize_name
from app.integrations.rues.adapter import (
    API_URL,
    DATASET_URL,
    FIELD_MAP,
    PUBLIC_FIELDS,
    SOURCE_ID,
    RuesDataSource,
    map_record,
    payload_hash,
    source_datetime,
)
from app.models.entities import Company, CompanyAlias, DataSource, SourceRecord
from app.schemas.api import AttributeState, Profile, RecordView, SearchItem, SearchPage, SourceView
from app.services.identity import classify

COMPANY_FIELDS = [
    "nit",
    "verification_digit",
    "legal_name",
    "legal_form",
    "registration_status",
    "primary_ciiu",
]
RANK = {
    name: i
    for i, name in enumerate(
        ["exact_nit", "exact_legal_name", "normalized_name", "partial_name", "unresolved"]
    )
}


async def ensure_source(session: AsyncSession) -> DataSource:
    await session.execute(
        insert(DataSource)
        .values(
            id=SOURCE_ID,
            name="RUES · Confecámaras",
            provider="Confecámaras",
            description=(
                "Official Colombian business registration records, "
                "including natural persons and ESALs."
            ),
            dataset_url=DATASET_URL,
            api_url=API_URL,
            enabled=True,
            availability="not_yet_checked",
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    source = await session.get(DataSource, SOURCE_ID)
    assert source is not None
    return source


async def persist(session: AsyncSession, row: dict[str, Any]) -> Company:
    mapped = map_record(row)
    key = SOURCE_ID + ":" + mapped["external_record_id"]
    values = {field: mapped[field] for field in COMPANY_FIELDS}
    values["normalized_name"] = normalize_name(mapped["legal_name"])
    await session.execute(
        insert(Company)
        .values(id=uuid.uuid4(), identity_key=key, **values)
        .on_conflict_do_nothing(index_elements=["identity_key"])
    )
    company = (
        await session.scalars(select(Company).where(Company.identity_key == key).with_for_update())
    ).one()
    for field, value in values.items():
        setattr(company, field, value)
    company.updated_at = datetime.now(UTC)
    await session.execute(
        insert(CompanyAlias)
        .values(
            id=uuid.uuid4(),
            company_id=company.id,
            name=mapped["legal_name"],
            normalized_name=values["normalized_name"],
            alias_type="source_legal_name",
            source_id=SOURCE_ID,
        )
        .on_conflict_do_nothing()
    )
    await session.execute(
        insert(SourceRecord)
        .values(
            id=uuid.uuid4(),
            source_id=SOURCE_ID,
            company_id=company.id,
            external_record_id=mapped["external_record_id"],
            source_nit=row.get("nit"),
            raw_payload=row,
            payload_hash=payload_hash(row),
            retrieved_at=datetime.now(UTC),
            source_updated_at=source_datetime(row.get("fecha_actualizacion")),
            source_url=DATASET_URL,
        )
        .on_conflict_do_update(
            index_elements=["source_id", "external_record_id", "payload_hash"],
            set_={"retrieved_at": datetime.now(UTC)},
        )
    )
    await session.flush()
    return company


async def search_companies(
    session: AsyncSession,
    adapter: RuesDataSource,
    query: str,
    nit: Nit | None,
    page: int,
    page_size: int,
) -> SearchPage:
    source = await ensure_source(session)
    if not source.enabled:
        raise SourceError("source_disabled", "The official source is currently disabled.")
    offset = (page - 1) * page_size
    stale, warning = False, None
    try:
        metadata = await adapter.metadata()
        rows = await (
            adapter.search_by_nit(nit.number, page_size + 1, offset)
            if nit
            else adapter.search_by_name(query, page_size + 1, offset)
        )
        source.last_checked_at = datetime.now(UTC)
        stamp = metadata.get("rowsUpdatedAt")
        source.last_updated_at = (
            datetime.fromtimestamp(stamp, UTC) if isinstance(stamp, (int, float)) else None
        )
        source.availability = "available"
        # Only one bounded page is cached, never a background copy of the registry.
        companies = [await persist(session, row) for row in rows[:page_size]]
        has_more = len(rows) > page_size
        if not rows and not nit:
            # Search-only compact keys recover spacing variants without changing identity keys.
            normalized = normalize_name(query)
            compact = compact_name(query)
            cached = select(CompanyAlias.company_id).where(
                or_(
                    CompanyAlias.normalized_name == normalized,
                    func.replace(
                        CompanyAlias.normalized_name, literal_column("' '"), literal_column("''")
                    ).startswith(compact, autoescape=True),
                )
            )
            companies = list(
                await session.scalars(
                    select(Company)
                    .where(
                        or_(
                            Company.normalized_name == normalized,
                            func.replace(
                                Company.normalized_name, literal_column("' '"), literal_column("''")
                            ).startswith(compact, autoescape=True),
                            Company.id.in_(cached),
                        )
                    )
                    .order_by(Company.normalized_name, Company.id)
                    .offset(offset)
                    .limit(page_size + 1)
                )
            )
            has_more = len(companies) > page_size
            companies = companies[:page_size]
            if companies:
                stale = True
                warning = (
                    "Source returned no current matches; showing cached normalized-name candidates."
                )
    except SourceError as exc:
        source.last_checked_at = datetime.now(UTC)
        source.availability = "failed_to_retrieve"
        condition = (
            Company.nit == nit.number
            if nit
            else or_(
                Company.normalized_name.startswith(normalize_name(query), autoescape=True),
                func.replace(
                    Company.normalized_name, literal_column("' '"), literal_column("''")
                ).startswith(compact_name(query), autoescape=True),
                Company.id.in_(
                    select(CompanyAlias.company_id).where(
                        or_(
                            CompanyAlias.normalized_name.startswith(
                                normalize_name(query), autoescape=True
                            ),
                            func.replace(
                                CompanyAlias.normalized_name,
                                literal_column("' '"),
                                literal_column("''"),
                            ).startswith(compact_name(query), autoescape=True),
                        )
                    )
                ),
            )
        )
        companies = list(
            await session.scalars(
                select(Company)
                .where(condition)
                .order_by(Company.normalized_name, Company.id)
                .offset(offset)
                .limit(page_size + 1)
            )
        )
        has_more = len(companies) > page_size
        companies = companies[:page_size]
        await session.commit()
        if not companies:
            raise exc
        stale, warning = (
            True,
            f"{exc.code}: official source failed; showing previously retrieved records.",
        )
    await session.commit()
    ranked_records = (
        select(
            SourceRecord.id,
            func.row_number()
            .over(
                partition_by=SourceRecord.company_id,
                order_by=(SourceRecord.retrieved_at.desc(), SourceRecord.id),
            )
            .label("position"),
        )
        .where(SourceRecord.company_id.in_([c.id for c in companies]))
        .subquery()
    )
    latest_records = (
        {
            r.company_id: r
            for r in await session.scalars(
                select(SourceRecord)
                .join(ranked_records, SourceRecord.id == ranked_records.c.id)
                .where(ranked_records.c.position == 1)
            )
        }
        if companies
        else {}
    )
    items = []
    for company in companies:
        latest = latest_records.get(company.id)
        registration = latest.raw_payload if latest else {}
        match_type, evidence = classify(company, query, nit)
        if ":hash:" in company.identity_key:
            match_type = "unresolved"
            evidence.append(
                "Stable source row ID missing; this record cannot be resolved across updates."
            )
        items.append(
            SearchItem.model_validate(
                {
                    **{
                        field: getattr(company, field)
                        for field in SearchItem.model_fields
                        if hasattr(company, field)
                    },
                    "registration_number": registration.get("matricula"),
                    "chamber": registration.get("camara_comercio"),
                    "chamber_code": registration.get("codigo_camara"),
                    "registration_date": registration.get("fecha_matricula") or None,
                    "renewal_date": registration.get("fecha_renovacion") or None,
                    "match_type": match_type,
                    "evidence": evidence,
                    "data_source": SOURCE_ID,
                }
            )
        )
    items.sort(key=lambda c: (RANK[c.match_type], normalize_name(c.legal_name), str(c.id)))
    return SearchPage(
        items=items, page=page, page_size=page_size, has_more=has_more, stale=stale, warning=warning
    )


async def records_for(session: AsyncSession, company_id: uuid.UUID) -> list[SourceRecord]:
    return list(
        await session.scalars(
            select(SourceRecord)
            .where(SourceRecord.company_id == company_id)
            .order_by(SourceRecord.retrieved_at.desc(), SourceRecord.id)
        )
    )


def serialize_record(record: SourceRecord) -> RecordView:
    return RecordView(
        id=record.id,
        external_record_id=record.external_record_id,
        source_id=record.source_id,
        source_url=record.source_url,
        retrieved_at=record.retrieved_at,
        source_updated_at=record.source_updated_at,
        payload_hash=record.payload_hash,
        fields={k: v for k, v in record.raw_payload.items() if k in PUBLIC_FIELDS},
        field_mapping=FIELD_MAP,
    )


async def profile(session: AsyncSession, company: Company) -> Profile:
    records = await records_for(session, company.id)
    latest = records[0] if records else None
    row = latest.raw_payload if latest else {}
    source = await session.get(DataSource, SOURCE_ID)
    attrs = {}
    for attr, field in FIELD_MAP.items():
        value = getattr(company, attr, row.get(field))
        attrs[attr] = AttributeState(
            state="present" if value else "missing_from_record",
            source_field=field,
            record_id=latest.id if latest else None,
        )
        if row.get(field) and value is None:
            attrs[attr].state = "ambiguous"
            attrs[attr].note = "Source value is malformed and could not be normalized."
    for attr in ("department", "municipality", "ciiu_description"):
        attrs[attr] = AttributeState(state="unavailable_in_source")
    for attr in ("securities_listing", "financials", "screening", "ownership"):
        attrs[attr] = AttributeState(state="not_yet_checked")
    conflict_count = 0
    if company.nit:
        conflict_count = int(
            await session.scalar(
                select(func.count())
                .select_from(Company)
                .where(Company.nit == company.nit, Company.id != company.id)
            )
            or 0
        )
    return Profile(
        **{
            field: getattr(company, field)
            for field in [
                *COMPANY_FIELDS,
                "id",
                "department",
                "municipality",
                "created_at",
                "updated_at",
            ]
        },
        registration={
            k: row.get(FIELD_MAP[k])
            for k in [
                "registration_number",
                "chamber",
                "chamber_code",
                "registration_date",
                "renewal_date",
                "last_renewed_year",
                "cancellation_date",
            ]
        },
        attributes=attrs,
        sources=[SourceView.model_validate(source)] if source else [],
        retrieved_at=latest.retrieved_at if latest else None,
        source_updated_at=latest.source_updated_at if latest else None,
        dataset_updated_at=source.last_updated_at if source else None,
        resolution_note=(
            "Registration-scoped profile. Shared NITs and similar names "
            "are never automatically merged."
        ),
        conflicting_registration_count=conflict_count,
    )
