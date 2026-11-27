"""Bounded, single-process admission controls. No query text or client IPs are logged."""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from starlette.requests import Request

from app.core.config import Settings


@dataclass
class Bucket:
    expires: float
    count: int


class RequestLimiter:
    """Fixed windows and shared company refresh cooldowns; full tables fail closed.

    Called without awaits on one event loop. Production deliberately runs one worker.
    A restart resets admission state, but not the underlying source evidence cache.
    """

    def __init__(self, settings: Settings, clock: Callable[[], float] = time.monotonic):
        self.settings = settings
        self.clock = clock
        self.buckets: dict[tuple[str, str], Bucket] = {}
        self.next_cleanup = 0.0

    def _take(self, key: tuple[str, str], limit: int, seconds: int, now: float) -> int:
        bucket = self.buckets.get(key)
        if bucket and bucket.expires > now:
            if bucket.count >= limit:
                return max(1, math.ceil(bucket.expires - now))
            bucket.count += 1
            return 0
        if key not in self.buckets and len(self.buckets) >= self.settings.rate_limit_max_entries:
            return 60
        self.buckets[key] = Bucket(now + seconds, 1)
        return 0

    def check(self, request: Request) -> int:
        if not self.settings.rate_limits_enabled:
            return 0
        path = request.url.path.rstrip("/")
        if not path.startswith("/api/v1/"):
            return 0
        now = self.clock()
        if now >= self.next_cleanup:
            self.buckets = {k: v for k, v in self.buckets.items() if v.expires > now}
            self.next_cleanup = now + 5
        # Uvicorn accepts forwarding headers only from the configured Caddy address.
        client = request.client.host if request.client else "unknown"
        retry = self._take(("api", client), 120, 60, now)
        if retry:
            return retry
        if path == "/api/v1/admin/imports/rnve":
            return self._take(("import", client), 3, 60, now)
        if path in ("/api/v1/companies", "/api/v1/capital-markets/issuers"):
            retry = self._take(
                ("search", client), self.settings.search_requests_per_minute, 60, now
            )
            if retry:
                return retry
        involvement_refresh = request.method == "POST" and path.endswith(
            "/screening/secop/involvement/refresh"
        )
        secop_refresh = request.method == "POST" and path.endswith("/screening/secop/refresh")
        if not (secop_refresh or involvement_refresh) and request.query_params.get(
            "refresh", ""
        ).lower() not in (
            "true",
            "1",
            "on",
            "yes",
            "t",
            "y",
        ):
            return 0
        parts = path.split("/")
        if len(parts) not in (
            (9,) if involvement_refresh else (8,) if secop_refresh else (5, 6)
        ) or parts[1:4] != [
            "api",
            "v1",
            "companies",
        ]:
            return 0
        if len(parts) == 6 and parts[5] != "capital-markets":
            return 0
        try:
            company = str(UUID(parts[4]))
        except ValueError:
            return 0
        retry = self._take(
            ("refresh-client", client), self.settings.refresh_requests_per_minute, 60, now
        )
        if retry:
            return retry
        # Company-wide: source selectors and different client IPs cannot bypass this interval.
        return self._take(
            ("refresh-company", company), 1, self.settings.refresh_min_interval_seconds, now
        )
