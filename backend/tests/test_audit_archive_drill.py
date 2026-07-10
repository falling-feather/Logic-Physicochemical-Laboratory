import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AuditLog
from app.services.audit import audit_log_chain_hash
from app.services.audit_archive_drill import run_audit_archive_drill
from scripts.audit_archive_drill import main, run_audit_archive_drill_report


def test_audit_archive_drill_reports_ready_read_only_posture(client):
    now = datetime.now(UTC)
    output_dir = Path.cwd() / ".tmp-test-audit-drill" / uuid4().hex
    first_created_at = now - timedelta(days=90)
    second_created_at = now - timedelta(days=60)
    retained_created_at = now - timedelta(days=5)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        first = _valid_audit_log(action="drill.archive", resource="drill:first", created_at=first_created_at)
        second = _valid_audit_log(
            action="drill.archive",
            resource="drill:second",
            created_at=second_created_at,
            prev_hash=first.current_hash,
        )
        retained = _valid_audit_log(
            action="drill.archive",
            resource="drill:retained",
            created_at=retained_created_at,
            prev_hash=second.current_hash,
        )
        db.add_all([first, second, retained])
        db.commit()
        before_count = int(db.scalar(select(func.count()).select_from(AuditLog)) or 0)
        report = run_audit_archive_drill(
            db,
            database_url=get_settings().database_url,
            settings=get_settings(),
            before_at=now - timedelta(days=30),
            action="drill.archive",
            output_dir=output_dir,
            generated_at=now,
        )
        after_count = int(db.scalar(select(func.count()).select_from(AuditLog)) or 0)

    assert report["ok"] is True
    assert report["status"] == "ready_for_archive_evidence"
    assert report["mode"] == "read_only"
    assert report["retention_plan"]["counts"]["archive_candidates"] == 2
    assert report["retention_plan"]["counts"]["retained"] == 1
    assert report["archive_preview"]["would_write_files"] is False
    assert report["archive_preview"]["would_delete_rows"] is False
    assert report["archive_preview"]["include_snapshot_default"] is False
    assert report["archive_preview"]["chain_scope"] == "filtered_candidate_subset"
    assert report["archive_preview"]["counts"]["previewed_count"] == 2
    assert report["archive_preview"]["capabilities"]["external_anchor"] is True
    assert report["chain_integrity"]["chain_status"] == "valid"
    assert report["chain_integrity"]["chain_scope"] == "filtered_candidate_subset"
    assert report["sensitive_field_scan"]["counts"]["issues"] == 0
    assert report["operation_boundaries"]["writes_audit_event"] is False
    assert report["operation_boundaries"]["external_anchor"] is False
    assert report["operation_boundaries"]["external_anchor_supported"] is True
    assert report["operation_boundaries"]["external_anchor_posture"]["enabled"] is False
    assert report["sensitive_values_returned"] is False
    assert before_count == after_count
    assert not output_dir.exists()


def test_audit_archive_drill_require_mysql_and_invalid_arguments(client):
    require_mysql_report = run_audit_archive_drill_report(require_mysql=True)
    assert require_mysql_report["ok"] is False
    assert require_mysql_report["database"]["status"] == "mysql_required"

    from scripts.archive_audit_logs import run_archive

    archive_report = run_archive(require_mysql=True, dry_run=True)
    assert archive_report["ok"] is False
    assert archive_report["status"] == "mysql_required"
    assert archive_report["database"]["dialect"] == "sqlite"

    settings = get_settings()
    session_factory = get_session_factory(settings.database_url)
    with session_factory() as db:
        report = run_audit_archive_drill(
            db,
            database_url=settings.database_url,
            settings=settings,
            before_at=datetime.now(UTC),
            retention_days=365,
        )

    assert report["ok"] is False
    assert report["status"] == "invalid_arguments"
    assert report["parameters"]["issue_counts_by_code"]["before_and_retention_days_conflict"] == 1
    assert report["retention_plan"]["status"] == "not_run"


def test_audit_archive_drill_detects_sensitive_candidates_without_leaking_values(client):
    now = datetime.now(UTC)
    secret_value = "ultra-private-drill-token"
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        log = _valid_audit_log(
            action="drill.sensitive",
            resource="drill:sensitive",
            created_at=now - timedelta(days=90),
            user_agent=f"Bearer {secret_value}",
            request_path=f"/api/audit?token={secret_value}",
            snapshot_json={"password": secret_value},
        )
        db.add(log)
        db.commit()
        report = run_audit_archive_drill(
            db,
            database_url=get_settings().database_url,
            settings=get_settings(),
            before_at=now - timedelta(days=30),
            action="drill.sensitive",
            generated_at=now,
        )

    assert report["ok"] is False
    assert report["sensitive_field_scan"]["status"] == "issues_found"
    assert report["sensitive_field_scan"]["issue_counts_by_code"]["exported_audit_field_may_contain_secret"] == 2
    assert report["sensitive_field_scan"]["issue_counts_by_code"]["audit_snapshot_contains_sensitive_key"] == 1
    assert secret_value not in json.dumps(report, ensure_ascii=False)
    assert "request_path" in {issue.get("field") for issue in report["sensitive_field_scan"]["issues"]}


def test_audit_archive_drill_detects_invalid_hash_chain(client):
    now = datetime.now(UTC)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        log = _valid_audit_log(action="drill.invalid_chain", resource="drill:bad", created_at=now - timedelta(days=90))
        log.current_hash = "not-a-valid-chain-hash"
        db.add(log)
        db.commit()
        report = run_audit_archive_drill(
            db,
            database_url=get_settings().database_url,
            settings=get_settings(),
            before_at=now - timedelta(days=30),
            action="drill.invalid_chain",
            generated_at=now,
        )

    assert report["ok"] is False
    assert report["chain_integrity"]["status"] == "issues_found"
    assert report["chain_integrity"]["issue_counts_by_code"]["audit_chain_invalid"] == 1
    assert report["chain_integrity"]["current_hash_mismatch_count"] == 1


def test_audit_archive_drill_cli_returns_json_for_invalid_now(capsys):
    exit_code = main(["--now", "not-a-date"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["ok"] is False
    assert output["status"] == "invalid_argument"


def _valid_audit_log(
    *,
    action: str,
    resource: str,
    created_at: datetime,
    prev_hash: str | None = None,
    user_agent: str | None = None,
    request_path: str = "/api/drill",
    snapshot_json: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        action=action,
        resource=resource,
        resource_type="audit_drill_test",
        resource_id=resource.rsplit(":", 1)[-1],
        event_result="success",
        request_id=f"{resource}-request",
        user_agent=user_agent,
        request_method="POST",
        request_path=request_path,
        prev_hash=prev_hash,
        snapshot_json=snapshot_json or {},
        created_at=created_at,
        updated_at=created_at,
    )
    log.current_hash = audit_log_chain_hash(log)
    return log
