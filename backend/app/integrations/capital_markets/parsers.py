"""Parsers for observed official reports; all files remain untrusted inputs."""

import hashlib
import io
import re
import zipfile
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Literal
from zoneinfo import ZoneInfo

from openpyxl import load_workbook
from pydantic import BaseModel, Field

from app.core.normalization import InvalidIdentifier, normalize_name, normalize_nit
from app.integrations.capital_markets.types import SecurityCategory

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10000
ISSUER_HEADERS = (
    "Reporte",
    "Tipo de entidad",
    "Descripción tipo de entidad",
    "Código de entidad",
    "Nombre entidad",
    "NIT",
    "Direccion",
    "Ciudad",
    "Teléfono",
    "Correo electronico",
    "Página web",
    "Nivel de supervisión",
    "Organismo de supervisión",
)
SECURITY_HEADERS = (
    "Nombre del título",
    "Código ANN",
    "No. Emisión",
    "Tipo Inscripción",
    "Inscrito en",
    "Número de Acto Administrativo RNVE",
    "Inscrito RNVE Fecha",
    "Inscrito BVC Fecha",
    "Monto Autorizado",
    "Moneda",
    "Última Calificacion",
)


class IssuerRow(BaseModel):
    external_id: str
    issuer_name: str = Field(min_length=1, max_length=1000)
    nit: str | None
    source_nit: str | None
    verification_digit: str | None = None
    identity_eligible: bool = False
    entity_type: str
    entity_code: str
    raw: dict[str, str]


class InstrumentRow(BaseModel):
    external_id: str
    security_name: str = Field(min_length=1, max_length=1000)
    security_type_raw: str = Field(max_length=500)
    security_category: SecurityCategory
    ann_code: str | None = Field(default=None, max_length=100)
    issuance_number: str | None = Field(default=None, max_length=100)
    exchange: str | None = Field(default=None, max_length=100)
    rnve_registration_date: str | None = None
    bvc_registration_date: str | None = None
    authorized_amount: Decimal | None = None
    currency: str | None = Field(default=None, max_length=20)
    credit_rating: str | None = Field(default=None, max_length=200)
    raw: dict[str, str]


def optional(value: str) -> str | None:
    return None if value.strip().upper() in ("", "N/A", "NA", "N.D.", "NULL") else value.strip()


def verification_digit(nit: str) -> str:
    weights = (71, 67, 59, 53, 47, 43, 41, 37, 29, 23, 19, 17, 13, 7, 3)
    remainder = sum(int(n) * w for n, w in zip(nit, weights[-len(nit) :], strict=True)) % 11
    return str(remainder if remainder < 2 else 11 - remainder)


def issuer_nit(
    raw: str, entity_type: str, mode: Literal["preserve", "concatenated-dv"]
) -> tuple[str | None, str | None, bool]:
    """Explicit report-specific DV rule; never apply it to trust/fund/foreign IDs.

    The export has concatenated DV examples AND extended compartment identifiers.
    Default preserves bare digits. Opt-in splitting requires ten digits and a valid
    checksum; structures 092/095/141 never auto-match a corporate RUES registration.
    """
    try:
        parsed = normalize_nit(raw)
    except InvalidIdentifier:
        return None, None, False
    if entity_type in {"092", "095", "141"}:
        return parsed.number, parsed.verification_digit, False
    if parsed.verification_digit:
        return parsed.number, parsed.verification_digit, True
    if mode == "concatenated-dv":
        if len(parsed.number) == 10 and verification_digit(parsed.number[:-1]) == parsed.number[-1]:
            return parsed.number[:-1], parsed.number[-1], True
        return parsed.number, None, False
    return parsed.number, None, False


def observed_time(text: str) -> datetime | None:
    match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})", text)
    if not match:
        return None
    value = datetime.strptime(" ".join(match.groups()), "%d/%m/%Y %H:%M:%S")
    return value.replace(tzinfo=ZoneInfo("America/Bogota")).astimezone(UTC)


