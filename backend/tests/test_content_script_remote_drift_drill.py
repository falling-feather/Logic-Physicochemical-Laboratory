import base64
from datetime import UTC, datetime, timedelta
import hashlib
import json

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import (
    AdminAlertOutboxEntry,
    ContentPageRecord,
    ContentPageVersion,
    ContentScriptAsset,
    ContentScriptAssetScanRun,
    ContentScriptHostPolicy,
    User,
)
from app.schemas.content import ContentPage
from app.services.content_script_assets import external_script_references
from app.services.content_script_policy import collect_content_script_manifests
from app.services.content_script_remote_drift_drill import run_content_script_remote_drift_drill
from scripts.content_script_remote_drift_drill import main, run_content_script_remote_drift_drill_report


def test_content_script_remote_drift_drill_reports_ready_observe_only_posture(client):
    now = datetime(2026, 7, 8, 18, 0, tzinfo=UTC)
    with get_session_factory(get_settings().database_url)() as db:
        db.add(
            ContentScriptAssetScanRun(
                run_key="content-script-remote-drift:script:ready",
                scan_type="remote_drift",
                trigger_source="script",
                status="success",
                started_at=now - timedelta(minutes=5),
                finished_at=now - timedelta(minutes=4),
                attempt_count=1,
                filters_json={
                    "source_host": "cdn-ready.example.test",
                    "limit": 1,
                    "offset": 0,
                    "confirm_external_network": True,
                },
                totals_json={
                    "total_pages_scanned": 1,
                    "total_external_references": 1,
                    "total_scanned_references": 1,
                    "total_remote_fetches": 1,
                    "total_skipped_references": 0,
                    "total_issues": 0,
                    "issue_summary_count": 0,
                },
                issue_counts_json={"by_code": {}, "by_severity": {}},
                issue_summary_json=[],
                alert_status="ok",
            )
        )
        db.commit()

        report = run_content_script_remote_drift_drill(
            db,
            database_url=get_settings().database_url,
            settings=get_settings(),
            source_host="cdn-ready.example.test",
            generated_at=now,
        )

    assert report["ok"] is True
    assert report["mode"] == "read_only"
    assert report["scan_runs"]["counts"]["runs_scanned"] == 1
    assert report["external_observation_evidence"]["status"] == "external_evidence_required"
    assert report["outbox"]["policy"]["external_delivery"] is False
    assert report["sensitive_fields_returned"] is False
    rendered = json.dumps(report, ensure_ascii=False)
    assert '"source_url"' not in rendered
    assert "integrity" not in rendered
    assert "content_bytes" not in rendered
    assert "scheduler_lease_token" not in rendered


def test_content_script_remote_drift_drill_require_mysql_rejects_sqlite_and_disabled_scheduler(client):
    report = run_content_script_remote_drift_drill_report(
        database_url=get_settings().database_url,
        require_mysql=True,
        expect_scheduler_enabled=True,
    )

    assert report["ok"] is False
    assert report["database"]["status"] == "mysql_required"
    assert report["configuration"]["issue_counts_by_code"] == {
        "remote_drift_scheduler_disabled_when_expected": 1
    }


