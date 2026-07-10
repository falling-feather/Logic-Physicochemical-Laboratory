import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import Settings


def _assert_api_security_headers(response) -> None:
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["X-Request-ID"]


@pytest.mark.parametrize("status_code", [200, 401, 403, 404, 409, 422, 429, 503])
def test_api_statuses_always_return_no_store(client, status_code: int):
    route_path = f"/api/cache-policy-status-{status_code}"

    async def status_route():
        if status_code == 200:
            return {"ok": True}
        raise HTTPException(status_code=status_code, detail="cache policy test")

    client.app.add_api_route(route_path, status_route, methods=["GET"])
    response = client.get(route_path, headers={"X-Request-ID": f"cache-{status_code}"})

    assert response.status_code == status_code
    assert response.headers["X-Request-ID"] == f"cache-{status_code}"
    _assert_api_security_headers(response)


def test_unhandled_api_error_is_sanitized_and_no_store(client):
    async def boom():
        raise RuntimeError("database secret must not reach the client")

    client.app.add_api_route("/api/cache-policy-boom", boom, methods=["GET"])
    response = client.get(
        "/api/cache-policy-boom",
        headers={
            "X-Request-ID": "cache-boom",
            "Origin": "http://localhost:8766",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "database secret" not in response.text
    assert response.headers["X-Request-ID"] == "cache-boom"
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:8766"
    assert response.headers["Access-Control-Expose-Headers"] == "X-Request-ID"
    _assert_api_security_headers(response)


def test_cors_preflight_is_no_store_and_has_request_id(client):
    response = client.options(
        "/api/render/page/physics/energy-conservation",
        headers={
            "Origin": "http://localhost:8766",
            "Access-Control-Request-Method": "GET",
            "X-Request-ID": "cache-preflight",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8766"
    assert response.headers["X-Request-ID"] == "cache-preflight"
    _assert_api_security_headers(response)


def test_api_prefix_match_does_not_cover_apiary(client):
    async def apiary():
        return {"ok": True}

    client.app.add_api_route("/apiary/cache-policy", apiary, methods=["GET"])
    response = client.get("/apiary/cache-policy")

    assert response.status_code == 200
    assert "Cache-Control" not in response.headers
    assert response.headers["X-Request-ID"]


def test_api_cache_control_setting_cannot_enable_storage():
    with pytest.raises(ValidationError):
        Settings(api_cache_control="max-age=600")
