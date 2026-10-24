"""Version 1 API router aggregate."""
from fastapi import APIRouter

from app.routers.v1 import (  # noqa: I001
    admin,
    auth,
    destinations,
    finance,
    health,
    library,
    programs,
    profile,
    recommendations,
)

from app.routers.v1 import universities as college_universities

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(programs.router)
api_router.include_router(college_universities.router)
api_router.include_router(profile.router)
api_router.include_router(recommendations.router)
api_router.include_router(library.router)
api_router.include_router(finance.router)
api_router.include_router(destinations.router)
api_router.include_router(admin.router)
