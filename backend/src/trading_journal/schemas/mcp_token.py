"""API schemas for issuing and managing MCP credentials."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Profile = Literal["read", "entry"]


class McpTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    profile: Profile
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value


class McpTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    profile: Profile
    token_prefix: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


class McpTokenIssued(McpTokenRead):
    token: str
