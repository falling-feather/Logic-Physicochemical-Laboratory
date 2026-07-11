import hmac
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from app.core.config import Settings
from app.models import AdminAlertOutboxEntry


@dataclass(frozen=True)
class AlertDeliveryReceipt:
    provider: str
    status_code: int
    receipt_hash: str


class AlertDeliveryError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class AlertDeliveryAdapter(Protocol):
    provider: str
    delivery_target: str

    def deliver(self, envelope: dict[str, Any], *, idempotency_key: str) -> AlertDeliveryReceipt: ...


class WebhookAlertDeliveryAdapter:
    provider = "webhook"
    delivery_target = "configured_webhook"

    def __init__(self, *, url: str, token: str, timeout_seconds: int) -> None:
        self._url = url
        self._token = token
        self._timeout_seconds = timeout_seconds

    def deliver(self, envelope: dict[str, Any], *, idempotency_key: str) -> AlertDeliveryReceipt:
        body = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self._token.encode("utf-8"), body, sha256).hexdigest()
        request = urllib_request.Request(
            self._url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json; charset=utf-8",
                "Idempotency-Key": idempotency_key,
                "User-Agent": "Astra-Alert-Delivery/1",
                "X-Astra-Signature-SHA256": signature,
            },
        )
        try:
            with _open_webhook_request(request, timeout=self._timeout_seconds) as response:
                response_status = getattr(response, "status", None)
                status_code = int(response_status if response_status is not None else response.getcode())
                response_body = response.read(64 * 1024)
        except urllib_error.HTTPError as exc:
            code = int(exc.code)
            raise AlertDeliveryError(
                "webhook_http_5xx" if code >= 500 else "webhook_http_4xx",
                retryable=code >= 500 or code == 429,
            ) from None
        except (TimeoutError, urllib_error.URLError):
            raise AlertDeliveryError("webhook_network_error", retryable=True) from None
        except Exception:
            raise AlertDeliveryError("webhook_unexpected_error", retryable=False) from None
        if status_code < 200 or status_code >= 300:
            raise AlertDeliveryError(
                "webhook_http_5xx" if status_code >= 500 else "webhook_http_4xx",
                retryable=status_code >= 500 or status_code == 429,
            )
        receipt_hash = sha256(
            f"{status_code}:".encode("ascii") + response_body
        ).hexdigest()
        return AlertDeliveryReceipt(
            provider=self.provider,
            status_code=status_code,
            receipt_hash=receipt_hash,
        )


class _NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def _open_webhook_request(request: urllib_request.Request, *, timeout: int):
    opener = urllib_request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def alert_delivery_posture(settings: Settings) -> dict[str, Any]:
    url = (settings.alert_delivery_webhook_url or "").strip()
    parsed = urlparse(url) if url else None
    token = settings.alert_delivery_webhook_token
    configured = bool(
        settings.alert_delivery_provider == "webhook"
        and parsed is not None
        and parsed.scheme == "https"
        and parsed.netloc
        and token is not None
        and token.get_secret_value().strip()
    )
    return {
        "enabled": settings.alert_delivery_enabled,
        "provider": settings.alert_delivery_provider,
        "configured": configured,
        "delivery_target": "configured_webhook" if configured else None,
        "credentials_source": "environment_or_secure_settings",
        "timeout_seconds": settings.alert_delivery_timeout_seconds,
        "batch_limit": settings.alert_delivery_batch_limit,
        "automatic_dispatch": False,
        "payload_policy": "redacted_alert_envelope_v1",
    }


def build_alert_delivery_adapter(settings: Settings) -> AlertDeliveryAdapter:
    posture = alert_delivery_posture(settings)
    if not posture["enabled"]:
        raise AlertDeliveryError("external_delivery_disabled", retryable=False)
    if not posture["configured"]:
        raise AlertDeliveryError("external_delivery_not_configured", retryable=False)
    token = settings.alert_delivery_webhook_token
    assert token is not None
    return WebhookAlertDeliveryAdapter(
        url=(settings.alert_delivery_webhook_url or "").strip(),
        token=token.get_secret_value().strip(),
        timeout_seconds=settings.alert_delivery_timeout_seconds,
    )


def build_alert_delivery_envelope(entry: AdminAlertOutboxEntry) -> dict[str, Any]:
    return {
        "schema": "astra.alert-envelope.v1",
        "entry_id": entry.id,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "source_key_sha256": sha256(entry.source_key.encode("utf-8")).hexdigest(),
        "event_code": entry.event_code,
        "severity": entry.severity,
        "action_hint": entry.action_hint,
        "payload_hash": entry.payload_hash,
        "first_seen_at": entry.first_seen_at.isoformat(),
        "last_seen_at": entry.last_seen_at.isoformat(),
        "seen_count": entry.seen_count,
    }
