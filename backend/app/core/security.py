import base64
import hashlib
import hmac
import secrets
import time
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_db
from app.features.users.models import User

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return ":".join(
        (
            "scrypt",
            base64.urlsafe_b64encode(salt).decode(),
            base64.urlsafe_b64encode(derived).decode(),
        )
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, salt_value, digest_value = password_hash.split(":", 2)
        if scheme != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_value)
        expected = base64.urlsafe_b64decode(digest_value)
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def create_token(user_id: UUID) -> str:
    expires_at = int(time.time()) + settings.access_token_expire_minutes * 60
    payload = f"{user_id}:{expires_at}".encode("ascii")
    signature = hmac.new(
        settings.auth_secret_key.encode(), payload, hashlib.sha256
    ).digest()
    return f"{_encode(payload)}.{_encode(signature)}"


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload_value, signature_value = credentials.credentials.split(".", 1)
        payload = base64.urlsafe_b64decode(
            payload_value + "=" * (-len(payload_value) % 4)
        )
        signature = base64.urlsafe_b64decode(
            signature_value + "=" * (-len(signature_value) % 4)
        )
        user_id_value, expires_value = payload.decode("ascii").rsplit(":", 1)
        expected = hmac.new(
            settings.auth_secret_key.encode(), payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected) or int(expires_value) <= int(
            time.time()
        ):
            raise unauthorized
        user_id = UUID(user_id_value)
    except (ValueError, TypeError, UnicodeDecodeError):
        raise unauthorized from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user
