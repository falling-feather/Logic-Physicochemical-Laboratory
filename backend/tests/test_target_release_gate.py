import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts import target_release_evidence, target_release_gate


NOW = datetime(2026, 7, 16, 16, 0, tzinfo=UTC)
ORIGIN = "https://learn.astra.school"
VERSION = "V7.4.28"
REVISION = "1" * 40
ROLLBACK_REVISION = "2" * 40
INSTANCE_ID = "astra-staging-01"
BUNDLE_ID = "astra-v7428-staging-20260716"
PUBLIC_PROBE_HOST = "edge.astra.school"
ARTIFACT_MANIFEST_PATH = "release-artifacts.json"
ARTIFACT_MANIFEST = {
    "schema_version": target_release_gate.ARTIFACT_MANIFEST_SCHEMA_VERSION,
    "release_version": VERSION,
    "release_revision": REVISION,
    "artifacts": [
        {
            "component": component,
            "artifact_ref": f"artifacts/{component}-v7428.zip",
            "sha256": str(index) * 64,
            "size_bytes": 1024 + index,
        }
        for index, component in enumerate(("static", "api", "worker", "proxy", "migrations"), start=5)
    ],
}
ARTIFACT_MANIFEST_SHA256 = hashlib.sha256(
    json.dumps(ARTIFACT_MANIFEST, ensure_ascii=True, indent=2, sort_keys=True).encode("utf-8")
).hexdigest()


def test_target_release_gate_passes_complete_bound_bundle(tmp_path):
    manifest_path = _write_bundle(tmp_path)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    assert report["ok"] is True
    assert report["status"] == "ready"
    assert report["decision"]["recommended"] == "通过"
    assert report["counts"] == {"total": 51, "passed": 51, "blocked": 0}
    assert report["target"] == {
        "environment": "staging",
        "public_origin": ORIGIN,
        "instance_id": INSTANCE_ID,
    }
    assert report["release"] == {
        "version": VERSION,
        "revision": REVISION,
        "artifact_manifest_path": ARTIFACT_MANIFEST_PATH,
        "artifact_manifest_sha256": ARTIFACT_MANIFEST_SHA256,
        "evidence_bundle_id": BUNDLE_ID,
    }
    assert report["sensitive_fields_returned"] is False
    assert report["sensitive_values_returned"] is False


