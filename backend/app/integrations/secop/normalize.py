from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, cast
from urllib.parse import urlsplit

from app.core.normalization import InvalidIdentifier, normalize_name, normalize_nit
from app.integrations.rues.adapter import payload_hash, source_datetime
from app.integrations.secop.adapter import DATASET_URL
from app.schemas.secop import ActivityGroup, ContractStatus, ContractView, ScreeningSummary

SUMMARY_POLICY = "raw_status_groups_v1"
CURRENCY_POLICY = "secop_cop_v1"
CURRENCY_WARNING = (
    "Los valores se interpretan en pesos colombianos (COP) por configuración de la aplicación; "
    "la fuente no publica un campo de moneda. No equivalen a pagos ni ingresos."
)


def apply_currency_policy(contract: ContractView) -> ContractView:
    if contract.currency is None:
        return contract.model_copy(
            update={"currency": "COP", "currency_basis": "application_policy"}
        )
    return contract


MATCHING_WARNING = (
    "NIT del proveedor: nueve dígitos se comparan con el NIT base; diez dígitos se "
    "comparan con el NIT base más el DV confirmado. Otras longitudes se excluyen."
)

WARNINGS = [
    (
        "Cobertura limitada al conjunto SECOP II de contratos electrónicos; no es un "
        "historial completo del Estado."
    ),
    CURRENCY_WARNING,
    (
        "Valor total reportado por la fuente; no equivale a pagos ni ingresos. No se "
        "verifica si incorpora todas las modificaciones."
    ),
    (
        "Se conserva la observación más reciente por ID de contrato; versiones "
        "contradictorias sin orden temporal se excluyen."
    ),
    MATCHING_WARNING,
    (
        "Participar en contratación pública no constituye una señal adversa. La "
        "fuente puede tener retrasos e inconsistencias."
    ),
]


def supplier_matches(row: dict[str, Any], nit: str, dv: str | None) -> bool:
    if str(row.get("tipodocproveedor", "")).strip().upper() != "NIT":
        return False
    # A group identifier is never attributed to an individual member, even with matching text.
    if normalize_name(str(row.get("es_grupo", ""))) != "NO":
        return False
    try:
        value = normalize_nit(str(row.get("documento_proveedor", "")))
    except InvalidIdentifier:
        return False
    if len(nit) != 9:
        return False
    digits = value.number + (value.verification_digit or "")
    if len(digits) == 9 and value.verification_digit is None:
        return digits == nit
    if len(digits) == 10 and dv is not None:
        return digits == nit + dv
    return False


def money(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value))
        if (
            not result.is_finite()
            or result < 0
            or result.adjusted() > 24
            or (
                isinstance(result.as_tuple().exponent, int) and int(result.as_tuple().exponent) < -6
            )
        ):
            return None
        return result
    except (InvalidOperation, ValueError, TypeError):
        return None


def event_date(value: Any) -> date | None:
    # A calendar date is kept in its reported local calendar, without UTC day shifts.
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def status(value: Any) -> str:
    return {
        "EN EJECUCION": "in_execution",
        "FIRMADO": "signed",
        "CERRADO": "closed",
        "TERMINADO": "terminated",
        "LIQUIDADO": "liquidated",
        "SUSPENDIDO": "suspended",
        "CANCELADO": "cancelled",
        "BORRADOR": "draft",
    }.get(normalize_name(str(value or "")), "other")


def source_link(row: dict[str, Any]) -> tuple[str, str]:
    # urlproceso is an official process link, not an individual contract permalink.
    value = row.get("urlproceso")
    url = value.get("url") if isinstance(value, dict) else value
    if isinstance(url, str):
        try:
            parsed = urlsplit(url)
            if (
                parsed.scheme == "https"
                and parsed.hostname == "community.secop.gov.co"
                and not parsed.username
                and not parsed.password
                and parsed.port in (None, 443)
                and parsed.path.startswith("/Public/")
            ):
                return url, "Proceso oficial SECOP II"
        except ValueError:
            pass
    return DATASET_URL, "Conjunto de datos oficial"


