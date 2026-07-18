from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import ipaddress
import json
from pathlib import Path
import re
from typing import Any

from scripts.target_release_evidence import (
    ARTIFACT_MANIFEST_SCHEMA_VERSION,
    REQUIRED_EVIDENCE,
    TARGET_RELEASE_SCHEMA_VERSION,
    has_public_dns_syntax,
    is_legacy_ipv4_literal,
    normalize_public_https_origin,
    validate_release_artifact_manifest,
    validate_evidence_envelope,
)

SCHEMA_VERSION = TARGET_RELEASE_SCHEMA_VERSION
MAX_EVIDENCE_BYTES = 10 * 1024 * 1024
REQUIRED_SERVICES = {"static", "api", "worker", "proxy"}
SENSITIVE_KEY_PARTS = (
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
_RELEASE_VERSION_RE = re.compile(r"V\d+\.\d+\.\d+")
_GIT_REVISION_RE = re.compile(r"[0-9a-fA-F]{40}")
_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{5,127}")
_EXAMPLE_DOMAIN_ROOTS = ("example.com", "example.net", "example.org", "example.edu")


def build_target_release_report(
    manifest_path: str | Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    generated_at = _utc(now or datetime.now(UTC))
    source = Path(manifest_path).resolve()
    bundle_root = source.parent
    checks: list[dict[str, Any]] = []

    def check(control: str, ok: bool, reason: str = "ready") -> bool:
        checks.append({"control": control, "ok": bool(ok), "reason": reason if not ok else "ready"})
        return bool(ok)

    try:
        manifest = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        return _report(
            generated_at=generated_at,
            manifest_path=source,
            checks=[{"control": "manifest", "ok": False, "reason": exc.__class__.__name__}],
        )

    if not isinstance(manifest, dict):
        return _report(
            generated_at=generated_at,
            manifest_path=source,
            checks=[{"control": "manifest", "ok": False, "reason": "manifest_must_be_object"}],
        )

    sensitive_paths = _sensitive_manifest_paths(manifest)
    check("manifest_schema", manifest.get("schema_version") == SCHEMA_VERSION, "unsupported_schema_version")
    check("manifest_secret_boundary", not sensitive_paths, "plaintext_secret_field_detected")

    target = _mapping(manifest.get("target"))
    environment = str(target.get("environment") or "").strip().lower()
    raw_public_origin = str(target.get("public_origin") or "").strip()
    normalized_public_origin, origin_reason = normalize_public_https_origin(raw_public_origin)
    origin_ok = normalized_public_origin is not None
    public_origin = normalized_public_origin or raw_public_origin
    approved_at = _parse_datetime(target.get("approved_at"))
    check("target_environment", environment in {"staging", "production"}, "target_must_be_staging_or_production")
    check("target_public_origin", origin_ok, origin_reason)
    target_instance_id = str(target.get("instance_id") or "").strip()
    check(
        "target_instance_id",
        _present(target_instance_id) and bool(_IDENTIFIER_RE.fullmatch(target_instance_id)),
        "target_instance_id_missing_or_invalid",
    )
    check("operations_owner", _present(target.get("operations_owner")), "operations_owner_missing")
    check("change_record", _present(target.get("change_record")), "change_record_missing")
    check(
        "target_approval",
        _recent(approved_at, generated_at, days=30),
        "approval_missing_future_or_older_than_30_days",
    )

    release_source = _mapping(manifest.get("release"))
    release_version = str(release_source.get("version") or "").strip()
    release_revision = str(release_source.get("revision") or "").strip().lower()
    artifact_manifest_sha256 = str(release_source.get("artifact_manifest_sha256") or "").strip().lower()
    artifact_manifest_path = str(release_source.get("artifact_manifest_path") or "").strip()
    evidence_bundle_id = str(release_source.get("evidence_bundle_id") or "").strip()
    check(
        "release_version",
        bool(_RELEASE_VERSION_RE.fullmatch(release_version)),
        "release_version_must_use_Vx_y_z",
    )
    check(
        "release_revision",
        bool(_GIT_REVISION_RE.fullmatch(release_revision)),
        "release_revision_must_be_40_hex_git_commit",
    )
    artifact_manifest_ok, artifact_manifest_reason = validate_release_artifact_manifest(
        bundle_root,
        {
            "version": release_version,
            "revision": release_revision,
            "artifact_manifest_path": artifact_manifest_path,
            "artifact_manifest_sha256": artifact_manifest_sha256,
        },
    )
    check("release_artifact_manifest", artifact_manifest_ok, artifact_manifest_reason)
    check(
        "release_evidence_bundle",
        _present(evidence_bundle_id) and bool(_IDENTIFIER_RE.fullmatch(evidence_bundle_id)),
        "evidence_bundle_id_missing_or_invalid",
    )
    release = {
        "version": release_version,
        "revision": release_revision,
        "artifact_manifest_path": artifact_manifest_path,
        "artifact_manifest_sha256": artifact_manifest_sha256,
        "evidence_bundle_id": evidence_bundle_id,
    }

    controls = _mapping(manifest.get("controls"))
    _validate_tls(_mapping(controls.get("tls")), generated_at, check)
    _validate_network(_mapping(controls.get("network")), check)
    _validate_secrets(_mapping(controls.get("secrets")), check)
    _validate_database(_mapping(controls.get("database")), check)
    _validate_backup(_mapping(controls.get("backup")), generated_at, check)
    _validate_logging(_mapping(controls.get("logging")), check)
    _validate_monitoring(_mapping(controls.get("monitoring")), public_origin, check)
    _validate_rollback(_mapping(controls.get("rollback")), generated_at, check)

    evidence_root = bundle_root
    evidence_items = manifest.get("evidence") if isinstance(manifest.get("evidence"), list) else []
    evidence_by_id = {
        str(item.get("id")): item
        for item in evidence_items
        if isinstance(item, dict) and _present(item.get("id"))
    }
    for evidence_id in REQUIRED_EVIDENCE:
        item = evidence_by_id.get(evidence_id)
        ok, reason = _validate_evidence_item(
            evidence_root,
            item,
            evidence_id=evidence_id,
            target={
                "environment": environment,
                "public_origin": public_origin,
                "instance_id": target_instance_id,
            },
            release=release,
            controls=controls,
            now=generated_at,
        )
        check(f"evidence.{evidence_id}", ok, reason)

    identified_items = [item for item in evidence_items if isinstance(item, dict) and _present(item.get("id"))]
    run_ids = [str(item.get("run_id") or "").strip() for item in identified_items]
    duplicate_ids = len(evidence_by_id) != len(identified_items)
    invalid_or_duplicate_run_ids = (
        len(run_ids) != len(set(run_ids))
        or any(not _present(run_id) or not _IDENTIFIER_RE.fullmatch(run_id) for run_id in run_ids)
    )
    check(
        "evidence_unique_ids",
        len(evidence_items) == len(REQUIRED_EVIDENCE)
        and set(evidence_by_id) == set(REQUIRED_EVIDENCE)
        and len(identified_items) == len(REQUIRED_EVIDENCE)
        and not duplicate_ids
        and not invalid_or_duplicate_run_ids,
        "duplicate_or_invalid_evidence_id_or_run_id",
    )

    return _report(
        generated_at=generated_at,
        manifest_path=source,
        checks=checks,
        target={
            "environment": environment,
            "public_origin": public_origin if origin_ok else None,
            "instance_id": target_instance_id or None,
        },
        release=release,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a target-environment release evidence bundle.")
    parser.add_argument("--manifest", required=True, help="Path to target-release-v2 JSON manifest.")
    parser.add_argument("--now", default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--allow-test-time-override",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    try:
        if args.now is not None or args.allow_test_time_override:
            raise ValueError("cli_time_override_not_supported")
        report = build_target_release_report(args.manifest)
    except Exception as exc:
        report = {
            "ok": False,
            "status": "invalid_argument",
            "error": exc.__class__.__name__,
            "detail": str(exc),
            "sensitive_fields_returned": False,
            "sensitive_values_returned": False,
        }
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


def _validate_tls(tls: dict[str, Any], now: datetime, check: Any) -> None:
    not_after = _parse_datetime(tls.get("not_after"))
    check("tls_certificate_reference", _present(tls.get("certificate_ref")), "certificate_reference_missing")
    check(
        "tls_minimum_protocol",
        tls.get("minimum_protocol") in {"TLSv1.2", "TLSv1.3"},
        "minimum_tls_must_be_1_2_or_newer",
    )
    check("tls_hsts", tls.get("hsts_enabled") is True, "hsts_not_confirmed")
    check(
        "tls_expiry",
        bool(not_after and not_after >= now + timedelta(days=14)),
        "certificate_expires_within_14_days_or_missing",
    )


def _validate_network(network: dict[str, Any], check: Any) -> None:
    public_ports = sorted(_integer_list(network.get("public_ports")))
    inner_ports = _integer_list(network.get("blocked_inner_ports"))
    external_probe_ref = network.get("external_probe_ref")
    public_probe_host = network.get("public_probe_host")
    check("network_public_ports", public_ports == [80, 443], "public_ports_must_be_exactly_80_443")
    check(
        "network_inner_ports",
        bool(inner_ports) and not ({80, 443} & set(inner_ports)),
        "blocked_inner_ports_missing_or_include_public_ports",
    )
    check(
        "network_external_probe",
        _present(external_probe_ref) and _public_probe_host(public_probe_host),
        "external_probe_reference_or_public_probe_host_missing_or_invalid",
    )


def _validate_secrets(secrets: dict[str, Any], check: Any) -> None:
    refs = secrets.get("references") if isinstance(secrets.get("references"), list) else []
    check("secret_store_provider", _present(secrets.get("provider")), "secret_store_provider_missing")
    check(
        "secret_references",
        len(refs) >= 3 and len(set(str(value) for value in refs)) == len(refs) and all(
            _opaque_secret_reference(value) for value in refs
        ),
        "at_least_three_distinct_opaque_secret_references_required",
    )
    check("secret_rotation_owner", _present(secrets.get("rotation_owner")), "secret_rotation_owner_missing")


def _validate_database(database: dict[str, Any], check: Any) -> None:
    check("database_engine", str(database.get("engine") or "").lower() == "mysql", "target_database_must_be_mysql")
    check("database_service_account", _present(database.get("service_account_ref")), "service_account_reference_missing")
    check(
        "database_least_privilege_review",
        _present(database.get("least_privilege_review_ref")),
        "least_privilege_review_reference_missing",
    )


def _validate_backup(backup: dict[str, Any], now: datetime, check: Any) -> None:
    restore_at = _parse_datetime(backup.get("restore_completed_at"))
    source_database = str(backup.get("source_database") or "").strip()
    restore_database = str(backup.get("restore_database") or "").strip()
    check("backup_reference", _present(backup.get("backup_ref")), "backup_reference_missing")
    check("backup_checksum", _sha256_text(backup.get("backup_sha256")), "backup_sha256_invalid")
    check("backup_retention", _integer(backup.get("retention_days")) >= 7, "backup_retention_below_7_days")
    check(
        "backup_independent_restore",
        bool(source_database and restore_database and source_database != restore_database),
        "restore_database_must_differ_from_source",
    )
    check("backup_restore_report", _present(backup.get("restore_report_ref")), "restore_report_reference_missing")
    check(
        "backup_restore_recency",
        _recent(restore_at, now, days=30),
        "restore_evidence_missing_future_or_older_than_30_days",
    )


def _validate_logging(logging: dict[str, Any], check: Any) -> None:
    services = {str(value).strip().lower() for value in logging.get("services", []) if _present(value)} if isinstance(logging.get("services"), list) else set()
    check("log_rotation", logging.get("rotation_enabled") is True, "log_rotation_not_confirmed")
    check("log_retention", _integer(logging.get("retention_days")) >= 7, "log_retention_below_7_days")
    check("log_service_coverage", REQUIRED_SERVICES <= services, "static_api_worker_proxy_logs_required")
    check("log_evidence", _present(logging.get("rotation_test_ref")), "log_rotation_test_reference_missing")


def _validate_monitoring(monitoring: dict[str, Any], public_origin: str, check: Any) -> None:
    health_url = str(monitoring.get("health_url") or "").strip()
    services = {str(value).strip().lower() for value in monitoring.get("service_monitors", []) if _present(value)} if isinstance(monitoring.get("service_monitors"), list) else set()
    expected_health = f"{public_origin}/api/health" if public_origin else ""
    check("monitoring_health", bool(expected_health and health_url == expected_health), "health_url_must_match_public_origin_api_health")
    check("monitoring_service_coverage", REQUIRED_SERVICES <= services, "static_api_worker_proxy_monitors_required")
    check("monitoring_alert_channel", _present(monitoring.get("alert_channel_ref")), "alert_channel_reference_missing")
    check("monitoring_alert_test", _present(monitoring.get("alert_test_ref")), "alert_test_reference_missing")


def _validate_rollback(rollback: dict[str, Any], now: datetime, check: Any) -> None:
    completed_at = _parse_datetime(rollback.get("drill_completed_at"))
    for name in ("config_ref", "binary_ref", "database_ref"):
        check(f"rollback_{name}", _present(rollback.get(name)), f"{name}_missing")
    check(
        "rollback_recency",
        _recent(completed_at, now, days=30),
        "rollback_evidence_missing_future_or_older_than_30_days",
    )


def _validate_evidence_item(
    root: Path,
    item: Any,
    *,
    evidence_id: str,
    target: dict[str, Any],
    release: dict[str, Any],
    controls: dict[str, Any],
    now: datetime,
) -> tuple[bool, str]:
    if not isinstance(item, dict):
        return False, "evidence_entry_missing"
    if "status_path" in item or "expected" in item:
        return False, "evidence_status_override_not_allowed"
    run_id = str(item.get("run_id") or "").strip()
    relative = item.get("path")
    expected_sha = str(item.get("sha256") or "").strip().lower()
    if not _present(relative) or not _sha256_text(expected_sha):
        return False, "evidence_path_or_sha256_invalid"
    evidence_path = (root / str(relative)).resolve()
    try:
        evidence_path.relative_to(root)
    except ValueError:
        return False, "evidence_path_escapes_bundle"
    try:
        if not evidence_path.is_file() or evidence_path.stat().st_size > MAX_EVIDENCE_BYTES:
            return False, "evidence_file_missing_or_too_large"
        raw = evidence_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha:
            return False, "evidence_sha256_mismatch"
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        return False, exc.__class__.__name__
    return validate_evidence_envelope(
        payload,
        evidence_id=evidence_id,
        run_id=run_id,
        target=target,
        release=release,
        controls=controls,
        now=now,
    )


def _report(
    *,
    generated_at: datetime,
    manifest_path: Path,
    checks: list[dict[str, Any]],
    target: dict[str, Any] | None = None,
    release: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blockers = [item for item in checks if not item["ok"]]
    return {
        "ok": not blockers,
        "status": "ready" if not blockers else "blocked",
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "manifest_name": manifest_path.name,
        "target": target or {"environment": None, "public_origin": None, "instance_id": None},
        "release": release or {
            "version": None,
            "revision": None,
            "artifact_manifest_path": None,
            "artifact_manifest_sha256": None,
            "evidence_bundle_id": None,
        },
        "counts": {"total": len(checks), "passed": len(checks) - len(blockers), "blocked": len(blockers)},
        "checks": checks,
        "blockers": blockers,
        "decision": {"recommended": "通过" if not blockers else "延期"},
        "sensitive_fields_returned": False,
        "sensitive_values_returned": False,
    }


def _sensitive_manifest_paths(value: Any, prefix: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            child_path = f"{prefix}.{key}"
            is_reference = normalized.endswith("_ref") or normalized in {"references", "provider"}
            has_sensitive_name = any(part in normalized for part in SENSITIVE_KEY_PARTS)
            if (
                is_reference
                and has_sensitive_name
                and isinstance(child, str)
                and not _opaque_secret_reference(child)
            ):
                found.append(child_path)
            elif not is_reference and normalized != "secrets" and has_sensitive_name:
                found.append(child_path)
            found.extend(_sensitive_manifest_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_sensitive_manifest_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and re.search(r"://[^/@\s]+:[^/@\s]+@", value):
        found.append(prefix)
    return found


def _public_https_origin(value: str) -> tuple[bool, str]:
    normalized, reason = normalize_public_https_origin(value)
    return normalized is not None, reason


def _public_probe_host(value: Any) -> bool:
    host = str(value or "").strip().lower()
    if not _present(host) or re.search(r"\s|/|@", host):
        return False
    if host.startswith("[") or host.endswith("]"):
        if not (host.startswith("[") and host.endswith("]")):
            return False
        if host.count("[") != 1 or host.count("]") != 1:
            return False
        try:
            address = ipaddress.ip_address(host[1:-1])
        except ValueError:
            return False
        return isinstance(address, ipaddress.IPv6Address) and bool(address.is_global)
    if host in {"localhost", "0.0.0.0", "::", "::1"}:
        return False
    try:
        address = ipaddress.ip_address(host)
        return bool(address.is_global)
    except ValueError:
        if is_legacy_ipv4_literal(host):
            return False
    if not has_public_dns_syntax(host) or host.endswith((".example", ".invalid", ".test", ".localhost", ".local", ".internal")):
        return False
    return not any(host == root or host.endswith(f".{root}") for root in _EXAMPLE_DOMAIN_ROOTS)


def _parse_datetime(value: Any) -> datetime | None:
    if not _present(value):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _utc(parsed)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _recent(value: datetime | None, now: datetime, *, days: int) -> bool:
    return bool(value and now - timedelta(days=days) <= value <= now + timedelta(minutes=5))


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _present(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and not text.upper().startswith(("REPLACE_", "TODO", "CHANGEME"))


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _integer_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    return [_integer(item) for item in value if _integer(item) > 0]


def _sha256_text(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", str(value or "").strip()))


def _opaque_secret_reference(value: Any) -> bool:
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


if __name__ == "__main__":
    raise SystemExit(main())