def test_content_script_remote_drift_drill_reports_host_policy_buckets(client, monkeypatch):
    monkeypatch.setenv("ASTRA_CONTENT_SCRIPT_ALLOWED_HOSTS", "cdn-allowed.example.test,cdn-conflict.example.test")
    get_settings.cache_clear()
    now = datetime(2026, 7, 8, 19, 0, tzinfo=UTC)
    with get_session_factory(get_settings().database_url)() as db:
        admin = _insert_user(db, "remote_drift_policy_admin")
        for host in [
            "cdn-unreviewed.example.test",
            "cdn-watch.example.test",
            "cdn-blocked.example.test",
            "cdn-conflict.example.test",
        ]:
            _insert_published_script_asset(
                db,
                slug=f"physics/{host.split('.')[0]}",
                source_url=f"https://{host}/asset.js",
                payload=b"console.log('policy bucket');\n",
                publisher_user_id=admin.id,
                published_at=now,
            )
        db.add_all(
            [
                ContentScriptHostPolicy(
                    source_host="cdn-trusted.example.test",
                    status="trusted",
                    reason="trusted but not in env allowlist",
                    reviewed_by_user_id=admin.id,
                    reviewed_at=now,
                ),
                ContentScriptHostPolicy(
                    source_host="cdn-watch.example.test",
                    status="watch",
                    reason="watch sample",
                    reviewed_by_user_id=admin.id,
                    reviewed_at=now,
                ),
                ContentScriptHostPolicy(
                    source_host="cdn-blocked.example.test",
                    status="blocked",
                    reason="blocked sample",
                    reviewed_by_user_id=admin.id,
                    reviewed_at=now,
                ),
                ContentScriptHostPolicy(
                    source_host="cdn-conflict.example.test",
                    status="blocked",
                    reason="blocked but still configured",
                    reviewed_by_user_id=admin.id,
                    reviewed_at=now,
                ),
            ]
        )
        db.commit()

        report = run_content_script_remote_drift_drill(
            db,
            database_url=get_settings().database_url,
            settings=get_settings(),
            generated_at=now,
        )

    assert report["ok"] is False
    assert report["host_policies"]["counts"]["trusted"] == 1
    assert report["host_policies"]["counts"]["watch"] == 1
    assert report["host_policies"]["counts"]["blocked"] == 2
    assert report["host_policies"]["counts"]["unreviewed"] >= 2
    codes = report["host_policies"]["issue_counts_by_code"]
    assert codes["observed_host_unreviewed"] >= 1
    assert codes["observed_host_on_watch"] == 1
    assert codes["blocked_host_has_published_assets"] == 2
    assert codes["blocked_host_still_configured_allowed"] == 1
    assert codes["trusted_host_not_in_allowed_config"] == 1


