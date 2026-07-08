from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AuditLog
from app.services.audit import audit_log_chain_hash
from app.services.audit_chain import verify_audit_log_chain


AUDIT_ARCHIVE_SCHEMA_VERSION = 1
AUDIT_ARCHIVE_FIELDS = (
    "id",
    "actor_user_id",
    "actor_role",
    "action",
    "resource",
    "resource_type",
    "resource_id",
    "school_id",
    "class_id",
    "event_result",
    "failure_reason",
    "request_id",
    "client_ip_hash",
    "user_agent",
    "request_method",
    "request_path",
    "prev_hash",
    "current_hash",
    "snapshot_json",
    "created_at",
)
ArchiveFormat = Literal["jsonl", "csv"]


def run_archive(
    *,
    database_url: str | None = None,
    output_dir: Path | None = None,
    archive_format: ArchiveFormat = "jsonl",
    include_snapshot: bool = False,
    before_at: datetime | None = None,
    retention_days: int | None = None,
    limit: int = 5000,
    dry_run: bool = False,
    actor_user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    school_id: int | None = None,
    class_id: int | None = None,
    event_result: str | None = None,
    failure_reason: str | None = None,
    request_id: str | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    require_mysql: bool = False,
) -> dict[str, Any]:
    if archive_format not in {"jsonl", "csv"}:
        raise ValueError("archive_format must be jsonl or csv")
    if before_at is not None and retention_days is not None:
        raise ValueError("before_at and retention_days are mutually exclusive")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if retention_days is not None and retention_days < 1:
        raise ValueError("retention_days must be at least 1")
    normalized_from_at = _ensure_utc(from_at) if from_at is not None else None
    normalized_to_at = _ensure_utc(to_at) if to_at is not None else None
    if normalized_from_at is not None and normalized_to_at is not None and normalized_from_at > normalized_to_at:
        raise ValueError("from_at must be earlier than to_at")

    settings = get_settings()
    target_database_url = database_url or settings.database_url
    dialect = _database_dialect(target_database_url)
    if require_mysql and dialect != "mysql":
        return {
            "ok": False,
            "status": "mysql_required",
            "database": {
                "dialect": dialect,
                "require_mysql": True,
                "safe_database_url": _safe_database_url(target_database_url),
            },
        }
    generated_at = _utc_now()
    cutoff_at, cutoff_source, effective_retention_days = _resolve_cutoff(
        before_at=before_at,
        retention_days=retention_days,
        configured_retention_days=settings.audit_log_retention_days,
        generated_at=generated_at,
    )
    filters = _archive_filters(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id,
        class_id=class_id,
        event_result=event_result,
        failure_reason=failure_reason,
        request_id=request_id,
        from_at=normalized_from_at,
        to_at=normalized_to_at,
    )

    session_factory = get_session_factory(target_database_url)
    with session_factory() as db:
        statement = _archive_statement(
            cutoff_at=cutoff_at,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            school_id=school_id,
            class_id=class_id,
            event_result=event_result,
            failure_reason=failure_reason,
            request_id=request_id,
            from_at=normalized_from_at,
            to_at=normalized_to_at,
        )
        total_candidates = int(db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0)
        logs = list(db.scalars(statement.limit(limit)).all())

    records = [_audit_archive_record(log, include_snapshot=include_snapshot) for log in logs]
    manifest = _archive_manifest(
        generated_at=generated_at,
        cutoff_at=cutoff_at,
        cutoff_source=cutoff_source,
        retention_days=effective_retention_days,
        filters=filters,
        archive_format=archive_format,
        include_snapshot=include_snapshot,
        limit=limit,
        total_candidates=total_candidates,
        records=records,
        chain_report=verify_audit_log_chain(logs),
    )
    if dry_run:
        return {
            "ok": True,
            "status": "dry_run",
            "manifest": manifest,
        }

    target_dir = output_dir or Path("audit-archives")
    target_dir.mkdir(parents=True, exist_ok=True)
    filename_stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    archive_path = target_dir / f"audit-logs-archive-{filename_stamp}.{archive_format}"
    manifest_path = target_dir / f"audit-logs-archive-{filename_stamp}.manifest.json"
    _write_archive(archive_path, records, archive_format=archive_format)
    manifest["archive_file"] = archive_path.name
    manifest["archive_sha256"] = _sha256_file(archive_path)
    manifest["archive_bytes"] = archive_path.stat().st_size
    manifest["manifest_file"] = manifest_path.name
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "status": "written",
        "archive_file": str(archive_path),
        "manifest_file": str(manifest_path),
        "manifest": manifest,
    }


