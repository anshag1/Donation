import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class PublicEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    description: str | None
    banner_url: str | None
    start_date: date | None
    end_date: date | None


class AdminEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    description: str | None
    banner_url: str | None
    status: str
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime


class EventCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    banner_url: str | None = Field(default=None, max_length=500)
    status: str = Field(default="draft")
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        v = v.lower().strip()
        if not SLUG_RE.match(v):
            raise ValueError("Slug must be lowercase letters/numbers separated by hyphens")
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in {"draft", "active", "closed"}:
            raise ValueError("Status must be one of: draft, active, closed")
        return v


class EventUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    banner_url: str | None = Field(default=None, max_length=500)
    status: str | None = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in {"draft", "active", "closed"}:
            raise ValueError("Status must be one of: draft, active, closed")
        return v
