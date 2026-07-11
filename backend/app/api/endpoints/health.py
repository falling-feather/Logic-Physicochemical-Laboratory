from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_database


router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    database_check = check_database(settings.database_url)
    database = {key: value for key, value in database_check.items() if key != "url"}
    database["url_returned"] = False
    return {
        "status": "ok" if database["ok"] else "degraded",
        "service": "astra-backend",
        "version": settings.app_version,
        "environment": settings.environment,
        "database": database,
    }

