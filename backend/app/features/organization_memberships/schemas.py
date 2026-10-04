from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.features.organization_memberships.models import MembershipRole


class MembershipCreate(BaseModel):
    email: str
    role: MembershipRole = MembershipRole.MEMBER


class MembershipRoleUpdate(BaseModel):
    role: MembershipRole


class MembershipPublic(BaseModel):
    user_id: UUID
    organization_id: UUID
    role: MembershipRole
    email: str
    name: str

    model_config = ConfigDict(from_attributes=True)