def test_content_script_remote_drift_drill_detects_bad_runs_and_outbox_without_leaks(client):
    now = datetime(2026, 7, 8, 20, 0, tzinfo=UTC)
    with get_session_factory(get_settings().database_url)() as db:
        db.add_all(
            [
                ContentScriptAssetScanRun(
                    run_key="content-script-remote-drift:manual:critical",
                    scan_type="remote_drift",
                    trigger_source="manual",
                    status="success",
                    started_at=now - timedelta(hours=2),
                    finished_at=now - timedelta(hours=1, minutes=55),
                    attempt_count=1,
                    filters_json={
                        "source_host": "cdn-secret.example.test",
                        "limit": 5,
                        "offset": 0,
                        "confirm_external_network": True,
                    },
                    totals_json={"total_issues": 1, "issue_summary_count": 1},
                    issue_counts_json={
                        "by_code": {"remote_hash_mismatch": 1},
                        "by_severity": {"critical": 1},
                    },
                    issue_summary_json=[
                        {
                            "code": "remote_hash_mismatch",
                            "severity": "critical",
                            "message": "raw https://cdn-secret.example.test/secret-token.js changed",
                            "slug": "physics/secret",
                            "source_host": "cdn-secret.example.test",
                            "source_url_sha256": "a" * 64,
                            "asset_sha256": "b" * 64,
                            "remote_asset_sha256": "c" * 64,
                            "remote_asset_size_bytes": 12,
                        }
                    ],
                    alert_status="critical",
                ),
                ContentScriptAssetScanRun(
                    run_key="content-script-remote-drift:scheduler:failed",
                    scan_type="remote_drift",
                    trigger_source="scheduler",
                    status="failed",
                    started_at=now - timedelta(hours=3),
                    finished_at=now - timedelta(hours=2, minutes=58),
                    attempt_count=2,
                    filters_json={"source_host": "cdn-secret.example.test"},
                    totals_json={},
                    issue_counts_json={"by_code": {}, "by_severity": {}},
                    issue_summary_json=[],
                    alert_status="critical",
                    error_message="RuntimeError secret exception body",
                ),
                ContentScriptAssetScanRun(
                    run_key="content-script-remote-drift:scheduler:stale",
                    scan_type="remote_drift",
                    trigger_source="scheduler",
                    status="running",
                    started_at=now - timedelta(hours=4),
                    finished_at=None,
                    attempt_count=1,
                    scheduler_lease_owner="worker-secret-owner",
                    scheduler_lease_token="secret-scheduler-lease-token",
                    scheduler_lease_expires_at=now - timedelta(hours=1),
                    scheduler_heartbeat_at=now - timedelta(hours=2),
                    filters_json={"source_host": "cdn-secret.example.test"},
                    totals_json={},
                    issue_counts_json={"by_code": {}, "by_severity": {}},
                    issue_summary_json=[],
                    alert_status="ok",
                ),
            ]
        )
        db.add(
            AdminAlertOutboxEntry(
                source_type="content_script_asset_scan_run_alert",
                source_id=1,
                source_key="content-script-remote-drift:manual:critical",
                event_code="remote_hash_mismatch",
                severity="critical",
                action_hint="review_host",
                status="queued",
                dispatch_mode="manual_review",
                delivery_target="admin_outbox",
                external_delivery=True,
                dedupe_key="remote-drift-secret-outbox",
                payload_hash="d" * 64,
                payload_json={"raw": "https://cdn-secret.example.test/secret-token.js"},
                first_seen_at=now,
                last_seen_at=now,
                available_at=now,
            )
        )
        db.commit()

        report = run_content_script_remote_drift_drill(
            db,
            database_url=get_settings().database_url,
            settings=get_settings(),
            source_host="cdn-secret.example.test",
            generated_at=now,
        )

    assert report["ok"] is False
    assert report["scan_runs"]["issue_counts_by_code"]["critical_remote_drift_issue_run"] == 2
    assert report["scan_runs"]["issue_counts_by_code"]["failed_scan_run_requires_review"] == 1
    assert report["alerts"]["issue_counts_by_code"]["critical_remote_drift_alert_candidates"] == 1
    assert report["outbox"]["issue_counts_by_code"]["outbox_external_delivery_enabled"] == 1
    rendered = json.dumps(report, ensure_ascii=False)
    assert "secret-scheduler-lease-token" not in rendered
    assert "worker-secret-owner" not in rendered
    assert "secret exception body" not in rendered
    assert "secret-token.js" not in rendered
    assert '"source_url"' not in rendered
    assert "integrity" not in rendered
    assert "content_bytes" not in rendered
    assert "payload_json" not in rendered
    assert "scheduler_lease_token" not in rendered


def test_blocked_content_script_host_policy_disables_render_embed_and_runtime_assets(client):
    now = datetime(2026, 7, 8, 21, 0, tzinfo=UTC)
    slug = "physics/blocked-runtime-host"
    source_url = "https://cdn-blocked-runtime.example.test/secret-runtime-token.js"
    payload = b"console.log('blocked runtime host');\n"
    with get_session_factory(get_settings().database_url)() as db:
        admin = _insert_user(db, "blocked_runtime_admin")
        schema, _page, _version, _asset = _insert_published_script_asset(
            db,
            slug=slug,
            source_url=source_url,
            payload=payload,
            publisher_user_id=admin.id,
            published_at=now,
        )
        db.add(
            ContentScriptHostPolicy(
                source_host="cdn-blocked-runtime.example.test",
                status="blocked",
                reason="runtime block",
                reviewed_by_user_id=admin.id,
                reviewed_at=now,
            )
        )
        db.commit()

    manifest = collect_content_script_manifests(ContentPage.model_validate(schema), include_private_values=True)[0]
    sandbox_id = manifest["sandboxId"]
    reference_sha = manifest["references"][0]["valueSha256"]

    render = client.get(f"/api/render/page/{slug}")
    assert render.status_code == 200
    render_text = json.dumps(render.json(), ensure_ascii=False)
    assert '"embed"' not in render_text
    assert "secret-runtime-token" not in render_text

    sandbox = client.get(f"/api/render/script-sandboxes/{sandbox_id}/page/{slug}")
    assert sandbox.status_code == 409
    assert sandbox.json()["detail"]["code"] == "content_script_host_blocked"

    bootstrap = client.get(f"/api/render/script-sandboxes/{sandbox_id}/bootstrap/page/{slug}")
    assert bootstrap.status_code == 409
    assert bootstrap.json()["detail"]["code"] == "content_script_host_blocked"

    asset = client.get(f"/api/render/script-sandboxes/{sandbox_id}/assets/{reference_sha}/page/{slug}")
    assert asset.status_code == 409
    assert asset.json()["detail"]["code"] == "content_script_host_blocked"


