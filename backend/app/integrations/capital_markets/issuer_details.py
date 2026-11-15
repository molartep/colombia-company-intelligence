"""Allowlisted fields from a saved, rendered public RNVE issuer-summary page."""

import re
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.core.normalization import normalize_name
from app.integrations.capital_markets.parsers import MAX_BYTES, ReportHTML, issuer_nit, optional

DETAILS_SOURCE = "sfc_rnve_issuer_details"
DETAIL_FIELDS = (
    "Nombre:",
    "NIT:",
    "Tipo Entidad:",
    "Código Entidad:",
    "Correo institucional",
    "Dirección",
    "Ciudad",
    "Teléfono",
    "Web",
    "Redes Sociales",
    "Nro. Miembros Junta Directiva",
    "Representante Legal principal",
    "Representante Legal principal responsable de la informacion presentada al RNVE",
)


class IssuerDetailsRow(BaseModel):
    raw: dict[str, str]
    social_urls: list[str] = Field(default_factory=list)


class DetailTables(ReportHTML):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.social_urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        super().handle_starttag(tag, attrs)
        if tag == "tr":
            self.links = []
        if tag == "a" and self.cell is not None:
            href = dict(attrs).get("href")
            if href and len(href) <= 2000:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self.row and normalize_name(self.row[0]) == "REDES SOCIALES":
            self.social_urls.extend(self.links)
        super().handle_endtag(tag)


def validate_details_url(url: str, entity_type: str, entity_code: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.superfinanciera.gov.co"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use the original official public RNVE summary URL.")
    match = re.fullmatch(r"/SIMEV2/rnve/resumenentidad/([0-9]{1,3})/([0-9]{1,3})/0/?", parsed.path)
    if not match or match[1].zfill(3) != entity_type or match[2].zfill(3) != entity_code:
        raise ValueError("The RNVE summary URL does not belong to the selected issuer.")


def parse_issuer_details(
    content: bytes, *, issuer_name: str, source_nit: str | None, entity_type: str, entity_code: str
) -> IssuerDetailsRow:
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Issuer details report is empty or exceeds size limits.")
    parser = DetailTables()
    parser.feed(content.decode("utf-8-sig"))
    allowed = {normalize_name(field): field for field in DETAIL_FIELDS}
    raw: dict[str, str] = {}
    for cells in parser.rows:
        if len(cells) != 2:
            continue
        field = allowed.get(normalize_name(cells[0]))
        if field:
            if field in raw or len(cells[1]) > 2000:
                raise ValueError("Conflicting or oversized issuer-detail fields; review required.")
            raw[field] = cells[1]
    reported_name = normalize_name(raw.get("Nombre:", ""))
    expected_name = normalize_name(issuer_name)
    # Observed Bancolombia summary appends an explicit legal trading-name clause.
    # Exact source NIT and regulatory codes are still independently required below.
    if reported_name != expected_name and not reported_name.startswith(
        expected_name + " PODRA GIRAR "
    ):
        raise ValueError("Issuer details belong to a different entity or an unrendered page.")
    kind = re.match(r"^([0-9]{1,3})\s*[-–]", raw.get("Tipo Entidad:", ""))
    code = raw.get("Código Entidad:", "")
    if not kind or kind[1].zfill(3) != entity_type or code.zfill(3) != entity_code:
        raise ValueError("Issuer-detail regulatory codes do not match the selected record.")
    nit = optional(raw.get("NIT:", ""))
    if source_nit:
        if not nit:
            raise ValueError("Issuer-detail NIT is missing; identity cannot be confirmed.")
        # Compare report identifiers without stripping compartment/foreign suffixes.
        reported = issuer_nit(nit, entity_type, "concatenated-dv")[:2]
        expected = issuer_nit(source_nit, entity_type, "concatenated-dv")[:2]
        if reported[0] != expected[0] or (
            reported[1] is not None and expected[1] is not None and reported[1] != expected[1]
        ):
            raise ValueError("Issuer-detail NIT does not match the selected record.")
    return IssuerDetailsRow(raw=raw, social_urls=list(dict.fromkeys(parser.social_urls)))
