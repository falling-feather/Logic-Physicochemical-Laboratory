from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_health_reports_sqlite_test_database(monkeypatch):
    monkeypatch.setenv("ASTRA_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "astra-backend"
    assert payload["database"]["ok"] is True
    assert payload["database"]["status"] == "connected"

