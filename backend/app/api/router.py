from fastapi import APIRouter

from app.features.auth.router import router as auth_router
from app.features.documents.router import router as documents_router
from app.features.health.router import router as health_router
from app.features.organizations.router import router as organizations_router
from app.features.teams.router import router as teams_router
from app.features.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(organizations_router)
api_router.include_router(teams_router)
api_router.include_router(documents_router)
