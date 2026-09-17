import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.dependencies import get_settings


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
async def health(
    app_settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    logger.info("Health check requested")

    return {
        "status": "healthy",
        "environment": app_settings.environment,
    }