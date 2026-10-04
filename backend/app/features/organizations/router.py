from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.permissions import (
    organization_ids_for_user,
    require_admin,
    require_membership,
)
from app.core.security import get_current_user
from app.features.organization_memberships.models import (
    MembershipRole,
    OrganizationMembership,
)
from app.features.organization_memberships.schemas import (
    MembershipCreate,
    MembershipPublic,
    MembershipRoleUpdate,
)
from app.features.organizations.models import Organization
from app.features.organizations.schemas import OrganizationCreate, OrganizationPublic
from app.features.teams.models import Team, TeamMembership
from app.features.users.models import User

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("", response_model=list[OrganizationPublic])
def list_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Organization]:
    organization_ids = organization_ids_for_user(current_user.id, db)
    if not organization_ids:
        return []
    return list(
        db.scalars(
            select(Organization)
            .where(Organization.id.in_(organization_ids))
            .order_by(Organization.name.asc())
        )
    )


@router.get("/{organization_id}", response_model=OrganizationPublic)
def get_organization(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Organization:
    require_membership(organization_id, current_user, db)
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


@router.post("", response_model=OrganizationPublic, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Organization:
    existing = db.execute(
        select(Organization).where(Organization.slug == payload.slug)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=400, detail="An organization with that slug already exists"
        )

    organization = Organization(name=payload.name, slug=payload.slug)
    db.add(organization)
    db.flush()
    db.add(
        OrganizationMembership(
            user_id=current_user.id,
            organization_id=organization.id,
            role=MembershipRole.OWNER,
        )
    )
    db.commit()
    db.refresh(organization)
    return organization


@router.get("/{organization_id}/members", response_model=list[MembershipPublic])
def list_members(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[MembershipPublic]:
    require_membership(organization_id, current_user, db)
    rows = db.execute(
        select(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .where(OrganizationMembership.organization_id == organization_id)
        .order_by(User.name.asc())
    ).all()
    return [
        MembershipPublic(
            user_id=membership.user_id,
            organization_id=membership.organization_id,
            role=membership.role,
            email=user.email,
            name=user.name,
        )
        for membership, user in rows
    ]


@router.post(
    "/{organization_id}/members", response_model=MembershipPublic, status_code=201
)
def add_member(
    organization_id: UUID,
    payload: MembershipCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MembershipPublic:
    admin_membership = require_admin(organization_id, current_user, db)
    if payload.role == MembershipRole.OWNER:
        raise HTTPException(
            status_code=400,
            detail="Owner role cannot be assigned through this endpoint",
        )
    if (
        payload.role == MembershipRole.ADMIN
        and admin_membership.role != MembershipRole.OWNER
    ):
        raise HTTPException(
            status_code=403, detail="Only an owner can assign administrators"
        )
    user = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if db.get(OrganizationMembership, (user.id, organization_id)) is not None:
        raise HTTPException(
            status_code=409, detail="User is already a member of this organization"
        )

    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=organization_id,
        role=payload.role,
    )
    db.add(membership)
    db.commit()
    return MembershipPublic(
        user_id=user.id,
        organization_id=organization_id,
        role=membership.role,
        email=user.email,
        name=user.name,
    )


@router.patch("/{organization_id}/members/{user_id}", response_model=MembershipPublic)
def update_member_role(
    organization_id: UUID,
    user_id: UUID,
    payload: MembershipRoleUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MembershipPublic:
    admin_membership = require_admin(organization_id, current_user, db)
    if payload.role == MembershipRole.OWNER:
        raise HTTPException(
            status_code=400,
            detail="Owner role cannot be assigned through this endpoint",
        )
    if admin_membership.role != MembershipRole.OWNER:
        raise HTTPException(
            status_code=403, detail="Only an owner can change member roles"
        )
    membership = db.get(OrganizationMembership, (user_id, organization_id))
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    user = db.get(User, user_id)
    membership.role = payload.role
    db.commit()
    return MembershipPublic(
        user_id=user.id,
        organization_id=organization_id,
        role=membership.role,
        email=user.email,
        name=user.name,
    )


@router.delete(
    "/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    organization_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    admin_membership = require_admin(organization_id, current_user, db)
    if admin_membership.role != MembershipRole.OWNER:
        raise HTTPException(status_code=403, detail="Only an owner can remove members")
    membership = db.get(OrganizationMembership, (user_id, organization_id))
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    if membership.role == MembershipRole.OWNER:
        raise HTTPException(
            status_code=409, detail="Owner membership cannot be removed"
        )
    team_ids = db.scalars(
        select(Team.id).where(Team.organization_id == organization_id)
    ).all()
    if team_ids:
        db.query(TeamMembership).filter(
            TeamMembership.team_id.in_(team_ids),
            TeamMembership.user_id == user_id,
        ).delete(synchronize_session=False)
    db.delete(membership)
    db.commit()
