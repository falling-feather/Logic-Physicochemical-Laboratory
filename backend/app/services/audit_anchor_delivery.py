from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

from app.core.config import Settings
from app.models import AuditArchiveAnchor


@dataclass(frozen=True)
class AuditAnchorReceipt:
    provider: str
    status_code: int
    receipt_id: str
    anchored_at: datetime
    receipt_hash: str


class AuditAnchorDeliveryError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class AuditAnchorAdapter(Protocol):
    provider: str

    def anchor(self, envelope: dict[str, Any], *, idempotency_key: str) -> AuditAnchorReceipt: ...


class WebhookAuditAnchorAdapter:
    provider = "webhook"

    def __init__(self, *, url: str, token: str, timeout_seconds: int) -> None:
        self._url = url
        self._token = token
        self._timeout_seconds = timeout_seconds

    def anchor(self, envelope: dict[str, Any], *, idempotency_key: str) -> AuditAnchorReceipt:
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
                "User-Agent": "Astra-Audit-Anchor/1",
                "X-Astra-Signature-SHA256": signature,
            },
        )
        try:
            with _open_anchor_request(request, timeout=self._timeout_seconds) as response:
                response_status = getattr(response, "status", None)
                status_code = int(response_status if response_status is not None else response.getcode())
                response_body = response.read(64 * 1024)
        except urllib_error.HTTPError as exc:
            code = int(exc.code)
            raise AuditAnchorDeliveryError(
                "anchor_http_5xx" if code >= 500 else "anchor_http_4xx",
                retryable=code >= 500 or code == 429,
            ) from None
        except (TimeoutError, urllib_error.URLError):
            raise AuditAnchorDeliveryError("anchor_network_error", retryable=True) from None
        except Exception:
            raise AuditAnchorDeliveryError("anchor_unexpected_error", retryable=False) from None
        if status_code < 200 or status_code >= 300:
            raise AuditAnchorDeliveryError(
                "anchor_http_5xx" if status_code >= 500 else "anchor_http_4xx",
                retryable=status_code >= 500 or status_code == 429,
            )
        try:
            payload = json.loads(response_body)
            receipt_id = str(payload["receiptId"]).strip()
            returned_manifest_hash = str(payload["manifestSha256"]).strip().lower()
            anchored_at = _parse_datetime(str(payload["anchoredAt"]))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            raise AuditAnchorDeliveryError("anchor_invalid_receipt", retryable=False) from None
        if not receipt_id or len(receipt_id) > 200:
            raise AuditAnchorDeliveryError("anchor_invalid_receipt", retryable=False)
        if returned_manifest_hash != str(envelope.get("manifest_sha256") or "").lower():
            raise AuditAnchorDeliveryError("anchor_manifest_hash_mismatch", retryable=False)
        return AuditAnchorReceipt(
            provider=self.provider,
            status_code=status_code,
            receipt_id=receipt_id,
            anchored_at=anchored_at,
            receipt_hash=sha256(f"{status_code}:".encode("ascii") + response_body).hexdigest(),
        )


class _NoRedirectHandler(urllib_request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def _open_anchor_request(request: urllib_request.Request, *, timeout: int):
    return urllib_request.build_opener(_NoRedirectHandler()).open(request, timeout=timeout)


def audit_anchor_posture(settings: Settings) -> dict[str, Any]:
    url = (settings.audit_anchor_webhook_url or "").strip()
    parsed = urlparse(url) if url else None
    token = settings.audit_anchor_webhook_token
    configured = bool(
        settings.audit_anchor_provider == "webhook"
        and parsed is not None
        and parsed.scheme == "https"
        and parsed.netloc
        and token is not None
        and token.get_secret_value().strip()
    )
    return {
        "enabled": settings.audit_anchor_enabled,
        "provider": settings.audit_anchor_provider,
        "configured": configured,
        "transport": "https_hmac_sha256",
        "receipt_contract": "astra.audit-archive-anchor-receipt.v1",
        "credentials_source": "environment_or_secure_settings",
        "timeout_seconds": settings.audit_anchor_timeout_seconds,
        "payload_policy": "hashes_and_range_only",
        "redirects_allowed": False,
    }


def build_audit_anchor_adapter(settings: Settings) -> AuditAnchorAdapter:
    posture = audit_anchor_posture(settings)
    if not posture["enabled"]:
        raise AuditAnchorDeliveryError("audit_anchor_disabled", retryable=False)
    if not posture["configured"]:
        raise AuditAnchorDeliveryError("audit_anchor_not_configured", retryable=False)
    token = settings.audit_anchor_webhook_token
    assert token is not None
    return WebhookAuditAnchorAdapter(
        url=(settings.audit_anchor_webhook_url or "").strip(),
        token=token.get_secret_value().strip(),
        timeout_seconds=settings.audit_anchor_timeout_seconds,
    )


def build_audit_anchor_envelope(anchor: AuditArchiveAnchor) -> dict[str, Any]:
    return {
        "schema": "astra.audit-archive-anchor.v1",
        "manifest_sha256": anchor.manifest_sha256,
        "archive_sha256": anchor.archive_sha256,
        "manifest_schema_version": anchor.manifest_schema_version,
        "evidence_level": anchor.evidence_level,
        "exported_count": anchor.exported_count,
        "range": {
            "first_log_id": anchor.first_log_id,
            "last_log_id": anchor.last_log_id,
            "oldest_created_at": _datetime_value(anchor.oldest_created_at),
            "newest_created_at": _datetime_value(anchor.newest_created_at),
        },
        "chain": {
            "start_prev_hash": anchor.chain_start_prev_hash,
            "end_current_hash": anchor.chain_end_current_hash,
        },
    }


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
