from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.features.documents.models import Document, DocumentChunk  # noqa: F401
from app.features.organization_memberships.models import (
    OrganizationMembership,  # noqa: F401
)
from app.features.organizations.models import Organization  # noqa: F401
from app.features.teams.models import Team, TeamMembership  # noqa: F401
from app.features.users.models import User  # noqa: F401

connect_args = {}
engine_kwargs = {}

if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine_kwargs = {"connect_args": connect_args}

engine = create_engine(settings.database_url, **engine_kwargs)
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
