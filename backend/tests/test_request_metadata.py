from hashlib import sha256

import pytest
from starlette.requests import Request

from app.core.config import get_settings
from app.services.request_metadata import request_client_ip_hash


@pytest.fixture(autouse=True)
def _clear_settings_cache_after_test():
    yield
    get_settings.cache_clear()


def test_request_client_ip_hash_ignores_forwarded_for_by_default(monkeypatch):
    monkeypatch.delenv("ASTRA_AUDIT_TRUST_FORWARDED_FOR", raising=False)
    monkeypatch.delenv("ASTRA_AUDIT_TRUSTED_PROXY_HOSTS", raising=False)
    get_settings.cache_clear()
    request = _request(
        headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"},
        client_host="198.51.100.25",
    )

    assert request_client_ip_hash(request) == _expected_hash("198.51.100.25")


def test_request_client_ip_hash_requires_configured_trusted_proxy(monkeypatch):
    monkeypatch.setenv("ASTRA_AUDIT_TRUST_FORWARDED_FOR", "true")
    monkeypatch.delenv("ASTRA_AUDIT_TRUSTED_PROXY_HOSTS", raising=False)
    get_settings.cache_clear()
    request = _request(
        headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"},
        client_host="198.51.100.25",
    )

    assert request_client_ip_hash(request) == _expected_hash("198.51.100.25")


def test_request_client_ip_hash_uses_forwarded_for_from_trusted_proxy(monkeypatch):
    monkeypatch.setenv("ASTRA_AUDIT_TRUST_FORWARDED_FOR", "true")
    monkeypatch.setenv("ASTRA_AUDIT_TRUSTED_PROXY_HOSTS", "198.51.100.25, 198.51.100.26")
    get_settings.cache_clear()
    request = _request(
        headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"},
        client_host="198.51.100.25",
    )

    assert request_client_ip_hash(request) == _expected_hash("203.0.113.10")


def test_request_client_ip_hash_ignores_forwarded_for_from_untrusted_proxy(monkeypatch):
    monkeypatch.setenv("ASTRA_AUDIT_TRUST_FORWARDED_FOR", "true")
    monkeypatch.setenv("ASTRA_AUDIT_TRUSTED_PROXY_HOSTS", "198.51.100.26")
    get_settings.cache_clear()
    request = _request(
        headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"},
        client_host="198.51.100.25",
    )

    assert request_client_ip_hash(request) == _expected_hash("198.51.100.25")


def _request(*, headers: dict[str, str], client_host: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": "/unit",
            "raw_path": b"/unit",
            "query_string": b"",
            "server": ("testserver", 80),
            "client": (client_host, 12345),
            "headers": [(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in headers.items()],
        }
    )


def _expected_hash(ip_address: str) -> str:
    return sha256(f"astra-dev-audit-salt:{ip_address}".encode("utf-8")).hexdigest()
