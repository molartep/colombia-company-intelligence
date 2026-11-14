import re
from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from app.integrations.rues.parameters import allowed_codes


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: list[str] = Field(default_factory=list, max_length=70)
    chamber: list[str] = Field(default_factory=list, max_length=70)
    organization: list[str] = Field(default_factory=list, max_length=70)
    category: list[str] = Field(default_factory=list, max_length=70)
    ciiu: str | None = Field(default=None, pattern=r"^[0-9]{1,4}$")
    ciiu_match: Literal["exact", "prefix"] = "exact"
    ciiu_scope: Literal["primary", "any"] = "primary"
    registration_from: date | None = None
    registration_to: date | None = None
    renewal_from: date | None = None
    renewal_to: date | None = None
    renewed_year: int | None = Field(default=None, ge=1000, le=9998)
    renewed_year_mode: Literal["exact", "minimum"] = "exact"

    @field_validator("status", "chamber", "organization", "category")
    @classmethod
    def known_codes(cls, values: list[str], info: ValidationInfo) -> list[str]:
        key = info.field_name or ""
        if not set(values) <= allowed_codes(key):
            raise ValueError(f"Unknown {key} code; consult /api/v1/parameters.")
        return sorted(set(values))

    @field_validator(
        "registration_from", "registration_to", "renewal_from", "renewal_to", mode="before"
    )
    @classmethod
    def iso_dates_only(cls, value: object) -> object:
        if value is not None and not isinstance(value, date):
            if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                raise ValueError("Use a calendar date in YYYY-MM-DD format.")
        return value

    @model_validator(mode="after")
    def valid_ranges(self) -> Self:
        for start, end in [
            (self.registration_from, self.registration_to),
            (self.renewal_from, self.renewal_to),
        ]:
            if start and end and start > end:
                raise ValueError("The start date must not follow the end date.")
            if any(d and d.year == 9999 for d in (start, end)):
                raise ValueError("Year 9999 is reserved for source placeholders.")
        if self.ciiu and self.ciiu_match == "exact" and len(self.ciiu) != 4:
            raise ValueError(
                "An exact CIIU code must have four digits; use prefix for fewer digits."
            )
        return self

    @property
    def active(self) -> bool:
        return bool(
            self.status
            or self.chamber
            or self.organization
            or self.category
            or self.ciiu
            or self.registration_from
            or self.registration_to
            or self.renewal_from
            or self.renewal_to
            or self.renewed_year
        )


class CompanySearchRequest(SearchFilters):
    q: str = Field(min_length=2, max_length=160)
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=20, ge=1, le=50)
