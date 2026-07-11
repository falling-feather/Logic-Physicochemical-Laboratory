import json
from datetime import UTC, datetime

from scripts import backend_stage_gate


def test_backend_stage_gate_passes_when_all_reports_and_manual_evidence_are_ready(monkeypatch):
    _patch_stage_gate_reports(monkeypatch)

    report = backend_stage_gate.run_backend_stage_gate_report(
        require_mysql=True,
        run_topology_live=True,
        confirm_backend_tests_passed=True,
        confirm_core_manual_paths=True,
        confirm_deploy_docs_reviewed=True,
        confirm_admin_bootstrap_reviewed=True,
        confirm_rollback_reviewed=True,
        generated_at=datetime(2026, 7, 8, tzinfo=UTC),
    )

    assert report["ok"] is True
    assert report["status"] == "ready"
    assert report["phase"] == "V6.6.44"
    assert report["decision"]["recommended"] == "通过"
    assert report["counts"]["blocked"] == 0
    assert report["counts"]["missing_evidence"] == 0
    assert report["gates"]["mysql_gate_enforced"]["ok"] is True
    assert report["sensitive_fields_returned"] is False
    assert report["sensitive_values_returned"] is False


def test_backend_stage_gate_requires_mysql_topology_and_manual_evidence(monkeypatch):
    _patch_stage_gate_reports(monkeypatch)

    report = backend_stage_gate.run_backend_stage_gate_report(require_mysql=False)

    missing_gates = {item["gate"] for item in report["missing_evidence"]}
    assert report["ok"] is False
    assert report["status"] == "missing_evidence"
    assert report["decision"]["recommended"] == "延期"
    assert "mysql_gate_enforced" in missing_gates
    assert "deploy_topology" in missing_gates
    assert "backend_tests" in missing_gates
    assert "core_manual_paths" in missing_gates


def test_backend_stage_gate_blocks_on_failed_subreport(monkeypatch):
    _patch_stage_gate_reports(monkeypatch)
    monkeypatch.setattr(
        backend_stage_gate,
        "run_preflight",
        lambda *args, **kwargs: _report(ok=False, status="unexpected_dialect"),
    )

    report = backend_stage_gate.run_backend_stage_gate_report(
        require_mysql=True,
        run_topology_live=True,
        confirm_backend_tests_passed=True,
        confirm_core_manual_paths=True,
        confirm_deploy_docs_reviewed=True,
        confirm_admin_bootstrap_reviewed=True,
        confirm_rollback_reviewed=True,
    )

    blockers = {item["gate"]: item for item in report["blockers"]}
    assert report["ok"] is False
    assert report["status"] == "blocked"
    assert report["decision"]["recommended"] == "延期"
    assert blockers["deploy_preflight"]["reason"] == "unexpected_dialect"


def test_backend_stage_gate_blocks_on_sensitive_subreport(monkeypatch):
    _patch_stage_gate_reports(monkeypatch)
    monkeypatch.setattr(
        backend_stage_gate,
        "run_audit_archive_drill_report",
        lambda *args, **kwargs: _report(sensitive_values_returned=True),
    )

    report = backend_stage_gate.run_backend_stage_gate_report(
        require_mysql=True,
        run_topology_live=True,
        confirm_backend_tests_passed=True,
        confirm_core_manual_paths=True,
        confirm_deploy_docs_reviewed=True,
        confirm_admin_bootstrap_reviewed=True,
        confirm_rollback_reviewed=True,
    )

    blockers = {item["gate"]: item for item in report["blockers"]}
    assert report["ok"] is False
    assert report["status"] == "blocked"
    assert report["sensitive_values_returned"] is True
    assert blockers["audit_archive"]["reason"] == "sensitive_fields_returned"


def test_backend_stage_gate_optionally_adds_v63_external_scope_as_fifteenth_gate(monkeypatch):
    _patch_stage_gate_reports(monkeypatch)
    monkeypatch.setattr(backend_stage_gate, "run_rc_external_scope_gate", lambda *args, **kwargs: _report())

    report = backend_stage_gate.run_backend_stage_gate_report(
        require_mysql=True,
        run_topology_live=True,
        run_rc_external_scope=True,
        confirm_database_restore_evidence=True,
        confirm_runtime_rollback_evidence=True,
        confirm_backend_tests_passed=True,
        confirm_core_manual_paths=True,
        confirm_deploy_docs_reviewed=True,
        confirm_admin_bootstrap_reviewed=True,
        confirm_rollback_reviewed=True,
    )

    assert report["ok"] is True
    assert report["phase"] == "V6.6.63"
    assert report["counts"]["total_gates"] == 15
    assert report["counts"]["passed"] == 15
    assert report["gates"]["rc_external_scope"]["ok"] is True


def test_backend_stage_gate_cli_returns_json_for_invalid_now(capsys):
    exit_code = backend_stage_gate.main(["--now", "not-a-date"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["ok"] is False
    assert output["status"] == "invalid_argument"


def _patch_stage_gate_reports(monkeypatch):
    monkeypatch.setattr(backend_stage_gate, "run_preflight", lambda *args, **kwargs: _report())
    monkeypatch.setattr(backend_stage_gate, "run_smoke", lambda *args, **kwargs: _report())
    monkeypatch.setattr(backend_stage_gate, "run_auth_security_drill", lambda *args, **kwargs: _report())
    monkeypatch.setattr(backend_stage_gate, "run_content_lifecycle_drill_report", lambda *args, **kwargs: _report())
    monkeypatch.setattr(
        backend_stage_gate,
        "run_knowledge_snapshot_scheduler_drill_report",
        lambda *args, **kwargs: _report(),
    )
    monkeypatch.setattr(
        backend_stage_gate,
        "run_content_script_remote_drift_drill_report",
        lambda *args, **kwargs: _report(),
    )
    monkeypatch.setattr(backend_stage_gate, "run_audit_archive_drill_report", lambda *args, **kwargs: _report())
    monkeypatch.setattr(backend_stage_gate, "run_topology_drill", lambda *args, **kwargs: _report())


def _report(*, ok: bool = True, status: str = "ready", sensitive_values_returned: bool = False):
    return {
        "ok": ok,
        "status": status,
        "mode": "read_only",
        "sensitive_fields_returned": False,
        "sensitive_values_returned": sensitive_values_returned,
    }
