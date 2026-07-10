from __future__ import annotations

import http.client
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


class OutboundDestinationError(ValueError):
    pass


def fetch_public_https_bytes(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: int,
    user_agent: str,
) -> bytes:
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise OutboundDestinationError("Outbound URL has an invalid port") from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or port not in {None, 443}
    ):
        raise OutboundDestinationError("Outbound URL must be credential-free HTTPS on port 443")

    host = parsed.hostname.rstrip(".").lower()
    addresses = _resolve_public_addresses(host, 443)
    request_target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    connection = _PinnedHTTPSConnection(host, 443, addresses, timeout=timeout_seconds)
    try:
        connection.request(
            "GET",
            request_target,
            headers={
                "Accept": "application/javascript, text/javascript, */*;q=0.1",
                "User-Agent": user_agent,
            },
        )
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise OutboundDestinationError("Outbound redirects are disabled")
        if response.status != 200:
            raise OutboundDestinationError("Outbound endpoint did not return HTTP 200")
        content_length = response.getheader("Content-Length")
        if content_length is not None:
            try:
                parsed_content_length = int(content_length)
            except ValueError as exc:
                raise OutboundDestinationError("Outbound response has an invalid Content-Length") from exc
            if parsed_content_length > max_bytes:
                raise OutboundDestinationError("Outbound response exceeds the maximum size")
        payload = response.read(max_bytes + 1)
    finally:
        connection.close()
    if len(payload) > max_bytes:
        raise OutboundDestinationError("Outbound response exceeds the maximum size")
    return payload


def _resolve_public_addresses(host: str, port: int) -> tuple[str, ...]:
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise OutboundDestinationError("Outbound host could not be resolved") from exc
    addresses: list[str] = []
    for _, _, _, _, sockaddr in records:
        address_text = str(sockaddr[0])
        address = ipaddress.ip_address(address_text)
        if address.version == 6 and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
            address_text = str(address)
        if not address.is_global:
            raise OutboundDestinationError("Outbound host resolved to a non-public address")
        if address_text not in addresses:
            addresses.append(address_text)
    if not addresses:
        raise OutboundDestinationError("Outbound host has no usable address")
    return tuple(addresses)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        port: int,
        addresses: tuple[str, ...],
        *,
        timeout: int,
    ) -> None:
        super().__init__(host=host, port=port, timeout=timeout)
        self._validated_addresses = addresses

    def connect(self) -> None:
        last_error: OSError | None = None
        for address in self._validated_addresses:
            raw_socket: socket.socket | None = None
            try:
                raw_socket = socket.create_connection(
                    (address, self.port),
                    self.timeout,
                    self.source_address,
                )
                self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
                return
            except OSError as exc:
                if raw_socket is not None:
                    raw_socket.close()
                last_error = exc
        raise OSError("Unable to connect to a validated outbound address") from last_error
