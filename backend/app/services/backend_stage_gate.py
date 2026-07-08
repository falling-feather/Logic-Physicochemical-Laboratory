from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any


SUBREPORT_LABELS = {
    "deploy_preflight": "deploy_preflight --require-mysql",
    "deploy_smoke": "deploy_smoke --require-mysql",
    "auth_security": "auth_security_drill",
    "content_lifecycle": "content_lifecycle_drill",
    "knowledge_scheduler": "knowledge_snapshot_scheduler_drill",
    "content_script_remote_drift": "content_script_remote_drift_drill",
    "audit_archive": "audit_archive_drill",
    "deploy_topology": "deploy_topology_drill",
}

MANUAL_EVIDENCE = {
    "backend_tests": {
        "label": "backend full pytest suite",
        "command": "python -m pytest backend -q -p no:cacheprovider",
    },
    "core_manual_paths": {
        "label": "core backend manual path evidence",
        "command": "admin bootstrap, login/logout/session revoke, content render, assignment submit/grade",
    },
    "deploy_docs": {
        "label": "deployment docs/env/rollback review",
        "command": "review doc/04 deployment, environment variables, rollback and service restart path",
    },
    "admin_bootstrap": {
        "label": "production admin bootstrap review",
        "command": "verify ASTRA_ADMIN_BOOTSTRAP_TOKEN policy and first-admin initialization evidence",
    },
    "rollback": {
        "label": "rollback and recovery evidence",
        "command": "verify code rollback, DB backup/restore posture and non-destructive migration boundary",
    },
}


def build_backend_stage_gate_report(
    *,
    subreports: dict[str, dict[str, Any] | None],
    confirmations: dict[str, bool],
    require_mysql: bool,
    generated_at: datetime | None = None,
    topology_live_requested: bool = False,
) -> dict[str, Any]:
    generated = generated_at or datetime.now(UTC)
    gates: dict[str, dict[str, Any]] = {
        "mysql_gate_enforced": _mysql_gate(require_mysql=require_mysql),
    }
    for key in (
        "deploy_preflight",
        "deploy_smoke",
        "auth_security",
        "content_lifecycle",
        "knowledge_scheduler",
        "content_script_remote_drift",
        "audit_archive",
    ):
        gates[key] = _subreport_gate(key, subreports.get(key))
    gates["deploy_topology"] = (
        _subreport_gate("deploy_topology", subreports.get("deploy_topology"))
        if topology_live_requested
        else _missing_gate(
            "deploy_topology",
            label=SUBREPORT_LABELS["deploy_topology"],
            evidence="run with --run-topology-live against the real proxy/service topology",
        )
    )
    for key, meta in MANUAL_EVIDENCE.items():
        gates[key] = _manual_gate(key, confirmed=bool(confirmations.get(key)), meta=meta)

    blockers = [_gate_issue(code, gate) for code, gate in gates.items() if gate["status"] == "blocked"]
    missing = [_gate_issue(code, gate) for code, gate in gates.items() if gate["status"] == "missing_evidence"]
    warning_gates = [_gate_issue(code, gate) for code, gate in gates.items() if gate["status"] == "warning"]
    status = "ready"
    if blockers:
        status = "blocked"
    elif missing:
        status = "missing_evidence"
    elif warning_gates:
        status = "risk_acceptance_required"
    ok = status == "ready"
    sensitive_fields_returned = any(bool(gate.get("sensitive_fields_returned")) for gate in gates.values())
    sensitive_values_returned = any(bool(gate.get("sensitive_values_returned")) for gate in gates.values())
    return {
        "ok": ok,
        "status": status,
        "phase": "V6.6.44",
        "generated_at": _datetime_value(generated),
        "mode": "read_only",
        "require_mysql": require_mysql,
        "decision": _decision(status=status, blockers=blockers, missing=missing, warnings=warning_gates),
        "counts": _counts(gates, blockers=blockers, missing=missing, warnings=warning_gates),
        "gates": gates,
        "blockers": blockers,
        "missing_evidence": missing,
        "warnings": warning_gates,
        "evidence_required": _evidence_required(),
        "sensitive_fields_returned": sensitive_fields_returned,
        "sensitive_values_returned": sensitive_values_returned,
    }


def _subreport_gate(key: str, report: dict[str, Any] | None) -> dict[str, Any]:
    label = SUBREPORT_LABELS[key]
    if report is None:
        return _missing_gate(key, label=label, evidence=f"run {label} and attach JSON output")
    ok = bool(report.get("ok"))
    sensitive_returned = bool(report.get("sensitive_fields_returned") or report.get("sensitive_values_returned"))
    if ok and sensitive_returned:
        return {
            "ok": False,
            "status": "blocked",
            "label": label,
            "reason": "sensitive_fields_returned",
            "source_status": _source_status(report),
            "sensitive_fields_returned": bool(report.get("sensitive_fields_returned")),
            "sensitive_values_returned": bool(report.get("sensitive_values_returned")),
            "summary": _report_summary(report),
        }
    return {
        "ok": ok,
        "status": "passed" if ok else "blocked",
        "label": label,
        "reason": None if ok else _source_status(report),
        "source_status": _source_status(report),
        "sensitive_fields_returned": bool(report.get("sensitive_fields_returned")),
        "sensitive_values_returned": bool(report.get("sensitive_values_returned")),
        "summary": _report_summary(report),
    }