def test_content_script_remote_drift_drill_cli_returns_json_for_invalid_now(capsys):
    exit_code = main(["--now", "not-a-date"])

    assert exit_code == 1
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is False
    assert body["status"] == "invalid_argument"
    assert body["error"] == "InvalidNowTimestamp"


def _insert_user(db, username: str) -> User:
    user = User(
        username=username,
        normalized_username=username,
        display_name=username.replace("_", " ").title(),
        password_hash="test",
        role="admin",
        status="active",
    )
    db.add(user)
    db.flush()
    return user


def _insert_published_script_asset(
    db,
    *,
    slug: str,
    source_url: str,
    payload: bytes,
    publisher_user_id: int,
    published_at: datetime,
) -> tuple[dict, ContentPageRecord, ContentPageVersion, ContentScriptAsset]:
    schema = _script_asset_schema(slug, source_url, _sri_sha384(payload))
    schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True).encode("utf-8")).hexdigest()
    page = ContentPageRecord(
        slug=slug,
        status="published",
        version="v-test",
        schema_json=schema,
        schema_hash=schema_hash,
        published_by_user_id=publisher_user_id,
        published_at=published_at,
    )
    db.add(page)
    db.flush()
    version = ContentPageVersion(
        page_id=page.id,
        slug=slug,
        status="published",
        version="v-test",
        schema_hash=schema_hash,
        schema_json=schema,
        published_by_user_id=publisher_user_id,
        published_at=published_at,
        note="remote drift drill fixture",
    )
    db.add(version)
    db.flush()
    page.current_version_id = version.id
    reference = external_script_references(schema)[0]
    asset = ContentScriptAsset(
        page_id=page.id,
        page_version_id=version.id,
        slug=slug,
        sandbox_id=reference.sandbox_id,
        reference_key=reference.reference_key,
        reference_value_sha256=reference.reference_value_sha256,
        source_url=reference.source_url,
        source_host=reference.source_host,
        integrity=reference.integrity,
        matched_algorithm="sha384",
        asset_sha256=hashlib.sha256(payload).hexdigest(),
        asset_size_bytes=len(payload),
        content_bytes=payload,
        policy_version="v6.6.42",
        policy_context_hash="e" * 64,
        published_by_user_id=publisher_user_id,
        published_at=published_at,
    )
    db.add(asset)
    return schema, page, version, asset


def _script_asset_schema(slug: str, source_url: str, integrity: str) -> dict:
    return {
        "slug": slug,
        "galaxy": "englab",
        "subject": "physics",
        "title": "Remote Drift Drill",
        "summary": "Remote drift drill fixture",
        "layout": "experiment-page",
        "status": "published",
        "version": "v-test",
        "sections": [
            {
                "sectionId": f"{slug.rsplit('/', 1)[-1]}-section",
                "type": "experiment",
                "title": "Remote Drift Drill",
                "props": {
                    "scriptUrl": source_url,
                    "scriptIntegrity": integrity,
                    "scriptCrossorigin": "anonymous",
                    "scriptSandbox": {
                        "mode": "isolated-iframe",
                        "network": "same-origin",
                    },
                },
            }
        ],
        "sources": [],
    }


def _sri_sha384(payload: bytes) -> str:
    digest = hashlib.sha384(payload).digest()
    return "sha384-" + base64.b64encode(digest).decode("ascii").rstrip("=")
