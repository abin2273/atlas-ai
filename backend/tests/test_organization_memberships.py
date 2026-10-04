from uuid import uuid4

import pytest
from app.db.session import SessionLocal
from app.features.organization_memberships.models import (
    MembershipRole,
    OrganizationMembership,
)
from app.features.organizations.models import Organization
from app.features.users.models import User
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def db() -> Session:
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_user_can_join_organization(db: Session) -> None:
    organization = Organization(
        name="Test Organization",
        slug=f"test-org-{uuid4()}",
    )

    user = User(
        email=f"user-{uuid4()}@example.com",
        name="Test User",
        password_hash="test-hash",
    )

    db.add_all([organization, user])
    db.flush()

    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=organization.id,
        role=MembershipRole.MEMBER,
    )

    db.add(membership)
    db.commit()

    assert membership.user_id == user.id
    assert membership.organization_id == organization.id
    assert membership.role == MembershipRole.MEMBER


def test_user_can_join_multiple_organizations(db: Session) -> None:
    user = User(
        email=f"user-{uuid4()}@example.com",
        name="Multi Org User",
        password_hash="test-hash",
    )

    organization_a = Organization(
        name="Organization A",
        slug=f"org-a-{uuid4()}",
    )

    organization_b = Organization(
        name="Organization B",
        slug=f"org-b-{uuid4()}",
    )

    db.add_all([user, organization_a, organization_b])
    db.flush()

    membership_a = OrganizationMembership(
        user_id=user.id,
        organization_id=organization_a.id,
        role=MembershipRole.OWNER,
    )

    membership_b = OrganizationMembership(
        user_id=user.id,
        organization_id=organization_b.id,
        role=MembershipRole.VIEWER,
    )

    db.add_all([membership_a, membership_b])
    db.commit()

    assert membership_a.role == MembershipRole.OWNER
    assert membership_b.role == MembershipRole.VIEWER


def test_duplicate_membership_is_rejected(db: Session) -> None:
    organization = Organization(
        name="Duplicate Test Organization",
        slug=f"duplicate-org-{uuid4()}",
    )

    user = User(
        email=f"user-{uuid4()}@example.com",
        name="Duplicate Test User",
        password_hash="test-hash",
    )

    db.add_all([organization, user])
    db.flush()

    first_membership = OrganizationMembership(
        user_id=user.id,
        organization_id=organization.id,
        role=MembershipRole.MEMBER,
    )

    db.add(first_membership)
    db.commit()

    duplicate_membership = OrganizationMembership(
        user_id=user.id,
        organization_id=organization.id,
        role=MembershipRole.ADMIN,
    )

    db.add(duplicate_membership)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()
