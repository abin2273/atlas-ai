import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserBase(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)]
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]

    model_config = ConfigDict(from_attributes=True)

    @field_validator("email")
    @classmethod
    def normalize_and_validate_email(cls, value: str) -> str:
        normalized = value.lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("A valid email address is required")
        return normalized


class UserCreate(UserBase):
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserLogin(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)]
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class UserPublic(UserBase):
    id: UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic

    model_config = ConfigDict(from_attributes=True)
