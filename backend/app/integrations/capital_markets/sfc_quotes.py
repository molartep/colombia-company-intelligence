"""Official SFC daily weighted-average reports, joined by the reported ANN."""

import asyncio
import random
import re
from datetime import datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

from app.core.errors import SourceError
from app.integrations.capital_markets.bvc import canonical
from app.integrations.capital_markets.parsers import MAX_BYTES, ReportHTML
from app.integrations.capital_markets.quote_provider import QuoteProvider
from app.integrations.capital_markets.secondary_quotes import SecondaryQuote

SFC_QUOTES = "sfc_daily_quotes"
BASE = "https://www.superfinanciera.gov.co/info/superfinancierav8/media/MercadoAccionario/Precios/Diarios/"
INDEX_URL = BASE + "ppal_promedios.htm"


def quote_url(ann: str) -> str | None:
    return BASE + "d_" + ann.lower() + ".htm" if re.fullmatch(r"[A-Z0-9]{12}", ann) else None


def validate_url(url: str) -> None:
    p = urlparse(url)
    if (
        p.scheme != "https"
        or p.netloc != "www.superfinanciera.gov.co"
        or not re.fullmatch(re.escape(urlparse(BASE).path) + r"d_[a-z0-9]{12}\.htm", p.path)
        or p.query
        or p.fragment
    ):
        raise ValueError("Unsupported official quote URL")


def parse_daily_quote(content: bytes) -> SecondaryQuote:
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Empty or oversized SFC quote report")
    parser = ReportHTML()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252")
    parser.feed(text)
    code_rows = [r for r in parser.rows if len(r) == 2 and canonical(r[0]) == "CODIGO DE LA ACCION"]
    if len(code_rows) != 1 or not re.fullmatch(r"[A-Z0-9]{12}", code_rows[0][1]):
        raise SourceError("quote_identity_missing", "SFC report lacks an unambiguous action code.")
    headers = [
        i
        for i, row in enumerate(parser.rows)
        if [canonical(v) for v in row] == ["PROMEDIO PONDERADO", "MAX", "MIN", "VR. PATRIMONIAL"]
    ]
    if len(headers) != 1 or len(parser.rows) < headers[0] + 3:
        raise ValueError("SFC weighted-price table changed")
    dates, values = parser.rows[headers[0] + 1 : headers[0] + 3]
    if (
        len(dates) != 4
        or len(values) != 4
        or not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}", values[0])
    ):
        raise ValueError("Malformed SFC price or date row")
    price = Decimal(values[0].replace(",", ""))
    stamp = datetime.strptime(dates[0], "%d/%m/%Y").date()
    if stamp.year < 1901:
        raise ValueError("Placeholder SFC price date")
    names = [r[0] for r in parser.rows if len(r) >= 2 and r[0].startswith("AO ")]
    if len(names) != 1:
        raise ValueError("Missing ordinary-share report title")
    classes = [r[1] for r in parser.rows if len(r) == 2 and canonical(r[0]) == "CLASE DE ACCION"]
    note = (
        "SFC indica clase " + classes[0] + "; RNVE clasifica el mismo ANN como Acciones ordinarias."
        if classes and canonical(classes[0]) != "ORDINARIA"
        else None
    )
    return SecondaryQuote(
        legal_name=names[0][3:].strip(),
        ann_code=code_rows[0][1],
        ticker=None,
        last_price=price,
        raw_price=values[0],
        currency="COP",
        price_date=stamp,
        price_kind="daily_weighted_average",
        source_note=note,
    )


SFC_PROVIDER = QuoteProvider(
    SFC_QUOTES, "SFC · Promedio diario de cotización", quote_url, validate_url, parse_daily_quote
)


class SfcQuotePages:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def fetch(self, url: str) -> bytes:
        validate_url(url)
        for attempt in range(3):
            try:
                async with self.http.stream("GET", url, follow_redirects=False) as response:
                    if response.status_code == 429 or 500 <= response.status_code < 600:
                        delay = 2**attempt + random.uniform(0, 0.2)
                        header = response.headers.get("Retry-After")
                        if header:
                            try:
                                delay = float(header)
                            except ValueError:
                                from datetime import UTC

                                delay = (
                                    parsedate_to_datetime(header) - datetime.now(UTC)
                                ).total_seconds()
                        if attempt == 2 or delay > 15:
                            raise SourceError(
                                "sfc_quote_unavailable",
                                "SFC quote source is temporarily unavailable.",
                            )
                    elif response.status_code != 200:
                        raise SourceError(
                            "sfc_quote_unavailable", "SFC quote report is not available."
                        )
                    else:
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            content.extend(chunk)
                            if len(content) > MAX_BYTES:
                                raise ValueError("SFC quote exceeds size limit")
                        return bytes(content)
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise SourceError(
                        "sfc_quote_unavailable", "SFC quote transport failed."
                    ) from exc
                delay = 2**attempt
            await asyncio.sleep(max(0, delay))
        raise SourceError("sfc_quote_unavailable", "SFC quote source unavailable.")
