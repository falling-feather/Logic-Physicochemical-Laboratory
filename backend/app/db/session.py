from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def make_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        future=True,
        connect_args=_connect_args(database_url),
    )


def check_database(database_url: str) -> dict:
    safe_url = _safe_url(database_url)
    try:
        engine = make_engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
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

