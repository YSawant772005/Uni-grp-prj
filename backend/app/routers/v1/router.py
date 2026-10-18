"""Version 1 API router aggregate."""
from fastapi import APIRouter

from app.routers.v1 import auth, health, programs, profile, recommendations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(programs.router)
api_router.include_router(profile.router)
api_router.include_router(recommendations.router)
