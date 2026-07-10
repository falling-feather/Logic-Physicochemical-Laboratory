from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import BugExternalSyncOperation, BugRecord
from app.models.base import utc_now
from app.services.external_issue_providers import (
    ExternalCommentReceipt,
    ExternalIssueReceipt,
    IssueProviderAdapter,
    IssueProviderError,
    build_issue_provider_adapter,
    external_issue_comment_content,
    external_issue_create_content,
    validate_external_issue_binding,
)


@dataclass(frozen=True)
class BugExternalSyncResult:
    bug: BugRecord
    operation: BugExternalSyncOperation
    recovered: bool


class BugExternalSyncError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        ambiguous: bool = False,
        operation_id: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.ambiguous = ambiguous
        self.operation_id = operation_id


def create_external_issue_for_bug(
    db: Session,
    *,
    bug_id: int,
    settings: Settings,
    created_by_user_id: int | None,
    adapter_factory: Callable[[Settings], IssueProviderAdapter] = build_issue_provider_adapter,
) -> BugExternalSyncResult:
    bug = _get_bug(db, bug_id)
    if bug.external_issue_provider or bug.external_issue_id or bug.external_issue_url:
        raise BugExternalSyncError("external_issue_already_bound", retryable=False)
    operation_key = f"{settings.external_issue_sync_provider}:bug:{bug.id}:create"
    operation, recovered = _begin_operation(
        db,
        bug=bug,
        provider=settings.external_issue_sync_provider,
        operation="create",
        operation_key=operation_key,
        created_by_user_id=created_by_user_id,
    )
    if recovered:
        _recover_bug_binding_from_operation(db, bug, operation)
        return BugExternalSyncResult(bug=bug, operation=operation, recovered=True)
    try:
        title, body = external_issue_create_content(bug, operation_key=operation_key)
        adapter = adapter_factory(settings)
        receipt = adapter.create_issue(title=title, body=body)
    except IssueProviderError as exc:
        _finish_failure(db, operation, exc)
        raise _sync_error(exc, operation) from None
    except Exception:
        exc = IssueProviderError("provider_unexpected_error", retryable=True, ambiguous=True)
        _finish_failure(db, operation, exc)
        raise _sync_error(exc, operation) from None
    _require_receipt_provider(db, receipt.provider, operation, ambiguous=True)
    _finish_issue_success(db, bug, operation, receipt)
    return BugExternalSyncResult(bug=bug, operation=operation, recovered=False)


def sync_external_issue_status_for_bug(
    db: Session,
    *,
    bug_id: int,
    settings: Settings,
    created_by_user_id: int | None,
    adapter_factory: Callable[[Settings], IssueProviderAdapter] = build_issue_provider_adapter,
) -> BugExternalSyncResult:
    bug = _get_bug(db, bug_id)
    desired_state = "closed" if bug.status == "closed" else "open"
    operation_key = (
        f"{settings.external_issue_sync_provider}:bug:{bug.id}:"
        f"status:{bug.external_sync_revision}:{desired_state}"
    )
    operation, recovered = _begin_operation(
        db,
        bug=bug,
        provider=settings.external_issue_sync_provider,
        operation="status",
        operation_key=operation_key,
        desired_state=desired_state,
        created_by_user_id=created_by_user_id,
    )
    if recovered:
        return BugExternalSyncResult(bug=bug, operation=operation, recovered=True)
    try:
        issue_id = validate_external_issue_binding(settings, bug)
    except IssueProviderError as error:
        _finish_failure(db, operation, error)
        raise _sync_error(error, operation) from None
    try:
        adapter = adapter_factory(settings)
        receipt = adapter.update_issue_state(issue_id, state=desired_state)
    except IssueProviderError as exc:
        _finish_failure(db, operation, exc)
        raise _sync_error(exc, operation) from None
    except Exception:
        exc = IssueProviderError("provider_unexpected_error", retryable=True, ambiguous=False)
        _finish_failure(db, operation, exc)
        raise _sync_error(exc, operation) from None
    _require_receipt_provider(db, receipt.provider, operation, ambiguous=False)
    if receipt.issue_id != issue_id:
        error = IssueProviderError("external_issue_response_id_mismatch", retryable=False, ambiguous=True)
        _finish_failure(db, operation, error)
        raise _sync_error(error, operation)
    _finish_issue_success(db, bug, operation, receipt)
    return BugExternalSyncResult(bug=bug, operation=operation, recovered=False)


