from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.permissions import require_admin, require_membership
from app.core.security import get_current_user
from app.features.organization_memberships.models import OrganizationMembership
from app.features.teams.models import Team, TeamMembership
from app.features.teams.schemas import (
    TeamCreate,
    TeamMemberCreate,
    TeamMemberPublic,
    TeamPublic,
)
from app.features.users.models import User

router = APIRouter(prefix="/organizations/{organization_id}/teams", tags=["Teams"])


def _get_team(organization_id: UUID, team_id: UUID, db: Session) -> Team:
    team = db.execute(
        select(Team).where(
            Team.id == team_id,
            Team.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("", response_model=list[TeamPublic])
def list_teams(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Team]:
    require_membership(organization_id, current_user, db)
    return list(
        db.scalars(
            select(Team)
            .where(Team.organization_id == organization_id)
            .order_by(Team.name.asc())
        )
    )


@router.post("", response_model=TeamPublic, status_code=status.HTTP_201_CREATED)
def create_team(
    organization_id: UUID,
    payload: TeamCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Team:
    require_admin(organization_id, current_user, db)
    team = Team(
        organization_id=organization_id,
        name=payload.name,
        slug=payload.slug,
    )
    db.add(team)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A team with that slug already exists in this organization",
        ) from None
    db.refresh(team)
    return team


@router.get("/{team_id}/members", response_model=list[TeamMemberPublic])
def list_team_members(
    organization_id: UUID,
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[TeamMemberPublic]:
    require_membership(organization_id, current_user, db)
    _get_team(organization_id, team_id, db)
    rows = db.execute(
        select(TeamMembership, User)
        .join(User, User.id == TeamMembership.user_id)
        .where(TeamMembership.team_id == team_id)
        .order_by(User.name.asc())
    ).all()
    return [
        TeamMemberPublic(
            team_id=membership.team_id,
            user_id=user.id,
            email=user.email,
            name=user.name,
        )
        for membership, user in rows
    ]


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberPublic,
    status_code=status.HTTP_201_CREATED,
)
def add_team_member(
    organization_id: UUID,
    team_id: UUID,
    payload: TeamMemberCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TeamMemberPublic:
    require_admin(organization_id, current_user, db)
    _get_team(organization_id, team_id, db)
    user = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if db.get(OrganizationMembership, (user.id, organization_id)) is None:
        raise HTTPException(
            status_code=409,
            detail="User must be an organization member before joining a team",
        )
    if db.get(TeamMembership, (team_id, user.id)) is not None:
        raise HTTPException(status_code=409, detail="User is already on this team")

    membership = TeamMembership(team_id=team_id, user_id=user.id)
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="User is already on this team"
        ) from None
    return TeamMemberPublic(
        team_id=team_id,
        user_id=user.id,
        email=user.email,
        name=user.name,
    )


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(
    organization_id: UUID,
    team_id: UUID,
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    require_admin(organization_id, current_user, db)
    _get_team(organization_id, team_id, db)
    membership = db.get(TeamMembership, (team_id, user_id))
    if membership is None:
        raise HTTPException(status_code=404, detail="Team membership not found")
    db.delete(membership)
    db.commit()


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    organization_id: UUID,
    team_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    require_admin(organization_id, current_user, db)
    team = _get_team(organization_id, team_id, db)
    db.delete(team)
    db.commit()
