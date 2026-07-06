from hashlib import sha256

from fastapi import Request

from app.core.config import get_settings


def request_metadata(request: Request | None) -> dict[str, str | None]:
    if request is None:
        return {
            "request_id": None,
            "client_ip_hash": None,
            "user_agent": None,
            "request_method": None,
            "request_path": None,
        }
    request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
    return {
        "request_id": trim_metadata_value(request_id, 64),
        "client_ip_hash": request_client_ip_hash(request),
        "user_agent": request_user_agent(request),
        "request_method": trim_metadata_value(request.method.upper(), 12),
        "request_path": trim_metadata_value(str(request.url.path), 240),
    }


def request_client_ip_hash(request: Request | None) -> str | None:
    if request is None:
        return None
    client_ip = _client_ip(request)
    if not client_ip:
        return None
    salt = get_settings().audit_ip_hash_salt
    return sha256(f"{salt}:{client_ip}".encode("utf-8")).hexdigest()


def request_user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    return trim_metadata_value(request.headers.get("user-agent"), 240)


def request_device_label(request: Request | None) -> str | None:
    if request is None:
        return None
    explicit_label = trim_metadata_value(
        request.headers.get("x-device-label") or request.headers.get("x-device-name"),
        120,
    )
    if explicit_label:
        return explicit_label
    return trim_metadata_value(request_user_agent(request), 120)


def trim_metadata_value(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    return value[:max_length]


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_ip = forwarded_for.split(",", 1)[0].strip()
        if first_ip:
            return first_ip
    if request.client is None:
        return None
    return request.client.host
