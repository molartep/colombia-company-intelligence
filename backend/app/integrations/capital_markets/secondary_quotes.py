"""Public secondary quotes matched by identity fields, never by URLs or tickers."""

import asyncio
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from playwright.async_api import Error, Route, async_playwright
from pydantic import BaseModel

from app.core.errors import SourceError
from app.core.normalization import InvalidIdentifier, normalize_nit
from app.integrations.capital_markets.bvc import PublicText, canonical
from app.integrations.capital_markets.parsers import MAX_BYTES

LR_SOURCE = "la_republica_quotes"
LR_DIRECTORY_SOURCE = "la_republica_stock_directory"
LR_INDEX_URL = "https://www.larepublica.co/indicadores-economicos/movimiento-accionario"


class SecondaryQuote(BaseModel):
    legal_name: str
    nit: str | None = None
    ann_code: str | None = None
    ticker: str | None
    last_price: Decimal
    currency: str | None = None
    price_kind: str = "last_trade"
    price_date: date | None = None
    source_note: str | None = None
    raw_price: str
    price_as_of: datetime | None = None
    variation_percent: Decimal | None = None
    volume: Decimal | None = None
    share_class: str = "unknown"
    reported_listing: str | None = None


def exact_name(value: str) -> str:
    # Presentation-only normalization. Keep punctuation, diacritics and every legal suffix.
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def exact_match(
    quote: SecondaryQuote,
    nit: str | None,
    legal_names: list[str],
    common_codes: set[str],
    verification_digit: str | None = None,
) -> tuple[str, str, str] | None:
    if quote.share_class == "preferred" or (quote.ticker or "").upper().startswith("PF"):
        return None
    if quote.ann_code and quote.ann_code not in common_codes:
        return None
    matched_nit = False
    if quote.nit:
        try:
            source_nit = normalize_nit(quote.nit)
        except InvalidIdentifier:
            return None
        if source_nit.number != nit or (
            source_nit.verification_digit
            and verification_digit
            and source_nit.verification_digit != verification_digit
        ):
            return None
        matched_nit = True
    code = (
        quote.ann_code
        if quote.ann_code in common_codes
        else (next(iter(common_codes)) if len(common_codes) == 1 else None)
    )
    if not code:
        return None  # A company identity alone cannot choose between multiple ordinary instruments.
    if matched_nit:
        return "exact_nit", quote.nit or "", code
    if quote.ann_code:
        return "exact_ann", quote.ann_code, code
    if any(exact_name(quote.legal_name) == exact_name(name) for name in legal_names):
        return "exact_legal_name", quote.legal_name, code
    return None


def colombian_number(value: str) -> Decimal:
    if len(value) > 80:
        raise ValueError("Quote number exceeds field limits.")
    value = re.sub(r"[\s$%]", "", value)
    if not re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,3})?", value):
        raise ValueError("Unexpected Colombian quote number format.")
    return Decimal(value.replace(".", "").replace(",", "."))


