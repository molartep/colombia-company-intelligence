"""Optional bounded live check. No database or raw identifiers/records in output.

backend/.venv/bin/python scripts/secop_smoke.py --nit 901449437
"""
import argparse
import asyncio
from datetime import UTC, datetime

import httpx
from app.core.config import get_settings
from app.core.normalization import normalize_nit
from app.integrations.secop.adapter import SecopSource
from app.integrations.secop.normalize import aggregate, verified_contracts
from app.integrations.socrata import SocrataClient


async def main(value: str) -> None:
    nit = normalize_nit(value)
    settings = get_settings()
    headers = {"X-App-Token": settings.socrata_app_token} if settings.socrata_app_token else {}
    async with httpx.AsyncClient(timeout=settings.socrata_timeout, headers=headers) as http:
        source = SecopSource(SocrataClient(http, retries=1))
        async with asyncio.timeout(90):
            rows, updated = await source.fetch(nit.number, nit.verification_digit, cap=200)
        contracts, excluded = verified_contracts(rows, nit.number, nit.verification_digit, datetime.now(UTC))
        summary = aggregate([c for c, _ in contracts])
        print(f"SECOP schema and filtered pagination validated; dataset updated {updated}.")
        print(f"Source rows: {len(rows)}; unique verified contracts: {summary.total_contracts}; excluded: {excluded}.")
        print("Currency absent in schema; amounts interpreted as COP by application policy.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nit", required=True)
    asyncio.run(main(parser.parse_args().nit))
