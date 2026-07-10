from hashlib import sha256

from fastapi import Request

from app.core.config import get_settings


_SENSITIVE_METADATA_MARKERS = (
    "password=",
    "passwd=",
    "pwd=",
    "token=",
    "secret=",
    "api_key=",
    "apikey=",
    "authorization:",
    "bearer ",
    "set-cookie",
    "cookie:",
    "session=",
    "access_token",
    "refresh_token",
    "client_secret",
    "private_key",
)
_REDACTED_METADATA_VALUE = "[redacted]"


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
    return safe_client_metadata_value(request.headers.get("user-agent"), 240)


def request_device_label(request: Request | None) -> str | None:
    if request is None:
        return None
    explicit_label = safe_client_metadata_value(
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


def safe_client_metadata_value(value: str | None, max_length: int) -> str | None:
    normalized = trim_metadata_value(value, max_length)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if any(marker in lowered for marker in _SENSITIVE_METADATA_MARKERS):
        return _REDACTED_METADATA_VALUE
    return normalized


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    if _should_trust_forwarded_for(request):
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            first_ip = forwarded_for.split(",", 1)[0].strip()
            if first_ip:
                return first_ip
    return request.client.host


def _should_trust_forwarded_for(request: Request) -> bool:
    settings = get_settings()
    if not settings.audit_trust_forwarded_for:
        return False
    trusted_proxy_hosts = set(settings.audit_trusted_proxy_host_list)
    if not trusted_proxy_hosts:
        return False
    if request.client is None:
        return False
    return request.client.host in trusted_proxy_hosts
