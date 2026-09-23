from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.features.organizations.models import Organization  # noqa: F401
from app.features.users.models import User  # noqa: F401
