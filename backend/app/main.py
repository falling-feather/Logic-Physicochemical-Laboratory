from contextlib import asynccontextmanager
import logging
from uuid import uuid4

from fastapi import Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import get_session_factory, init_db
from app.services.content_catalog import ensure_seed_pages
from app.services.content_script_asset_scan_scheduler import scheduler_from_settings as content_script_scheduler_from_settings
from app.services.background_task_worker import worker_from_settings
from app.services.knowledge_snapshot_scheduler import scheduler_from_settings


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )
    if settings.auto_create_tables:
        init_db(settings.database_url)
        session_factory = get_session_factory(settings.database_url)
        with session_factory() as db:
            ensure_seed_pages(db)

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Accept",
                "X-Request-ID",
                "X-Device-Label",
                "X-Device-Name",
            ],
            expose_headers=["X-Request-ID"],
        )

    @app.middleware("http")
    async def attach_request_id_and_api_cache_policy(request: Request, call_next):
        request_id = _request_id_from_header(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        is_api = _is_api_path(request.url.path, settings.api_prefix)
        try:
            response = await call_next(request)
        except Exception:
            if not is_api:
                raise
            logger.exception("Unhandled API error request_id=%s path=%s", request_id, request.url.path)
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
            origin = request.headers.get("origin", "")
            if origin in settings.cors_origin_list:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
                response.headers["Vary"] = "Origin"
        response.headers["X-Request-ID"] = request_id
        if is_api:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    scheduler = None
    content_script_scheduler = None
    background_task_worker = None
    if settings.background_task_worker_enabled:
        background_task_worker = worker_from_settings(settings)
        app.state.background_task_worker = background_task_worker
        background_task_worker.start()
    if settings.knowledge_snapshot_scheduler_enabled and not settings.background_task_worker_enabled:
        scheduler = scheduler_from_settings(settings)
        app.state.knowledge_snapshot_scheduler = scheduler
        scheduler.start()
    if settings.content_script_remote_drift_scheduler_enabled and not settings.background_task_worker_enabled:
        content_script_scheduler = content_script_scheduler_from_settings(settings)
        app.state.content_script_remote_drift_scheduler = content_script_scheduler
        content_script_scheduler.start()
    try:
        yield
    finally:
        if background_task_worker is not None:
            await background_task_worker.stop()
        if content_script_scheduler is not None:
            await content_script_scheduler.stop()
        if scheduler is not None:
            await scheduler.stop()


def _request_id_from_header(value: str | None) -> str:
    request_id = (value or "").strip()
    if not request_id:
        return uuid4().hex
    return request_id[:64]


def _is_api_path(path: str, api_prefix: str) -> bool:
    prefix = api_prefix.rstrip("/") or "/api"
    return path == prefix or path.startswith(f"{prefix}/")


app = create_app()
