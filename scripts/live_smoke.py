"""Optional network check: metadata plus two filtered requests, at most one row each.

Run from the repository root with backend/.venv/bin/python scripts/live_smoke.py.
No raw records or tokens are printed or written. Does not require a database.
"""

import asyncio

import httpx
from app.core.config import get_settings
from app.integrations.rues.adapter import RuesDataSource, map_record
from app.integrations.socrata import SocrataClient


async def main() -> None:
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


if __name__ == "__main__":
    asyncio.run(main())
