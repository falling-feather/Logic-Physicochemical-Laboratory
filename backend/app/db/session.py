from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _engine_options(database_url: str) -> dict:
    options = {
        "pool_pre_ping": True,
        "future": True,
        "connect_args": _connect_args(database_url),
    }
    if database_url == "sqlite+pysqlite:///:memory:":
        options["poolclass"] = StaticPool
    return options


@lru_cache(maxsize=None)
def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, **_engine_options(database_url))


@lru_cache(maxsize=None)
def get_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(database_url), autoflush=False, autocommit=False, future=True)


def init_db(database_url: str | None = None) -> None:
    from app.models import Base

    url = database_url or get_settings().database_url
    Base.metadata.create_all(bind=make_engine(url))


def reset_database_state() -> None:
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
