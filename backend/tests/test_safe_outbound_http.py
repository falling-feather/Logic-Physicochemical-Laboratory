import socket

import pytest

from app.services import safe_outbound_http


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.8", "169.254.169.254", "::1", "fc00::1", "fe80::1"],
)
def test_resolver_rejects_non_public_addresses(monkeypatch, address):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    monkeypatch.setattr(
        safe_outbound_http.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))],
    )

    with pytest.raises(safe_outbound_http.OutboundDestinationError, match="non-public"):
        safe_outbound_http._resolve_public_addresses("cdn.example.test", 443)


def test_resolver_rejects_mixed_public_and_private_answers(monkeypatch):
    monkeypatch.setattr(
        safe_outbound_http.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443)),
        ],
    )

    with pytest.raises(safe_outbound_http.OutboundDestinationError, match="non-public"):
        safe_outbound_http._resolve_public_addresses("cdn.example.test", 443)


def test_fetch_connects_only_to_resolved_public_address_and_bounds_read(monkeypatch):
    captured = {}

    class FakeResponse:
        status = 200

        def getheader(self, name):
            return None

        def read(self, size):
            captured["read_size"] = size
            return b"approved bytes"

    class FakeConnection:
        def __init__(self, host, port, addresses, *, timeout):
            captured.update(host=host, port=port, addresses=addresses, timeout=timeout)

        def request(self, method, target, headers):
            captured.update(method=method, target=target, headers=headers)

        def getresponse(self):
            return FakeResponse()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(
        safe_outbound_http,
        "_resolve_public_addresses",
        lambda host, port: ("93.184.216.34",),
    )
    monkeypatch.setattr(safe_outbound_http, "_PinnedHTTPSConnection", FakeConnection)

    payload = safe_outbound_http.fetch_public_https_bytes(
        "https://cdn.example.test/assets/tool.js",
        max_bytes=1024,
        timeout_seconds=5,
        user_agent="test-agent",
    )

    assert payload == b"approved bytes"
    assert captured["addresses"] == ("93.184.216.34",)
    assert captured["target"] == "/assets/tool.js"
    assert captured["read_size"] == 1025
    assert captured["closed"] is True


def test_fetch_rejects_redirect_response_without_following_location(monkeypatch):
    class RedirectResponse:
        status = 302

        def getheader(self, name):
            return "https://127.0.0.1/private" if name == "Location" else None

    class FakeConnection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return RedirectResponse()

        def close(self):
            pass

    monkeypatch.setattr(safe_outbound_http, "_resolve_public_addresses", lambda *args: ("93.184.216.34",))
    monkeypatch.setattr(safe_outbound_http, "_PinnedHTTPSConnection", FakeConnection)

    with pytest.raises(safe_outbound_http.OutboundDestinationError, match="redirects are disabled"):
        safe_outbound_http.fetch_public_https_bytes(
            "https://cdn.example.test/tool.js",
            max_bytes=1024,
            timeout_seconds=5,
            user_agent="test-agent",
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://cdn.example.test/tool.js",
        "https://127.0.0.1:444/tool.js",
        "https://user:secret@cdn.example.test/tool.js",
        "https://cdn.example.test/tool.js#fragment",
    ],
)
def test_fetch_rejects_unsafe_url_shapes_before_resolution(monkeypatch, url):
    monkeypatch.setattr(
        safe_outbound_http,
        "_resolve_public_addresses",
        lambda *args: pytest.fail("unsafe URL must fail before DNS resolution"),
    )
    with pytest.raises(safe_outbound_http.OutboundDestinationError):
        safe_outbound_http.fetch_public_https_bytes(
            url,
            max_bytes=1024,
            timeout_seconds=5,
            user_agent="test-agent",
        )
