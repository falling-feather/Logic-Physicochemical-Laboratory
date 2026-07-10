from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import AuditArchiveAnchor
from app.models.base import utc_now
from app.services.audit_anchor_delivery import (
    AuditAnchorAdapter,
    AuditAnchorDeliveryError,
    build_audit_anchor_adapter,
    build_audit_anchor_envelope,
)
from app.services.background_tasks import BackgroundTaskEnqueueResult, enqueue_background_task
from scripts.archive_audit_logs import verify_archive_manifest


@dataclass(frozen=True)
class AuditArchiveAnchorEnqueueResult:
    anchor: AuditArchiveAnchor
    task_result: BackgroundTaskEnqueueResult
    anchor_created: bool


class AuditArchiveAnchorError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


def enqueue_audit_archive_anchor(
    db: Session,
    *,
    manifest_path: Path,
    settings: Settings,
    created_by_user_id: int | None = None,
) -> AuditArchiveAnchorEnqueueResult:
    resolved_path = manifest_path.expanduser().resolve()
    verification = verify_archive_manifest(resolved_path)
    if not verification.get("ok"):
        raise AuditArchiveAnchorError(
            f"archive_{str(verification.get('reason') or 'verification_failed')}"[:80],
            retryable=False,
        )
    manifest = _read_manifest(resolved_path)
    manifest_sha256 = _sha256_file(resolved_path)
    existing = db.scalar(
        select(AuditArchiveAnchor).where(AuditArchiveAnchor.manifest_sha256 == manifest_sha256)
    )
    anchor_created = existing is None
    if existing is None:
        archive_chain = verification.get("archive_chain") or {}
        anchor = AuditArchiveAnchor(
            provider=settings.audit_anchor_provider,
            status="pending",
            manifest_schema_version=int(manifest.get("schema_version") or 1),
            manifest_sha256=manifest_sha256,
            manifest_path_sha256=sha256(str(resolved_path).encode("utf-8")).hexdigest(),
            archive_sha256=str(verification["archive_sha256"]),
            evidence_level=str(archive_chain.get("status") or "partial"),
            exported_count=int(verification.get("exported_count") or 0),
            first_log_id=_optional_int(manifest.get("first_id")),
            last_log_id=_optional_int(manifest.get("last_id")),
            oldest_created_at=_optional_datetime(manifest.get("oldest_created_at")),
            newest_created_at=_optional_datetime(manifest.get("newest_created_at")),
            chain_start_prev_hash=_optional_hash(manifest.get("chain_start_prev_hash")),
            chain_end_current_hash=_optional_hash(manifest.get("chain_end_current_hash")),
            created_by_user_id=created_by_user_id,
        )
        try:
            with db.begin_nested():
                db.add(anchor)
                db.flush()
        except IntegrityError:
            anchor = db.scalar(
                select(AuditArchiveAnchor).where(AuditArchiveAnchor.manifest_sha256 == manifest_sha256)
            )
            if anchor is None:
                raise
            anchor_created = False
    else:
        anchor = existing
    task_result = enqueue_background_task(
        db,
        task_type="audit_archive_anchor",
        idempotency_key=f"audit-archive-anchor:{manifest_sha256}",
        source_type="audit_archive_anchor",
        source_id=anchor.id,
        payload={"anchor_id": anchor.id, "manifest_path": str(resolved_path)},
        max_attempts=settings.audit_anchor_max_attempts,
        created_by_user_id=created_by_user_id,
    )
    return AuditArchiveAnchorEnqueueResult(
        anchor=anchor,
        task_result=task_result,
        anchor_created=anchor_created,
    )


