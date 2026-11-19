from datetime import UTC, datetime
from typing import Any

from app.core.errors import SourceError
from app.core.normalization import normalize_nit
from app.integrations.rues.queries import literal
from app.integrations.socrata import SocrataClient

MATCHING_POLICY = "supplier_nit_9_base_10_with_dv_v1"
SOURCE_ID = "secop-ii-jbjy-vk9h"
DATASET_URL = "https://www.datos.gov.co/d/jbjy-vk9h"
API_PATH = "/resource/jbjy-vk9h.json"
META_PATH = "/api/views/jbjy-vk9h.json"
# Verified against the official metadata; deliberately excludes personal/bank information.
FIELDS = {
    "id_contrato": "text",
    "proceso_de_compra": "text",
    "referencia_del_contrato": "text",
    "documento_proveedor": "text",
    "tipodocproveedor": "text",
    "es_grupo": "text",
    "nombre_entidad": "text",
    "nit_entidad": "number",
    "descripcion_del_proceso": "text",
    "objeto_del_contrato": "text",
    "valor_del_contrato": "number",
    "estado_contrato": "text",
    "tipo_de_contrato": "text",
    "modalidad_de_contratacion": "text",
    "fecha_de_firma": "calendar_date",
    "fecha_de_inicio_del_contrato": "calendar_date",
    "fecha_de_fin_del_contrato": "calendar_date",
    "departamento": "text",
    "ciudad": "text",
    "urlproceso": "url",
    "ultima_actualizacion": "calendar_date",
}


def supplier_variants(nit: str, dv: str | None) -> list[str]:
    base = normalize_nit(nit).number
    if base != nit or (dv is not None and (len(dv) != 1 or dv not in "0123456789")):
        raise ValueError("Canonical NIT required")
    if len(base) != 9:
        return []
    groups: list[str] = []
    remaining = base
    while remaining:
        groups.insert(0, remaining[-3:])
        remaining = remaining[:-3]
    variants = {base, ".".join(groups), " ".join(groups)}
    if dv is not None:
        variants |= {v + suffix for v in list(variants) for suffix in ("-" + dv, " - " + dv)}
        # Ten bare digits are explicitly the nine-digit base plus the confirmed DV.
        full = base + dv
        variants.add(full)
        variants.add(full[0] + "." + full[1:4] + "." + full[4:7] + "." + full[7:])
        variants.add(full[0] + " " + full[1:4] + " " + full[4:7] + " " + full[7:])
    return sorted(variants)


def supplier_where(nit: str, dv: str | None) -> str:
    variants = ",".join(literal(v) for v in supplier_variants(nit, dv))
    if not variants:
        return "upper(tipodocproveedor) = 'NIT' AND 1=0"
    return f"upper(tipodocproveedor) = 'NIT' AND documento_proveedor in ({variants})"


class SecopSource:
    def __init__(self, client: SocrataClient):
        self.client = client

    async def metadata(self) -> tuple[datetime | None, Any]:
        data = await self.client.get(META_PATH)
        if not isinstance(data, dict) or not isinstance(data.get("columns"), list):
            raise SourceError("source_schema_changed", "SECOP metadata is invalid.")
        columns = {
            c.get("fieldName"): c.get("dataTypeName")
            for c in data["columns"]
            if isinstance(c, dict)
        }
        if any(columns.get(k) != v for k, v in FIELDS.items()):
            raise SourceError("source_schema_changed", "SECOP schema requires adapter review.")
        stamp = data.get("rowsUpdatedAt")
        if not isinstance(stamp, int):
            raise SourceError("source_schema_changed", "SECOP update timestamp is missing.")
        return datetime.fromtimestamp(stamp, UTC), stamp

    async def collection(self, params: dict[str, str]) -> list[dict[str, Any]]:
        if not params.get("$where") or not 1 <= int(params.get("$limit", "0")) <= 200:
            raise ValueError("Selective bounded SECOP query required")
        data = await self.client.get(API_PATH, params)
        if (
            not isinstance(data, list)
            or len(data) > int(params["$limit"])
            or any(not isinstance(row, dict) for row in data)
        ):
            raise SourceError("source_invalid_response", "SECOP records are invalid.")
        for row in data:
            for field in FIELDS:
                value = row.get(field)
                if (
                    value is not None
                    and not isinstance(value, str)
                    and not (field == "urlproceso" and isinstance(value, dict))
                ):
                    raise SourceError("source_invalid_response", "SECOP field type is invalid.")
            if not isinstance(row.get("source_row_id"), str) and "$offset" in params:
                raise SourceError("source_invalid_response", "SECOP row identity is missing.")
        return data

    async def fetch(
        self, nit: str, dv: str | None, cap: int
    ) -> tuple[list[dict[str, Any]], datetime | None]:
        updated, stamp = await self.metadata()
        where = supplier_where(nit, dv)
        counts = await self.collection({"$select": "count(*) as n", "$where": where, "$limit": "1"})
        try:
            count = int(counts[0]["n"])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise SourceError("source_invalid_response", "SECOP count is invalid.") from exc
        if count < 0 or count > cap:
            raise SourceError(
                "secop_limit_exceeded", "Too many source rows; no partial totals published."
            )
        rows: list[dict[str, Any]] = []
        while len(rows) < count:
            page = await self.collection(
                {
                    "$select": ",".join(FIELDS) + ",:id as source_row_id",
                    "$where": where,
                    "$order": ":id ASC",
                    "$limit": "200",
                    "$offset": str(len(rows)),
                }
            )
            if not page:
                raise SourceError("source_changed", "SECOP changed during retrieval; retry later.")
            rows.extend(page)
        _, after = await self.metadata()
        ids = [r.get("source_row_id") for r in rows]
        if stamp != after or len(rows) != count or None in ids or len(set(ids)) != count:
            raise SourceError("source_changed", "SECOP changed during retrieval; retry later.")
        return rows, updated
