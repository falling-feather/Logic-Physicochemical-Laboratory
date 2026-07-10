import csv
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AuditLog
from app.services.audit import audit_log_chain_hash
from scripts.archive_audit_logs import main as archive_main
from scripts.archive_audit_logs import run_archive, verify_archive_manifest


@pytest.fixture()
def archive_output_dir():
    root = Path.cwd() / ".tmp-test-audit-archive"
    root.mkdir(exist_ok=True)
    path = root / uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _valid_audit_log(
    *,
    action: str,
    resource: str,
    created_at: datetime,
    prev_hash: str | None = None,
    user_agent: str | None = None,
    snapshot_json: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        action=action,
        resource=resource,
        resource_type="archive_test",
        resource_id=resource.rsplit(":", 1)[-1],
        event_result="success",
        request_id=f"{resource}-request",
        user_agent=user_agent,
        request_method="POST",
        request_path="/api/archive-test",
        prev_hash=prev_hash,
        snapshot_json=snapshot_json or {},
        created_at=created_at,
        updated_at=created_at,
    )
    log.current_hash = audit_log_chain_hash(log)
    return log


def test_audit_archive_writes_manifest_and_verifies_without_deleting(client, archive_output_dir):
    now = datetime.now(UTC)
    first_created_at = now - timedelta(days=60)
    second_created_at = now - timedelta(days=45)
    retained_created_at = now - timedelta(days=5)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        first = _valid_audit_log(
            action="archive.audit",
            resource="archive:first",
            created_at=first_created_at,
            snapshot_json={"secret": "not-exported"},
        )
        second = _valid_audit_log(
            action="archive.audit",
            resource="archive:second",
            created_at=second_created_at,
            prev_hash=first.current_hash,
            user_agent="=formula-risk",
            snapshot_json={"secret": "also-not-exported"},
        )
        retained = _valid_audit_log(
            action="archive.audit",
            resource="archive:retained",
            created_at=retained_created_at,
            prev_hash=second.current_hash,
        )
        db.add_all([first, second, retained])
        db.commit()
        first_id = first.id
        second_id = second.id

    report = run_archive(
        output_dir=archive_output_dir,
        archive_format="jsonl",
        before_at=now - timedelta(days=30),
        action="archive.audit",
        include_snapshot=False,
        exported_by="audit-operator-test",
    )

    assert report["ok"] is True
    assert report["status"] == "written"
    manifest = report["manifest"]
    assert manifest["format"] == "jsonl"
    assert manifest["filters"] == {"action": "archive.audit"}
    assert manifest["total_candidates"] == 2
    assert manifest["exported_count"] == 2
    assert manifest["truncated"] is False
    assert manifest["first_id"] == first_id
    assert manifest["last_id"] == second_id
    assert manifest["chain_start_current_hash"]
    assert manifest["chain_end_current_hash"]
    assert manifest["hash_chain"]["status"] == "valid"
    assert manifest["capabilities"] == {
        "delete": False,
        "purge": False,
        "worm": False,
        "external_anchor": True,
    }
    assert manifest["schema_version"] == 2
    assert manifest["schema"] == "astra.audit-archive-manifest.v2"
    assert manifest["exporter"]["version"] == "V6.6.56"
    assert manifest["exporter"]["exported_at"] == manifest["generated_at"]
    assert manifest["exporter"]["operator"] == "audit-operator-test"
    assert manifest["exporter"]["operator_attributed"] is True
    assert manifest["range"]["first_log_id"] == first_id
    assert manifest["range"]["last_log_id"] == second_id
    assert manifest["external_anchor"]["scheme"] == "https_hash_receipt"
    assert manifest["lifecycle_policy"]["source_deletion"] == "prohibited_not_implemented"
    assert manifest["lifecycle_policy"]["anchored_bytes_mutable"] is False

    archive_path = archive_output_dir / manifest["archive_file"]
    manifest_path = archive_output_dir / manifest["manifest_file"]
    records = [json.loads(line) for line in archive_path.read_text(encoding="utf-8").splitlines()]
    assert [record["id"] for record in records] == [first_id, second_id]
    assert records[0]["snapshot_json"] is None
    assert records[1]["snapshot_json"] is None

    verified = verify_archive_manifest(manifest_path)
    assert verified["ok"] is True
    assert verified["status"] == "verified"
    assert len(verified["manifest_sha256"]) == 64
    assert verified["exported_count"] == 2
    assert verified["archive_chain"]["status"] == "partial"
    assert verified["archive_chain"]["current_hash_recomputed"] is False
    assert verified["archive_chain"]["current_hash_recompute_reason"] == "snapshot_json_not_exported"
    assert verified["archive_chain"]["prev_hash_mismatch_count"] == 0

    with session_factory() as db:
        assert db.get(AuditLog, first_id) is not None
        assert db.get(AuditLog, second_id) is not None
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "archive.audit")) == 3