def sync_external_issue_comment_for_bug(
    db: Session,
    *,
    bug_id: int,
    comment: str,
    settings: Settings,
    created_by_user_id: int | None,
    adapter_factory: Callable[[Settings], IssueProviderAdapter] = build_issue_provider_adapter,
) -> BugExternalSyncResult:
    bug = _get_bug(db, bug_id)
    normalized_comment = comment.strip()
    comment_sha256 = sha256(normalized_comment.encode("utf-8")).hexdigest()
    operation_key = f"{settings.external_issue_sync_provider}:bug:{bug.id}:comment:{comment_sha256}"
    try:
        external_body = external_issue_comment_content(normalized_comment, operation_key=operation_key)
    except IssueProviderError as exc:
        raise BugExternalSyncError(exc.code, retryable=exc.retryable, ambiguous=exc.ambiguous) from None
    operation, recovered = _begin_operation(
        db,
        bug=bug,
        provider=settings.external_issue_sync_provider,
        operation="comment",
        operation_key=operation_key,
        comment_sha256=comment_sha256,
        comment_length=len(normalized_comment),
        created_by_user_id=created_by_user_id,
    )
    if recovered:
        return BugExternalSyncResult(bug=bug, operation=operation, recovered=True)
    try:
        issue_id = validate_external_issue_binding(settings, bug)
    except IssueProviderError as error:
        _finish_failure(db, operation, error)
        raise _sync_error(error, operation) from None
    try:
        adapter = adapter_factory(settings)
        receipt = adapter.create_comment(issue_id, body=external_body)
    except IssueProviderError as exc:
        _finish_failure(db, operation, exc)
        raise _sync_error(exc, operation) from None
    except Exception:
        exc = IssueProviderError("provider_unexpected_error", retryable=True, ambiguous=True)
        _finish_failure(db, operation, exc)
        raise _sync_error(exc, operation) from None
    _require_receipt_provider(db, receipt.provider, operation, ambiguous=True)
    _finish_comment_success(db, bug, operation, receipt)
    return BugExternalSyncResult(bug=bug, operation=operation, recovered=False)


def bug_external_sync_operation_read(operation: BugExternalSyncOperation) -> dict[str, Any]:
    return {
        "id": operation.id,
        "bug_record_id": operation.bug_record_id,
        "provider": operation.provider,
        "operation": operation.operation,
        "operation_key_prefix": operation.operation_key[:32],
        "status": operation.status,
        "desired_state": operation.desired_state,
        "comment_sha256": operation.comment_sha256,
        "comment_length": operation.comment_length,
        "external_issue_id": operation.external_issue_id,
        "external_issue_url": operation.external_issue_url,
        "external_state": operation.external_state,
        "external_comment_id": operation.external_comment_id,
        "attempt_count": operation.attempt_count,
        "last_error_code": operation.last_error_code,
        "last_attempt_at": operation.last_attempt_at,
        "finished_at": operation.finished_at,
        "response_hash": operation.response_hash,
        "created_by_user_id": operation.created_by_user_id,
        "created_at": operation.created_at,
        "updated_at": operation.updated_at,
        "comment_body_returned": False,
        "operation_key_redacted": True,
    }


def _get_bug(db: Session, bug_id: int) -> BugRecord:
    bug = db.get(BugRecord, bug_id)
    if bug is None:
        raise BugExternalSyncError("bug_record_not_found", retryable=False)
    return bug


