from fastapi import APIRouter

from app.api.endpoints import (
    auth,
    classes,
    content,
    courses,
    health,
    learning_events,
    points,
    progress,
    render,
    schools,
    submissions,
    users,
)


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(schools.router, prefix="/schools", tags=["schools"])
api_router.include_router(classes.router, prefix="/classes", tags=["classes"])
api_router.include_router(courses.router, prefix="/courses", tags=["courses"])
api_router.include_router(learning_events.router, prefix="/learning-events", tags=["learning-events"])
api_router.include_router(submissions.router, tags=["submissions"])
api_router.include_router(points.router, prefix="/points", tags=["points"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(render.router, prefix="/render", tags=["render"])