def test_audit_archive_verify_recomputes_jsonl_hash_with_snapshot(client, archive_output_dir):
    now = datetime.now(UTC)
    created_at = now - timedelta(days=75)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        log = _valid_audit_log(
            action="archive.recompute",
            resource="archive:recompute",
            created_at=created_at,
            snapshot_json={"kept": "for-hash-proof"},
        )
        db.add(log)
        db.commit()

    report = run_archive(
        output_dir=archive_output_dir,
        archive_format="jsonl",
        before_at=now - timedelta(days=30),
        action="archive.recompute",
        include_snapshot=True,
    )
    manifest_path = archive_output_dir / report["manifest"]["manifest_file"]

    verified = verify_archive_manifest(manifest_path)

    assert verified["ok"] is True
    assert verified["status"] == "verified"
    assert verified["archive_chain"]["status"] == "valid"
    assert verified["archive_chain"]["valid"] is True
    assert verified["archive_chain"]["current_hash_recomputed"] is True
    assert verified["archive_chain"]["current_hash_mismatch_count"] == 0
    assert verified["archive_chain"]["prev_hash_mismatch_count"] == 0

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["first_id"] = int(manifest["first_id"]) + 1
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    mismatched = verify_archive_manifest(manifest_path)
    assert mismatched["ok"] is False
    assert mismatched["reason"] == "manifest_summary_mismatch"
    assert mismatched["mismatched_fields"] == ["first_id"]


def test_audit_archive_verify_detects_internal_chain_tamper_after_rehash(client, archive_output_dir):
    now = datetime.now(UTC)
    first_created_at = now - timedelta(days=80)
    second_created_at = now - timedelta(days=70)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        first = _valid_audit_log(
            action="archive.chain_tamper",
            resource="archive:chain-first",
            created_at=first_created_at,
        )
        second = _valid_audit_log(
            action="archive.chain_tamper",
            resource="archive:chain-second",
            created_at=second_created_at,
            prev_hash=first.current_hash,
        )
        db.add_all([first, second])
        db.commit()

    report = run_archive(
        output_dir=archive_output_dir,
        archive_format="jsonl",
        before_at=now - timedelta(days=30),
        action="archive.chain_tamper",
        include_snapshot=False,
    )
    manifest_path = archive_output_dir / report["manifest"]["manifest_file"]
    archive_path = archive_output_dir / report["manifest"]["archive_file"]

    records = [json.loads(line) for line in archive_path.read_text(encoding="utf-8").splitlines()]
    records[1]["prev_hash"] = "manually-broken-prev-hash"
    archive_path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["archive_sha256"] = _sha256_file_for_test(archive_path)
    manifest["archive_bytes"] = archive_path.stat().st_size
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    verified = verify_archive_manifest(manifest_path)

    assert verified["ok"] is False
    assert verified["reason"] == "archive_chain_invalid"
    assert verified["archive_chain"]["status"] == "invalid"
    assert verified["archive_chain"]["prev_hash_mismatch_count"] == 1
    assert verified["archive_chain"]["current_hash_recomputed"] is False


def test_audit_archive_csv_snapshot_and_tamper_detection(client, archive_output_dir):
    now = datetime.now(UTC)
    created_at = now - timedelta(days=90)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        log = _valid_audit_log(
            action="archive.csv",
            resource="archive:csv",
            created_at=created_at,
            user_agent="@csv-risk",
            snapshot_json={"kept": "when-explicit"},
        )
        db.add(log)
        db.commit()

    report = run_archive(
        output_dir=archive_output_dir,
        archive_format="csv",
        before_at=now - timedelta(days=30),
        action="archive.csv",
        include_snapshot=True,
    )
    manifest = report["manifest"]
    archive_path = archive_output_dir / manifest["archive_file"]
    manifest_path = archive_output_dir / manifest["manifest_file"]
    with archive_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["user_agent"] == "'@csv-risk"
    assert rows[0]["snapshot_json"] == '{"kept":"when-explicit"}'
    assert verify_archive_manifest(manifest_path)["ok"] is True

    archive_path.write_text(archive_path.read_text(encoding="utf-8") + "# tampered\n", encoding="utf-8")
    tampered = verify_archive_manifest(manifest_path)
    assert tampered["ok"] is False
    assert tampered["reason"] == "archive_sha256_mismatch"
    assert archive_main(["--verify", str(manifest_path)]) == 1


def test_audit_archive_dry_run_and_parameter_validation(client, archive_output_dir):
    now = datetime.now(UTC)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        legacy = AuditLog(
            action="archive.legacy",
            resource="archive:legacy",
            resource_type="archive_test",
            event_result="success",
            snapshot_json={},
            created_at=now - timedelta(days=400),
            updated_at=now - timedelta(days=400),
        )
        db.add(legacy)
        db.commit()

    report = run_archive(
        output_dir=archive_output_dir,
        archive_format="jsonl",
        retention_days=365,
        action="archive.legacy",
        dry_run=True,
    )
    assert report["ok"] is True
    assert report["status"] == "dry_run"
    assert report["manifest"]["policy"]["source"] == "query"
    assert report["manifest"]["hash_chain"]["status"] == "partial"
    assert list(archive_output_dir.iterdir()) == []

    assert archive_main(["--before", now.isoformat(), "--retention-days", "365", "--dry-run"]) == 1
    assert (
        archive_main(
            [
                "--before",
                now.isoformat(),
                "--from",
                now.isoformat(),
                "--to",
                (now - timedelta(days=1)).isoformat(),
                "--dry-run",
            ]
        )
        == 1
    )


def _sha256_file_for_test(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
