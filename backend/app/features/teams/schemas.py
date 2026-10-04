import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


class TeamCreate(BaseModel):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    slug: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        normalized = value.lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
            raise ValueError(
                "Slug must contain lowercase letters, numbers, and single hyphens"
            )
        return normalized


class TeamPublic(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    slug: str

    model_config = ConfigDict(from_attributes=True)


class TeamMemberCreate(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class TeamMemberPublic(BaseModel):
    team_id: UUID
    user_id: UUID
    email: str
    name: str
