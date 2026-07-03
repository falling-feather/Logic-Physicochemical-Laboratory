def test_health_reports_sqlite_test_database(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "astra-backend"
    assert payload["database"]["ok"] is True
    assert payload["database"]["status"] == "connected"
