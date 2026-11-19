import asyncio
import json
import logging
import random
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.core.errors import SourceError

logger = logging.getLogger(__name__)
BASE = "https://www.datos.gov.co"


class SocrataClient:
    """Fixed-host SODA 2.x transport. Calls and response sizes are bounded."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        retries: int = 2,
        concurrency: int = 4,
    ):
        self.client = client
        self.retries = retries
        self.slots = asyncio.Semaphore(concurrency)

    async def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        if path not in (
            "/resource/c82u-588k.json",
            "/api/views/c82u-588k.json",
            "/resource/jbjy-vk9h.json",
            "/api/views/jbjy-vk9h.json",
        ):
            raise ValueError("Unsupported source path")
        async with self.slots:
            for attempt in range(self.retries + 1):
                delay = min(2**attempt + random.uniform(0, 0.3), 8)
                try:
                    # Stream to enforce a response cap before JSON decoding.
                    async with self.client.stream("GET", BASE + path, params=params) as response:
                        status = response.status_code
                        if status == 429 or 500 <= status < 600:
                            retry_after = response.headers.get("Retry-After")
                            if retry_after:
                                try:
                                    delay = float(retry_after)
                                except ValueError:
                                    try:
                                        delay = (
                                            parsedate_to_datetime(retry_after) - datetime.now(UTC)
                                        ).total_seconds()
                                    except (TypeError, ValueError, OverflowError):
                                        pass
                            # Do not retry early when the server asks for a long wait.
                            if delay > 15 or attempt == self.retries:
                                raise SourceError(
                                    "source_rate_limited"
                                    if status == 429
                                    else "source_unavailable",
                                    "Official source unavailable.",
                                )
                        elif status != 200:
                            raise SourceError(
                                "source_request_failed", "Official source rejected query."
                            )
                        else:
                            chunks = bytearray()
                            async for chunk in response.aiter_bytes():
                                chunks.extend(chunk)
                                if len(chunks) > 2_000_000:
                                    raise SourceError(
                                        "source_invalid_response", "Source response too large."
                                    )
                            try:
                                return json.loads(chunks)
                            except ValueError as exc:
                                raise SourceError(
                                    "source_invalid_response", "Source returned invalid JSON."
                                ) from exc
                except httpx.TransportError as exc:
                    if attempt == self.retries:
                        raise SourceError(
                            "source_timeout", "Could not reach official source."
                        ) from exc
                logger.warning("socrata_retry", extra={"attempt": attempt + 1, "delay": delay})
                await asyncio.sleep(max(0, delay))
        raise SourceError("source_unavailable", "Official source unavailable.")

    async def records(self, params: dict[str, str]) -> list[dict[str, Any]]:
        limit = int(params.get("$limit", "0"))
        offset = int(params.get("$offset", "0"))
        if not 1 <= limit <= 51 or not 0 <= offset <= 5000:
            raise ValueError("Unbounded source request")
        data = await self.get("/resource/c82u-588k.json", params)
        if (
            not isinstance(data, list)
            or len(data) > limit
            or any(not isinstance(r, dict) for r in data)
        ):
            raise SourceError(
                "source_invalid_response", "Source returned an unexpected record collection."
            )
        return data
