import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts import target_release_gate


NOW = datetime(2026, 7, 11, 8, 0, tzinfo=UTC)


def test_target_release_gate_passes_complete_hashed_bundle(tmp_path):
    manifest_path = _write_bundle(tmp_path)

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    assert report["ok"] is True
    assert report["status"] == "ready"
    assert report["decision"]["recommended"] == "通过"
    assert report["counts"]["blocked"] == 0
    assert report["target"] == {
        "environment": "staging",
        "public_origin": "https://learn.example.edu",
    }
    assert report["sensitive_fields_returned"] is False
    assert report["sensitive_values_returned"] is False


def test_target_release_gate_rejects_local_origin_and_plaintext_secret(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["target"]["public_origin"] = "http://127.0.0.1:9012"
    manifest["controls"]["secrets"]["database_url"] = "mysql://user:do-not-return@db/astra"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert report["ok"] is False
    assert blockers["target_public_origin"] == "public_origin_must_be_https_origin"
    assert blockers["manifest_secret_boundary"] == "plaintext_secret_field_detected"
    serialized = json.dumps(report)
    assert "do-not-return" not in serialized
    assert "mysql://" not in serialized


def test_target_release_gate_rejects_evidence_hash_status_and_path_escape(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evidence"][0]["sha256"] = "0" * 64
    manifest["evidence"][1]["path"] = "../outside.json"
    smoke_path = tmp_path / "evidence" / "deploy-topology.json"
    smoke_path.write_text(json.dumps({"ok": False}), encoding="utf-8")
    manifest["evidence"][2]["sha256"] = hashlib.sha256(smoke_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blockers = {item["control"]: item["reason"] for item in report["blockers"]}
    assert blockers["evidence.deploy_preflight"] == "evidence_sha256_mismatch"
    assert blockers["evidence.deploy_smoke"] == "evidence_path_escapes_bundle"
    assert blockers["evidence.deploy_topology"] == "evidence_status_mismatch"


def test_target_release_gate_requires_recent_target_controls(tmp_path):
    manifest_path = _write_bundle(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["target"]["approved_at"] = (NOW - timedelta(days=31)).isoformat()
    manifest["controls"]["tls"]["not_after"] = (NOW + timedelta(days=13)).isoformat()
    manifest["controls"]["backup"]["restore_completed_at"] = "not-a-date"
    manifest["controls"]["rollback"]["drill_completed_at"] = (NOW + timedelta(days=1)).isoformat()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = target_release_gate.build_target_release_report(manifest_path, now=NOW)

    blocked = {item["control"] for item in report["blockers"]}
    assert {"target_approval", "tls_expiry", "backup_restore_recency", "rollback_recency"} <= blocked


def test_target_release_gate_cli_returns_json_for_invalid_now(tmp_path, capsys):
    exit_code = target_release_gate.main(["--manifest", str(tmp_path / "missing.json"), "--now", "bad-date"])
    report = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert report["status"] == "invalid_argument"
    assert report["sensitive_fields_returned"] is False


def _write_bundle(root: Path) -> Path:
    evidence_dir = root / "evidence"
    evidence_dir.mkdir()
    evidence = []
    for evidence_id in target_release_gate.REQUIRED_EVIDENCE:
        evidence_path = evidence_dir / f"{evidence_id.replace('_', '-')}.json"
        evidence_path.write_text(json.dumps({"ok": True, "status": "ready"}), encoding="utf-8")
        evidence.append(
            {
                "id": evidence_id,
                "path": str(evidence_path.relative_to(root)).replace("\\", "/"),
                "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
                "status_path": "ok",
                "expected": True,
            }
        )

    manifest = {
        "schema_version": target_release_gate.SCHEMA_VERSION,
        "target": {
            "environment": "staging",
            "public_origin": "https://learn.example.edu",
            "operations_owner": "platform-team",
            "change_record": "CHG-2026-0711",
            "approved_at": (NOW - timedelta(hours=2)).isoformat(),
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
                "external_probe_ref": "probe-2026-0711",
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
                "backup_ref": "object/backup-0711",
                "backup_sha256": "a" * 64,
                "retention_days": 30,
                "source_database": "astra",
                "restore_database": "astra_restore_0711",
                "restore_report_ref": "DBR-2026-0711",
                "restore_completed_at": (NOW - timedelta(hours=4)).isoformat(),
            },
            "logging": {
                "rotation_enabled": True,
                "retention_days": 30,
                "services": ["static", "api", "worker", "proxy"],
                "rotation_test_ref": "LOG-2026-0711",
            },
            "monitoring": {
                "health_url": "https://learn.example.edu/api/health",
                "service_monitors": ["static", "api", "worker", "proxy"],
                "alert_channel_ref": "monitor/channel/astra",
                "alert_test_ref": "ALERT-2026-0711",
            },
            "rollback": {
                "config_ref": "RB-CONFIG-0711",
                "binary_ref": "RB-BINARY-0711",
                "database_ref": "RB-DATABASE-0711",
                "drill_completed_at": (NOW - timedelta(hours=3)).isoformat(),
            },
        },
        "evidence": evidence,
    }
    manifest_path = root / "target-release.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path