def _manual_gate(key: str, *, confirmed: bool, meta: dict[str, str]) -> dict[str, Any]:
    return {
        "ok": confirmed,
        "status": "passed" if confirmed else "missing_evidence",
        "label": meta["label"],
        "reason": None if confirmed else "manual_evidence_not_confirmed",
        "expected_command_or_evidence": meta["command"],
        "confirmed": confirmed,
        "sensitive_fields_returned": False,
        "sensitive_values_returned": False,
    }


def _mysql_gate(*, require_mysql: bool) -> dict[str, Any]:
    return {
        "ok": require_mysql,
        "status": "passed" if require_mysql else "missing_evidence",
        "label": "MySQL production gate explicitly enabled",
        "reason": None if require_mysql else "stage_gate_requires_--require-mysql",
        "expected_command_or_evidence": "run backend_stage_gate with --require-mysql against staging/production MySQL",
        "confirmed": require_mysql,
        "sensitive_fields_returned": False,
        "sensitive_values_returned": False,
    }


def _missing_gate(key: str, *, label: str, evidence: str) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "missing_evidence",
        "label": label,
        "reason": "not_run",
        "expected_command_or_evidence": evidence,
        "sensitive_fields_returned": False,
        "sensitive_values_returned": False,
    }


def _gate_issue(code: str, gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate": code,
        "label": gate.get("label"),
        "reason": gate.get("reason"),
        "source_status": gate.get("source_status"),
        "expected_command_or_evidence": gate.get("expected_command_or_evidence"),
    }


def _source_status(report: dict[str, Any]) -> str:
    if isinstance(report.get("status"), str):
        return str(report["status"])
    for key in ("database", "configuration", "preflight", "schema", "api", "topology"):
        section = report.get(key)
        if isinstance(section, dict) and isinstance(section.get("status"), str):
            return str(section["status"])
    return "ready" if report.get("ok") else "failed"


def _report_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": bool(report.get("ok")),
        "status": _source_status(report),
    }
    for key in ("mode", "sensitive_fields_returned", "sensitive_values_returned"):
        if key in report:
            summary[key] = report[key]
    for key in ("database", "configuration", "schema", "api", "decision"):
        section = report.get(key)
        if isinstance(section, dict):
            summary[key] = {
                item_key: section.get(item_key)
                for item_key in ("ok", "status", "dialect", "require_mysql", "environment", "service")
                if item_key in section
            }
    return summary


def _counts(
    gates: dict[str, dict[str, Any]],
    *,
    blockers: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    status_counts = Counter(str(gate["status"]) for gate in gates.values())
    return {
        "total_gates": len(gates),
        "passed": status_counts.get("passed", 0),
        "blocked": len(blockers),
        "missing_evidence": len(missing),
        "warnings": len(warnings),
        "by_status": dict(status_counts),
    }


def _decision(
    *,
    status: str,
    blockers: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    if status == "ready":
        recommended = "通过"
        reason = "all required code-side gates and manual evidence confirmations are present"
    elif blockers:
        recommended = "延期"
        reason = "one or more required code-side gates failed"
    elif missing:
        recommended = "延期"
        reason = "one or more required production or manual evidence items are missing"
    else:
        recommended = "带风险通过"
        reason = "only warning-level risks remain; human release owner must accept them"
    return {
        "recommended": recommended,
        "reason": reason,
        "allowed_values": ["通过", "延期", "带风险通过"],
        "blocker_count": len(blockers),
        "missing_evidence_count": len(missing),
        "warning_count": len(warnings),
    }


def _evidence_required() -> list[str]:
    return [
        "desensitized MySQL DSN, Alembic current/head, deploy_preflight --require-mysql JSON",
        "deploy_smoke --require-mysql JSON including schema-column and /api/health checks",
        "full backend pytest output and exit code",
        "reverse proxy/service topology evidence or deploy_topology_drill live JSON",
        "auth_security_drill JSON plus admin bootstrap/login/session/password-reset manual evidence",
        "content_lifecycle_drill JSON plus init_content_pages/publish/rollback evidence",
        "knowledge_snapshot_scheduler_drill JSON plus multi-worker/cancel/requeue evidence",
        "content_script_remote_drift_drill JSON plus safe CDN scan and blocked-host evidence",
        "audit_archive_drill JSON plus archive dry-run/package/verify evidence",
        "deployment docs, environment variables, rollback and recovery steps reviewed",
        "explicit conclusion: 通过 / 延期 / 带风险通过",
    ]


def _datetime_value(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
