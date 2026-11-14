"""Explicit bounded reference-data discovery; no company or personal records are downloaded.

Run from the repository root. Review the resulting JSON diff before committing.
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from app.core.config import get_settings
from app.integrations.rues.parameters import parameter_catalog
from app.integrations.socrata import SocrataClient


async def main() -> None:
    settings = get_settings()
    headers = (
        {"X-App-Token": settings.socrata_app_token}
        if settings.socrata_app_token
        else {}
    )
    catalog = json.loads(json.dumps(parameter_catalog()))
    async with httpx.AsyncClient(
        timeout=settings.socrata_timeout, headers=headers
    ) as http:
        client = SocrataClient(http, retries=1)
        metadata = await client.get("/api/views/c82u-588k.json")
        catalog["dataset_updated_at"] = datetime.fromtimestamp(
            metadata["rowsUpdatedAt"], UTC
        ).isoformat()
        for group in catalog["groups"]:
            code, label = group["code_field"], group["label_field"]
            rows = await client.get(
                "/resource/c82u-588k.json",
                {
                    "$select": f"{code}, {label}, count(*) as record_count",
                    "$group": f"{code}, {label}",
                    "$order": f"{code}, {label}",
                    "$limit": "501",
                },
            )
            if not isinstance(rows, list) or len(rows) >= 501:
                raise ValueError(
                    "Reference result malformed or possibly truncated; review required."
                )
            options = []
            codes = set()
            for row in rows:
                if not isinstance(row, dict) or any(
                    not isinstance(v, str) for v in row.values()
                ):
                    raise ValueError("Reference schema changed; review required.")
                value = row.get(code) or "__missing__"
                if value in codes:
                    raise ValueError(
                        "Conflicting labels for one code; review before updating."
                    )
                codes.add(value)
                options.append(
                    {
                        "value": value,
                        "code": row.get(code) or None,
                        "label": row.get(label) or None,
                    }
                )
            group["options"] = options
            print(f"{group['title']}: {len(options)} observed options")
    catalog["verified_at"] = datetime.now(UTC).isoformat()
    # Write only after every bounded query has succeeded and validated.
    path = (
        Path(__file__).parents[1] / "backend/app/integrations/rues/data/parameters.json"
    )
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    print("Updated versioned catalog. Review the diff; restart the backend to load it.")


if __name__ == "__main__":
    asyncio.run(main())
