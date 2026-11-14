import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from app.core.errors import SourceError
from app.core.normalization import InvalidIdentifier, normalize_nit
from app.integrations.rues.filtering import CIIU_FIELDS, CODE_FIELDS, filter_clauses
from app.integrations.rues.queries import literal, name_order, nit_order
from app.integrations.socrata import SocrataClient
from app.schemas.filters import SearchFilters

SOURCE_ID = "rues-c82u-588k"
DATASET_URL = "https://www.datos.gov.co/d/c82u-588k"
API_URL = "https://www.datos.gov.co/resource/c82u-588k.json"
# These are verified API field names. Do not substitute citizen identifiers for missing NITs.
FIELD_MAP = {
    "nit": "nit",
    "verification_digit": "digito_verificacion",
    "legal_name": "razon_social",
    "legal_form": "organizacion_juridica",
    "registration_status": "estado_matricula",
    "primary_ciiu": "cod_ciiu_act_econ_pri",
    "registration_number": "matricula",
    "chamber": "camara_comercio",
    "chamber_code": "codigo_camara",
    "registration_date": "fecha_matricula",
    "renewal_date": "fecha_renovacion",
    "last_renewed_year": "ultimo_ano_renovado",
    "cancellation_date": "fecha_cancelacion",
}
PUBLIC_FIELDS = (
    set(FIELD_MAP.values())
    | set(CODE_FIELDS.values())
    | {
        "categoria_matricula",
        "cod_ciiu_act_econ_sec",
        "ciiu3",
        "ciiu4",
        "fecha_actualizacion",
        "upstream_id",
    }
)


class CompanyDataSource(Protocol):
    source_id: str

    async def search_by_nit(
        self,
        nit: str,
        limit: int = 20,
        offset: int = 0,
        verification_digit: str | None = None,
        filters: SearchFilters | None = None,
    ) -> list[dict[str, Any]]: ...

    async def search_by_name(
        self, name: str, limit: int = 20, offset: int = 0, filters: SearchFilters | None = None
    ) -> list[dict[str, Any]]: ...


def source_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        # Source timestamps carry no timezone; interpreted in Colombia time explicitly.
        parsed = datetime.fromisoformat(value.replace("/", "-"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("America/Bogota"))
        return parsed.astimezone(UTC)
    except ValueError:
        return None


def payload_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def map_record(row: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(row.get("razon_social"), str) or not row["razon_social"].strip():
        raise SourceError("source_schema_changed", "Source record has no valid legal name.")
    if any(not isinstance(v, str) for v in row.values()):
        raise SourceError("source_schema_changed", "Source record field types changed.")
    mapped = {key: row.get(field) or None for key, field in FIELD_MAP.items()}
    if mapped["nit"]:
        try:
            mapped["nit"] = normalize_nit(mapped["nit"]).number
        except InvalidIdentifier:
            mapped["nit"] = None
    if mapped["verification_digit"] and (
        len(mapped["verification_digit"]) != 1
        or not mapped["verification_digit"].isascii()
        or not mapped["verification_digit"].isdigit()
    ):
        mapped["verification_digit"] = None
    # System row IDs were verified live. If absent, use a content identity and flag unresolved.
    mapped["external_record_id"] = row.get("upstream_id") or "hash:" + payload_hash(row)
    mapped["stable_identity"] = bool(row.get("upstream_id"))
    return mapped


class RuesDataSource:
    source_id = SOURCE_ID

    def __init__(self, client: SocrataClient):
        self.client = client

    async def metadata(self) -> dict[str, Any]:
        data = await self.client.get("/api/views/c82u-588k.json")
        if not isinstance(data, dict) or not isinstance(data.get("columns"), list):
            raise SourceError("source_schema_changed", "Source metadata is malformed.")
        columns = {
            c.get("fieldName"): c.get("dataTypeName")
            for c in data["columns"]
            if isinstance(c, dict)
        }
        required = set(FIELD_MAP.values()) | set(CIIU_FIELDS) | set(CODE_FIELDS.values())
        if any(columns.get(f) != "text" for f in required):
            raise SourceError(
                "source_schema_changed", "Verified RUES columns changed; adapter review required."
            )
        return data

    async def search(
        self, where: str, limit: int, offset: int, order: str, filters: SearchFilters | None = None
    ) -> list[dict[str, Any]]:
        if filters and filters.active:
            where = " AND ".join(f"({part})" for part in [where, *filter_clauses(filters)])
        rows = await self.client.records(
            {
                "$select": "*, :id as upstream_id",
                "$where": where,
                "$order": order,
                "$limit": str(limit),
                "$offset": str(offset),
            }
        )
        for row in rows:
            map_record(row)
        return rows

    async def search_by_nit(
        self,
        nit: str,
        limit: int = 20,
        offset: int = 0,
        verification_digit: str | None = None,
        filters: SearchFilters | None = None,
    ) -> list[dict[str, Any]]:
        return await self.search(
            "nit = " + literal(nit), limit, offset, nit_order(verification_digit), filters
        )

    async def search_by_name(
        self, name: str, limit: int = 20, offset: int = 0, filters: SearchFilters | None = None
    ) -> list[dict[str, Any]]:
        # Wildcards are controlled: user '%' and '_' never broaden a query.
        name = name.replace("%", " ").replace("_", " ").strip()
        compact = "".join(name.upper().split())
        if len(compact) < 2:
            raise ValueError("Enter at least two searchable characters.")
        return await self.search(
            "replace(upper(razon_social), ' ', '') like " + literal("%" + compact + "%"),
            limit,
            offset,
            name_order(name),
            filters,
        )
