from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_database


router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    database = check_database(settings.database_url)
    return {
        "status": "ok" if database["ok"] else "degraded",
        "service": "astra-backend",
        "version": settings.app_version,
        "environment": settings.environment,
        "database": database,
    }