def _begin_operation(
    db: Session,
    *,
    bug: BugRecord,
    provider: str,
    operation: str,
    operation_key: str,
    created_by_user_id: int | None,
    desired_state: str | None = None,
    comment_sha256: str | None = None,
    comment_length: int | None = None,
) -> tuple[BugExternalSyncOperation, bool]:
    sync_operation = db.scalar(
        select(BugExternalSyncOperation)
        .where(BugExternalSyncOperation.operation_key == operation_key)
        .with_for_update()
    )
    if sync_operation is None:
        sync_operation = BugExternalSyncOperation(
            bug_record_id=bug.id,
            provider=provider,
            operation=operation,
            operation_key=operation_key,
            status="pending",
            desired_state=desired_state,
            comment_sha256=comment_sha256,
            comment_length=comment_length,
            created_by_user_id=created_by_user_id,
        )
        try:
            with db.begin_nested():
                db.add(sync_operation)
                db.flush()
        except IntegrityError:
            sync_operation = db.scalar(
                select(BugExternalSyncOperation)
                .where(BugExternalSyncOperation.operation_key == operation_key)
                .with_for_update()
            )
            if sync_operation is None:
                raise
    if sync_operation.status == "succeeded":
        return sync_operation, True
    if sync_operation.status in {"dispatching", "ambiguous"}:
        raise BugExternalSyncError(
            "external_issue_sync_ambiguous",
            retryable=False,
            ambiguous=True,
            operation_id=sync_operation.id,
        )
    sync_operation.status = "dispatching"
    sync_operation.attempt_count += 1
    sync_operation.last_attempt_at = utc_now()
    sync_operation.last_error_code = None
    sync_operation.finished_at = None
    db.commit()
    db.refresh(sync_operation)
    return sync_operation, False


def _finish_failure(
    db: Session,
    operation: BugExternalSyncOperation,
    error: IssueProviderError,
) -> None:
    operation = db.get(BugExternalSyncOperation, operation.id) or operation
    operation.status = "ambiguous" if error.ambiguous else "failed"
    operation.last_error_code = error.code[:80]
    operation.finished_at = utc_now()
    db.commit()


def _finish_issue_success(
    db: Session,
    bug: BugRecord,
    operation: BugExternalSyncOperation,
    receipt: ExternalIssueReceipt,
) -> None:
    bug = db.get(BugRecord, bug.id) or bug
    operation = db.get(BugExternalSyncOperation, operation.id) or operation
    synced_at = utc_now()
    bug.external_issue_provider = receipt.provider
    bug.external_issue_id = receipt.issue_id
    bug.external_issue_url = receipt.issue_url
    bug.external_issue_state = receipt.state
    bug.external_issue_synced_at = synced_at
    operation.status = "succeeded"
    operation.external_issue_id = receipt.issue_id
    operation.external_issue_url = receipt.issue_url
    operation.external_state = receipt.state
    operation.response_hash = receipt.response_hash
    operation.last_error_code = None
    operation.finished_at = synced_at
    db.commit()
    db.refresh(bug)
    db.refresh(operation)


def _finish_comment_success(
    db: Session,
    bug: BugRecord,
    operation: BugExternalSyncOperation,
    receipt: ExternalCommentReceipt,
) -> None:
    bug = db.get(BugRecord, bug.id) or bug
    operation = db.get(BugExternalSyncOperation, operation.id) or operation
    synced_at = utc_now()
    bug.external_issue_synced_at = synced_at
    operation.status = "succeeded"
    operation.external_issue_id = bug.external_issue_id
    operation.external_issue_url = bug.external_issue_url
    operation.external_state = bug.external_issue_state
    operation.external_comment_id = receipt.comment_id
    operation.response_hash = receipt.response_hash
    operation.last_error_code = None
    operation.finished_at = synced_at
    db.commit()
    db.refresh(bug)
    db.refresh(operation)


def _recover_bug_binding_from_operation(
    db: Session,
    bug: BugRecord,
    operation: BugExternalSyncOperation,
) -> None:
    if operation.external_issue_id and operation.external_issue_url:
        bug.external_issue_provider = operation.provider
        bug.external_issue_id = operation.external_issue_id
        bug.external_issue_url = operation.external_issue_url
        bug.external_issue_state = operation.external_state
        bug.external_issue_synced_at = operation.finished_at
        db.commit()
        db.refresh(bug)


def _require_receipt_provider(
    db: Session,
    receipt_provider: str,
    operation: BugExternalSyncOperation,
    *,
    ambiguous: bool,
) -> None:
    if receipt_provider == operation.provider:
        return
    error = IssueProviderError("external_issue_provider_mismatch", retryable=False, ambiguous=ambiguous)
    _finish_failure(db, operation, error)
    raise _sync_error(error, operation)


def _sync_error(error: IssueProviderError, operation: BugExternalSyncOperation) -> BugExternalSyncError:
    return BugExternalSyncError(
        error.code,
        retryable=error.retryable and not error.ambiguous,
        ambiguous=error.ambiguous,
        operation_id=operation.id,
    )
