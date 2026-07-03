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


def test_cors_allows_local_preview_origin(client):
    response = client.options(
        "/api/render/page/physics/energy-conservation",
        headers={
            "Origin": "http://localhost:8766",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8766"
