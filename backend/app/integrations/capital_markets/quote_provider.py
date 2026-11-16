"""Small provider configuration for the shared public-quote cache."""

from collections.abc import Callable
from dataclasses import dataclass

from app.integrations.capital_markets.secondary_quotes import SecondaryQuote


@dataclass(frozen=True)
class QuoteProvider:
    source_id: str
    name: str
    url_for: Callable[[str], str | None]
    validate_url: Callable[[str], None]
    parse: Callable[[bytes], SecondaryQuote]
