"""Bounded publisher-directory discovery. Candidate labels never establish identity."""

import asyncio
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import SourceError
from app.integrations.capital_markets.ingestion import ensure_sources, raw_record, record_failure
from app.integrations.capital_markets.reports import store_artifact
from app.integrations.capital_markets.secondary_quotes import (
    LR_DIRECTORY_SOURCE,
    LR_INDEX_URL,
    DirectoryRetriever,
    SecondaryQuote,
    exact_match,
    parse_la_republica,
    validate_lr_url,
)
from app.models.capital_markets import CapitalMarketsSourceSnapshot as Snapshot
from app.models.entities import DataSource, SourceRecord

MAX_DIRECTORY_PAGES = 100
MAX_CANDIDATES = 3
DIRECTORY_TTL = timedelta(hours=24)
FAILURE_TTL = timedelta(minutes=15)
_catalog_lock = asyncio.Lock()


class StockPage(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    url: str


class DirectoryLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: dict[str, str] = {}
        self.url: str | None = None
        self.label: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.url, self.label = None, []
            href = dict(attrs).get("href")
            if href:
                url = urljoin(LR_INDEX_URL, href).rstrip("/")
                try:
                    validate_lr_url(url)
                except ValueError:
                    return
                self.url = url

    def handle_data(self, data: str) -> None:
        if self.url:
            self.label.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.url:
            label = " ".join(" ".join(self.label).split())
            if label and len(label) <= 100:
                self.links.setdefault(self.url, label)
            self.url = None


def parse_directory(content: bytes) -> list[StockPage]:
    from app.integrations.capital_markets.parsers import MAX_BYTES

    if not content or len(content) > MAX_BYTES:
        raise SourceError("lr_directory_invalid", "Publisher directory is empty or oversized.")
    parser = DirectoryLinks()
    parser.feed(content.decode("utf-8-sig"))
    if not parser.links or len(parser.links) > MAX_DIRECTORY_PAGES:
        raise SourceError("lr_directory_invalid", "Publisher directory layout or size changed.")
    return [StockPage(url=url, label=label) for url, label in sorted(parser.links.items())]


def compact(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"[^a-z0-9]", "", value)


def candidates(pages: list[StockPage], names: list[str], preferred: str | None) -> list[StockPage]:
    names = [compact(name) for name in names]
    ranked = []
    for page in pages:
        label = compact(page.label)
        # Preferred-share pages cannot supply an ordinary-share quote.
        if label.startswith("pf"):
            continue
        score = (
            1000
            if page.url == preferred
            else (len(label) if len(label) >= 3 and any(label in name for name in names) else 0)
        )
        if score:
            ranked.append((score, page))
    ranked.sort(key=lambda item: (-item[0], item[1].url))
    return [page for _, page in ranked[:MAX_CANDIDATES]]


async def directory(
    session: AsyncSession, retriever: DirectoryRetriever
) -> tuple[list[StockPage], str]:
    async with _catalog_lock:
        now = datetime.now(UTC)
        saved = await session.scalar(
            select(SourceRecord)
            .where(
                SourceRecord.source_id == LR_DIRECTORY_SOURCE,
                SourceRecord.external_record_id == "public-stock-directory",
            )
            .order_by(SourceRecord.retrieved_at.desc(), SourceRecord.id)
            .limit(1)
        )
        latest = await session.scalar(
            select(Snapshot)
            .where(
                Snapshot.source_id == LR_DIRECTORY_SOURCE,
            )
            .order_by(Snapshot.retrieved_at.desc(), Snapshot.id)
            .limit(1)
        )
        if saved and now - saved.retrieved_at < DIRECTORY_TTL:
            return [
                StockPage.model_validate(p) for p in saved.raw_payload["pages"]
            ], saved.raw_payload["content_hash"]
        if (
            latest
            and latest.ingestion_status == "failed"
            and now - latest.retrieved_at < FAILURE_TTL
        ):
            raise SourceError(
                "lr_directory_unavailable", "Publisher directory is in its retry cooldown."
            )
        digest = None
        try:
            content = await retriever.fetch_index()
            pages = parse_directory(content)
            digest = store_artifact(content, get_settings().capital_markets_storage_dir)
            await ensure_sources(session)
            await raw_record(
                session,
                LR_DIRECTORY_SOURCE,
                "public-stock-directory",
                {"pages": [p.model_dump() for p in pages], "content_hash": digest},
                LR_INDEX_URL,
            )
            session.add(
                Snapshot(
                    source_id=LR_DIRECTORY_SOURCE,
                    source_url=LR_INDEX_URL,
                    retrieved_at=now,
                    content_hash=digest,
                    record_count=len(pages),
                    ingestion_status="success",
                    details={"coverage": "publisher_link_directory", "ttl_hours": 24},
                )
            )
            source = await session.get(DataSource, LR_DIRECTORY_SOURCE)
            assert source
            source.last_checked_at, source.availability = now, "available"
            await session.commit()
            # Quote mapping provenance uses the actual downloaded HTML hash.
            return pages, digest
        except (SourceError, ValueError, TimeoutError) as exc:
            await record_failure(session, LR_DIRECTORY_SOURCE, LR_INDEX_URL, exc, digest)
            raise SourceError(
                "lr_directory_unavailable", "Could not discover publisher stock pages."
            ) from exc


@dataclass
class DiscoveredQuote:
    quote: SecondaryQuote
    content: bytes
    url: str
    match: tuple[str, str, str]
    directory_hash: str
    discovered_at: str


async def discover_quote(
    session: AsyncSession,
    retriever: DirectoryRetriever,
    nit: str | None,
    names: list[str],
    codes: set[str],
    dv: str | None,
    preferred: str | None = None,
) -> DiscoveredQuote:
    pages, directory_hash = await directory(session, retriever)
    selected = candidates(pages, names, preferred)
    if not selected:
        raise SourceError(
            "lr_no_candidate", "No candidate page was found in the bounded publisher directory."
        )
    matches = []
    failures: list[str] = []
    for page in selected:
        try:
            validate_lr_url(page.url)
            content = await retriever.fetch(page.url)
            quote = parse_la_republica(content)
            match = exact_match(quote, nit, names, codes, dv)
            if match:
                matches.append(
                    DiscoveredQuote(
                        quote,
                        content,
                        page.url,
                        match,
                        directory_hash,
                        datetime.now(UTC).isoformat(),
                    )
                )
            else:
                failures.append("quote_no_exact_match")
        except SourceError as exc:
            failures.append(exc.code)
        except ValueError:
            failures.append("lr_page_invalid")
    if len(matches) > 1:
        raise SourceError(
            "lr_ambiguous_match", "Multiple publisher pages matched; no quote was selected."
        )
    if matches:
        return matches[0]
    code = "quote_no_exact_match" if "quote_no_exact_match" in failures else failures[0]
    raise SourceError(code, "The discovered pages did not supply a verified ordinary-share quote.")