def parse_issuers(
    content: bytes, nit_mode: Literal["preserve", "concatenated-dv"] = "preserve"
) -> tuple[list[IssuerRow], datetime | None]:
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Issuer report exceeds file-size limits or is empty.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > 500 or sum(i.file_size for i in members) > 5 * MAX_BYTES:
                raise ValueError("Spreadsheet archive exceeds expanded-size limits.")
            if any(
                "vbaproject" in i.filename.lower() or "externallinks/" in i.filename.lower()
                for i in members
            ):
                raise ValueError("Macros and external workbook links are not accepted.")
        workbook = load_workbook(
            io.BytesIO(content), read_only=True, data_only=False, keep_links=False
        )
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise ValueError("Expected a valid official XLSX issuer report.") from exc
    try:
        if len(workbook.worksheets) != 1:
            raise ValueError("Issuer workbook sheet layout changed.")
        sheet = workbook.worksheets[0]
        if (sheet.max_row or 0) > MAX_ROWS + 30 or (sheet.max_column or 0) > 30:
            raise ValueError("Issuer workbook dimensions exceed limits.")
        rows: list[IssuerRow] = []
        header_found = False
        generated = None
        for number, cells in enumerate(sheet.iter_rows(), 1):
            if number > MAX_ROWS + 30:
                raise ValueError("Issuer report row limit exceeded.")
            if any(c.data_type == "f" for c in cells):
                raise ValueError("Spreadsheet formulas are not accepted or executed.")
            values = [str(c.value).strip() if c.value is not None else "" for c in cells]
            if any(len(v) > 5000 for v in values):
                raise ValueError("Issuer report cell exceeds limits.")
            if not any(values):
                continue
            if not header_found:
                generated = generated or observed_time(" ".join(values))
                if tuple(normalize_name(v) for v in values) == tuple(
                    normalize_name(v) for v in ISSUER_HEADERS
                ):
                    header_found = True
                elif number > 20:
                    raise ValueError("Official issuer header not found; schema review required.")
                continue
            if len(values) != len(ISSUER_HEADERS) or values[0] != "EMISORES":
                raise ValueError("Issuer report row/schema changed; import aborted.")
            row = dict(zip(ISSUER_HEADERS, values, strict=True))
            kind, code = row["Tipo de entidad"], row["Código de entidad"]
            if not re.fullmatch(r"[0-9]{1,3}", kind) or not re.fullmatch(r"[0-9]{1,3}", code):
                raise ValueError("Invalid regulatory entity type/code.")
            kind, code = kind.zfill(3), code.zfill(3)
            nit, dv, eligible = issuer_nit(row["NIT"], kind, nit_mode)
            # Keep only the requested issuer contact fields; exclude other personal data.
            public = {k: row[k] for k in ISSUER_HEADERS[:11]}
            rows.append(
                IssuerRow(
                    external_id=f"{kind}:{code}",
                    issuer_name=row["Nombre entidad"],
                    nit=nit,
                    source_nit=optional(row["NIT"]),
                    verification_digit=dv,
                    identity_eligible=eligible,
                    entity_type=kind,
                    entity_code=code,
                    raw=public,
                )
            )
        if not header_found or not rows:
            raise ValueError("Issuer report is empty or has an unrecognized schema.")
        if len({r.external_id for r in rows}) != len(rows):
            raise ValueError("Duplicate regulatory entity keys; import aborted.")
        return rows, generated
    finally:
        workbook.close()


class ReportHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.cell: list[str] | None = None
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
            self.row = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)


def category(name: str) -> SecurityCategory:
    # Only source conventions verified in the official "Ver códigos" report.
    code = normalize_name(name).split(" ", 1)[0]
    return {
        "AO": SecurityCategory.COMMON,
        "ADP": SecurityCategory.PREFERRED,
        "AP": SecurityCategory.EQUITY,
        "BO": SecurityCategory.BONDS,
        "BGG": SecurityCategory.BONDS,
        "BGE": SecurityCategory.BONDS,
        "BOCEAS": SecurityCategory.BONDS,
        "PC": SecurityCategory.PAPER,
        "TCC": SecurityCategory.DEBT,
        "TP": SecurityCategory.OTHER,
        "ACE": SecurityCategory.DEBT,
        "CDT": SecurityCategory.DEBT,
        "CDAT": SecurityCategory.DEBT,
        "CAVC": SecurityCategory.DEBT,
        "BDPI": SecurityCategory.DEBT,
    }.get(code, SecurityCategory.OTHER)


