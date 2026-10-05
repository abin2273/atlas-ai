from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import get_current_user
from app.features.organization_memberships.models import (
    MembershipRole,
    OrganizationMembership,
)
from app.features.users.models import User


def require_membership(
    organization_id: UUID,
    user: User,
    db: Session,
) -> OrganizationMembership:
    membership = db.get(OrganizationMembership, (user.id, organization_id))
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return membership


def require_admin(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OrganizationMembership:
    membership = require_membership(organization_id, current_user, db)
    if membership.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization administrator role required",
        )
    return membership


def organization_ids_for_user(user_id: UUID, db: Session) -> list[UUID]:
    return list(
        db.scalars(
            select(OrganizationMembership.organization_id).where(
                OrganizationMembership.user_id == user_id
            )
        )
    )
