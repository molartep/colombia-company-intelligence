"""Optional network check: metadata plus two filtered requests, at most one row each.

Run from the repository root with backend/.venv/bin/python scripts/live_smoke.py.
No raw records or tokens are printed or written. Does not require a database.
"""

import argparse
import asyncio

import httpx
from app.core.config import get_settings
from app.integrations.rues.adapter import RuesDataSource, map_record
from app.integrations.socrata import SocrataClient


async def main(check_ranking: bool = False) -> None:
    settings = get_settings()
    headers = (
        {"X-App-Token": settings.socrata_app_token}
        if settings.socrata_app_token
        else {}
    )
    async with httpx.AsyncClient(
        timeout=settings.socrata_timeout, headers=headers
    ) as http:
        source = RuesDataSource(SocrataClient(http, retries=1))
        metadata = await source.metadata()
        print(
            f"Metadata validated: {len(metadata['columns'])} columns; rowsUpdatedAt={metadata.get('rowsUpdatedAt')}"
        )
        for kind, rows in [
            ("NIT", await source.search_by_nit("890001255", limit=1)),
            ("name", await source.search_by_name("URBANIZADORA LA SUIZA", limit=1)),
        ]:
            for row in rows:
                mapped = map_record(row)
                assert mapped["stable_identity"], "Socrata system row ID missing"
            print(f"{kind} filtered lookup: valid response, {len(rows)} record(s).")
            if not rows:
                print(
                    "No match for smoke-test identifier; dataset contents may have changed."
                )
        if check_ranking:
            first = await source.search_by_name("Zulu", limit=5)
            second = await source.search_by_name("Zulu", limit=5, offset=5)
            combined = await source.search_by_name("Zulu", limit=10)
            assert first, (
                "No Zulu smoke-test matches; review test query against current source."
            )
            assert [r["upstream_id"] for r in first + second] == [
                r["upstream_id"] for r in combined
            ], (
                "Ranked page boundaries differ; source data may have changed between requests."
            )
            assert len({r["upstream_id"] for r in combined}) == len(combined)
            print(
                f"Global ranking: {len(combined)} rows have consistent bounded page ordering."
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ranking",
        action="store_true",
        help="Also compare two globally ranked pages with one combined page (3 extra bounded requests)",
    )
    args = parser.parse_args()
    asyncio.run(main(check_ranking=args.ranking))
