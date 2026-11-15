import asyncio
import hashlib
import os
import random
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode

import httpx

from app.core.errors import SourceError
from app.integrations.capital_markets.parsers import MAX_BYTES
from app.integrations.capital_markets.types import SECURITIES_BASE, ListingStatus


def securities_url(entity_type: str, entity_code: str) -> str:
    if not all(re.fullmatch(r"[0-9]{3}", v) for v in (entity_type, entity_code)):
        raise ValueError("Expected source-verified three-digit entity type and code.")
    return SECURITIES_BASE + "?" + urlencode({"entidad": entity_code, "tipoEntidad": entity_type})


class SecuritiesRetriever(Protocol):
    async def securities(self, entity_type: str, entity_code: str) -> bytes: ...


class OfficialReports:
    """Only the observed public report page; not a proxy or undocumented API client."""

    def __init__(self, client: httpx.AsyncClient, retries: int = 2):
        self.client, self.retries = client, retries

    async def securities(self, entity_type: str, entity_code: str) -> bytes:
        url = securities_url(entity_type, entity_code)
        for attempt in range(self.retries + 1):
            delay = min(2**attempt + random.uniform(0, 0.3), 8)
            try:
                async with self.client.stream("GET", url, follow_redirects=False) as response:
                    if response.status_code == 429 or 500 <= response.status_code < 600:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                try:
                                    delay = (
                                        parsedate_to_datetime(retry_after) - datetime.now(UTC)
                                    ).total_seconds()
                                except (ValueError, TypeError, OverflowError):
                                    pass
                        if attempt == self.retries or delay > 15:
                            raise SourceError(
                                "capital_source_unavailable",
                                "SFC report is temporarily unavailable.",
                            )
                    elif response.status_code != 200:
                        raise SourceError(
                            "capital_source_rejected",
                            "SFC report could not be retrieved through public access.",
                        )
                    else:
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_BYTES:
                                raise SourceError(
                                    "capital_source_oversized", "SFC report exceeds size limits."
                                )
                        return bytes(body)
            except httpx.TransportError as exc:
                if attempt == self.retries:
                    raise SourceError(
                        "capital_source_timeout", "Could not retrieve the public SFC report."
                    ) from exc
            await asyncio.sleep(max(0, delay))
        raise SourceError("capital_source_unavailable", "SFC report unavailable.")


@dataclass(frozen=True)
class ListingObservation:
    identifier: str
    status: ListingStatus
    source_url: str
    observed_at: datetime
    ticker: str | None = None
    isin: str | None = None


class BvcDataSource(Protocol):
    async def verify_listing(self, identifier: str) -> ListingObservation: ...


class BvcUnavailable:
    availability = "requires_authorized_source"
    explanation = (
        "No reproducible authorized public listing feed verified; public "
        "BVC pages returned HTTP 403."
    )

    async def verify_listing(self, identifier: str) -> ListingObservation:
        raise SourceError("bvc_authorized_source_required", self.explanation)


def store_artifact(content: bytes, directory: Path) -> str:
    if len(content) > MAX_BYTES:
        raise ValueError("Report exceeds storage limits.")
    digest = hashlib.sha256(content).hexdigest()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / digest
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Stored artifact hash mismatch; operator review required.")
        return digest
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)  # Atomic publication without replacing immutable bytes.
        except FileExistsError:
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError(
                    "Stored artifact hash mismatch; operator review required."
                ) from None
    finally:
        Path(temporary).unlink(missing_ok=True)
    return digest
