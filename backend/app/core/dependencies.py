from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.db.session import SessionLocal


def get_settings() -> Settings:
    return settings


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