def execute_audit_archive_anchor(
    db: Session,
    *,
    anchor_id: int,
    manifest_path: Path,
    settings: Settings,
    adapter_factory: Callable[[Settings], AuditAnchorAdapter] = build_audit_anchor_adapter,
) -> dict[str, Any]:
    anchor = db.scalar(
        select(AuditArchiveAnchor)
        .where(AuditArchiveAnchor.id == anchor_id)
        .with_for_update()
    )
    if anchor is None:
        raise AuditArchiveAnchorError("audit_archive_anchor_missing", retryable=False)
    if anchor.status == "anchored":
        return _anchor_summary(anchor, recovered=True)
    resolved_path = manifest_path.expanduser().resolve()
    if sha256(str(resolved_path).encode("utf-8")).hexdigest() != anchor.manifest_path_sha256:
        _mark_anchor_failure(db, anchor, "audit_anchor_manifest_path_mismatch")
        raise AuditArchiveAnchorError("audit_anchor_manifest_path_mismatch", retryable=False)
    verification = verify_archive_manifest(resolved_path)
    if not verification.get("ok"):
        code = f"archive_{str(verification.get('reason') or 'verification_failed')}"[:80]
        _mark_anchor_failure(db, anchor, code)
        raise AuditArchiveAnchorError(code, retryable=False)
    if _sha256_file(resolved_path) != anchor.manifest_sha256:
        _mark_anchor_failure(db, anchor, "audit_anchor_manifest_sha256_mismatch")
        raise AuditArchiveAnchorError("audit_anchor_manifest_sha256_mismatch", retryable=False)
    if str(verification.get("archive_sha256") or "") != anchor.archive_sha256:
        _mark_anchor_failure(db, anchor, "audit_anchor_archive_sha256_mismatch")
        raise AuditArchiveAnchorError("audit_anchor_archive_sha256_mismatch", retryable=False)

    anchor.status = "anchoring"
    anchor.attempt_count += 1
    anchor.last_attempt_at = utc_now()
    anchor.last_error_code = None
    db.commit()
    try:
        adapter = adapter_factory(settings)
        receipt = adapter.anchor(
            build_audit_anchor_envelope(anchor),
            idempotency_key=f"astra:audit-archive-anchor:{anchor.manifest_sha256}",
        )
    except AuditAnchorDeliveryError as exc:
        refreshed = db.get(AuditArchiveAnchor, anchor_id)
        if refreshed is not None:
            _mark_anchor_failure(db, refreshed, exc.code)
        raise AuditArchiveAnchorError(exc.code, retryable=exc.retryable) from None
    except Exception:
        refreshed = db.get(AuditArchiveAnchor, anchor_id)
        if refreshed is not None:
            _mark_anchor_failure(db, refreshed, "anchor_unexpected_error")
        raise AuditArchiveAnchorError("anchor_unexpected_error", retryable=True) from None

    anchor = db.get(AuditArchiveAnchor, anchor_id)
    if anchor is None:
        raise AuditArchiveAnchorError("audit_archive_anchor_missing", retryable=False)
    if receipt.provider != anchor.provider:
        _mark_anchor_failure(db, anchor, "anchor_receipt_provider_mismatch")
        raise AuditArchiveAnchorError("anchor_receipt_provider_mismatch", retryable=False)
    anchor.status = "anchored"
    anchor.last_error_code = None
    anchor.anchored_at = utc_now()
    anchor.external_receipt_id = receipt.receipt_id
    anchor.external_anchored_at = receipt.anchored_at
    anchor.receipt_hash = receipt.receipt_hash
    db.commit()
    db.refresh(anchor)
    return _anchor_summary(anchor, recovered=False)


def audit_archive_anchor_read(anchor: AuditArchiveAnchor) -> dict[str, Any]:
    return {
        "id": anchor.id,
        "provider": anchor.provider,
        "status": anchor.status,
        "manifest_schema_version": anchor.manifest_schema_version,
        "manifest_sha256": anchor.manifest_sha256,
        "manifest_path_sha256": anchor.manifest_path_sha256,
        "archive_sha256": anchor.archive_sha256,
        "evidence_level": anchor.evidence_level,
        "exported_count": anchor.exported_count,
        "first_log_id": anchor.first_log_id,
        "last_log_id": anchor.last_log_id,
        "chain_start_prev_hash": anchor.chain_start_prev_hash,
        "chain_end_current_hash": anchor.chain_end_current_hash,
        "attempt_count": anchor.attempt_count,
        "last_error_code": anchor.last_error_code,
        "last_attempt_at": _datetime_value(anchor.last_attempt_at),
        "anchored_at": _datetime_value(anchor.anchored_at),
        "external_receipt_id": anchor.external_receipt_id,
        "external_anchored_at": _datetime_value(anchor.external_anchored_at),
        "receipt_hash": anchor.receipt_hash,
        "created_at": _datetime_value(anchor.created_at),
        "updated_at": _datetime_value(anchor.updated_at),
        "manifest_path_returned": False,
    }


def _mark_anchor_failure(db: Session, anchor: AuditArchiveAnchor, code: str) -> None:
    anchor.status = "failed"
    anchor.last_error_code = code[:80]
    db.commit()


def _anchor_summary(anchor: AuditArchiveAnchor, *, recovered: bool) -> dict[str, Any]:
    return {
        "anchor_id": anchor.id,
        "status": anchor.status,
        "provider": anchor.provider,
        "manifest_sha256": anchor.manifest_sha256,
        "archive_sha256": anchor.archive_sha256,
        "evidence_level": anchor.evidence_level,
        "receipt_hash": anchor.receipt_hash,
        "recovered_existing_anchor": recovered,
        "manifest_path_returned": False,
    }


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditArchiveAnchorError("archive_manifest_unreadable", retryable=False) from exc
    if not isinstance(value, dict):
        raise AuditArchiveAnchorError("archive_manifest_invalid", retryable=False)
    return value


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _optional_hash(value: Any) -> str | None:
    return str(value) if value else None


def _optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
