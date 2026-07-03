from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("ASTRA_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    get_settings.cache_clear()
    return TestClient(create_app())


def test_energy_conservation_render_schema(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/render/page/physics/energy-conservation")

    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == "physics/energy-conservation"
    assert payload["layout"] == "experiment-page"
    assert payload["sections"][2]["type"] == "experiment"
    assert payload["sections"][2]["experimentId"] == "energy-conservation"
    assert payload["courseUnit"]["unitId"] == "physics-energy-conservation"


def test_unknown_render_schema_returns_404(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/render/page/physics/missing")

    assert response.status_code == 404

