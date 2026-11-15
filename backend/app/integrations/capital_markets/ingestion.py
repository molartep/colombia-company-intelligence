import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import SourceError
from app.core.normalization import normalize_name
from app.integrations.capital_markets.matching import reconcile
from app.integrations.capital_markets.parsers import parse_issuers, parse_securities
from app.integrations.capital_markets.reports import BvcUnavailable, store_artifact
from app.integrations.capital_markets.types import (
    BVC_SOURCE,
    DIRECTORY_URL,
    ISSUER_SOURCE,
    SECURITIES_BASE,
    SECURITIES_SOURCE,
    ListingStatus,
    RegistrationStatus,
)
from app.models.capital_markets import (
    CapitalMarketsSourceSnapshot,
    SecuritiesIssuer,
    SecurityInstrument,
)
from app.models.entities import DataSource, SourceRecord


async def ensure_sources(session: AsyncSession) -> None:
    for key, name, url, description in [
        (
            ISSUER_SOURCE,
            "SFC · Registro Nacional de Valores y Emisores",
            DIRECTORY_URL,
            (
                "Official issuer export. Imported snapshots, independent of RUES "
                "legal form and ownership."
            ),
        ),
        (
            SECURITIES_SOURCE,
            "SFC · Valores inscritos",
            SECURITIES_BASE,
            (
                "Public issuer-specific registered-securities reports. A BVC "
                "registration date is not a current trading verification."
            ),
        ),
        (
            BVC_SOURCE,
            "Bolsa de Valores de Colombia · Listing corroboration",
            "https://www.bvc.com.co/",
            BvcUnavailable.explanation,
        ),
    ]:
        await session.execute(
            insert(DataSource)
            .values(
                id=key,
                name=name,
                description=description,
                provider="Bolsa de Valores de Colombia"
                if key == BVC_SOURCE
                else "Superintendencia Financiera de Colombia",
                dataset_url=url,
                api_url=None,
                enabled=True,
                availability="requires_authorized_source"
                if key == BVC_SOURCE
                else "not_yet_checked",
            )
            .on_conflict_do_nothing()
        )


