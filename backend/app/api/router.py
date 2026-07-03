from fastapi import APIRouter

from app.api.endpoints import auth, classes, content, health, render, schools, users


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(schools.router, prefix="/schools", tags=["schools"])
api_router.include_router(classes.router, prefix="/classes", tags=["classes"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(render.router, prefix="/render", tags=["render"])
