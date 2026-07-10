from app.core.config import get_settings
from app.db.session import make_engine


def test_health_reports_sqlite_test_database(client):
    response = client.get("/api/health", headers={"X-Request-ID": "health-smoke"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "health-smoke"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "astra-backend"
    assert payload["database"]["ok"] is True
    assert payload["database"]["status"] == "connected"


def test_health_probe_reuses_the_application_connection_pool(client):
    engine = make_engine(get_settings().database_url)
    pool = engine.pool

    response = client.get("/api/health")

    assert response.status_code == 200
    assert engine.pool is pool


def test_health_generates_request_id_when_header_missing(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert request_id
    assert len(request_id) <= 64
    assert response.headers["Cache-Control"] == "no-store"


def test_cors_allows_local_preview_origin(client):
    response = client.options(
        "/api/render/page/physics/energy-conservation",
        headers={
            "Origin": "http://localhost:8766",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "X-Device-Name, Authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8766"
    assert "DELETE" in response.headers["access-control-allow-methods"]
    assert "X-Device-Name" in response.headers["access-control-allow-headers"]
