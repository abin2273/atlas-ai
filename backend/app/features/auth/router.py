from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import (
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.features.users.models import User
from app.features.users.schemas import TokenResponse, UserCreate, UserLogin, UserPublic

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
def register_user(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that email already exists",
        ) from None
    db.refresh(user)
    return TokenResponse(
        access_token=create_token(user.id), user=UserPublic.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
def login_user(
    payload: UserLogin,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_token(user.id), user=UserPublic.model_validate(user)
    )


@router.get("/me", response_model=UserPublic)
def get_authenticated_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