def parse_la_republica(content: bytes) -> SecondaryQuote:
    if not content or len(content) > MAX_BYTES:
        raise ValueError("Secondary quote page is empty or oversized.")
    parser = PublicText()
    parser.feed(content.decode("utf-8-sig"))
    tokens = parser.parts
    norm = [canonical(t) for t in tokens]
    fichas = [i for i, t in enumerate(norm) if t.startswith("FICHA TECNICA:")]
    descriptions = [i for i, t in enumerate(norm) if t == "DESCRIPCION"]
    if not fichas and descriptions:
        raise SourceError(
            "quote_identity_missing", "The quote page has no technical-sheet identity evidence."
        )
    if len(fichas) != 1 or len(descriptions) != 1:
        raise ValueError("La República quote/technical-sheet layout changed or is ambiguous.")
    ficha = fichas[0]
    legal_name = tokens[ficha].partition(":")[2].strip() or tokens[ficha + 1]
    technical_end = next(
        (
            i
            for i in range(ficha + 1, min(len(tokens), ficha + 28))
            if canonical(tokens[i]).startswith("VER ESTADOS FINANCIEROS")
        ),
        ficha + 28,
    )
    technical = tokens[ficha:technical_end]
    technical_norm = [canonical(t).rstrip(":") for t in technical]

    def field(label: str) -> str | None:
        label = canonical(label).rstrip(":")
        positions = [i for i, t in enumerate(technical_norm) if t == label]
        if len(positions) > 1:
            raise ValueError("Conflicting secondary-source identity fields.")
        return (
            technical[positions[0] + 1] if positions and positions[0] + 1 < len(technical) else None
        )

    ticker = field("Nemotécnico")
    if not ticker or not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,29}", ticker):
        raise ValueError("La República technical sheet has no valid ticker.")
    start = descriptions[0]
    section = tokens[start : min(start + 35, ficha)]
    section_norm = [canonical(t).rstrip(":") for t in section]
    if len(section) < 3 or not section[2].strip().startswith("$"):
        raise ValueError("La República primary stock price could not be identified.")
    raw_price = section[2]
    price = colombian_number(raw_price)
    if price < 0:
        raise ValueError("Negative stock quote rejected.")
    stamp = None
    if "FECHA" in section_norm:
        date_index = section_norm.index("FECHA") + 1
        if date_index >= len(section):
            raise ValueError("Quote date is missing.")
        stamp = datetime.strptime(section[date_index], "%d/%m/%Y - %I:%M:%S %p").replace(
            tzinfo=ZoneInfo("America/Bogota")
        )
    variation = colombian_number(section[4]) if len(section) > 4 and "%" in section[4] else None
    volume = None
    if "VOLUMEN" in section_norm:
        volume = colombian_number(section[section_norm.index("VOLUMEN") + 1])
    description = canonical(section[1])
    return SecondaryQuote(
        legal_name=legal_name,
        nit=field("NIT"),
        ann_code=field("Código Superfinanciera") or field("ANN"),
        ticker=ticker,
        last_price=price,
        raw_price=raw_price,
        price_as_of=stamp,
        variation_percent=variation,
        volume=volume,
        share_class="preferred" if "PREFERENCIAL" in description else "unknown",
        reported_listing=field("Cotiza sus acciones en la BVC"),
    )


def validate_lr_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.larepublica.co"
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(
            r"/indicadores-economicos/movimiento-accionario/[a-z0-9-]+/?", parsed.path
        )
    ):
        raise ValueError("Use the official La República stock indicator URL.")


class SecondaryRetriever(Protocol):
    async def fetch(self, url: str) -> bytes: ...


@runtime_checkable
class DirectoryRetriever(SecondaryRetriever, Protocol):
    async def fetch_index(self) -> bytes: ...


class LaRepublicaPublicPages:
    def __init__(self) -> None:
        self._slots = asyncio.Semaphore(2)

    async def fetch(self, url: str) -> bytes:
        async with self._slots:
            return await self._fetch(url)

    async def fetch_index(self) -> bytes:
        async with self._slots:
            return await self._fetch(LR_INDEX_URL, directory=True)

    async def _fetch(self, url: str, directory: bool = False) -> bytes:
        if not directory:
            validate_lr_url(url)
        elif url != LR_INDEX_URL:
            raise ValueError("Only the fixed publisher directory can be fetched.")
        try:
            async with async_playwright() as driver:
                browser = await driver.chromium.launch(channel="chromium", headless=True)
                try:
                    context = await browser.new_context(
                        service_workers="block", accept_downloads=False
                    )

                    async def restrict(route: Route) -> None:
                        p = urlparse(route.request.url)
                        if (
                            p.scheme == "https"
                            and p.netloc == "www.larepublica.co"
                            and route.request.method == "GET"
                            and route.request.resource_type not in {"image", "font", "media"}
                        ):
                            await route.continue_()
                        else:
                            await route.abort()

                    await context.route("**/*", restrict)
                    page = await context.new_page()
                    response = await page.goto(url, wait_until="domcontentloaded")
                    if not response or response.status != 200:
                        raise SourceError(
                            "lr_page_unavailable",
                            "La República public quote page could not be loaded.",
                        )
                    await page.wait_for_function(
                        # Publisher CSS can hide the body while the complete public quote is
                        # already server-rendered. Parsing below still validates price/identity.
                        "() => !!document.querySelector('a[href*=\"movimiento-accionario/\"]')"
                        if directory
                        else "() => (document.body.textContent || '').normalize('NFD')"
                        ".replace(/[\\u0300-\\u036f]/g, '').toUpperCase().includes('DESCRIPCION')"
                    )
                    content = (await page.content()).encode()
                    if len(content) > MAX_BYTES:
                        raise SourceError(
                            "lr_page_oversized", "Secondary quote page exceeds size limits."
                        )
                    return content
                finally:
                    await browser.close()
        except Error as exc:
            raise SourceError(
                "lr_page_unavailable", "La República public quote page could not be rendered."
            ) from exc
