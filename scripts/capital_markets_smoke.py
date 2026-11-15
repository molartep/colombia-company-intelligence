"""Optional live SFC smoke: validate an official XLSX and fetch one selected public report."""

import argparse
import asyncio

import httpx
from app.core.config import get_settings
from app.integrations.capital_markets.parsers import (
    MAX_BYTES,
    parse_issuers,
    parse_securities,
)
from app.integrations.capital_markets.reports import OfficialReports


def read_export(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read(MAX_BYTES + 1)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issuer-export", required=True)
    parser.add_argument(
        "--entity", required=True, help="Source TYPE:CODE from the supplied export"
    )
    args = parser.parse_args()
    content = await asyncio.to_thread(read_export, args.issuer_export)
    rows, observed = parse_issuers(content)
    issuer = next((row for row in rows if row.external_id == args.entity), None)
    if not issuer:
        parser.error("Selected issuer key is not in the supplied official export.")
    print(
        f"Issuer schema validated: {len(rows)} rows; generated={observed}. Coverage not inferred."
    )
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.capital_markets_timeout) as http:
        report = await OfficialReports(http, retries=1).securities(
            issuer.entity_type, issuer.entity_code
        )
    instruments, observed = parse_securities(report, issuer.issuer_name)
    print(
        f"Public SFC report validated: {len(instruments)} instruments; observed={observed}."
    )
    print("BVC current listing and ownership remain unverified.")


if __name__ == "__main__":
    asyncio.run(main())
