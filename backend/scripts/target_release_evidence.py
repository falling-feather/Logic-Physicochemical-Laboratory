from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
from typing import Any, Callable
from urllib.parse import urlsplit


TARGET_RELEASE_SCHEMA_VERSION = "target-release-v2"
EVIDENCE_SCHEMA_VERSION = "target-release-evidence-v1"
ARTIFACT_MANIFEST_SCHEMA_VERSION = "release-artifact-manifest-v1"
EXPECTED_ALEMBIC_REVISION = "20260719_0049"
EXPECTED_ORGANIZATION_GOVERNANCE_REVISION = "20260716_0047"
MAX_EVIDENCE_AGE = timedelta(days=7)
MAX_ARTIFACT_MANIFEST_BYTES = 10 * 1024 * 1024
REQUIRED_EVIDENCE = (
    "deploy_preflight",
    "deploy_smoke",
    "deploy_topology",
    "backend_stage_gate",
    "database_restore",
    "runtime_rollback",
    "target_browser_smoke",
)
AUTOMATED_EVIDENCE = {
    "deploy_preflight",
    "deploy_smoke",
    "deploy_topology",
    "backend_stage_gate",
}
REQUIRED_SERVICE_NAMES = {"EngLab", "AstraApi", "AstraWorker", "AstraProxy"}
REQUIRED_ARTIFACT_COMPONENTS = {"static", "api", "worker", "proxy", "migrations"}
REQUIRED_STAGE_GATES = {
    "mysql_gate_enforced",
    "deploy_preflight",
    "deploy_smoke",
    "auth_security",
    "content_lifecycle",
    "knowledge_scheduler",
    "content_script_remote_drift",
    "audit_archive",
    "deploy_topology",
    "rc_external_scope",
    "backend_tests",
    "core_manual_paths",
    "deploy_docs",
    "admin_bootstrap",
    "rollback",
}
REQUIRED_BROWSER_ROLES = {"student", "teacher", "admin"}
REQUIRED_BROWSER_VIEWPORTS = {"desktop", "390x844"}
REQUIRED_BROWSER_CHECKS = {
    "login_before_shell",
    "cookie_session",
    "role_navigation_isolation",
    "role_resource_isolation",
    "unauthorized_requests_denied",
    "service_worker_api_no_store",
    "organization_stale_version_409",
    "organization_archive",
    "organization_restore",
    "no_console_errors",
    "no_page_errors",
    "no_horizontal_overflow",
}
_RELEASE_VERSION_RE = re.compile(r"V\d+\.\d+\.\d+")
_REVISION_RE = re.compile(r"[0-9a-fA-F]{40}")
_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{5,127}")
_PUBLIC_DNS_LABEL_RE = re.compile(r"(?!-)[a-z0-9-]{1,63}(?<!-)")
_RESERVED_PUBLIC_SUFFIXES = (".example", ".invalid", ".localhost", ".local", ".test")
_EXAMPLE_DOMAIN_ROOTS = ("example.com", "example.net", "example.org", "example.edu")
_SENSITIVE_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "credential",
    "private_key",
    "api_key",
    "access_key",
    "database_url",
    "dsn",
)


def normalize_public_https_origin(value: Any) -> tuple[str | None, str]:
    """Validate and normalize one exact public HTTPS origin."""
    text = str(value or "").strip()
    if not text or _placeholder(text):
        return None, "public_origin_placeholder_not_replaced"
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError:
        return None, "public_origin_invalid"
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None, "public_origin_must_be_https_origin"
    if parsed.path or "?" in text or "#" in text or port not in {None, 443}:
        return None, "public_origin_must_not_include_path_query_fragment_or_nonstandard_port"

    hostname = parsed.hostname.lower()
    authority = parsed.netloc.lower()
    if authority not in {hostname, f"{hostname}:443"}:
        return None, "public_origin_domain_invalid"
    if any(
        hostname == suffix[1:] or hostname.endswith(suffix)
        for suffix in _RESERVED_PUBLIC_SUFFIXES
    ) or any(
        hostname == root or hostname.endswith(f".{root}") for root in _EXAMPLE_DOMAIN_ROOTS
    ):
        return None, "public_origin_placeholder_domain_not_allowed"
    try:
        ipaddress.ip_address(hostname)
        return None, "public_origin_must_use_approved_domain"
    except ValueError:
        pass
    if is_legacy_ipv4_literal(hostname):
        return None, "public_origin_must_use_approved_domain"
    if (
        not has_public_dns_syntax(hostname)
    ):
        return None, "public_origin_domain_invalid"
    return f"https://{hostname}", "ready"


def has_public_dns_syntax(value: Any) -> bool:
    hostname = str(value or "").strip().lower()
    labels = hostname.split(".")
    return bool(
        len(hostname) <= 253
        and len(labels) >= 2
        and all(_PUBLIC_DNS_LABEL_RE.fullmatch(label) for label in labels)
        and re.search(r"[a-z]", labels[-1])
    )


