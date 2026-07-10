from functools import lru_cache
from hashlib import sha256
import logging
from threading import Lock
from time import perf_counter
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


logger = logging.getLogger(__name__)
_ENGINE_REGISTRY: set[Engine] = set()
_ENGINE_REGISTRY_LOCK = Lock()


def _connect_args(database_url: str, settings: Any | None = None) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    if database_url.startswith("mysql+pymysql"):
        active_settings = settings or get_settings()
        return {
            "connect_timeout": active_settings.database_connect_timeout_seconds,
            "read_timeout": active_settings.database_read_timeout_seconds,
            "write_timeout": active_settings.database_write_timeout_seconds,
        }
    return {}


def _engine_options(database_url: str, settings: Any | None = None) -> dict:
    active_settings = settings or get_settings()
    options = {
        "pool_pre_ping": True,
        "future": True,
        "connect_args": _connect_args(database_url, active_settings),
    }
    if database_url == "sqlite+pysqlite:///:memory:":
        options["poolclass"] = StaticPool
    elif database_url.startswith("mysql"):
        options.update(
            {
                "pool_size": active_settings.database_pool_size,
                "max_overflow": active_settings.database_max_overflow,
                "pool_timeout": active_settings.database_pool_timeout_seconds,
                "pool_recycle": active_settings.database_pool_recycle_seconds,
                "pool_use_lifo": True,
            }
        )
    return options


@lru_cache(maxsize=None)
def make_engine(database_url: str) -> Engine:
    settings = get_settings()
    engine = create_engine(database_url, **_engine_options(database_url, settings))
    _install_slow_query_logging(
        engine,
        enabled=settings.performance_slow_query_logging_enabled,
        threshold_ms=settings.performance_slow_query_threshold_ms,
    )
    with _ENGINE_REGISTRY_LOCK:
        _ENGINE_REGISTRY.add(engine)
    return engine


@lru_cache(maxsize=None)
def get_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(database_url), autoflush=False, autocommit=False, future=True)


def init_db(database_url: str | None = None) -> None:
    from app.models import Base

    url = database_url or get_settings().database_url
    Base.metadata.create_all(bind=make_engine(url))


def reset_database_state() -> None:
    with _ENGINE_REGISTRY_LOCK:
        engines = list(_ENGINE_REGISTRY)
        _ENGINE_REGISTRY.clear()
    for engine in engines:
        engine.dispose()
    make_engine.cache_clear()
    get_session_factory.cache_clear()


def get_db():
    session_factory = get_session_factory(get_settings().database_url)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def check_database(database_url: str) -> dict:
    safe_url = _safe_url(database_url)
    try:
        engine = make_engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "ok": True,
            "status": "connected",
            "url": safe_url,
        }
    except (ImportError, ModuleNotFoundError) as exc:
        return {
            "ok": False,
            "status": "driver_missing",
            "url": safe_url,
            "error": exc.__class__.__name__,
        }
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "status": "unavailable",
            "url": safe_url,
            "error": exc.__class__.__name__,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "url": safe_url,
            "error": exc.__class__.__name__,
        }
def _safe_url(database_url: str) -> str:
    if "://" not in database_url or "@" not in database_url:
        return database_url
    scheme, rest = database_url.split("://", 1)
    _, host = rest.rsplit("@", 1)
    return f"{scheme}://***:***@{host}"


def database_engine_posture(settings: Any) -> dict[str, Any]:
    return {
        "pool_pre_ping": True,
        "pool_use_lifo": True,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_timeout_seconds": settings.database_pool_timeout_seconds,
        "pool_recycle_seconds": settings.database_pool_recycle_seconds,
        "connect_timeout_seconds": settings.database_connect_timeout_seconds,
        "read_timeout_seconds": settings.database_read_timeout_seconds,
        "write_timeout_seconds": settings.database_write_timeout_seconds,
        "automatic_transaction_retry": False,
        "slow_query_logging_enabled": settings.performance_slow_query_logging_enabled,
        "slow_query_threshold_ms": settings.performance_slow_query_threshold_ms,
        "sql_text_logged": False,
        "parameters_logged": False,
        "database_url_returned": False,
    }


def _install_slow_query_logging(engine: Engine, *, enabled: bool, threshold_ms: int) -> None:
    if not enabled or getattr(engine, "_astra_slow_query_logging", False):
        return
    setattr(engine, "_astra_slow_query_logging", True)

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor_execute(connection, cursor, statement, parameters, context, executemany):
        connection.info.setdefault("astra_query_started_at", []).append(perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after_cursor_execute(connection, cursor, statement, parameters, context, executemany):
        started = connection.info.get("astra_query_started_at", [])
        if not started:
            return
        duration_ms = (perf_counter() - started.pop()) * 1000
        if duration_ms < threshold_ms:
            return
        metadata = slow_query_metadata(statement, duration_ms=duration_ms, dialect=engine.dialect.name)
        logger.warning(
            "slow_database_query query_sha256=%s operation=%s duration_ms=%.2f dialect=%s",
            metadata["query_sha256"],
            metadata["operation"],
            metadata["duration_ms"],
            metadata["dialect"],
        )

    @event.listens_for(engine, "handle_error")
    def _handle_error(exception_context):
        connection = exception_context.connection
        if connection is None:
            return
        started = connection.info.get("astra_query_started_at", [])
        if started:
            started.pop()


def slow_query_metadata(statement: str, *, duration_ms: float, dialect: str) -> dict[str, Any]:
    normalized = " ".join(str(statement).split())
    operation = normalized.split(" ", 1)[0].upper() if normalized else "UNKNOWN"
    return {
        "query_sha256": sha256(normalized.encode("utf-8")).hexdigest(),
        "operation": operation[:16],
        "duration_ms": round(max(0.0, duration_ms), 2),
        "dialect": dialect,
        "sql_text_logged": False,
        "parameters_logged": False,
    }
