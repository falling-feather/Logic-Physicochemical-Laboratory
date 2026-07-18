"""Create the first local-preview administrator through the authoritative API."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from httpx import ASGITransport, AsyncClient, Response

from app.core.config import get_settings
from app.main import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-local-preview", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_local_preview:
        parser.error("--confirm-local-preview is required")

    settings = get_settings()
    if not settings.is_local_development:
        raise SystemExit("Administrator bootstrap is limited to local development")
    if not settings.database_url.startswith("sqlite"):
        raise SystemExit("Administrator bootstrap requires the local SQLite database")
    if not settings.admin_bootstrap_enabled:
        raise SystemExit("ASTRA_ADMIN_BOOTSTRAP_ENABLED must be true for this one command")

    try:
        raw = sys.stdin.read(16_385).lstrip("\ufeff")
        if len(raw) > 16_384:
            raise ValueError("payload is too large")
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid bootstrap payload: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"username", "password", "display_name"}:
        raise SystemExit("Bootstrap payload must contain username, password and display_name only")

    response = asyncio.run(_post_bootstrap(payload))
    if response.status_code == 201:
        user = response.json()
        print(json.dumps({
            "status": "created",
            "id": user.get("id"),
            "username": user.get("username"),
            "display_name": user.get("display_name"),
            "role": user.get("role"),
        }, ensure_ascii=False))
        return 0
    detail = response.json().get("detail", "Administrator bootstrap failed")
    if response.status_code == 409 and detail == "Admin bootstrap is already complete":
        print(json.dumps({"status": "already-complete"}, ensure_ascii=False))
        return 0
    raise SystemExit(f"Administrator bootstrap failed ({response.status_code}): {detail}")


async def _post_bootstrap(payload: dict[str, object]) -> Response:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://astra-local") as client:
        return await client.post("/api/admin/bootstrap", json=payload)


if __name__ == "__main__":
    raise SystemExit(main())
