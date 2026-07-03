from fastapi import APIRouter

from app.api.endpoints import content, health, render


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(render.router, prefix="/render", tags=["render"])

