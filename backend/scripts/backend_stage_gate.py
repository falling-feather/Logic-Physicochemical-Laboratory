from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

from app.services.backend_stage_gate import build_backend_stage_gate_report
from scripts.audit_archive_drill import run_audit_archive_drill_report
from scripts.auth_security_drill import run_auth_security_drill
from scripts.content_lifecycle_drill import run_content_lifecycle_drill_report
from scripts.content_script_remote_drift_drill import run_content_script_remote_drift_drill_report
from scripts.deploy_preflight import BACKEND_ROOT, run_preflight
from scripts.deploy_smoke import run_smoke
from scripts.deploy_topology_drill import run_topology_drill
from scripts.knowledge_snapshot_scheduler_drill import run_knowledge_snapshot_scheduler_drill_report


def run_backend_stage_gate_report(
    *,
    database_url: str | None = None,
    backend_root: Path | None = None,
    require_mysql: bool = False,
    require_production: bool = False,
    require_admin_bootstrap_token: bool = False,
    expect_knowledge_scheduler_enabled: bool = False,
    expect_content_script_scheduler_enabled: bool = False,
    run_topology_live: bool = False,
    topology_options: dict[str, Any] | None = None,
    render_url: str | None = None,
    static_url: str | None = None,
    confirm_backend_tests_passed: bool = False,
    confirm_core_manual_paths: bool = False,
    confirm_deploy_docs_reviewed: bool = False,
    confirm_admin_bootstrap_reviewed: bool = False,
    confirm_rollback_reviewed: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    root = backend_root or BACKEND_ROOT
    subreports: dict[str, dict[str, Any] | None] = {
        "deploy_preflight": _safe_report(
            lambda: run_preflight(database_url=database_url, backend_root=root, require_mysql=require_mysql)
        ),
        "deploy_smoke": _safe_report(
            lambda: run_smoke(database_url=database_url, backend_root=root, require_mysql=require_mysql)
        ),
        "auth_security": _safe_report(
            lambda: run_auth_security_drill(
                require_production=require_production,
                require_admin_bootstrap_token=require_admin_bootstrap_token,
            )
        ),
        "content_lifecycle": _safe_report(
            lambda: run_content_lifecycle_drill_report(
                database_url=database_url,
                require_mysql=require_mysql,
                render_url=render_url,
                static_url=static_url,
            )
        ),
        "knowledge_scheduler": _safe_report(
            lambda: run_knowledge_snapshot_scheduler_drill_report(
                database_url=database_url,
                require_mysql=require_mysql,
                expect_scheduler_enabled=expect_knowledge_scheduler_enabled,
                now=generated_at,
            )
        ),
        "content_script_remote_drift": _safe_report(
            lambda: run_content_script_remote_drift_drill_report(
                database_url=database_url,
                require_mysql=require_mysql,
                expect_scheduler_enabled=expect_content_script_scheduler_enabled,
                now=generated_at,
            )
        ),
        "audit_archive": _safe_report(
            lambda: run_audit_archive_drill_report(
                database_url=database_url,
                require_mysql=require_mysql,
                generated_at=generated_at,
            )
        ),
        "deploy_topology": None,
    }
    if run_topology_live:
        subreports["deploy_topology"] = _safe_report(lambda: run_topology_drill(**(topology_options or {})))
    return build_backend_stage_gate_report(
        subreports=subreports,
        confirmations={
            "backend_tests": confirm_backend_tests_passed,
            "core_manual_paths": confirm_core_manual_paths,
            "deploy_docs": confirm_deploy_docs_reviewed,
            "admin_bootstrap": confirm_admin_bootstrap_reviewed,
            "rollback": confirm_rollback_reviewed,
        },
        require_mysql=require_mysql,
        generated_at=generated_at,
        topology_live_requested=run_topology_live,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the V6.6.44 backend stage-completion gate report.")
    parser.add_argument("--database-url", default=None, help="Override ASTRA_DATABASE_URL for this run.")
    parser.add_argument("--require-mysql", action="store_true", help="Require real MySQL-compatible reports.")
    parser.add_argument("--require-production", action="store_true", help="Require production-like auth posture.")
    parser.add_argument(
        "--require-admin-bootstrap-token",
        action="store_true",
        help="Require a configured non-placeholder ASTRA_ADMIN_BOOTSTRAP_TOKEN.",
    )
    parser.add_argument("--expect-knowledge-scheduler-enabled", action="store_true")
    parser.add_argument("--expect-content-script-scheduler-enabled", action="store_true")
    parser.add_argument("--run-topology-live", action="store_true", help="Run live deploy_topology_drill probes.")
    parser.add_argument("--static-url", default=None, help="Static site URL for content lifecycle and topology probes.")
    parser.add_argument("--render-url", default=None, help="Live /api/render/page/{slug} URL for content lifecycle.")
    parser.add_argument("--proxied-api-url", default=None, help="Proxied /api/health URL for topology probes.")
    parser.add_argument("--direct-api-url", default=None, help="Direct FastAPI /api/health URL for topology probes.")
    parser.add_argument("--public-direct-api-url", default=None, help="Optional public direct FastAPI URL expected to fail.")
    parser.add_argument("--origin", default=None, help="Optional Origin header for CORS topology probe.")
    parser.add_argument("--api-bind-host", default=None, help="Expected FastAPI bind host for topology policy.")
    parser.add_argument("--api-bind-port", type=int, default=None, help="Expected FastAPI bind port for topology policy.")
    parser.add_argument("--confirm-backend-tests-passed", action="store_true")
    parser.add_argument("--confirm-core-manual-paths", action="store_true")
    parser.add_argument("--confirm-deploy-docs-reviewed", action="store_true")
    parser.add_argument("--confirm-admin-bootstrap-reviewed", action="store_true")
    parser.add_argument("--confirm-rollback-reviewed", action="store_true")
    parser.add_argument("--now", default=None, help="Override generated_at for deterministic reports.")
    args = parser.parse_args(argv)

    try:
        generated_at = _parse_datetime(args.now) if args.now else None
    except ValueError as exc:
        report = {
            "ok": False,
            "status": "invalid_argument",
            "error": exc.__class__.__name__,
            "detail": str(exc),
            "sensitive_fields_returned": False,
        }
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
        return 1

    topology_options = _topology_options(args)
    report = run_backend_stage_gate_report(
        database_url=args.database_url,
        require_mysql=args.require_mysql,
        require_production=args.require_production,
        require_admin_bootstrap_token=args.require_admin_bootstrap_token,
        expect_knowledge_scheduler_enabled=args.expect_knowledge_scheduler_enabled,
        expect_content_script_scheduler_enabled=args.expect_content_script_scheduler_enabled,
        run_topology_live=args.run_topology_live,
        topology_options=topology_options,
        render_url=args.render_url,
        static_url=args.static_url,
        confirm_backend_tests_passed=args.confirm_backend_tests_passed,
        confirm_core_manual_paths=args.confirm_core_manual_paths,
        confirm_deploy_docs_reviewed=args.confirm_deploy_docs_reviewed,
        confirm_admin_bootstrap_reviewed=args.confirm_admin_bootstrap_reviewed,
        confirm_rollback_reviewed=args.confirm_rollback_reviewed,
        generated_at=generated_at,
    )
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


def _safe_report(factory: Any) -> dict[str, Any]:
    try:
        return factory()
    except Exception as exc:
        return {
            "ok": False,
            "status": "exception",
            "error": exc.__class__.__name__,
            "sensitive_fields_returned": False,
        }


def _topology_options(args: argparse.Namespace) -> dict[str, Any]:
    options: dict[str, Any] = {}
    for arg_name, option_name in {
        "static_url": "static_url",
        "proxied_api_url": "proxied_api_url",
        "direct_api_url": "direct_api_url",
        "public_direct_api_url": "public_direct_api_url",
        "origin": "origin",
        "api_bind_host": "api_bind_host",
        "api_bind_port": "api_bind_port",
    }.items():
        value = getattr(args, arg_name)
        if value is not None:
            options[option_name] = value
    return options


def _parse_datetime(value: str) -> datetime:
    text = value.strip()
    if len(text) == 10:
        return datetime.fromisoformat(text).replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
