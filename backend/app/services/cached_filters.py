"""Apply the same source filters to latest cached records before local pagination."""

from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.integrations.rues.filtering import (
    CIIU_FIELDS,
    CODE_FIELDS,
    LEAP_CENTURIES,
    LEAP_ENDINGS,
    LONG_MONTHS,
)
from app.models.entities import Company, SourceRecord
from app.schemas.filters import SearchFilters


def valid_date(field: Any) -> ColumnElement[bool]:
    digits = field
    for digit in "0123456789":
        digits = func.replace(digits, digit, "")
    year, month, day = (func.substr(field, start, size) for start, size in ((1, 4), (5, 2), (7, 2)))
    return and_(
        field.like("________"),
        digits == "",
        year.between("0001", "9998"),
        month.between("01", "12"),
        or_(
            day.between("01", "28"),
            and_(day.in_(["29", "30"]), month != "02"),
            and_(day == "31", month.in_(LONG_MONTHS)),
            and_(
                day == "29",
                month == "02",
                or_(func.substr(field, 3, 2).in_(LEAP_ENDINGS), year.in_(LEAP_CENTURIES)),
            ),
        ),
    )


def cached_conditions(filters: SearchFilters) -> list[ColumnElement[bool]]:
    latest = (
        select(SourceRecord.raw_payload)
        .where(SourceRecord.company_id == Company.id)
        .order_by(SourceRecord.retrieved_at.desc(), SourceRecord.id)
        .limit(1)
        .correlate(Company)
        .scalar_subquery()
    )
    clauses = []
    for key, source_field in CODE_FIELDS.items():
        selected = getattr(filters, key)
        if selected:
            field = latest[source_field].astext
            codes = [v for v in selected if v != "__missing__"]
            parts = [field.in_(codes)] if codes else []
            if "__missing__" in selected:
                parts.append(or_(field.is_(None), func.trim(field) == ""))
            clauses.append(or_(*parts))
    if filters.ciiu:
        fields = CIIU_FIELDS if filters.ciiu_scope == "any" else CIIU_FIELDS[:1]
        clauses.append(
            or_(
                *[
                    latest[f].astext.startswith(filters.ciiu, autoescape=True)
                    if filters.ciiu_match == "prefix"
                    else latest[f].astext == filters.ciiu
                    for f in fields
                ]
            )
        )
    for source_field, start, end in (
        ("fecha_matricula", filters.registration_from, filters.registration_to),
        ("fecha_renovacion", filters.renewal_from, filters.renewal_to),
    ):
        field = latest[source_field].astext
        if start or end:
            clauses.append(valid_date(field))
            if start:
                clauses.append(field >= f"{start.year:04}{start.month:02}{start.day:02}")
            if end:
                clauses.append(field <= f"{end.year:04}{end.month:02}{end.day:02}")
    if filters.renewed_year:
        field = latest["ultimo_ano_renovado"].astext
        digits = field
        for digit in "0123456789":
            digits = func.replace(digits, digit, "")
        clauses.extend(
            [
                field.like("____"),
                digits == "",
                field <= "9998",
                field == str(filters.renewed_year)
                if filters.renewed_year_mode == "exact"
                else field >= str(filters.renewed_year),
            ]
        )
    return clauses
