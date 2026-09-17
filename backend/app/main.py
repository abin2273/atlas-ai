import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("AtlasAI application starting")

    yield

    logger.info("AtlasAI application shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Enterprise Knowledge Intelligence Platform",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    logger.info("Root endpoint requested")

    return {
        "project": settings.app_name,
        "status": "running",
        "version": settings.app_version,
    }
