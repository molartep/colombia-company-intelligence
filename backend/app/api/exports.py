from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.db.session import get_session
from app.integrations.capital_markets import service as capital
from app.integrations.capital_markets.types import MatchStatus
from app.models.entities import Company, SourceRecord
from app.schemas.secop import ContractStatus
from app.services import secop
from app.services.companies import profile
from app.services.currency import ReferenceRates, presentation_rate
from app.services.exports import (
    IDENTITY_FIELDS,
    INSTRUMENT_FIELDS,
    ISSUER_FIELDS,
    MAX_ROWS,
    QUOTE_FIELDS,
    converted,
    download,
    project,
)

router = APIRouter()


class ExportOptions(BaseModel):
    format: Literal["csv", "json"] = "json"
    run_id: UUID | None = None
    status: ContractStatus | None = None
    raw_status: str | None = Field(None, max_length=300)
    entity: str | None = Field(None, max_length=1000)
    year: int | None = Field(None, ge=1990, le=2100)
    missing_signature_date: bool = False
    modality: str | None = Field(None, max_length=500)
    q: str = Field("", max_length=160)
    sort: Literal["date", "value"] = "date"
    direction: Literal["asc", "desc"] = "desc"
    fx_mode: Literal["cop", "reference", "manual"] = "cop"
    manual_rate: str | None = Field(None, max_length=25)
    rate_date: date | None = None


@router.get("/api/v1/companies/{company_id}/exports/{scope}")
async def export_company(
    company_id: UUID,
    scope: Literal["research", "contracts"],
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    options: Annotated[ExportOptions, Query()],
) -> Response:
    if options.year is not None and options.missing_signature_date:
        raise HTTPException(422, "Choose a year or missing dates, not both.")
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "Company not found.")
    data = (await profile(session, company)).model_dump(mode="json")
    screening = await secop.view(session, company)
    rate = await presentation_rate(
        cast(ReferenceRates, request.app.state.reference_rates),
        options.fx_mode,
        options.manual_rate,
        options.rate_date,
    )
    metadata: dict[str, Any] = {
        "schema_version": "1.0",
        "scope": scope,
        "exported_at": datetime.now(UTC).isoformat(),
        "company": project(data, IDENTITY_FIELDS),
        "screening": screening.model_dump(mode="json", exclude={"query_metadata"}),
        "filters": options.model_dump(
            mode="json", exclude={"format", "fx_mode", "manual_rate", "rate_date"}
        ),
        "presentation_rate": rate.model_dump(mode="json") if rate else None,
        "warnings": [
            *screening.warnings,
            "Public projections only; missing evidence is not clearance.",
            "COP for SECOP is an application convention, not a source currency field.",
            "USD is a presentation estimate, not historical FX or a payment/revenue amount.",
        ],
        "row_limit": MAX_ROWS,
        "truncated": False,
    }
    rows = []
    if scope == "contracts":
        if not screening.summary or not screening.run_id:
            raise HTTPException(409, "No successful screening snapshot is available to export.")
        # The UI pins the displayed snapshot. Reject a superseded run instead of silently
        # exporting rows with freshness metadata for a different run.
        if options.run_id and options.run_id != screening.run_id:
            raise HTTPException(409, "Screening changed. Reload results before exporting.")
        filters = options.model_dump(
            include={
                "status",
                "raw_status",
                "entity",
                "year",
                "missing_signature_date",
                "modality",
                "q",
                "sort",
                "direction",
            }
        )
        result = await secop.contracts_page(
            session, company, 1, MAX_ROWS + 1, run_id=screening.run_id, **filters
        )
        if result.total > MAX_ROWS:
            raise HTTPException(413, "Export exceeds 1,000 rows. Narrow the filters.")
        rows = [converted(c.model_dump(mode="json"), "value", rate) for c in result.items]
        metadata["filtered_total"] = result.total
        metadata["snapshot_run_id"] = str(result.run_id)
    else:
        rows.append(
            {
                "record_type": "registration",
                **project(
                    data,
                    (
                        *IDENTITY_FIELDS,
                        "registration_status",
                        "primary_ciiu",
                        "registration",
                        "attributes",
                        "retrieved_at",
                        "source_updated_at",
                        "dataset_updated_at",
                        "sources",
                        "resolution_note",
                        "conflicting_registration_count",
                    ),
                ),
            }
        )
        evidence = await session.scalars(
            select(SourceRecord)
            .where(SourceRecord.company_id == company_id)
            .order_by(SourceRecord.retrieved_at.desc())
            .limit(51)
        )
        records = list(evidence)
        if len(records) > 50:
            metadata["warnings"].append("Evidence history limited to the latest 50 versions.")
        for r in records[:50]:
            rows.append(
                {
                    "record_type": "evidence",
                    "id": str(r.id),
                    "source_id": r.source_id,
                    "source_identifier": r.external_record_id,
                    "source_url": r.source_url,
                    "retrieved_at": r.retrieved_at.isoformat(),
                }
            )
        # No retrievers: read local evidence without making export refresh any source.
        markets = await capital.company_profile(session, company)
        metadata["capital_markets"] = markets.model_dump(
            mode="json",
            include={
                "rnve",
                "ownership",
                "securities_availability",
                "sources",
                "stale",
                "limitations",
            },
        )
        for issuer in markets.issuers:
            rows.append(
                {"record_type": "issuer", **project(issuer.model_dump(mode="json"), ISSUER_FIELDS)}
            )
        links = await capital.company_links(session, company)
        verified_ids = [i.id for i, m in links if m.match_status == MatchStatus.VERIFIED]
        instruments = await capital.instrument_views(session, verified_ids, 1, MAX_ROWS + 1)
        for item in instruments.items:
            rows.append(
                {
                    "record_type": "security",
                    **converted(
                        project(item.model_dump(mode="json"), INSTRUMENT_FIELDS),
                        "authorized_amount",
                        rate,
                    ),
                }
            )
        for quote in markets.exchange_listing.quotes:
            rows.append(
                {
                    "record_type": "quote",
                    **converted(
                        project(quote.model_dump(mode="json"), QUOTE_FIELDS), "last_price", rate
                    ),
                }
            )
        metadata["warnings"].extend(markets.limitations)
        if instruments.has_more:
            raise HTTPException(413, "Research exceeds the export row limit.")
    return download({**metadata, "rows": rows}, options.format, f"{scope}-{company_id}")
