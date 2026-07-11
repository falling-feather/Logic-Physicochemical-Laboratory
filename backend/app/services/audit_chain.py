from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.models import AuditLog
from app.services.audit import audit_log_chain_hash


def verify_audit_log_chain(logs: Sequence[AuditLog], *, issue_limit: int = 50) -> dict[str, Any]:
    null_current_hash_count = 0
    current_hash_mismatch_count = 0
    prev_hash_mismatch_count = 0
    issues: list[dict[str, Any]] = []
    previous: AuditLog | None = None

    for log in logs:
        current_hash_valid = False
        if log.current_hash is None:
            null_current_hash_count += 1
            _append_issue(
                issues,
                issue_limit=issue_limit,
                issue_type="null_current_hash",
                log_id=log.id,
                previous_log_id=previous.id if previous is not None else None,
            )
        else:
            expected_current_hash = audit_log_chain_hash(log)
            current_hash_valid = expected_current_hash == log.current_hash
            if not current_hash_valid:
                current_hash_mismatch_count += 1
                _append_issue(
                    issues,
                    issue_limit=issue_limit,
                    issue_type="current_hash_mismatch",
                    log_id=log.id,
                    previous_log_id=previous.id if previous is not None else None,
                    expected_hash=expected_current_hash,
                    actual_hash=log.current_hash,
                )

        if previous is not None and previous.current_hash is not None and log.current_hash is not None:
            if log.prev_hash != previous.current_hash:
                prev_hash_mismatch_count += 1
                _append_issue(
                    issues,
                    issue_limit=issue_limit,
                    issue_type="prev_hash_mismatch",
                    log_id=log.id,
                    previous_log_id=previous.id,
                    expected_hash=previous.current_hash,
                    actual_hash=log.prev_hash,
                )

        previous = log

    status = "valid"
    if null_current_hash_count:
        status = "partial"
    if current_hash_mismatch_count or prev_hash_mismatch_count:
        status = "invalid"

    return {
        "algorithm": "sha256",
        "chain_version": 1,
        "status": status,
        "valid": status == "valid",
        "scanned_count": len(logs),
        "null_current_hash_count": null_current_hash_count,
        "current_hash_mismatch_count": current_hash_mismatch_count,
        "prev_hash_mismatch_count": prev_hash_mismatch_count,
        "issue_count": null_current_hash_count + current_hash_mismatch_count + prev_hash_mismatch_count,
        "issues": issues,
        "issues_truncated": (null_current_hash_count + current_hash_mismatch_count + prev_hash_mismatch_count)
        > len(issues),
    }


def _append_issue(
    issues: list[dict[str, Any]],
    *,
    issue_limit: int,
    issue_type: str,
    log_id: int,
    previous_log_id: int | None,
    expected_hash: str | None = None,
    actual_hash: str | None = None,
) -> None:
    if len(issues) >= issue_limit:
        return
    issues.append(
        {
            "type": issue_type,
            "log_id": log_id,
            "previous_log_id": previous_log_id,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
        }
    )
