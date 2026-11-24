"""Versioned, bounded public projections, never raw source payloads."""

import csv
import io
import json
from typing import Any

from fastapi import HTTPException
from starlette.responses import Response

from app.services.currency import Rate, usd

MAX_ROWS = 1000
MAX_BYTES = 5 * 1024 * 1024
IDENTITY_FIELDS = ("id", "nit", "verification_digit", "legal_name", "legal_form")
ISSUER_FIELDS = (
    "id",
    "nit",
    "source_nit",
    "verification_digit",
    "issuer_name",
    "regulator_entity_code",
    "regulator_entity_type",
    "registration_status",
    "registration_date",
    "cancellation_date",
    "last_verified_at",
    "source_id",
    "source_url",
    "snapshot_id",
    "match_status",
    "match_method",
)
INSTRUMENT_FIELDS = (
    "id",
    "issuer_id",
    "security_name",
    "security_type_raw",
    "security_category",
    "ticker",
    "isin",
    "ann_code",
    "exchange",
    "listing_status",
    "authorized_amount",
    "currency",
    "source_id",
    "source_record_id",
    "last_verified_at",
    "source_url",
    "snapshot_id",
    "stale",
    "observation_status",
    "quality_notes",
)
QUOTE_FIELDS = (
    "source_id",
    "source_name",
    "instrument_id",
    "price_kind",
    "price_date",
    "last_price",
    "raw_price",
    "currency",
    "retrieved_at",
    "price_as_of",
    "source_url",
    "stale",
    "ticker",
)


def project(data: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {key: data.get(key) for key in fields}


def converted(row: dict[str, Any], amount_key: str, rate: Rate | None) -> dict[str, Any]:
    result = dict(row)
    if rate and row.get("currency") == "COP" and row.get(amount_key) is not None:
        result["presentation_usd"] = usd(str(row[amount_key]), rate.cop_per_usd)
    return result


def cell(value: Any) -> str:
    if value is None:
        return ""
    text = (
        json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if isinstance(value, (dict, list))
        else str(value)
    )
    # Quote escaping alone does not prevent spreadsheet execution. Protect controls too.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        text = "'" + text
    return text


def download(document: dict[str, Any], fmt: str, name: str) -> Response:
    rows = document["rows"]
    if len(rows) > MAX_ROWS:
        raise HTTPException(413, "Export exceeds 1,000 rows. Narrow the filters.")
    if fmt == "json":
        content = json.dumps(document, ensure_ascii=False, indent=2)
        media = "application/json"
    else:
        output = io.StringIO(newline="")
        columns = list(dict.fromkeys(key for row in rows for key in row))
        columns = ["metadata_json", *columns]
        writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\r\n")
        writer.writeheader()
        for row in rows or [{}]:
            writer.writerow(
                {
                    k: cell(v)
                    for k, v in {
                        "metadata_json": {k: v for k, v in document.items() if k != "rows"},
                        **row,
                    }.items()
                }
            )
        content = "\ufeff" + output.getvalue()
        media = "text/csv; charset=utf-8"
    body = content.encode("utf-8")
    if len(body) > MAX_BYTES:
        raise HTTPException(413, "Export exceeds 5 MiB. Narrow the filters.")
    return Response(
        body,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{name}.{fmt}"',
            "Cache-Control": "no-store",
        },
    )