def is_legacy_ipv4_literal(value: Any) -> bool:
    """Return whether a string uses inet_aton-compatible legacy IPv4 notation."""
    try:
        socket.inet_aton(str(value or "").strip())
        return True
    except (OSError, UnicodeError):
        return False


def validate_evidence_envelope(
    payload: Any,
    *,
    evidence_id: str,
    run_id: str,
    target: dict[str, Any],
    release: dict[str, Any],
    controls: dict[str, Any],
    now: datetime,
) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "evidence_envelope_must_be_object"
    if payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        return False, "evidence_schema_version_mismatch"
    if payload.get("evidence_id") != evidence_id:
        return False, "evidence_id_mismatch"
    if payload.get("run_id") != run_id or not _valid_identifier(run_id):
        return False, "evidence_run_id_mismatch_or_invalid"

    generated_at = _parse_datetime(payload.get("generated_at"))
    if not _recent(generated_at, now, max_age=MAX_EVIDENCE_AGE):
        return False, "evidence_generated_at_missing_future_or_older_than_7_days"

    envelope_target = _mapping(payload.get("target"))
    if (
        envelope_target.get("environment") != target.get("environment")
        or envelope_target.get("public_origin") != target.get("public_origin")
        or envelope_target.get("instance_id") != target.get("instance_id")
    ):
        return False, "evidence_target_mismatch"

    envelope_release = _mapping(payload.get("release"))
    if (
        envelope_release.get("version") != release.get("version")
        or str(envelope_release.get("revision") or "").lower()
        != str(release.get("revision") or "").lower()
        or str(envelope_release.get("artifact_manifest_sha256") or "").lower()
        != str(release.get("artifact_manifest_sha256") or "").lower()
        or envelope_release.get("artifact_manifest_path") != release.get("artifact_manifest_path")
        or envelope_release.get("evidence_bundle_id") != release.get("evidence_bundle_id")
    ):
        return False, "evidence_release_mismatch"

    report = payload.get("report")
    if not isinstance(report, dict):
        return False, "evidence_report_missing"
    if _contains_sensitive_values(report):
        return False, "evidence_sensitive_value_detected"
    if evidence_id in AUTOMATED_EVIDENCE and not _report_generated_recent(report, now):
        return False, "evidence_raw_generated_at_missing_future_or_older_than_7_days"
    if evidence_id == "target_browser_smoke" and not _recent(
        _parse_datetime(report.get("completed_at")),
        now,
        max_age=MAX_EVIDENCE_AGE,
    ):
        return False, "target_browser_completed_at_missing_future_or_older_than_7_days"
    return validate_evidence_report(
        evidence_id,
        report,
        target=target,
        release=release,
        controls=controls,
        generated_at=generated_at,
    )


def validate_evidence_report(
    evidence_id: str,
    report: dict[str, Any],
    *,
    target: dict[str, Any],
    release: dict[str, Any],
    controls: dict[str, Any],
    generated_at: datetime,
) -> tuple[bool, str]:
    validators: dict[str, Callable[..., bool]] = {
        "deploy_preflight": _deploy_preflight_ready,
        "deploy_smoke": _deploy_smoke_ready,
        "deploy_topology": _deploy_topology_ready,
        "backend_stage_gate": _backend_stage_gate_ready,
        "database_restore": _database_restore_ready,
        "runtime_rollback": _runtime_rollback_ready,
        "target_browser_smoke": _target_browser_smoke_ready,
    }
    validator = validators.get(evidence_id)
    if validator is None:
        return False, "unsupported_evidence_id"
    if report.get("ok") is not True or report.get("status") not in {None, "ready"}:
        return False, f"{evidence_id}_not_ready"
    if report.get("sensitive_fields_returned") not in {None, False}:
        return False, "evidence_sensitive_fields_returned"
    if report.get("sensitive_values_returned") not in {None, False}:
        return False, "evidence_sensitive_values_returned"
    if not validator(
        report,
        target=target,
        release=release,
        controls=controls,
        generated_at=generated_at,
    ):
        return False, f"{evidence_id}_semantics_invalid"
    return True, "ready"


