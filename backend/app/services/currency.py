"""Optional presentation rate; never mutates source amounts or currencies."""

import asyncio
import re
import time
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from app.core.errors import SourceError
from app.integrations.socrata import SocrataClient

SOURCE_URL = "https://www.datos.gov.co/d/32sa-8pi3"
RATE_PATTERN = re.compile(r"[0-9]{1,12}(?:\.[0-9]{1,12})?\Z")


def positive_rate(value: str) -> Decimal:
    if not RATE_PATTERN.fullmatch(value) or Decimal(value) <= 0:
        raise ValueError("Use a positive decimal COP per USD rate (up to 12+12 digits).")
    return Decimal(value)


def usd(amount: str, rate: str) -> str:
    with localcontext() as ctx:
        ctx.prec = 80
        ctx.rounding = ROUND_HALF_EVEN
        return format((Decimal(amount) / positive_rate(rate)).quantize(Decimal("0.01")), "f")


class Rate(BaseModel):
    cop_per_usd: str
    source: str
    source_url: str | None
    license_url: str | None = "https://creativecommons.org/licenses/by-sa/4.0/"
    effective_date: date
    effective_until: date
    retrieved_at: datetime
    manual: bool = False
    stale: bool = False
    provider_failed: bool = False
    rounding: str = "USD cents, half even"


class ReferenceRates:
    """One-hour process cache, serialized refresh, one-minute failure cooldown."""

    def __init__(self, client: SocrataClient):
        self.client = client
        self.cached: Rate | None = None
        self.next_check = 0.0
        self.lock = asyncio.Lock()

    async def get(self) -> Rate:
        async with self.lock:
            today = datetime.now(ZoneInfo("America/Bogota")).date()
            if time.monotonic() >= self.next_check:
                try:
                    rows = await self.client.get(
                        "/resource/32sa-8pi3.json",
                        {
                            "$select": "valor,unidad,vigenciadesde,vigenciahasta",
                            "$where": f"vigenciadesde <= '{today.isoformat()}T00:00:00'",
                            "$order": "vigenciadesde DESC",
                            "$limit": "1",
                        },
                    )
                    if not isinstance(rows, list) or len(rows) != 1:
                        raise ValueError("Missing rate")
                    row = rows[0]
                    value = str(row["valor"])
                    positive_rate(value)
                    start = date.fromisoformat(row["vigenciadesde"][:10])
                    end = date.fromisoformat(row["vigenciahasta"][:10])
                    if row["unidad"] != "COP" or not start <= today or end < start:
                        raise ValueError("Invalid TRM metadata")
                    self.cached = Rate(
                        cop_per_usd=value,
                        source="Superintendencia Financiera de Colombia — TRM",
                        source_url=SOURCE_URL,
                        effective_date=start,
                        effective_until=end,
                        retrieved_at=datetime.now(UTC),
                    )
                    self.next_check = time.monotonic() + 3600
                except (SourceError, ValueError, KeyError, TypeError):
                    self.next_check = time.monotonic() + 60
                    if self.cached:
                        self.cached = self.cached.model_copy(update={"provider_failed": True})
            if not self.cached:
                raise SourceError("rate_unavailable", "TRM unavailable. Use COP or a manual rate.")
            return self.cached.model_copy(
                update={"stale": self.cached.provider_failed or today > self.cached.effective_until}
            )


async def presentation_rate(
    provider: ReferenceRates,
    mode: Literal["cop", "reference", "manual"],
    manual_rate: str | None,
    effective_date: date | None,
) -> Rate | None:
    if mode == "cop":
        return None
    if mode == "reference":
        rate = await provider.get()
        if rate.stale:
            raise SourceError("rate_stale", "TRM is stale. Use COP or a manual rate.")
        return rate
    try:
        positive_rate(manual_rate or "")
    except ValueError as exc:
        raise SourceError("invalid_rate", str(exc), status=422) from exc
    if effective_date is None:
        raise SourceError("invalid_rate", "A manual rate date is required.", status=422)
    return Rate(
        cop_per_usd=manual_rate or "",
        source="User entered",
        source_url=None,
        license_url=None,
        effective_date=effective_date,
        effective_until=effective_date,
        retrieved_at=datetime.now(UTC),
        manual=True,
    )
