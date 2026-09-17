from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.features.organizations.models import Organization  # noqa: F401