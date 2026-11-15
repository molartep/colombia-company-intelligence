"""Synthetic regulatory fixtures matching the observed SFC report layout."""

import io
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from app.integrations.capital_markets.parsers import (
    ISSUER_HEADERS,
    SECURITY_HEADERS,
    verification_digit,
)

SYNTHETIC_NIT = "000123456"


def issuer_xlsx(rows=None):
    if rows is None:
        rows = [
            (
                "SYNTHETIC EMISOR SAS",
                SYNTHETIC_NIT + verification_digit(SYNTHETIC_NIT),
                "001",
                "001",
            )
        ]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Emisores"
    sheet.append(
        [
            "Fecha y hora de generación : "
            + datetime.now(ZoneInfo("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S")
        ]
    )
    sheet.append(ISSUER_HEADERS)
    for name, nit, kind, code in rows:
        sheet.append(
            [
                "EMISORES",
                kind,
                "SYNTHETIC ENTITY TYPE",
                code,
                name,
                nit,
                "SYNTHETIC PRIVATE ADDRESS",
                "SYNTHETIC CITY",
                "SYNTHETIC PHONE",
                "SYNTHETIC PRIVATE EMAIL",
                "",
                "",
                "",
            ]
        )
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def security_html(issuer="SYNTHETIC EMISOR SAS", rows=None):
    if rows is None:
        rows = [
            [
                "BO SYNTHETIC BOND",
                "SYNTHETIC-ANN",
                "001",
                "AUT",
                "BVC",
                "N/A",
                "29/02/2024",
                "01/03/2024",
                "1.000.000,50",
                "COP",
                "AAA",
            ],
            [
                "ACE SYNTHETIC DEBT",
                "SYNTHETIC-ANN-2",
                "002",
                "AUT",
                "RNVE",
                "N/A",
                "01/03/2024",
                "N/A",
                "N/A",
                "USD",
                "N/A",
            ],
        ]
    stamp = datetime.now(ZoneInfo("America/Bogota")).strftime("%d/%m/%Y %H:%M:%S")
    header = "".join(f"<th>{escape(v)}</th>" for v in SECURITY_HEADERS)
    body = "".join("<tr>" + "".join(f"<td>{escape(v)}</td>" for v in row) + "</tr>" for row in rows)
    return (
        f"<html><h1>Valores Inscritos</h1><div>{escape(issuer)}</div>"
        f"<span>Títulos vigentes al {stamp}</span>"
        f"<table><tr>{header}</tr>{body}</table><p>Registros encontrados {len(rows)}</p></html>"
    ).encode()