def test_target_release_gate_rejects_local_origin_and_plaintext_secret(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    manifest["target"]["public_origin"] = "http://127.0.0.1:9012"
    manifest["controls"]["secrets"]["database_url"] = "mysql://user:do-not-return@db/astra"
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert report["ok"] is False
    assert blockers["target_public_origin"] == "public_origin_must_be_https_origin"
    assert blockers["manifest_secret_boundary"] == "plaintext_secret_field_detected"
    serialized = json.dumps(report)
    assert "do-not-return" not in serialized
    assert "mysql://" not in serialized


def test_target_release_gate_rejects_example_origin_even_when_https(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    manifest["target"]["public_origin"] = "https://learn.example.edu"
    manifest["controls"]["monitoring"]["health_url"] = "https://learn.example.edu/api/health"
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["target_public_origin"] == "public_origin_placeholder_domain_not_allowed"


def test_target_release_gate_rejects_evidence_hash_path_and_fixed_semantics(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    manifest["evidence"][0]["sha256"] = "0" * 64
    manifest["evidence"][1]["path"] = "../outside.json"

    topology_path = tmp_path / "evidence" / "deploy-topology.json"
    topology = _read_json(topology_path)
    topology["report"]["public_exposure"] = {
        "ok": True,
        "status": "skipped_no_public_direct_api_url",
        "url": None,
    }
    _write_json(topology_path, topology)
    manifest["evidence"][2]["sha256"] = _sha256(topology_path)
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["evidence.deploy_preflight"] == "evidence_sha256_mismatch"
    assert blockers["evidence.deploy_smoke"] == "evidence_path_escapes_bundle"
    assert blockers["evidence.deploy_topology"] == "deploy_topology_semantics_invalid"


def test_target_release_gate_rejects_manifest_chosen_status_override(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    manifest["evidence"][0]["status_path"] = "anything"
    manifest["evidence"][0]["expected"] = "self-approved"
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["evidence.deploy_preflight"] == "evidence_status_override_not_allowed"


def test_target_release_gate_rejects_cross_target_cross_revision_and_stale_evidence(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    mutations = (
        (0, lambda envelope: envelope["target"].update(environment="production")),
        (1, lambda envelope: envelope["release"].update(revision="3" * 40)),
        (2, lambda envelope: envelope.update(generated_at=(NOW - timedelta(days=8)).isoformat())),
    )
    for index, mutate in mutations:
        evidence_path = tmp_path / manifest["evidence"][index]["path"]
        envelope = _read_json(evidence_path)
        mutate(envelope)
        _write_json(evidence_path, envelope)
        manifest["evidence"][index]["sha256"] = _sha256(evidence_path)
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["evidence.deploy_preflight"] == "evidence_target_mismatch"
    assert blockers["evidence.deploy_smoke"] == "evidence_release_mismatch"
    assert blockers["evidence.deploy_topology"] == "evidence_generated_at_missing_future_or_older_than_7_days"


def test_target_release_gate_rejects_hashed_ok_only_evidence_shell(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    stage_path = tmp_path / "evidence" / "backend-stage-gate.json"
    stage = _read_json(stage_path)
    stage["report"] = {"ok": True, "status": "ready"}
    _write_json(stage_path, stage)
    manifest["evidence"][3]["sha256"] = _sha256(stage_path)
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert (
        blockers["evidence.backend_stage_gate"]
        == "evidence_raw_generated_at_missing_future_or_older_than_7_days"
    )


def test_target_release_gate_rejects_invalid_instance_artifact_bundle_and_duplicate_run(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    manifest["target"]["instance_id"] = "x"
    manifest["release"]["artifact_manifest_sha256"] = "not-a-sha"
    manifest["release"]["evidence_bundle_id"] = "short"
    manifest["evidence"][1]["run_id"] = manifest["evidence"][0]["run_id"]
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["target_instance_id"] == "target_instance_id_missing_or_invalid"
    assert blockers["release_artifact_manifest"] == "artifact_manifest_path_or_sha256_invalid"
    assert blockers["release_evidence_bundle"] == "evidence_bundle_id_missing_or_invalid"
    assert blockers["evidence_unique_ids"] == "duplicate_or_invalid_evidence_id_or_run_id"


def test_target_release_gate_rejects_artifact_inventory_revision_mismatch(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    artifact_path = tmp_path / ARTIFACT_MANIFEST_PATH
    artifact_manifest = _read_json(artifact_path)
    artifact_manifest["release_revision"] = "3" * 40
    _write_json(artifact_path, artifact_manifest)
    manifest["release"]["artifact_manifest_sha256"] = _sha256(artifact_path)
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["release_artifact_manifest"] == "artifact_manifest_release_revision_mismatch"


def test_target_release_gate_rejects_fresh_envelope_around_stale_raw_report(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    preflight_path = tmp_path / "evidence" / "deploy-preflight.json"
    envelope = _read_json(preflight_path)
    envelope["report"]["generated_at"] = (NOW - timedelta(days=8)).isoformat()
    _write_json(preflight_path, envelope)
    manifest["evidence"][0]["sha256"] = _sha256(preflight_path)
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert (
        blockers["evidence.deploy_preflight"]
        == "evidence_raw_generated_at_missing_future_or_older_than_7_days"
    )


def test_target_release_gate_rejects_raw_report_outside_gate_window_even_when_close_to_envelope(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    preflight_path = tmp_path / "evidence" / "deploy-preflight.json"
    envelope = _read_json(preflight_path)
    envelope["generated_at"] = (NOW - timedelta(days=6)).isoformat()
    envelope["report"]["generated_at"] = (NOW - timedelta(days=12)).isoformat()
    _write_json(preflight_path, envelope)
    manifest["evidence"][0]["sha256"] = _sha256(preflight_path)
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert (
        blockers["evidence.deploy_preflight"]
        == "evidence_raw_generated_at_missing_future_or_older_than_7_days"
    )


def test_target_release_gate_rejects_unbound_public_probe_and_name_only_scm_shell(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    topology_path = tmp_path / "evidence" / "deploy-topology.json"
    envelope = _read_json(topology_path)
    topology = envelope["report"]
    unrelated_url = "http://unrelated.astra.school:9011/api/health"
    topology["topology"]["public_direct_api_url"] = unrelated_url
    topology["public_exposure"]["url"] = unrelated_url
    topology["windows_services"]["services"] = [
        {"name": name} for name in ("EngLab", "AstraApi", "AstraWorker", "AstraProxy")
    ]
    _write_json(topology_path, envelope)
    manifest["evidence"][2]["sha256"] = _sha256(topology_path)
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["evidence.deploy_topology"] == "deploy_topology_semantics_invalid"


def test_target_release_gate_rejects_plain_secret_reference_and_sensitive_evidence_body(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    manifest["controls"]["secrets"]["references"][0] = "bearer:live-token"
    restore_path = tmp_path / "evidence" / "database-restore.json"
    restore = _read_json(restore_path)
    restore["report"]["secret"] = "must-not-enter-evidence"
    _write_json(restore_path, restore)
    manifest["evidence"][4]["sha256"] = _sha256(restore_path)
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["secret_references"] == "at_least_three_distinct_opaque_secret_references_required"
    assert blockers["evidence.database_restore"] == "evidence_sensitive_value_detected"
    assert "must-not-enter-evidence" not in json.dumps(report)


def test_target_release_gate_rejects_unknown_plaintext_secret_in_manifest(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    manifest["controls"]["network"]["api_key"] = "must-not-enter-manifest"
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["manifest_secret_boundary"] == "plaintext_secret_field_detected"
    assert "must-not-enter-manifest" not in json.dumps(report)


def test_target_release_gate_rejects_extra_custom_evidence_item(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    manifest["evidence"].append(
        {
            "id": "self_approval",
            "run_id": "self-approval-run-20260716",
            "path": manifest["evidence"][0]["path"],
            "sha256": manifest["evidence"][0]["sha256"],
        }
    )
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["evidence_unique_ids"] == "duplicate_or_invalid_evidence_id_or_run_id"


def test_target_release_gate_rejects_anonymous_extra_evidence_item(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    manifest["evidence"].append(
        {
            "run_id": manifest["evidence"][0]["run_id"],
            "path": manifest["evidence"][0]["path"],
            "sha256": manifest["evidence"][0]["sha256"],
            "status_path": "ok",
            "expected": True,
        }
    )
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["evidence_unique_ids"] == "duplicate_or_invalid_evidence_id_or_run_id"


def test_target_release_gate_requires_browser_archive_and_restore_checks(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    browser_path = tmp_path / "evidence" / "target-browser-smoke.json"
    envelope = _read_json(browser_path)
    envelope["report"]["checks"]["organization_archive"] = False
    envelope["report"]["checks"].pop("organization_restore")
    _write_json(browser_path, envelope)
    manifest["evidence"][6]["sha256"] = _sha256(browser_path)
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["evidence.target_browser_smoke"] == "target_browser_smoke_semantics_invalid"


def test_target_release_gate_rejects_browser_completion_outside_gate_window(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    browser_path = tmp_path / "evidence" / "target-browser-smoke.json"
    envelope = _read_json(browser_path)
    envelope["generated_at"] = (NOW - timedelta(days=6)).isoformat()
    envelope["report"]["completed_at"] = (NOW - timedelta(days=12)).isoformat()
    _write_json(browser_path, envelope)
    manifest["evidence"][6]["sha256"] = _sha256(browser_path)
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert (
        blockers["evidence.target_browser_smoke"]
        == "target_browser_completed_at_missing_future_or_older_than_7_days"
    )


def test_target_release_gate_requires_recent_target_controls(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = _read_json(manifest_path)
    manifest["target"]["approved_at"] = (NOW - timedelta(days=31)).isoformat()
    manifest["controls"]["tls"]["not_after"] = (NOW + timedelta(days=13)).isoformat()
    manifest["controls"]["backup"]["restore_completed_at"] = "not-a-date"
    manifest["controls"]["rollback"]["drill_completed_at"] = (NOW + timedelta(days=1)).isoformat()
    _write_json(manifest_path, manifest)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blocked = {item["control"] for item in report["blockers"]}
    assert {"target_approval", "tls_expiry", "backup_restore_recency", "rollback_recency"} <= blocked


def test_target_release_evidence_cli_seals_valid_report_without_overwriting_input(tmp_path, capsys):
    manifest_path = _write_bundle(tmp_path)
    raw_path = tmp_path / "raw-preflight.json"
    output_path = tmp_path / "sealed-preflight.json"
    raw = _ready_reports(_read_json(manifest_path))["deploy_preflight"]
    raw["generated_at"] = datetime.now(UTC).isoformat()
    _write_json(raw_path, raw)

    exit_code = target_release_evidence.main(
        [
            "seal",
            "--manifest",
            str(manifest_path),
            "--evidence-id",
            "deploy_preflight",
            "--run-id",
            "deploy-preflight-run-20260716",
            "--input",
            str(raw_path),
            "--output",
            str(output_path),
        ]
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert summary["status"] == "sealed"
    assert summary["sha256"] == _sha256(output_path)
    assert _read_json(raw_path) == raw
    sealed = _read_json(output_path)
    assert sealed["evidence_id"] == "deploy_preflight"
    assert sealed["target"] == {
        "environment": "staging",
        "public_origin": ORIGIN,
        "instance_id": INSTANCE_ID,
    }
    assert sealed["release"] == {
        "version": VERSION,
        "revision": REVISION,
        "artifact_manifest_path": ARTIFACT_MANIFEST_PATH,
        "artifact_manifest_sha256": ARTIFACT_MANIFEST_SHA256,
        "evidence_bundle_id": BUNDLE_ID,
    }


def test_target_release_evidence_manual_template_is_fail_closed(tmp_path, capsys):
    output_path = tmp_path / "database-restore-template.json"

    exit_code = target_release_evidence.main(
        ["template", "--evidence-id", "database_restore", "--output", str(output_path)]
    )
    summary = json.loads(capsys.readouterr().out)
    template = _read_json(output_path)

    assert exit_code == 0
    assert summary["template_is_evidence"] is False
    assert template["ok"] is False
    assert template["status"] == "replace_template"
    assert all(value is False for value in template["integrity_checks"].values())


def test_target_release_gate_cli_returns_json_for_invalid_now(tmp_path, capsys):
    exit_code = target_release_gate.main(["--manifest", str(tmp_path / "missing.json"), "--now", "bad-date"])
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert report["status"] == "invalid_argument"
    assert report["sensitive_fields_returned"] is False


def test_target_release_gate_cli_rejects_time_override_even_with_legacy_test_flag(tmp_path, capsys):
    manifest_path = _write_bundle(tmp_path)

    exit_code = target_release_gate.main(
        [
            "--manifest",
            str(manifest_path),
            "--now",
            NOW.isoformat(),
            "--allow-test-time-override",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert report["status"] == "invalid_argument"
    assert report["detail"] == "cli_time_override_not_supported"


def test_target_release_evidence_cli_rejects_time_override_even_with_legacy_test_flag(tmp_path, capsys):
    manifest_path = _write_bundle(tmp_path)
    raw_path = tmp_path / "raw-preflight.json"
    output_path = tmp_path / "sealed-preflight.json"
    _write_json(raw_path, _ready_reports(_read_json(manifest_path))["deploy_preflight"])

    exit_code = target_release_evidence.main(
        [
            "seal",
            "--manifest",
            str(manifest_path),
            "--evidence-id",
            "deploy_preflight",
            "--run-id",
            "deploy-preflight-run-20260716",
            "--input",
            str(raw_path),
            "--output",
            str(output_path),
            "--now",
            NOW.isoformat(),
            "--allow-test-time-override",
        ]
    )
    summary = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert summary["reason"] == "cli_time_override_not_supported"
    assert output_path.exists() is False


def _write_bundle(root: Path) -> Path:
    evidence_dir = root / "evidence"
    evidence_dir.mkdir()
    _write_json(root / ARTIFACT_MANIFEST_PATH, ARTIFACT_MANIFEST)
    manifest = _manifest()
    reports = _ready_reports(manifest)
    evidence = []
    for evidence_id in target_release_gate.REQUIRED_EVIDENCE:
        run_id = f"{evidence_id.replace('_', '-')}-run-20260716"
        evidence_path = evidence_dir / f"{evidence_id.replace('_', '-')}.json"
        envelope = {
            "schema_version": target_release_evidence.EVIDENCE_SCHEMA_VERSION,
            "evidence_id": evidence_id,
            "run_id": run_id,
            "generated_at": (NOW - timedelta(hours=1)).isoformat(),
            "target": {
                "environment": manifest["target"]["environment"],
                "public_origin": manifest["target"]["public_origin"],
                "instance_id": manifest["target"]["instance_id"],
            },
            "release": manifest["release"],
            "report": reports[evidence_id],
        }
        _write_json(evidence_path, envelope)
        evidence.append(
            {
                "id": evidence_id,
                "run_id": run_id,
                "path": str(evidence_path.relative_to(root)).replace("\\", "/"),
                "sha256": _sha256(evidence_path),
            }
        )
    manifest["evidence"] = evidence
    manifest_path = root / "target-release.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def _manifest() -> dict:
    return {
        "schema_version": target_release_gate.SCHEMA_VERSION,
        "target": {
            "environment": "staging",
            "public_origin": ORIGIN,
            "instance_id": INSTANCE_ID,
            "operations_owner": "platform-team",
            "change_record": "CHG-2026-0716",
            "approved_at": (NOW - timedelta(hours=2)).isoformat(),
        },
        "release": {
            "version": VERSION,
            "revision": REVISION,
            "artifact_manifest_path": ARTIFACT_MANIFEST_PATH,
            "artifact_manifest_sha256": ARTIFACT_MANIFEST_SHA256,
            "evidence_bundle_id": BUNDLE_ID,
        },
        "controls": {
            "tls": {
                "certificate_ref": "cert-inventory-42",
                "minimum_protocol": "TLSv1.2",
                "hsts_enabled": True,
                "not_after": (NOW + timedelta(days=90)).isoformat(),
            },
            "network": {
                "public_ports": [443, 80],
                "blocked_inner_ports": [9010, 9011, 9012],
                "public_probe_host": PUBLIC_PROBE_HOST,
                "external_probe_ref": "probe-2026-0716",
            },
            "secrets": {
                "provider": "managed-vault",
                "references": ["db/account", "admin/bootstrap", "audit/salt"],
                "rotation_owner": "security-team",
            },
            "database": {
                "engine": "mysql",
                "service_account_ref": "iam/astra-service",
                "least_privilege_review_ref": "SEC-918",
            },
            "backup": {
                "backup_ref": "object/backup-0716",
                "backup_sha256": "a" * 64,
                "retention_days": 30,
                "source_database": "astra",
                "restore_database": "astra_restore_0716",
                "restore_report_ref": "DBR-2026-0716",
                "restore_completed_at": (NOW - timedelta(hours=4)).isoformat(),
            },
            "logging": {
                "rotation_enabled": True,
                "retention_days": 30,
                "services": ["static", "api", "worker", "proxy"],
                "rotation_test_ref": "LOG-2026-0716",
            },
            "monitoring": {
                "health_url": f"{ORIGIN}/api/health",
                "service_monitors": ["static", "api", "worker", "proxy"],
                "alert_channel_ref": "monitor/channel/astra",
                "alert_test_ref": "ALERT-2026-0716",
            },
            "rollback": {
                "config_ref": "RB-CONFIG-0716",
                "binary_ref": "RB-BINARY-0716",
                "database_ref": "RB-DATABASE-0716",
                "drill_completed_at": (NOW - timedelta(hours=3)).isoformat(),
            },
        },
        "evidence": [],
    }


def _ready_reports(manifest: dict) -> dict[str, dict]:
    report_generated_at = (NOW - timedelta(hours=1)).isoformat()
    preflight = {
        "ok": True,
        "generated_at": report_generated_at,
        "configuration": {
            "ok": True,
            "status": "ready",
            "require_mysql": True,
            "auto_create_tables": False,
            "environment": manifest["target"]["environment"],
        },
        "database": {"ok": True, "status": "connected", "url": "mysql://***:***@db/astra"},
        "migrations": {
            "ok": True,
            "status": "up_to_date",
            "heads": [target_release_evidence.EXPECTED_ALEMBIC_REVISION],
            "current": [target_release_evidence.EXPECTED_ALEMBIC_REVISION],
        },
        "compatibility": {
            "ok": True,
            "status": "ready",
            "dialect": "mysql",
            "require_mysql": True,
            "character_set_database": "utf8mb4",
            "character_set_connection": "utf8mb4",
            "collation_database": "utf8mb4_0900_ai_ci",
            "collation_connection": "utf8mb4_0900_ai_ci",
            "server_version": "8.4.0",
            "database_name": "astra",
            "current_user": "astra_service@10.%",
        },
    }
    topology = {
        "ok": True,
        "generated_at": report_generated_at,
        "target_requirements": {
            "public_port_isolation_required": True,
            "windows_services_requested": True,
        },
        "topology": {
            "ok": True,
            "static_url": f"{ORIGIN}/",
            "proxied_api_url": f"{ORIGIN}/api/health",
            "direct_api_url": "http://127.0.0.1:9011/api/health",
            "public_direct_api_url": f"http://{PUBLIC_PROBE_HOST}:9011/api/health",
            "proxied_api_path_ok": True,
            "static_path_ok": True,
            "direct_api_host_private_or_loopback": True,
            "api_bind_host_private_or_loopback": True,
            "api_bind_port": 9011,
        },
        "static_site": {
            "ok": True,
            "status": "ready",
            "url": f"{ORIGIN}/",
            "status_code": 200,
            "html_detected": True,
        },
        "proxied_api": {
            "ok": True,
            "status": "ready",
            "url": f"{ORIGIN}/api/health",
            "status_code": 200,
            "health_status": "ok",
            "service": "astra-backend",
            "service_ok": True,
            "cache_no_store_ok": True,
            "request_id": "astra-target-run-20260716",
            "request_id_ok": True,
            "cors_origin": ORIGIN,
            "cors_ok": True,
            "database_url_returned": False,
            "database_url_policy_ok": True,
        },
        "direct_api": {
            "ok": True,
            "status": "ready",
            "url": "http://127.0.0.1:9011/api/health",
            "status_code": 200,
            "service": "astra-backend",
            "service_ok": True,
            "cache_no_store_ok": True,
            "request_id": "astra-target-run-20260716",
            "request_id_ok": True,
            "database_url_returned": False,
            "database_url_policy_ok": True,
            "direct_api_host_private_or_loopback": True,
            "api_bind_host_private_or_loopback": True,
        },
        "public_exposure": {
            "ok": True,
            "status": "not_reachable",
            "url": f"http://{PUBLIC_PROBE_HOST}:9011/api/health",
            "required": True,
            "external_probe_ref": "probe-2026-0716",
            "target_host": PUBLIC_PROBE_HOST,
            "target_resolved": True,
            "resolved_public_address": True,
            "resolved_addresses": ["8.8.8.8"],
            "error": "TimeoutError",
        },
        "service_plan": {
            "ok": True,
            "status": "ready",
            "static_service_name": "EngLab",
            "api_service_name": "AstraApi",
            "worker_service_name": "AstraWorker",
            "proxy_service_name": "AstraProxy",
            "logs_configured": True,
            "names_configured": True,
            "api_bind_host_private_or_loopback": True,
        },
        "windows_services": {
            "ok": True,
            "status": "ready",
            "verification_requested": True,
            "expected_services": ["EngLab", "AstraApi", "AstraWorker", "AstraProxy"],
            "services": [
                {
                    "name": name,
                    "exists": True,
                    "state": "Running",
                    "start_mode": "Auto",
                    "account": "NT AUTHORITY\\LocalService",
                    "process_id": 1000 + index,
                    "running": True,
                    "automatic": True,
                    "process_id_present": True,
                    "minimal_account": True,
                    "ok": True,
                }
                for index, name in enumerate(("EngLab", "AstraApi", "AstraWorker", "AstraProxy"))
            ],
            "missing_services": [],
            "unhealthy_services": [],
        },
    }
    backup = manifest["controls"]["backup"]
    rollback = manifest["controls"]["rollback"]
    return {
        "deploy_preflight": preflight,
        "deploy_smoke": {
            "ok": True,
            "generated_at": report_generated_at,
            "preflight": preflight,
            "schema": {
                "ok": True,
                "status": "ready",
                "dialect": "mysql",
                "require_mysql": True,
                "expected_tables": ["alembic_version", "class_groups", "schools"],
                "actual_tables": ["alembic_version", "class_groups", "schools"],
                "checked_column_tables": 2,
                "missing_tables": [],
                "missing_columns": {},
                "datetime_precision_mismatches": {},
                "mysql_expected_datetime_precision": 6,
                "organization_governance_mismatches": {},
                "organization_version_invalid_rows": {"class_groups": 0, "schools": 0},
                "expected_organization_governance_revision": target_release_evidence.EXPECTED_ALEMBIC_REVISION,
            },
            "api": {
                "ok": True,
                "status": "healthy",
                "status_code": 200,
                "health": {"status": "ok", "service": "astra-backend", "database": {"ok": True}},
            },
        },
        "deploy_topology": topology,
        "backend_stage_gate": {
            "ok": True,
            "generated_at": report_generated_at,
            "time_override_used": False,
            "status": "ready",
            "phase": "V6.6.63",
            "mode": "read_only",
            "require_mysql": True,
            "decision": {"recommended": "通过"},
            "counts": {"total_gates": 15, "passed": 15, "blocked": 0, "missing_evidence": 0},
            "gates": {
                name: {
                    "ok": True,
                    "status": "passed",
                    "sensitive_fields_returned": False,
                    "sensitive_values_returned": False,
                }
                for name in target_release_evidence.REQUIRED_STAGE_GATES
            },
            "blockers": [],
            "missing_evidence": [],
            "warnings": [],
            "sensitive_fields_returned": False,
            "sensitive_values_returned": False,
        },
        "database_restore": {
            "ok": True,
            "status": "ready",
            "completed_at": backup["restore_completed_at"],
            "backup_ref": backup["backup_ref"],
            "backup_sha256": backup["backup_sha256"],
            "source_database": backup["source_database"],
            "restore_database": backup["restore_database"],
            "alembic_revision": target_release_evidence.EXPECTED_ALEMBIC_REVISION,
            "integrity_checks": {
                "schema": True,
                "row_counts": True,
                "audit_chain": True,
                "application_smoke": True,
            },
            "sensitive_fields_returned": False,
            "sensitive_values_returned": False,
        },
        "runtime_rollback": {
            "ok": True,
            "status": "ready",
            "completed_at": rollback["drill_completed_at"],
            "candidate_revision": manifest["release"]["revision"],
            "rollback_revision": ROLLBACK_REVISION,
            "config_ref": rollback["config_ref"],
            "binary_ref": rollback["binary_ref"],
            "database_ref": rollback["database_ref"],
            "service_names": ["EngLab", "AstraApi", "AstraWorker", "AstraProxy"],
            "checks": {
                "config_restored": True,
                "binaries_restored": True,
                "database_posture_verified": True,
                "static_smoke": True,
                "api_smoke": True,
                "worker_smoke": True,
                "proxy_smoke": True,
            },
            "sensitive_fields_returned": False,
            "sensitive_values_returned": False,
        },
        "target_browser_smoke": {
            "ok": True,
            "status": "ready",
            "completed_at": (NOW - timedelta(hours=1, minutes=10)).isoformat(),
            "public_origin": ORIGIN,
            "browser": {"name": "Microsoft Edge", "version": "150.0.0"},
            "roles": ["student", "teacher", "admin"],
            "viewports": ["desktop", "390x844"],
            "checks": {name: True for name in target_release_evidence.REQUIRED_BROWSER_CHECKS},
            "sensitive_fields_returned": False,
            "sensitive_values_returned": False,
        },
    }


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_bytes(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True).encode("utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
