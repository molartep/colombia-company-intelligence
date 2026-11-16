"""Public BVC stock pages, matched exclusively by their Código Superfinanciera."""

import re
import unicodedata
from decimal import Decimal
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urlparse

import httpx
from playwright.async_api import Error, Route, async_playwright
from pydantic import BaseModel

from app.core.errors import SourceError
from app.integrations.capital_markets.parsers import MAX_BYTES

# A source locator supplied with this integration, never a price/ticker/listing assertion.
DEFAULT_PAGES = {
    "COC04PAAO008": "https://www.bvc.com.co/renta-variable-mercado-local/ecopetrol?tab=resumen"
}
LABELS = [
    "Nemotécnico",
    "Código Superfinanciera",
    "ISIN",
    "Código CFI",
    "Modalidad de negociación",
    "Periodo de liquidación",
    "Estado",
]


def canonical(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return " ".join("".join(c for c in value if not unicodedata.combining(c)).upper().split())


def validate_page(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.bvc.com.co"
        or not re.fullmatch(r"/renta-variable-mercado-local/[a-z0-9-]+/?", parsed.path)
        or parsed.query not in ("", "tab=resumen")
        or parsed.fragment
    ):
        raise ValueError("Use a public BVC local-equity summary URL.")


class PublicText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(" ".join(data.split()))


class BvcQuote(BaseModel):
    code: str
    ticker: str
    isin: str | None = None
    state: str | None = None
    last_price: Decimal | None = None
    raw_price: str | None = None
    currency: str | None = None
    source_fields: dict[str, str]


def price_value(raw: str) -> Decimal | None:
    value = re.sub(r"^(?:COP\s*|\$\s*)", "", raw.strip())
    if re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{2})?", value):
        return Decimal(value.replace(",", ""))
    if re.fullmatch(r"(?:\d+|\d{1,3}(?:\.\d{3})+),\d{2}", value):
        return Decimal(value.replace(".", "").replace(",", "."))
    return None


def parse_quote(content: bytes, expected_code: str) -> BvcQuote:
    if not content or len(content) > MAX_BYTES:
        raise ValueError("BVC page is empty or exceeds limits.")
    parser = PublicText()
    parser.feed(content.decode("utf-8-sig"))
    # Some layouts split label words across spans; join only these known labels.
    text = "\n".join(parser.parts)
    for pattern, label in [
        (r"[UÚ]ltimo\s+precio", "Último precio"),
        (r"Informaci[oó]n\s+de\s+la\s+acci[oó]n", "Información de la acción"),
        (r"C[oó]digo\s+Superfinanciera", LABELS[1]),
        (r"C[oó]digo\s+CFI", LABELS[3]),
        (r"Modalidad\s+de\s+negociaci[oó]n", LABELS[4]),
        (r"Per[ií]odo\s+de\s+liquidaci[oó]n", LABELS[5]),
    ]:
        text = re.sub(pattern, label, text, flags=re.IGNORECASE)
    tokens = [line.strip() for line in text.splitlines() if line.strip()]
    norm = [canonical(t) for t in tokens]
    heading = canonical("Información de la acción")
    if heading not in norm:
        raise ValueError("BVC stock-information section was not found; schema review required.")
    section = norm.index(heading)
    labels = [canonical(label) for label in LABELS]
    fields: dict[str, str] = {}
    for i in range(section + 1, min(len(tokens), section + 100)):
        if norm[i : i + 7] == labels and len(tokens[i + 7 : i + 14]) == 7:
            fields = dict(zip(LABELS, tokens[i + 7 : i + 14], strict=True))
            break
    if not fields:
        for i in range(section + 1, min(len(tokens) - 1, section + 100)):
            if norm[i] in labels and norm[i + 1] not in labels:
                key = LABELS[labels.index(norm[i])]
                if key in fields and fields[key] != tokens[i + 1]:
                    raise ValueError("Conflicting BVC stock-information fields.")
                fields[key] = tokens[i + 1]
    code, ticker = fields.get(LABELS[1], "").strip(), fields.get(LABELS[0], "").strip()
    if code != expected_code or not re.fullmatch(r"[A-Z0-9]{12}", code):
        raise ValueError("BVC Código Superfinanciera does not match the RNVE common-equity record.")
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,29}", ticker):
        raise ValueError("BVC ticker is missing or malformed.")
    prices = []
    for i, token in enumerate(norm[:section]):
        if token == canonical("Último precio") and i + 1 < section:
            raw = tokens[i + 1]
            if raw in {"COP", "$"} and i + 2 < section:
                raw += " " + tokens[i + 2]
            prices.append(raw)
    if len(set(prices)) > 1:
        raise ValueError("Conflicting BVC last-price fields.")
    raw_price = prices[0] if prices else None
    isin = fields.get("ISIN")
    if isin in {"N/A", "NO DISPONIBLE", "-", ""}:
        isin = None
    if isin and not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
        raise ValueError("BVC ISIN has an unexpected format.")
    return BvcQuote(
        code=code,
        ticker=ticker,
        isin=isin,
        state=fields.get("Estado"),
        last_price=price_value(raw_price) if raw_price else None,
        raw_price=raw_price,
        currency="COP" if raw_price and raw_price.strip().startswith("COP") else None,
        source_fields=fields,
    )


class BvcRetriever(Protocol):
    async def fetch(self, url: str, expected_code: str) -> bytes: ...


class BvcPublicPages:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def fetch(self, url: str, expected_code: str) -> bytes:
        validate_page(url)
        try:
            async with self.client.stream("GET", url, follow_redirects=False) as response:
                if response.status_code != 200:
                    raise SourceError(
                        f"bvc_http_{response.status_code}",
                        "BVC public page could not be retrieved.",
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise SourceError(
                            "bvc_page_oversized", "BVC public page exceeds size limits."
                        )
                content = bytes(body)
                visible = PublicText()
                visible.feed(content.decode("utf-8-sig"))
                if expected_code in " ".join(visible.parts):
                    return content
                # Render an ordinary successful SPA response; never bypass a 403/challenge.
                return await self.render(url, expected_code)
        except httpx.TransportError as exc:
            raise SourceError(
                "bvc_transport_error", "BVC public page is temporarily unavailable."
            ) from exc

    async def render(self, url: str, expected_code: str) -> bytes:
        try:
            async with async_playwright() as driver:
                browser = await driver.chromium.launch(channel="chromium", headless=True)
                try:
                    context = await browser.new_context(
                        service_workers="block", accept_downloads=False
                    )

                    async def restrict(route: Route) -> None:
                        parsed = urlparse(route.request.url)
                        if (
                            parsed.scheme == "https"
                            and parsed.netloc == "www.bvc.com.co"
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
                            "bvc_page_unavailable", "BVC public page could not be rendered."
                        )
                    await page.wait_for_function(
                        "code => document.body.innerText.includes(code)", arg=expected_code
                    )
                    await page.evaluate(
                        "() => new Promise(r => requestAnimationFrame("
                        "() => requestAnimationFrame(r)))"
                    )
                    content = (await page.content()).encode()
                    if len(content) > MAX_BYTES:
                        raise SourceError(
                            "bvc_page_oversized", "BVC public page exceeds size limits."
                        )
                    return content
                finally:
                    await browser.close()
        except (TimeoutError, Error) as exc:
            raise SourceError(
                "bvc_page_unavailable", "BVC public page could not be rendered."
            ) from exc