def normalize_contract(row: dict[str, Any], nit: str, retrieved: datetime) -> ContractView:
    link, link_label = source_link(row)
    # COP is an explicit application convention, not a field supplied by SECOP.
    return ContractView(
        contract_id=row["id_contrato"],
        process_id=row.get("proceso_de_compra"),
        reference=row.get("referencia_del_contrato"),
        original_supplier_identifier=row["documento_proveedor"],
        normalized_supplier_identifier=nit,
        supplier_document_type=row["tipodocproveedor"],
        source_identifier=str(row["source_row_id"]),
        buyer=row.get("nombre_entidad"),
        buyer_nit=row.get("nit_entidad"),
        description=row.get("objeto_del_contrato") or row.get("descripcion_del_proceso"),
        value=money(row.get("valor_del_contrato")),
        currency="COP",
        currency_basis="application_policy",
        raw_status=row.get("estado_contrato"),
        status=cast(ContractStatus, status(row.get("estado_contrato"))),
        contract_type=row.get("tipo_de_contrato"),
        modality=row.get("modalidad_de_contratacion"),
        signature_date=event_date(row.get("fecha_de_firma")),
        start_date=event_date(row.get("fecha_de_inicio_del_contrato")),
        end_date=event_date(row.get("fecha_de_fin_del_contrato")),
        department=row.get("departamento"),
        city=row.get("ciudad"),
        source_url=link,
        source_link_label=link_label,
        retrieved_at=retrieved,
        source_updated_at=source_datetime(row.get("ultima_actualizacion")),
    )


def verified_contracts(
    rows: list[dict[str, Any]], nit: str, dv: str | None, retrieved: datetime
) -> tuple[list[tuple[ContractView, dict[str, Any]]], int]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded = 0
    for row in rows:
        if (
            not supplier_matches(row, nit, dv)
            or not isinstance(row.get("id_contrato"), str)
            or not row["id_contrato"].strip()
        ):
            excluded += 1
            continue
        grouped[row["id_contrato"]].append(row)
    result = []
    for key in sorted(grouped):
        versions = grouped[key]
        dated = [(source_datetime(r.get("ultima_actualizacion")), r) for r in versions]
        latest = max((d for d, _ in dated if d), default=None)
        candidates = [r for d, r in dated if d == latest] if latest else versions
        # Ignore transport row ID when comparing duplicate observations.
        hashes = {
            payload_hash({k: v for k, v in r.items() if k != "source_row_id"}) for r in candidates
        }
        if len(hashes) != 1 or (latest and any(d is None for d, _ in dated) and len(versions) > 1):
            excluded += 1
            continue
        row = min(candidates, key=lambda r: str(r.get("source_row_id", "")))
        result.append((normalize_contract(row, nit, retrieved), row))
    return result, excluded


def aggregate(contracts: list[ContractView]) -> ScreeningSummary:
    def values(items: list[ContractView]) -> dict[str, Decimal]:
        totals: dict[str, Decimal] = {}
        with localcontext() as ctx:
            ctx.prec = 50
            for c in items:
                if c.value is not None and c.currency:
                    totals[c.currency] = totals.get(c.currency, Decimal(0)) + c.value
        return totals

    def groups(field: str) -> list[ActivityGroup]:
        buckets: dict[str, list[ContractView]] = defaultdict(list)
        for c in contracts:
            v = (
                str(c.signature_date.year)
                if field == "year" and c.signature_date
                else (
                    "Sin fecha de firma"
                    if field == "year"
                    else str(getattr(c, field) or "No informado")
                )
            )
            if field == "raw_status":
                v = (c.raw_status or "").strip() or "No informado"
            buckets[v].append(c)
        return [
            ActivityGroup(label=k, count=len(v), values=values(v))
            for k, v in sorted(buckets.items())
        ]

    buyers = {
        (c.buyer_nit or normalize_name(c.buyer or "")) for c in contracts if c.buyer_nit or c.buyer
    }
    dates = [c.signature_date for c in contracts if c.signature_date]
    totals = values(contracts) if contracts else {"COP": Decimal(0)}
    top = sorted(
        groups("buyer"), key=lambda g: (-g.values.get("COP", Decimal(0)), -g.count, g.label)
    )[:5]
    reported_value = ""
    if totals:
        amounts = " · ".join(
            f"{amount:,.2f} {currency}" for currency, amount in sorted(totals.items())
        )
        reported_value = f"El valor contractual acumulado es {amounts}. "
    return ScreeningSummary(
        total_contracts=len(contracts),
        total_values=totals,
        monetary_contracts=sum(c.value is not None and c.currency is not None for c in contracts),
        missing_or_invalid_values=sum(c.value is None for c in contracts),
        unknown_currency_contracts=sum(
            c.value is not None and c.currency is None for c in contracts
        ),
        zero_value_contracts=sum(c.value == 0 for c in contracts),
        distinct_buyers=len(buyers),
        latest_signature_date=max(dates) if dates else None,
        annual=groups("year"),
        statuses=groups("raw_status"),
        top_buyers=top,
        modalities=groups("modality"),
        departments=groups("department"),
        executive_summary=(
            f"Se identificaron {len(contracts)} contratos únicos en SECOP II asociados "
            f"al NIT consultado, con {len(buyers)} entidades contratantes. "
            + (f"La firma más reciente es {max(dates).isoformat()}. " if dates else "")
            + reported_value
            + "Los valores SECOP se interpretan en COP por configuración; no representan ingresos."
        ),
    )