def calendar_date(raw: str) -> str | None:
    value = optional(raw)
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%d/%m/%Y").date()
        return parsed.isoformat() if parsed.year not in (1900, 9999) else None
    except ValueError:
        return None


def amount(raw: str) -> Decimal | None:
    value = optional(raw)
    if not value:
        return None
    if re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,4})?", value):
        value = value.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[0-9]+(?:,[0-9]{1,4})?", value):
        value = value.replace(",", ".")
    else:
        return None
    try:
        result = Decimal(value)
        return result if result < Decimal("1e28") else None
    except InvalidOperation:
        return None


def parse_securities(
    content: bytes, issuer_name: str
) -> tuple[list[InstrumentRow], datetime | None]:
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Securities report exceeds file-size limits or is empty.")
    parser = ReportHTML()
    parser.feed(content.decode("utf-8-sig"))
    text = " ".join(" ".join(parser.text).split())
    heading = re.search(
        r"([^<>]*?)Títulos vigentes al (\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})", text
    )
    if not heading or normalize_name(issuer_name) not in normalize_name(heading[1]):
        raise ValueError("Securities report issuer/header could not be verified.")
    # Require the full displayed heading name, not a brand-name substring.
    before = heading[1].rsplit("Valores Inscritos", 1)[-1].strip()
    # Script/style text precedes the heading; the last standalone data chunk contains its name.
    chunks = [part.strip() for part in parser.text if part.strip()]
    for index, chunk in enumerate(chunks):
        if "Títulos vigentes al" in chunk:
            before = chunk.split("Títulos vigentes al")[0].strip() or chunks[index - 1]
            break
    if normalize_name(before) != normalize_name(issuer_name):
        raise ValueError("Report belongs to a different issuer; review required.")
    header = next((i for i, row in enumerate(parser.rows) if tuple(row) == SECURITY_HEADERS), None)
    if header is None:
        raise ValueError("Securities report columns changed; review required.")
    found = re.search(r"Registros encontrados\s+(\d+)", text)
    if not found:
        raise ValueError("Securities report completeness count missing.")
    items = []
    for values in parser.rows[header + 1 :]:
        if len(values) != len(SECURITY_HEADERS):
            continue
        raw = dict(zip(SECURITY_HEADERS, values, strict=True))
        name = raw["Nombre del título"]
        identity_fields = ("Código ANN", "No. Emisión", "Inscrito en", "Inscrito RNVE Fecha")
        if not optional(raw["Código ANN"]):
            identity_fields = (
                "Nombre del título",
                "No. Emisión",
                "Inscrito en",
                "Inscrito RNVE Fecha",
            )
        identity = "|".join(raw[key] for key in identity_fields)
        items.append(
            InstrumentRow(
                external_id=hashlib.sha256(identity.encode()).hexdigest(),
                security_name=name,
                security_type_raw=name.split(" ", 1)[0],
                security_category=category(name),
                ann_code=optional(raw["Código ANN"]),
                issuance_number=optional(raw["No. Emisión"]),
                exchange=optional(raw["Inscrito en"]) if raw["Inscrito en"] != "RNVE" else None,
                rnve_registration_date=calendar_date(raw["Inscrito RNVE Fecha"]),
                bvc_registration_date=calendar_date(raw["Inscrito BVC Fecha"]),
                authorized_amount=amount(raw["Monto Autorizado"]),
                currency=optional(raw["Moneda"]),
                credit_rating=optional(raw["Última Calificacion"]),
                raw=raw,
            )
        )
    if len(items) != int(found[1]) or len(items) > MAX_ROWS:
        raise ValueError("Securities report is truncated or row counts disagree.")
    if len({r.external_id for r in items}) != len(items):
        raise ValueError("Duplicate securities rows require review; import aborted.")
    return items, observed_time(heading[2])
