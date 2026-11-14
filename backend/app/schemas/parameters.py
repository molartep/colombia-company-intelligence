from datetime import datetime

from pydantic import BaseModel


class ParameterOption(BaseModel):
    value: str
    code: str | None
    label: str | None


class ParameterGroup(BaseModel):
    key: str
    title: str
    code_field: str
    label_field: str
    description: str
    options: list[ParameterOption]


class ParameterCatalog(BaseModel):
    source_id: str
    source_url: str
    verified_at: datetime
    dataset_updated_at: datetime | None
    note: str
    groups: list[ParameterGroup]
