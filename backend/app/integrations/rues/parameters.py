"""Versioned, privacy-safe reference values discovered with bounded source aggregations."""

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast


@lru_cache(maxsize=1)
def parameter_catalog() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(files("app.integrations.rues").joinpath("data/parameters.json").read_text()),
    )


def allowed_codes(key: str) -> set[str]:
    return {
        option["value"]
        for group in parameter_catalog()["groups"]
        if group["key"] == key
        for option in group["options"]
    }
