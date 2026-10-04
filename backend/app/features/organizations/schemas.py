import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


class OrganizationBase(BaseModel):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    slug: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]

    model_config = ConfigDict(from_attributes=True)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        normalized = value.lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
            raise ValueError(
                "Slug must contain lowercase letters, numbers, and single hyphens"
            )
        return normalized


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationPublic(OrganizationBase):
    id: UUID
