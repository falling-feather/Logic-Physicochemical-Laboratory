import hashlib
import json

from app.main import app


ADMIN_ROUTE_COUNT = 73
ADMIN_ROUTE_SIGNATURE_SHA256 = "c8f674bf3cb7c0e6d183b64141c60c777c69582ad16988d4f2479994dadab72b"
ADMIN_OPENAPI_PATH_COUNT = 69
ADMIN_OPENAPI_SIGNATURE_SHA256 = "e7b82c14acac30fba40ed29f2a273d628d7170a279fa0ced0f41f41c89909b82"


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _admin_route_signature() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for route in app.routes:
        if not route.path.startswith("/api/admin"):
            continue
        response_model = getattr(route, "response_model", None)
        rows.append(
            {
                "path": route.path,
                "methods": sorted(route.methods or []),
                "name": route.name,
                "status_code": route.status_code,
                "response_model": getattr(response_model, "__name__", str(response_model)),
            }
        )
    return rows


def _admin_openapi_signature() -> dict[str, object]:
    allowed_methods = {"get", "post", "patch", "put", "delete"}
    return {
        path: {
            method: {
                "operationId": operation.get("operationId"),
                "responses": operation.get("responses"),
            }
            for method, operation in path_item.items()
            if method in allowed_methods
        }
        for path, path_item in app.openapi()["paths"].items()
        if path.startswith("/api/admin")
    }


def test_admin_route_and_openapi_contract_remain_compatible() -> None:
    routes = _admin_route_signature()
    openapi_paths = _admin_openapi_signature()

    assert len(routes) == ADMIN_ROUTE_COUNT
    assert _digest(routes) == ADMIN_ROUTE_SIGNATURE_SHA256
    assert len(openapi_paths) == ADMIN_OPENAPI_PATH_COUNT
    assert _digest(openapi_paths) == ADMIN_OPENAPI_SIGNATURE_SHA256

    assert routes[:4] == [
        {
            "path": "/api/admin/bootstrap",
            "methods": ["POST"],
            "name": "bootstrap_admin",
            "status_code": 201,
            "response_model": "AdminUserRead",
        },
        {
            "path": "/api/admin/users",
            "methods": ["GET"],
            "name": "list_users",
            "status_code": None,
            "response_model": "AdminUserPage",
        },
        {
            "path": "/api/admin/users/{user_id}",
            "methods": ["PATCH"],
            "name": "update_user",
            "status_code": None,
            "response_model": "AdminUserRead",
        },
        {
            "path": "/api/admin/users/{user_id}/password-reset",
            "methods": ["POST"],
            "name": "reset_user_password",
            "status_code": None,
            "response_model": "AdminUserPasswordResetResponse",
        },
    ]
