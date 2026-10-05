from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.features.users.models import User
from app.features.users.schemas import UserPublic

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserPublic)
def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