def build_evidence_envelope(
    *,
    evidence_id: str,
    run_id: str,
    report: dict[str, Any],
    target: dict[str, Any],
    release: dict[str, Any],
    controls: dict[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated = _utc(generated_at or datetime.now(UTC))
    if not _valid_identifier(run_id):
        raise ValueError("evidence_run_id_invalid")
    ok, reason = validate_evidence_report(
        evidence_id,
        report,
        target=target,
        release=release,
        controls=controls,
        generated_at=generated,
    )
    if not ok:
        raise ValueError(reason)
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "evidence_id": evidence_id,
        "run_id": run_id,
        "generated_at": generated.isoformat(),
        "target": {
            "environment": target.get("environment"),
            "public_origin": target.get("public_origin"),
            "instance_id": target.get("instance_id"),
        },
        "release": {
            "version": release.get("version"),
            "revision": str(release.get("revision") or "").lower(),
            "artifact_manifest_path": release.get("artifact_manifest_path"),
            "artifact_manifest_sha256": str(release.get("artifact_manifest_sha256") or "").lower(),
            "evidence_bundle_id": release.get("evidence_bundle_id"),
        },
        "report": report,
    }


def manual_evidence_template(evidence_id: str) -> dict[str, Any]:
    templates: dict[str, dict[str, Any]] = {
        "database_restore": {
            "ok": False,
            "status": "replace_template",
            "completed_at": "REPLACE_WITH_ISO8601_COMPLETION_TIME",
            "backup_ref": "REPLACE_WITH_BACKUP_REFERENCE",
            "backup_sha256": "REPLACE_WITH_64_HEX_SHA256",
            "source_database": "REPLACE_WITH_SOURCE_DATABASE_NAME",
            "restore_database": "REPLACE_WITH_DISTINCT_RESTORE_DATABASE_NAME",
            "alembic_revision": EXPECTED_ALEMBIC_REVISION,
            "integrity_checks": {
                "schema": False,
                "row_counts": False,
                "audit_chain": False,
                "application_smoke": False,
            },
            "sensitive_fields_returned": False,
            "sensitive_values_returned": False,
        },
        "runtime_rollback": {
            "ok": False,
            "status": "replace_template",
            "completed_at": "REPLACE_WITH_ISO8601_COMPLETION_TIME",
            "candidate_revision": "REPLACE_WITH_40_HEX_CANDIDATE_REVISION",
            "rollback_revision": "REPLACE_WITH_DISTINCT_40_HEX_PREVIOUS_REVISION",
            "config_ref": "REPLACE_WITH_CONFIG_ROLLBACK_REFERENCE",
            "binary_ref": "REPLACE_WITH_BINARY_ROLLBACK_REFERENCE",
            "database_ref": "REPLACE_WITH_DATABASE_ROLLBACK_REFERENCE",
            "service_names": ["EngLab", "AstraApi", "AstraWorker", "AstraProxy"],
            "checks": {
                "config_restored": False,
                "binaries_restored": False,
                "database_posture_verified": False,
                "static_smoke": False,
                "api_smoke": False,
                "worker_smoke": False,
                "proxy_smoke": False,
            },
            "sensitive_fields_returned": False,
            "sensitive_values_returned": False,
        },
        "target_browser_smoke": {
            "ok": False,
            "status": "replace_template",
            "completed_at": "REPLACE_WITH_ISO8601_COMPLETION_TIME",
            "public_origin": "REPLACE_WITH_TARGET_PUBLIC_ORIGIN",
            "release_revision": "REPLACE_WITH_40_HEX_RELEASE_REVISION",
            "browser": {"name": "REPLACE_WITH_BROWSER_NAME", "version": "REPLACE_WITH_BROWSER_VERSION"},
            "roles": ["student", "teacher", "admin"],
            "viewports": ["desktop", "390x844"],
            "checks": {name: False for name in sorted(REQUIRED_BROWSER_CHECKS)},
            "sensitive_fields_returned": False,
            "sensitive_values_returned": False,
        },
    }
    if evidence_id not in templates:
        raise ValueError("manual_template_only_supports_database_restore_runtime_rollback_target_browser_smoke")
    return templates[evidence_id]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create templates or seal target-release evidence envelopes.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    template_parser = subparsers.add_parser("template", help="Create a fail-closed raw manual evidence template.")
    template_parser.add_argument(
        "--evidence-id",
        required=True,
        choices=("database_restore", "runtime_rollback", "target_browser_smoke"),
    )
    template_parser.add_argument("--output", required=True)

    seal_parser = subparsers.add_parser("seal", help="Validate and bind a raw report to one target release.")
    seal_parser.add_argument("--manifest", required=True)
    seal_parser.add_argument("--evidence-id", required=True, choices=REQUIRED_EVIDENCE)
    seal_parser.add_argument("--run-id", required=True, help="Unique immutable run identifier for this evidence item.")
    seal_parser.add_argument("--input", required=True, help="Raw report JSON generated by the matching drill.")
    seal_parser.add_argument("--output", required=True, help="Destination evidence envelope JSON.")
    seal_parser.add_argument("--now", default=None, help=argparse.SUPPRESS)
    seal_parser.add_argument(
        "--allow-test-time-override",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    seal_parser.add_argument("--replace", action="store_true", help="Explicitly replace an existing output file.")
    args = parser.parse_args(argv)

    try:
        if args.command == "template":
            output = Path(args.output).resolve()
            payload = manual_evidence_template(args.evidence_id)
            _atomic_write_json(output, payload, replace=False)
            summary = {
                "ok": True,
                "status": "template_created",
                "evidence_id": args.evidence_id,
                "output_name": output.name,
                "template_is_evidence": False,
                "sensitive_fields_returned": False,
                "sensitive_values_returned": False,
            }
        else:
            if args.now is not None or args.allow_test_time_override:
                raise ValueError("cli_time_override_not_supported")
            generated_at = datetime.now(UTC)
            manifest_path = Path(args.manifest).resolve()
            input_path = Path(args.input).resolve()
            output = Path(args.output).resolve()
            _reject_alias(output, manifest_path, input_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            target, release, controls = _manifest_context(manifest)
            artifact_ok, artifact_reason = validate_release_artifact_manifest(manifest_path.parent, release)
            if not artifact_ok:
                raise ValueError(artifact_reason)
            report = json.loads(input_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("raw_report_must_be_object")
            if _contains_sensitive_values(report):
                raise ValueError("raw_report_contains_sensitive_value")
            payload = build_evidence_envelope(
                evidence_id=args.evidence_id,
                run_id=args.run_id,
                report=report,
                target=target,
                release=release,
                controls=controls,
                generated_at=generated_at,
            )
            encoded = _atomic_write_json(output, payload, replace=args.replace)
            summary = {
                "ok": True,
                "status": "sealed",
                "evidence_id": args.evidence_id,
                "output_name": output.name,
                "sha256": hashlib.sha256(encoded).hexdigest(),
                "target": target,
                "release": release,
                "sensitive_fields_returned": False,
                "sensitive_values_returned": False,
            }
    except Exception as exc:
        summary = {
            "ok": False,
            "status": "invalid_evidence",
            "reason": str(exc) if isinstance(exc, ValueError) else exc.__class__.__name__,
            "sensitive_fields_returned": False,
            "sensitive_values_returned": False,
        }
    print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


def _deploy_preflight_ready(report: dict[str, Any], **context: Any) -> bool:
    target = _mapping(context.get("target"))
    configuration = _mapping(report.get("configuration"))
    database = _mapping(report.get("database"))
    migrations = _mapping(report.get("migrations"))
    compatibility = _mapping(report.get("compatibility"))
    heads = _string_list(migrations.get("heads"))
    current = _string_list(migrations.get("current"))
    return bool(
        report.get("ok") is True
        and _report_generated_recent(report, context.get("generated_at"))
        and configuration.get("ok") is True
        and configuration.get("status") == "ready"
        and configuration.get("require_mysql") is True
        and configuration.get("auto_create_tables") is False
        and configuration.get("environment") == target.get("environment")
        and database.get("ok") is True
        and database.get("status") == "connected"
        and migrations.get("ok") is True
        and migrations.get("status") == "up_to_date"
        and heads == [EXPECTED_ALEMBIC_REVISION]
        and current == [EXPECTED_ALEMBIC_REVISION]
        and compatibility.get("ok") is True
        and compatibility.get("status") == "ready"
        and compatibility.get("dialect") == "mysql"
        and compatibility.get("require_mysql") is True
        and compatibility.get("character_set_database") == "utf8mb4"
        and compatibility.get("character_set_connection") == "utf8mb4"
        and str(compatibility.get("collation_database") or "").startswith("utf8mb4_")
        and str(compatibility.get("collation_connection") or "").startswith("utf8mb4_")
        and _present(compatibility.get("server_version"))
        and _present(compatibility.get("database_name"))
        and _present(compatibility.get("current_user"))
    )


def _deploy_smoke_ready(report: dict[str, Any], **context: Any) -> bool:
    preflight = _mapping(report.get("preflight"))
    schema = _mapping(report.get("schema"))
    api = _mapping(report.get("api"))
    invalid_rows = _mapping(schema.get("organization_version_invalid_rows"))
    return bool(
        report.get("ok") is True
        and _report_generated_recent(report, context.get("generated_at"))
        and _deploy_preflight_ready(preflight, **context)
        and schema.get("ok") is True
        and schema.get("status") == "ready"
        and schema.get("dialect") == "mysql"
        and schema.get("require_mysql") is True
        and schema.get("missing_tables") == []
        and schema.get("missing_columns") == {}
        and isinstance(schema.get("expected_tables"), list)
        and bool(schema.get("expected_tables"))
        and set(_string_list(schema.get("expected_tables")))
        <= set(_string_list(schema.get("actual_tables")))
        and _integer(schema.get("checked_column_tables")) > 0
        and schema.get("datetime_precision_mismatches") == {}
        and schema.get("mysql_expected_datetime_precision") == 6
        and schema.get("organization_governance_mismatches") == {}
        and invalid_rows == {"class_groups": 0, "schools": 0}
        and schema.get("expected_organization_governance_revision")
        == EXPECTED_ORGANIZATION_GOVERNANCE_REVISION
        and api.get("ok") is True
        and api.get("status") == "healthy"
        and api.get("status_code") == 200
        and _mapping(api.get("health")).get("service") == "astra-backend"
        and _mapping(_mapping(api.get("health")).get("database")).get("ok") is True
    )


def _deploy_topology_ready(report: dict[str, Any], **context: Any) -> bool:
    target = _mapping(context.get("target"))
    network = _mapping(_mapping(context.get("controls")).get("network"))
    origin = str(target.get("public_origin") or "").rstrip("/")
    topology = _mapping(report.get("topology"))
    static_site = _mapping(report.get("static_site"))
    proxied_api = _mapping(report.get("proxied_api"))
    direct_api = _mapping(report.get("direct_api"))
    public_exposure = _mapping(report.get("public_exposure"))
    service_plan = _mapping(report.get("service_plan"))
    windows_services = _mapping(report.get("windows_services"))
    requirements = _mapping(report.get("target_requirements"))
    services = windows_services.get("services") if isinstance(windows_services.get("services"), list) else []
    service_names = [str(item.get("name")) for item in services if isinstance(item, dict)]
    api_bind_port = _integer(topology.get("api_bind_port"))
    blocked_inner_ports = {_integer(value) for value in network.get("blocked_inner_ports", [])}
    public_probe = _safe_urlsplit(public_exposure.get("url"))
    expected_probe_host = str(network.get("public_probe_host") or "").strip().lower().strip("[]")
    proxied_request_id = str(proxied_api.get("request_id") or "").strip()
    direct_request_id = str(direct_api.get("request_id") or "").strip()
    services_ready = len(services) == len(REQUIRED_SERVICE_NAMES) and all(
        _windows_service_ready(item) for item in services
    )
    return bool(
        report.get("ok") is True
        and _report_generated_recent(report, context.get("generated_at"))
        and requirements.get("public_port_isolation_required") is True
        and requirements.get("windows_services_requested") is True
        and topology.get("ok") is True
        and str(topology.get("static_url") or "").rstrip("/") == origin
        and topology.get("proxied_api_url") == f"{origin}/api/health"
        and topology.get("direct_api_url") == direct_api.get("url")
        and topology.get("public_direct_api_url") == public_exposure.get("url")
        and topology.get("proxied_api_path_ok") is True
        and topology.get("static_path_ok") is True
        and topology.get("direct_api_host_private_or_loopback") is True
        and topology.get("api_bind_host_private_or_loopback") is True
        and api_bind_port > 0
        and api_bind_port in blocked_inner_ports
        and static_site.get("ok") is True
        and static_site.get("status") == "ready"
        and 200 <= _integer(static_site.get("status_code")) < 300
        and static_site.get("html_detected") is True
        and str(static_site.get("url") or "").rstrip("/") == origin
        and proxied_api.get("ok") is True
        and proxied_api.get("status") == "ready"
        and 200 <= _integer(proxied_api.get("status_code")) < 300
        and proxied_api.get("url") == f"{origin}/api/health"
        and proxied_api.get("health_status") in {"ok", "degraded"}
        and proxied_api.get("service") == "astra-backend"
        and proxied_api.get("service_ok") is True
        and proxied_api.get("cache_no_store_ok") is True
        and proxied_api.get("request_id_ok") is True
        and proxied_api.get("cors_ok") is True
        and proxied_api.get("cors_origin") == origin
        and _present(proxied_request_id)
        and proxied_api.get("database_url_returned") is False
        and proxied_api.get("database_url_policy_ok") is True
        and direct_api.get("ok") is True
        and direct_api.get("status") == "ready"
        and 200 <= _integer(direct_api.get("status_code")) < 300
        and direct_api.get("service") == "astra-backend"
        and direct_api.get("service_ok") is True
        and direct_api.get("cache_no_store_ok") is True
        and direct_api.get("request_id_ok") is True
        and direct_api.get("database_url_returned") is False
        and direct_api.get("database_url_policy_ok") is True
        and direct_request_id == proxied_request_id
        and direct_api.get("direct_api_host_private_or_loopback") is True
        and direct_api.get("api_bind_host_private_or_loopback") is True
        and public_exposure.get("ok") is True
        and public_exposure.get("status") == "not_reachable"
        and public_exposure.get("required") is True
        and public_exposure.get("external_probe_ref") == network.get("external_probe_ref")
        and str(public_exposure.get("target_host") or "").lower() == expected_probe_host
        and public_exposure.get("target_resolved") is True
        and public_exposure.get("resolved_public_address") is True
        and _has_global_address(public_exposure.get("resolved_addresses"))
        and _present(public_exposure.get("error"))
        and public_probe is not None
        and str(public_probe.hostname or "").lower() == expected_probe_host
        and _url_port(public_probe) == api_bind_port
        and public_probe.path == "/api/health"
        and service_plan.get("ok") is True
        and service_plan.get("status") == "ready"
        and service_plan.get("logs_configured") is True
        and service_plan.get("names_configured") is True
        and service_plan.get("api_bind_host_private_or_loopback") is True
        and {
            service_plan.get("static_service_name"),
            service_plan.get("api_service_name"),
            service_plan.get("worker_service_name"),
            service_plan.get("proxy_service_name"),
        }
        == REQUIRED_SERVICE_NAMES
        and windows_services.get("ok") is True
        and windows_services.get("status") == "ready"
        and windows_services.get("verification_requested") is True
        and set(_string_list(windows_services.get("expected_services"))) == REQUIRED_SERVICE_NAMES
        and windows_services.get("missing_services") == []
        and windows_services.get("unhealthy_services") == []
        and len(service_names) == len(REQUIRED_SERVICE_NAMES)
        and set(service_names) == REQUIRED_SERVICE_NAMES
        and services_ready
    )


def _backend_stage_gate_ready(report: dict[str, Any], **_context: Any) -> bool:
    decision = _mapping(report.get("decision"))
    counts = _mapping(report.get("counts"))
    gates = _mapping(report.get("gates"))
    return bool(
        report.get("ok") is True
        and _report_generated_recent(report, _context.get("generated_at"))
        and report.get("time_override_used") is False
        and report.get("status") == "ready"
        and report.get("phase") == "V6.6.63"
        and report.get("mode") == "read_only"
        and report.get("require_mysql") is True
        and decision.get("recommended") == "通过"
        and counts.get("total_gates") == 15
        and counts.get("passed") == 15
        and counts.get("blocked") == 0
        and counts.get("missing_evidence") == 0
        and report.get("blockers") == []
        and report.get("missing_evidence") == []
        and report.get("warnings") == []
        and set(gates) == REQUIRED_STAGE_GATES
        and all(
            isinstance(gate, dict)
            and gate.get("ok") is True
            and gate.get("status") == "passed"
            and gate.get("sensitive_fields_returned") is False
            and gate.get("sensitive_values_returned") is False
            for gate in gates.values()
        )
    )


def _database_restore_ready(report: dict[str, Any], **context: Any) -> bool:
    controls = _mapping(context.get("controls"))
    backup = _mapping(controls.get("backup"))
    integrity = _mapping(report.get("integrity_checks"))
    completed_at = _parse_datetime(report.get("completed_at"))
    expected_completed_at = _parse_datetime(backup.get("restore_completed_at"))
    return bool(
        report.get("ok") is True
        and report.get("status") == "ready"
        and report.get("backup_ref") == backup.get("backup_ref")
        and str(report.get("backup_sha256") or "").lower()
        == str(backup.get("backup_sha256") or "").lower()
        and _SHA256_RE.fullmatch(str(report.get("backup_sha256") or ""))
        and report.get("source_database") == backup.get("source_database")
        and report.get("restore_database") == backup.get("restore_database")
        and report.get("source_database") != report.get("restore_database")
        and report.get("alembic_revision") == EXPECTED_ALEMBIC_REVISION
        and completed_at is not None
        and expected_completed_at is not None
        and completed_at == expected_completed_at
        and all(integrity.get(name) is True for name in ("schema", "row_counts", "audit_chain", "application_smoke"))
    )


def _runtime_rollback_ready(report: dict[str, Any], **context: Any) -> bool:
    controls = _mapping(context.get("controls"))
    rollback = _mapping(controls.get("rollback"))
    release = _mapping(context.get("release"))
    checks = _mapping(report.get("checks"))
    completed_at = _parse_datetime(report.get("completed_at"))
    expected_completed_at = _parse_datetime(rollback.get("drill_completed_at"))
    candidate_revision = str(report.get("candidate_revision") or "").lower()
    rollback_revision = str(report.get("rollback_revision") or "").lower()
    return bool(
        report.get("ok") is True
        and report.get("status") == "ready"
        and candidate_revision == str(release.get("revision") or "").lower()
        and _REVISION_RE.fullmatch(candidate_revision)
        and _REVISION_RE.fullmatch(rollback_revision)
        and rollback_revision != candidate_revision
        and all(report.get(name) == rollback.get(name) for name in ("config_ref", "binary_ref", "database_ref"))
        and len(_string_list(report.get("service_names"))) == len(REQUIRED_SERVICE_NAMES)
        and set(_string_list(report.get("service_names"))) == REQUIRED_SERVICE_NAMES
        and all(
            checks.get(name) is True
            for name in (
                "config_restored",
                "binaries_restored",
                "database_posture_verified",
                "static_smoke",
                "api_smoke",
                "worker_smoke",
                "proxy_smoke",
            )
        )
        and completed_at is not None
        and expected_completed_at is not None
        and completed_at == expected_completed_at
    )


def _target_browser_smoke_ready(report: dict[str, Any], **context: Any) -> bool:
    target = _mapping(context.get("target"))
    release = _mapping(context.get("release"))
    generated_at = context.get("generated_at")
    completed_at = _parse_datetime(report.get("completed_at"))
    browser = _mapping(report.get("browser"))
    checks = _mapping(report.get("checks"))
    return bool(
        report.get("ok") is True
        and report.get("status") == "ready"
        and report.get("public_origin") == target.get("public_origin")
        and str(report.get("release_revision") or "").lower()
        == str(release.get("revision") or "").lower()
        and _present(browser.get("name"))
        and _present(browser.get("version"))
        and len(_string_list(report.get("roles"))) == len(REQUIRED_BROWSER_ROLES)
        and set(_string_list(report.get("roles"))) == REQUIRED_BROWSER_ROLES
        and len(_string_list(report.get("viewports"))) == len(REQUIRED_BROWSER_VIEWPORTS)
        and set(_string_list(report.get("viewports"))) == REQUIRED_BROWSER_VIEWPORTS
        and all(checks.get(name) is True for name in REQUIRED_BROWSER_CHECKS)
        and isinstance(generated_at, datetime)
        and _recent(completed_at, generated_at, max_age=MAX_EVIDENCE_AGE)
    )


def _manifest_context(manifest: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != TARGET_RELEASE_SCHEMA_VERSION:
        raise ValueError("manifest_must_use_target_release_v2")
    target = _mapping(manifest.get("target"))
    environment = str(target.get("environment") or "").strip().lower()
    public_origin, _ = normalize_public_https_origin(target.get("public_origin"))
    instance_id = str(target.get("instance_id") or "").strip()
    if environment not in {"staging", "production"}:
        raise ValueError("manifest_target_environment_invalid")
    if public_origin is None:
        raise ValueError("manifest_target_origin_invalid")
    if not _valid_identifier(instance_id):
        raise ValueError("manifest_target_instance_invalid")
    target = {
        "environment": environment,
        "public_origin": public_origin,
        "instance_id": instance_id,
    }

    release = _mapping(manifest.get("release"))
    version = str(release.get("version") or "").strip()
    revision = str(release.get("revision") or "").strip().lower()
    artifact_sha = str(release.get("artifact_manifest_sha256") or "").strip().lower()
    artifact_path = str(release.get("artifact_manifest_path") or "").strip()
    bundle_id = str(release.get("evidence_bundle_id") or "").strip()
    if (
        not _RELEASE_VERSION_RE.fullmatch(version)
        or not _REVISION_RE.fullmatch(revision)
        or not _SHA256_RE.fullmatch(artifact_sha)
        or not _present(artifact_path)
        or Path(artifact_path).is_absolute()
        or not _valid_identifier(bundle_id)
    ):
        raise ValueError("manifest_release_binding_invalid")
    controls = _mapping(manifest.get("controls"))
    return target, {
        "version": version,
        "revision": revision,
        "artifact_manifest_path": artifact_path,
        "artifact_manifest_sha256": artifact_sha,
        "evidence_bundle_id": bundle_id,
    }, controls


def validate_release_artifact_manifest(root: Path, release: dict[str, Any]) -> tuple[bool, str]:
    relative = str(release.get("artifact_manifest_path") or "").strip()
    expected_sha256 = str(release.get("artifact_manifest_sha256") or "").strip().lower()
    release_version = str(release.get("version") or "").strip()
    release_revision = str(release.get("revision") or "").strip().lower()
    if not _present(relative) or Path(relative).is_absolute() or not _SHA256_RE.fullmatch(expected_sha256):
        return False, "artifact_manifest_path_or_sha256_invalid"
    artifact_path = (root / relative).resolve()
    try:
        artifact_path.relative_to(root.resolve())
    except ValueError:
        return False, "artifact_manifest_path_escapes_bundle"
    try:
        if not artifact_path.is_file() or artifact_path.stat().st_size > MAX_ARTIFACT_MANIFEST_BYTES:
            return False, "artifact_manifest_missing_or_too_large"
        raw = artifact_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            return False, "artifact_manifest_sha256_mismatch"
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        return False, exc.__class__.__name__
    if not isinstance(payload, dict):
        return False, "artifact_manifest_must_be_object"
    if payload.get("schema_version") != ARTIFACT_MANIFEST_SCHEMA_VERSION:
        return False, "artifact_manifest_schema_version_mismatch"
    if payload.get("release_version") != release_version:
        return False, "artifact_manifest_release_version_mismatch"
    if str(payload.get("release_revision") or "").lower() != release_revision:
        return False, "artifact_manifest_release_revision_mismatch"
    if _contains_sensitive_values(payload):
        return False, "artifact_manifest_sensitive_field_detected"
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else []
    if not artifacts or not all(isinstance(item, dict) for item in artifacts):
        return False, "artifact_manifest_artifacts_missing"
    components = [str(item.get("component") or "").strip().lower() for item in artifacts]
    if len(components) != len(set(components)) or not REQUIRED_ARTIFACT_COMPONENTS <= set(components):
        return False, "artifact_manifest_components_missing_or_duplicate"
    for item in artifacts:
        if (
            not _immutable_artifact_reference(item.get("artifact_ref"))
            or not _SHA256_RE.fullmatch(str(item.get("sha256") or "").strip())
            or isinstance(item.get("size_bytes"), bool)
            or not isinstance(item.get("size_bytes"), int)
            or item["size_bytes"] <= 0
        ):
            return False, "artifact_manifest_entry_invalid"
    return True, "ready"


def _contains_sensitive_values(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in {"sensitive_fields_returned", "sensitive_values_returned"} and child is not False:
                return True
            if normalized.endswith("_url_returned") and child is not False:
                return True
            is_reference = normalized.endswith(("_ref", "_reference")) or normalized in {"references", "provider"}
            if (
                is_reference
                and isinstance(child, str)
                and any(part in normalized for part in _SENSITIVE_KEY_PARTS)
                and not _opaque_sensitive_reference(child)
            ):
                return True
            if (
                not is_reference
                and isinstance(child, str)
                and child.strip()
                and any(part in normalized for part in _SENSITIVE_KEY_PARTS)
            ):
                return True
            if _contains_sensitive_values(child):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_sensitive_values(item) for item in value)
    if isinstance(value, str):
        return _credential_url_contains_secret(value)
    return False


def _atomic_write_json(path: Path, payload: dict[str, Any], *, replace: bool) -> bytes:
    if path.exists() and not replace:
        raise ValueError("output_exists_use_--replace")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
        return encoded
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def _reject_alias(output: Path, *inputs: Path) -> None:
    for source in inputs:
        if output == source:
            raise ValueError("output_must_not_alias_input_or_manifest")
        if output.exists() and source.exists():
            try:
                if os.path.samefile(output, source):
                    raise ValueError("output_must_not_alias_input_or_manifest")
            except OSError:
                pass


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _report_generated_recent(report: dict[str, Any], envelope_generated_at: Any) -> bool:
    if not isinstance(envelope_generated_at, datetime):
        return False
    return _recent(_parse_datetime(report.get("generated_at")), envelope_generated_at, max_age=MAX_EVIDENCE_AGE)


def _windows_service_ready(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    account = str(value.get("account") or "").lower().replace(" ", "")
    process_id = value.get("process_id")
    return bool(
        value.get("name") in REQUIRED_SERVICE_NAMES
        and value.get("exists") is True
        and str(value.get("state") or "").lower() == "running"
        and str(value.get("start_mode") or "").lower() in {"auto", "automatic"}
        and account in {"ntauthority\\localservice", "ntauthority\\networkservice"}
        and isinstance(process_id, int)
        and not isinstance(process_id, bool)
        and process_id > 0
        and value.get("running") is True
        and value.get("automatic") is True
        and value.get("process_id_present") is True
        and value.get("minimal_account") is True
        and value.get("ok") is True
    )


def _safe_urlsplit(value: Any) -> Any | None:
    try:
        parsed = urlsplit(str(value or ""))
    except ValueError:
        return None
    return parsed if parsed.scheme and parsed.hostname else None


def _url_port(parsed: Any) -> int:
    try:
        return int(parsed.port or 0)
    except (TypeError, ValueError):
        return 0


def _has_global_address(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    for item in value:
        try:
            if ipaddress.ip_address(str(item).strip().strip("[]")).is_global:
                return True
        except ValueError:
            continue
    return False


def _credential_url_contains_secret(value: str) -> bool:
    for match in re.finditer(r"://([^/@\s]+):([^/@\s]+)@", value):
        username, password = (part.strip().lower() for part in match.groups())
        if username not in {"***", "redacted"} or password not in {"***", "redacted"}:
            return True
    return False


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _present(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and not _placeholder(text)


def _placeholder(value: str) -> bool:
    upper = value.strip().upper()
    return upper.startswith(("REPLACE_", "TODO", "CHANGEME")) or "REPLACE_WITH_" in upper


def _valid_identifier(value: str) -> bool:
    return bool(_IDENTIFIER_RE.fullmatch(value)) and not _placeholder(value)


def _immutable_artifact_reference(value: Any) -> bool:
    reference = str(value or "").strip()
    if not _present(reference) or not 4 <= len(reference) <= 512:
        return False
    if re.search(r"\s|=|://", reference):
        return False
    return any(separator in reference for separator in ("/", ":", "#"))


def _opaque_sensitive_reference(value: Any) -> bool:
    reference = str(value or "").strip()
    lowered = reference.lower()
    if not _present(reference) or not 4 <= len(reference) <= 256:
        return False
    if re.search(r"\s|=|://", reference):
        return False
    if lowered.startswith(
        (
            "sk-",
            "ghp_",
            "github_pat_",
            "bearer-",
            "bearer:",
            "basic:",
            "password:",
            "passwd:",
            "pwd:",
            "token:",
            "secret:",
            "apikey:",
            "api_key:",
        )
    ):
        return False
    return any(separator in reference for separator in ("/", ":", "#"))


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        return _utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _recent(value: datetime | None, now: datetime, *, max_age: timedelta) -> bool:
    return bool(value and _utc(now) - max_age <= value <= _utc(now) + timedelta(minutes=5))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