async def raw_record(
    session: AsyncSession, source: str, external_id: str, raw: dict[str, str], url: str
) -> uuid.UUID:
    digest = hashlib.sha256(
        json.dumps(raw, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    return (
        await session.execute(
            insert(SourceRecord)
            .values(
                id=uuid.uuid4(),
                source_id=source,
                external_record_id=external_id,
                raw_payload=raw,
                payload_hash=digest,
                retrieved_at=datetime.now(UTC),
                source_url=url,
            )
            .on_conflict_do_update(
                index_elements=["source_id", "external_record_id", "payload_hash"],
                set_={"retrieved_at": datetime.now(UTC)},
            )
            .returning(SourceRecord.id)
        )
    ).scalar_one()


async def record_failure(
    session: AsyncSession,
    source_id: str,
    url: str,
    exc: Exception,
    content_hash: str | None = None,
    details: dict[str, str] | None = None,
) -> None:
    await session.rollback()
    await ensure_sources(session)
    source = await session.get(DataSource, source_id)
    assert source
    source.last_checked_at = datetime.now(UTC)
    source.availability = "failed_to_retrieve"
    session.add(
        CapitalMarketsSourceSnapshot(
            source_id=source_id,
            source_url=url,
            content_hash=content_hash,
            record_count=0,
            ingestion_status="failed",
            error_details=exc.code
            if isinstance(exc, SourceError)
            else f"{type(exc).__name__}: import rejected; prior data preserved.",
            details=details or {},
        )
    )
    await session.commit()


async def ingest_issuers(
    session: AsyncSession,
    content: bytes,
    *,
    nit_mode: Literal["preserve", "concatenated-dv"] = "preserve",
    registration_status: RegistrationStatus = RegistrationStatus.ACTIVE,
    complete_current: bool = False,
    expected_count: int | None = None,
) -> CapitalMarketsSourceSnapshot:
    digest = None
    try:
        if registration_status not in (
            RegistrationStatus.ACTIVE,
            RegistrationStatus.CANCELLED,
            RegistrationStatus.HISTORICAL,
        ):
            raise ValueError("Imports require an observed registration state.")
        if complete_current and (
            registration_status != RegistrationStatus.ACTIVE or not expected_count
        ):
            raise ValueError(
                "Complete-current requires an active unfiltered report and "
                "expected source row count."
            )
        rows, generated = parse_issuers(content, nit_mode)
        if expected_count is not None and len(rows) != expected_count:
            raise ValueError("Expected source count differs; incomplete report rejected.")
        now = datetime.now(UTC)
        if generated and (generated - now).total_seconds() > 300:
            raise ValueError("Report generation timestamp is in the future.")
        digest = store_artifact(content, get_settings().capital_markets_storage_dir)
        await session.execute(text("SELECT pg_advisory_xact_lock(770209)"))
        await ensure_sources(session)
        snapshot = CapitalMarketsSourceSnapshot(
            source_id=ISSUER_SOURCE,
            retrieved_at=now,
            source_url=DIRECTORY_URL,
            content_hash=digest,
            record_count=len(rows),
            ingestion_status="success",
            details={
                "complete_current": complete_current,
                "expected_count": expected_count,
                "observed_at": generated.isoformat() if generated else None,
                "nit_format": nit_mode,
                "registration_status": registration_status.value,
                "corporate_nits_validated": all(
                    r.identity_eligible for r in rows if r.entity_type not in {"092", "095", "141"}
                ),
            },
        )
        session.add(snapshot)
        await session.flush()
        new, changed = 0, 0
        for row in rows:
            issuer = await session.scalar(
                select(SecuritiesIssuer).where(
                    SecuritiesIssuer.source_id == ISSUER_SOURCE,
                    SecuritiesIssuer.external_id == row.external_id,
                )
            )
            if not issuer:
                issuer = SecuritiesIssuer(source_id=ISSUER_SOURCE, external_id=row.external_id)
                session.add(issuer)
                new += 1
            elif (
                issuer.nit != row.nit
                or issuer.issuer_name != row.issuer_name
                or issuer.registration_status != registration_status
            ):
                changed += 1
            issuer.nit, issuer.source_nit = row.nit, row.source_nit
            issuer.verification_digit, issuer.identity_eligible = (
                row.verification_digit,
                row.identity_eligible,
            )
            issuer.issuer_name, issuer.normalized_name = (
                row.issuer_name,
                normalize_name(row.issuer_name),
            )
            issuer.regulator_entity_type, issuer.regulator_entity_code = (
                row.entity_type,
                row.entity_code,
            )
            issuer.registration_status = registration_status
            issuer.last_verified_at, issuer.last_snapshot_id = now, snapshot.id
            issuer.raw_source_record_id = await raw_record(
                session, ISSUER_SOURCE, row.external_id, row.raw, DIRECTORY_URL
            )
        await session.flush()
        if complete_current:
            old = await session.scalars(
                select(SecuritiesIssuer).where(
                    SecuritiesIssuer.source_id == ISSUER_SOURCE,
                    SecuritiesIssuer.registration_status == RegistrationStatus.ACTIVE,
                    SecuritiesIssuer.last_snapshot_id != snapshot.id,
                )
            )
            for issuer in old:
                issuer.registration_status = RegistrationStatus.HISTORICAL
        snapshot.details = {**snapshot.details, "new_records": new, "changed_records": changed}
        source = await session.get(DataSource, ISSUER_SOURCE)
        assert source
        source.last_checked_at, source.availability = now, "available"
        await reconcile(session)
        await session.commit()
        return snapshot
    except Exception as exc:
        await record_failure(session, ISSUER_SOURCE, DIRECTORY_URL, exc, digest)
        raise


async def ingest_securities(
    session: AsyncSession, issuer: SecuritiesIssuer, content: bytes, url: str
) -> CapitalMarketsSourceSnapshot:
    digest = None
    issuer_key = str(issuer.id)
    try:
        rows, observed = parse_securities(content, issuer.issuer_name)
        now = datetime.now(UTC)
        if observed and (observed - now).total_seconds() > 300:
            raise ValueError("Report observation timestamp is in the future.")
        digest = store_artifact(content, get_settings().capital_markets_storage_dir)
        await session.execute(text("SELECT pg_advisory_xact_lock(770209)"))
        await ensure_sources(session)
        snapshot = CapitalMarketsSourceSnapshot(
            source_id=SECURITIES_SOURCE,
            retrieved_at=now,
            source_url=url,
            content_hash=digest,
            record_count=len(rows),
            ingestion_status="success",
            details={
                "issuer_id": str(issuer.id),
                "observed_at": observed.isoformat() if observed else None,
                "coverage": "issuer_registered_securities",
                "current_trading_verified": False,
            },
        )
        session.add(snapshot)
        await session.flush()
        new, changed = 0, 0
        for row in rows:
            instrument = await session.scalar(
                select(SecurityInstrument).where(
                    SecurityInstrument.issuer_id == issuer.id,
                    SecurityInstrument.source_id == SECURITIES_SOURCE,
                    SecurityInstrument.external_id == row.external_id,
                )
            )
            if not instrument and row.ann_code:
                # Preserve existing UUIDs when upgrading a legacy name-sensitive key.
                same_identifier = list(
                    await session.scalars(
                        select(SecurityInstrument).where(
                            SecurityInstrument.issuer_id == issuer.id,
                            SecurityInstrument.source_id == SECURITIES_SOURCE,
                            SecurityInstrument.ann_code == row.ann_code,
                            SecurityInstrument.issuance_number == row.issuance_number,
                            SecurityInstrument.exchange == row.exchange,
                            SecurityInstrument.rnve_registration_date
                            == (
                                date.fromisoformat(row.rnve_registration_date)
                                if row.rnve_registration_date
                                else None
                            ),
                        )
                    )
                )
                if len(same_identifier) > 1:
                    raise ValueError("Conflicting source instrument identities require review.")
                if same_identifier:
                    instrument = same_identifier[0]
                    instrument.external_id = row.external_id
            if not instrument:
                instrument = SecurityInstrument(
                    issuer_id=issuer.id, source_id=SECURITIES_SOURCE, external_id=row.external_id
                )
                session.add(instrument)
                new += 1
            elif instrument.source_record_id:
                previous = await session.get(SourceRecord, instrument.source_record_id)
                changed += int(previous is not None and previous.raw_payload != row.raw)
            for field in (
                "security_name",
                "security_type_raw",
                "security_category",
                "ann_code",
                "issuance_number",
                "exchange",
                "authorized_amount",
                "currency",
                "credit_rating",
            ):
                setattr(instrument, field, getattr(row, field))
            instrument.rnve_registration_date = (
                date.fromisoformat(row.rnve_registration_date)
                if row.rnve_registration_date
                else None
            )
            instrument.bvc_registration_date = (
                date.fromisoformat(row.bvc_registration_date) if row.bvc_registration_date else None
            )
            # ANN codes and registration venues do not certify current listings or tickers.
            instrument.listing_status = ListingStatus.UNKNOWN
            instrument.last_verified_at, instrument.last_snapshot_id = now, snapshot.id
            instrument.source_record_id = await raw_record(
                session, SECURITIES_SOURCE, f"{issuer.external_id}:{row.external_id}", row.raw, url
            )
        snapshot.details = {**snapshot.details, "new_records": new, "changed_records": changed}
        source = await session.get(DataSource, SECURITIES_SOURCE)
        assert source
        source.last_checked_at, source.availability = now, "available"
        await session.commit()
        return snapshot
    except Exception as exc:
        await record_failure(
            session, SECURITIES_SOURCE, url, exc, digest, {"issuer_id": issuer_key}
        )
        raise