def verify_archive_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": "failed", "reason": exc.__class__.__name__}

    archive_file = manifest.get("archive_file")
    expected_hash = manifest.get("archive_sha256")
    archive_format = manifest.get("format")
    if not archive_file or not expected_hash:
        return {"ok": False, "status": "failed", "reason": "manifest_missing_archive_hash"}
    if archive_format not in {"jsonl", "csv"}:
        return {"ok": False, "status": "failed", "reason": "unsupported_archive_format"}

    archive_path = Path(archive_file)
    if not archive_path.is_absolute():
        archive_path = manifest_path.parent / archive_path
    if not archive_path.exists():
        return {"ok": False, "status": "failed", "reason": "archive_file_missing"}

    actual_hash = _sha256_file(archive_path)
    if actual_hash != expected_hash:
        return {
            "ok": False,
            "status": "failed",
            "reason": "archive_sha256_mismatch",
            "expected_sha256": expected_hash,
            "actual_sha256": actual_hash,
        }

    expected_count = int(manifest.get("exported_count") or 0)
    actual_count = _count_archive_records(archive_path, archive_format=archive_format)
    if actual_count != expected_count:
        return {
            "ok": False,
            "status": "failed",
            "reason": "archive_record_count_mismatch",
            "expected_count": expected_count,
            "actual_count": actual_count,
        }
    try:
        records = _read_archive_records(archive_path, archive_format=archive_format)
        archive_chain = _archive_chain_report(
            records,
            archive_format=archive_format,
            include_snapshot=bool(manifest.get("include_snapshot")),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return {
            "ok": False,
            "status": "failed",
            "reason": "archive_records_unreadable",
            "error": exc.__class__.__name__,
        }
    if archive_chain["status"] == "invalid":
        return {
            "ok": False,
            "status": "failed",
            "reason": "archive_chain_invalid",
            "archive_file": str(archive_path),
            "archive_sha256": actual_hash,
            "exported_count": actual_count,
            "archive_chain": archive_chain,
        }

    return {
        "ok": True,
        "status": "verified",
        "archive_file": str(archive_path),
        "archive_sha256": actual_hash,
        "exported_count": actual_count,
        "archive_chain": archive_chain,
    }


def _resolve_cutoff(
    *,
    before_at: datetime | None,
    retention_days: int | None,
    configured_retention_days: int,
    generated_at: datetime,
) -> tuple[datetime, str, int | None]:
    if before_at is not None:
        return _ensure_utc(before_at), "before", None
    days = retention_days or configured_retention_days
    source = "query" if retention_days is not None else "config"
    return generated_at - timedelta(days=days), source, days


def _archive_statement(
    *,
    cutoff_at: datetime,
    actor_user_id: int | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    school_id: int | None,
    class_id: int | None,
    event_result: str | None,
    failure_reason: str | None,
    request_id: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> Any:
    statement = (
        select(AuditLog)
        .where(AuditLog.created_at <= cutoff_at)
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    )
    if actor_user_id is not None:
        statement = statement.where(AuditLog.actor_user_id == actor_user_id)
    if action is not None:
        statement = statement.where(AuditLog.action == action.strip())
    if resource_type is not None:
        statement = statement.where(AuditLog.resource_type == resource_type.strip())
    if resource_id is not None:
        statement = statement.where(AuditLog.resource_id == resource_id.strip())
    if school_id is not None:
        statement = statement.where(AuditLog.school_id == school_id)
    if class_id is not None:
        statement = statement.where(AuditLog.class_id == class_id)
    if event_result is not None:
        statement = statement.where(AuditLog.event_result == event_result.strip())
    if failure_reason is not None:
        statement = statement.where(AuditLog.failure_reason == failure_reason.strip())
    if request_id is not None:
        statement = statement.where(AuditLog.request_id == request_id.strip())
    if from_at is not None:
        statement = statement.where(AuditLog.created_at >= from_at)
    if to_at is not None:
        statement = statement.where(AuditLog.created_at <= to_at)
    return statement


def _archive_filters(
    *,
    actor_user_id: int | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    school_id: int | None,
    class_id: int | None,
    event_result: str | None,
    failure_reason: str | None,
    request_id: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    for key, value in {
        "actor_user_id": actor_user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "school_id": school_id,
        "class_id": class_id,
        "event_result": event_result,
        "failure_reason": failure_reason,
        "request_id": request_id,
    }.items():
        if value is not None:
            filters[key] = value.strip() if isinstance(value, str) else value
    if from_at is not None:
        filters["from"] = from_at.isoformat()
    if to_at is not None:
        filters["to"] = to_at.isoformat()
    return filters


def _archive_manifest(
    *,
    generated_at: datetime,
    cutoff_at: datetime,
    cutoff_source: str,
    retention_days: int | None,
    filters: dict[str, Any],
    archive_format: ArchiveFormat,
    include_snapshot: bool,
    limit: int,
    total_candidates: int,
    records: list[dict[str, Any]],
    chain_report: dict[str, Any],
) -> dict[str, Any]:
    first = records[0] if records else None
    last = records[-1] if records else None
    return {
        "schema_version": AUDIT_ARCHIVE_SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "format": archive_format,
        "include_snapshot": include_snapshot,
        "capabilities": {
            "delete": False,
            "purge": False,
            "worm": False,
            "external_anchor": False,
        },
        "policy": {
            "source": cutoff_source,
            "retention_days": retention_days,
            "cutoff_at": cutoff_at.isoformat(),
        },
        "filters": filters,
        "limit": limit,
        "total_candidates": total_candidates,
        "exported_count": len(records),
        "truncated": total_candidates > len(records),
        "first_id": first["id"] if first is not None else None,
        "last_id": last["id"] if last is not None else None,
        "oldest_created_at": first["created_at"] if first is not None else None,
        "newest_created_at": last["created_at"] if last is not None else None,
        "chain_start_prev_hash": first["prev_hash"] if first is not None else None,
        "chain_start_current_hash": first["current_hash"] if first is not None else None,
        "chain_end_current_hash": last["current_hash"] if last is not None else None,
        "hash_chain": chain_report,
        "archive_file": None,
        "archive_sha256": None,
        "archive_bytes": None,
        "manifest_file": None,
    }


def _audit_archive_record(log: AuditLog, *, include_snapshot: bool) -> dict[str, Any]:
    return {
        "id": log.id,
        "actor_user_id": log.actor_user_id,
        "actor_role": log.actor_role,
        "action": log.action,
        "resource": log.resource,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "school_id": log.school_id,
        "class_id": log.class_id,
        "event_result": log.event_result,
        "failure_reason": log.failure_reason,
        "request_id": log.request_id,
        "client_ip_hash": log.client_ip_hash,
        "user_agent": log.user_agent,
        "request_method": log.request_method,
        "request_path": log.request_path,
        "prev_hash": log.prev_hash,
        "current_hash": log.current_hash,
        "snapshot_json": log.snapshot_json if include_snapshot else None,
        "created_at": _datetime_value(log.created_at),
    }


def _write_archive(path: Path, records: list[dict[str, Any]], *, archive_format: ArchiveFormat) -> None:
    if archive_format == "jsonl":
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        return

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=AUDIT_ARCHIVE_FIELDS, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow({field: _csv_value(record.get(field)) for field in AUDIT_ARCHIVE_FIELDS})
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _count_archive_records(path: Path, *, archive_format: str) -> int:
    if archive_format == "jsonl":
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _read_archive_records(path: Path, *, archive_format: str) -> list[dict[str, Any]]:
    if archive_format == "jsonl":
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
        return records
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _archive_chain_report(
    records: list[dict[str, Any]],
    *,
    archive_format: str,
    include_snapshot: bool,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    null_current_hash_count = 0
    current_hash_mismatch_count = 0
    prev_hash_mismatch_count = 0
    previous: dict[str, Any] | None = None
    can_recompute_current_hash = archive_format == "jsonl" and include_snapshot
    for index, record in enumerate(records):
        current_hash = _archive_record_value(record, "current_hash")
        prev_hash = _archive_record_value(record, "prev_hash")
        if not current_hash:
            null_current_hash_count += 1
            _append_archive_chain_issue(issues, "null_current_hash", index=index, log_id=record.get("id"))
        if previous is not None:
            previous_current_hash = _archive_record_value(previous, "current_hash")
            if previous_current_hash and current_hash and prev_hash != previous_current_hash:
                prev_hash_mismatch_count += 1
                _append_archive_chain_issue(
                    issues,
                    "prev_hash_mismatch",
                    index=index,
                    log_id=record.get("id"),
                    previous_log_id=previous.get("id"),
                )
        if can_recompute_current_hash and current_hash:
            expected_hash = audit_log_chain_hash(_audit_log_from_archive_record(record))
            if expected_hash != current_hash:
                current_hash_mismatch_count += 1
                _append_archive_chain_issue(
                    issues,
                    "current_hash_mismatch",
                    index=index,
                    log_id=record.get("id"),
                )
        previous = record
    status = "valid"
    if null_current_hash_count or not can_recompute_current_hash:
        status = "partial"
    if current_hash_mismatch_count or prev_hash_mismatch_count:
        status = "invalid"
    return {
        "verification_scope": "archive_file_internal_order",
        "archive_format": archive_format,
        "include_snapshot": include_snapshot,
        "current_hash_recomputed": can_recompute_current_hash,
        "current_hash_recompute_reason": None
        if can_recompute_current_hash
        else (
            "snapshot_json_not_exported"
            if not include_snapshot
            else "csv_formula_escaping_prevents_lossless_hash_recompute"
        ),
        "status": status,
        "valid": status == "valid",
        "scanned_count": len(records),
        "null_current_hash_count": null_current_hash_count,
        "current_hash_mismatch_count": current_hash_mismatch_count,
        "prev_hash_mismatch_count": prev_hash_mismatch_count,
        "issue_count": null_current_hash_count + current_hash_mismatch_count + prev_hash_mismatch_count,
        "issues": issues[:50],
        "issues_truncated": len(issues) > 50,
    }


def _archive_record_value(record: dict[str, Any], key: str) -> Any:
    value = record.get(key)
    if value == "":
        return None
    return value


def _append_archive_chain_issue(
    issues: list[dict[str, Any]],
    issue_type: str,
    *,
    index: int,
    log_id: Any,
    previous_log_id: Any | None = None,
) -> None:
    issues.append(
        {
            "type": issue_type,
            "index": index,
            "log_id": _safe_int(log_id),
            "previous_log_id": _safe_int(previous_log_id),
        }
    )


def _audit_log_from_archive_record(record: dict[str, Any]) -> AuditLog:
    return AuditLog(
        actor_user_id=_safe_int(record.get("actor_user_id")),
        actor_role=_archive_record_value(record, "actor_role"),
        action=str(_archive_record_value(record, "action") or ""),
        resource=str(_archive_record_value(record, "resource") or ""),
        resource_type=str(_archive_record_value(record, "resource_type") or ""),
        resource_id=_archive_record_value(record, "resource_id"),
        school_id=_safe_int(record.get("school_id")),
        class_id=_safe_int(record.get("class_id")),
        event_result=_archive_record_value(record, "event_result"),
        failure_reason=_archive_record_value(record, "failure_reason"),
        request_id=_archive_record_value(record, "request_id"),
        client_ip_hash=_archive_record_value(record, "client_ip_hash"),
        user_agent=_archive_record_value(record, "user_agent"),
        request_method=_archive_record_value(record, "request_method"),
        request_path=_archive_record_value(record, "request_path"),
        prev_hash=_archive_record_value(record, "prev_hash"),
        snapshot_json=_snapshot_from_archive_record(record),
        created_at=_parse_datetime(str(_archive_record_value(record, "created_at"))),
    )


def _snapshot_from_archive_record(record: dict[str, Any]) -> Any:
    value = record.get("snapshot_json")
    if value in (None, ""):
        return {}
    if isinstance(value, (dict, list)):
        return value
    return json.loads(str(value))


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return f"'{text}"
    return text


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _ensure_utc(value).isoformat()


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if len(text) == 10:
        return datetime.fromisoformat(text).replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return _ensure_utc(parsed)


def _database_dialect(database_url: str) -> str:
    try:
        return make_url(database_url).get_backend_name()
    except ArgumentError:
        return "invalid"


def _safe_database_url(database_url: str) -> str:
    try:
        return str(make_url(database_url).render_as_string(hide_password=True))
    except ArgumentError:
        return "<invalid>"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export audit-log archive candidates into a verifiable package.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this run.")
    parser.add_argument("--output-dir", type=Path, default=Path("audit-archives"), help="Archive output directory.")
    parser.add_argument("--format", choices=["jsonl", "csv"], default="jsonl", help="Archive file format.")
    parser.add_argument("--include-snapshot", action="store_true", help="Include raw snapshot_json in the archive file.")
    parser.add_argument("--before", default=None, help="Archive logs created at or before this ISO datetime/date.")
    parser.add_argument("--retention-days", type=int, default=None, help="Override ASTRA_AUDIT_LOG_RETENTION_DAYS.")
    parser.add_argument("--limit", type=int, default=5000, help="Maximum records to export in one package.")
    parser.add_argument("--dry-run", action="store_true", help="Print the manifest preview without writing files.")
    parser.add_argument("--require-mysql", action="store_true", help="Fail when the target database is not MySQL.")
    parser.add_argument("--verify", type=Path, default=None, help="Verify an existing manifest and archive file.")
    parser.add_argument("--actor-user-id", type=int, default=None)
    parser.add_argument("--action", default=None)
    parser.add_argument("--resource-type", default=None)
    parser.add_argument("--resource-id", default=None)
    parser.add_argument("--school-id", type=int, default=None)
    parser.add_argument("--class-id", type=int, default=None)
    parser.add_argument("--event-result", default=None)
    parser.add_argument("--failure-reason", default=None)
    parser.add_argument("--request-id", default=None)
    parser.add_argument("--from", dest="from_at", default=None, help="Only include logs at or after this ISO datetime.")
    parser.add_argument("--to", dest="to_at", default=None, help="Only include logs at or before this ISO datetime.")
    args = parser.parse_args(argv)

    if args.verify is not None:
        report = verify_archive_manifest(args.verify)
    else:
        try:
            report = run_archive(
                database_url=args.database_url,
                output_dir=args.output_dir,
                archive_format=args.format,
                include_snapshot=args.include_snapshot,
                before_at=_parse_datetime(args.before) if args.before else None,
                retention_days=args.retention_days,
                limit=args.limit,
                dry_run=args.dry_run,
                actor_user_id=args.actor_user_id,
                action=args.action,
                resource_type=args.resource_type,
                resource_id=args.resource_id,
                school_id=args.school_id,
                class_id=args.class_id,
                event_result=args.event_result,
                failure_reason=args.failure_reason,
                request_id=args.request_id,
                from_at=_parse_datetime(args.from_at) if args.from_at else None,
                to_at=_parse_datetime(args.to_at) if args.to_at else None,
                require_mysql=args.require_mysql,
            )
        except (OSError, ValueError) as exc:
            report = {"ok": False, "status": "failed", "error": exc.__class__.__name__, "detail": str(exc)}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
