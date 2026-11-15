"""Import official XLSX issuers or fetch/import one issuer's public securities report."""

import argparse
import asyncio
from pathlib import Path

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import SourceError
from app.db.session import Session, engine
from app.integrations.capital_markets.ingestion import (
    ingest_issuer_details,
    ingest_issuers,
    ingest_securities,
    record_failure,
)
from app.integrations.capital_markets.matching import reconcile
from app.integrations.capital_markets.parsers import MAX_BYTES
from app.integrations.capital_markets.reports import OfficialReports, securities_url
from app.integrations.capital_markets.types import (
    DIRECTORY_URL,
    ISSUER_SOURCE,
    SECURITIES_SOURCE,
    RegistrationStatus,
)
from app.models.capital_markets import SecuritiesIssuer


def read_report(path: Path) -> bytes:
    with path.open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("Report exceeds maximum file size.")
    return content


async def run(args: argparse.Namespace) -> None:
    try:
        async with Session() as session:
            if args.issuer_report:
                try:
                    content = read_report(args.issuer_report)
                except (ValueError, OSError) as exc:
                    await record_failure(session, ISSUER_SOURCE, DIRECTORY_URL, exc)
                    raise
                snapshot = await ingest_issuers(
                    session,
                    content,
                    nit_mode=args.nit_format,
                    registration_status=RegistrationStatus(args.registration_status),
                    complete_current=args.complete_current,
                    expected_count=args.expected_count,
                )
                print(
                    f"Issuer snapshot {snapshot.id}: {snapshot.record_count} records; "
                    f"hash={snapshot.content_hash}"
                )
            elif args.entity:
                issuer = await session.scalar(
                    select(SecuritiesIssuer).where(SecuritiesIssuer.external_id == args.entity)
                )
                if (
                    not issuer
                    or not issuer.regulator_entity_type
                    or not issuer.regulator_entity_code
                ):
                    raise ValueError(
                        "Import the issuer first, then use its exact source entity key TYPE:CODE."
                    )
                if args.issuer_details_report:
                    snapshot = await ingest_issuer_details(
                        session,
                        issuer,
                        read_report(args.issuer_details_report),
                        args.details_source_url,
                    )
                    print(f"Issuer details snapshot {snapshot.id}: {snapshot.record_count} record")
                    return
                url = securities_url(issuer.regulator_entity_type, issuer.regulator_entity_code)
                issuer_key = str(issuer.id)
                if args.securities_report:
                    try:
                        content = read_report(args.securities_report)
                    except (ValueError, OSError) as exc:
                        await record_failure(
                            session, SECURITIES_SOURCE, url, exc, details={"issuer_id": issuer_key}
                        )
                        raise
                else:
                    try:
                        async with httpx.AsyncClient(
                            timeout=get_settings().capital_markets_timeout
                        ) as http:
                            content = await OfficialReports(
                                http, retries=get_settings().capital_markets_retries
                            ).securities(issuer.regulator_entity_type, issuer.regulator_entity_code)
                    except Exception as exc:
                        await record_failure(
                            session, SECURITIES_SOURCE, url, exc, details={"issuer_id": issuer_key}
                        )
                        raise
                snapshot = await ingest_securities(session, issuer, content, url)
                print(
                    f"Securities snapshot {snapshot.id}: {snapshot.record_count} records; "
                    f"hash={snapshot.content_hash}"
                )
            elif args.reconcile:
                await reconcile(session)
                await session.commit()
                print("Local issuer/company matches reconciled; no external requests.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument(
        "--issuer-report", type=Path, help="Official DESCARGAR EMISORES > REPORTE EXCEL file"
    )
    operation.add_argument(
        "--entity",
        help="Previously imported regulatory key, e.g. 001:001; fetches only this report",
    )
    operation.add_argument("--reconcile", action="store_true")
    parser.add_argument(
        "--securities-report",
        type=Path,
        help="Saved official issuer-specific HTML instead of a live GET",
    )
    parser.add_argument("--issuer-details-report", type=Path)
    parser.add_argument("--details-source-url")
    parser.add_argument("--nit-format", choices=["preserve", "concatenated-dv"], default="preserve")
    parser.add_argument(
        "--registration-status",
        choices=["registered_active", "registered_cancelled", "historical"],
        default="registered_active",
    )
    parser.add_argument(
        "--complete-current",
        action="store_true",
        help="Operator attests a complete, unfiltered current directory export",
    )
    parser.add_argument(
        "--expected-count", type=int, help="Count shown in the official unfiltered directory"
    )
    args = parser.parse_args()
    if args.securities_report and not args.entity:
        parser.error("--securities-report requires --entity")
    if args.issuer_details_report and (
        not args.entity or not args.details_source_url or args.securities_report
    ):
        parser.error(
            "--issuer-details-report requires --entity and --details-source-url, "
            "without --securities-report"
        )
    try:
        asyncio.run(run(args))
    except (ValueError, OSError, SourceError) as exc:
        parser.exit(1, f"Import rejected: {exc}\n")


if __name__ == "__main__":
    main()
