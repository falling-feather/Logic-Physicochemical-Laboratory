from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import get_session_factory, init_db
from app.services.content_catalog import ensure_seed_pages
from app.services.knowledge_snapshot_scheduler import scheduler_from_settings


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

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = _request_id_from_header(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith(settings.api_prefix):
            response.headers["Cache-Control"] = settings.api_cache_control
            response.headers["Pragma"] = "no-cache"
        return response

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
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    scheduler = None
    if settings.knowledge_snapshot_scheduler_enabled:
        scheduler = scheduler_from_settings(settings)
        app.state.knowledge_snapshot_scheduler = scheduler
        scheduler.start()
    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.stop()


def _request_id_from_header(value: str | None) -> str:
    request_id = (value or "").strip()
    if not request_id:
        return uuid4().hex
    return request_id[:64]


app = create_app()
