"""Controlled SoQL conditions. No caller-supplied expressions or field names."""

from app.integrations.rues.queries import literal
from app.schemas.filters import SearchFilters

CODE_FIELDS = {
    "status": "codigo_estado_matricula",
    "chamber": "codigo_camara",
    "organization": "codigo_organizacion_juridica",
    "category": "codigo_categoria_matricula",
}
CIIU_FIELDS = ("cod_ciiu_act_econ_pri", "cod_ciiu_act_econ_sec", "ciiu3", "ciiu4")
LONG_MONTHS = ("01", "03", "05", "07", "08", "10", "12")
LEAP_ENDINGS = tuple(f"{n:02}" for n in range(4, 100, 4))
LEAP_CENTURIES = tuple(f"{n:04}" for n in range(400, 10000, 400))


def values(items: tuple[str, ...] | list[str]) -> str:
    return "(" + ", ".join(literal(item) for item in items) + ")"


def valid_date(field: str) -> str:
    """Calendar validation using total text operations, never unsafe date casts.

    Socrata substring uses one-based indexing. Reject year 0000 / 9999, impossible
    dates, non-digits, blanks and zero placeholders, including Gregorian leap rules.
    """
    digits = field
    for digit in "0123456789":
        digits = f"replace({digits}, '{digit}', '')"
    year, month, day = (
        f"substring({field}, {start}, {size})" for start, size in ((1, 4), (5, 2), (7, 2))
    )
    leap = (
        f"(substring({field}, 3, 2) in {values(LEAP_ENDINGS)} OR "
        f"{year} in {values(LEAP_CENTURIES)})"
    )
    days = (
        f"({day} between '01' and '28' OR "
        f"({day} in ('29', '30') AND {month} != '02') OR "
        f"({day} = '31' AND {month} in {values(LONG_MONTHS)}) OR "
        f"({day} = '29' AND {month} = '02' AND {leap}))"
    )
    return (
        f"({field} like '________' AND {digits} = '' AND "
        f"{year} between '0001' and '9998' AND {month} between '01' and '12' AND {days})"
    )


def filter_clauses(filters: SearchFilters) -> list[str]:
    clauses = []
    for key, field in CODE_FIELDS.items():
        selected = getattr(filters, key)
        if not selected:
            continue
        codes = [v for v in selected if v != "__missing__"]
        parts = [f"{field} in {values(codes)}"] if codes else []
        if "__missing__" in selected:
            parts.append(f"({field} is null OR trim({field}) = '')")
        clauses.append("(" + " OR ".join(parts) + ")")
    if filters.ciiu:
        fields = CIIU_FIELDS if filters.ciiu_scope == "any" else CIIU_FIELDS[:1]
        condition = (
            f"like {literal(filters.ciiu + '%')}"
            if filters.ciiu_match == "prefix"
            else f"= {literal(filters.ciiu)}"
        )
        clauses.append("(" + " OR ".join(f"{f} {condition}" for f in fields) + ")")
    for field, start, end in (
        ("fecha_matricula", filters.registration_from, filters.registration_to),
        ("fecha_renovacion", filters.renewal_from, filters.renewal_to),
    ):
        if start or end:
            clauses.append(valid_date(field))
            if start:
                clauses.append(
                    f"{field} >= {literal(f'{start.year:04}{start.month:02}{start.day:02}')}"
                )
            if end:
                clauses.append(f"{field} <= {literal(f'{end.year:04}{end.month:02}{end.day:02}')}")
    if filters.renewed_year:
        year = "ultimo_ano_renovado"
        # Comparing known four-digit text avoids coercing malformed source values.
        clean = year
        for digit in "0123456789":
            clean = f"replace({clean}, '{digit}', '')"
        op = "=" if filters.renewed_year_mode == "exact" else ">="
        clauses.append(
            f"({year} like '____' AND {clean} = '' AND {year} <= '9998' "
            f"AND {year} {op} {literal(str(filters.renewed_year))})"
        )
    return clauses
