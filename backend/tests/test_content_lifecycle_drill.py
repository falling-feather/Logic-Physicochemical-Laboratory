import json

from app.db.session import get_session_factory, init_db, reset_database_state
from app.models import ContentDraft, ContentPageRecord, ContentPageVersion, User
from app.models.base import utc_now
from app.services.content_lifecycle_drill import run_content_lifecycle_drill
from scripts.content_lifecycle_drill import run_content_lifecycle_drill_report


def test_content_lifecycle_drill_reports_ready_read_only_posture():
    database_url = _database_url()
    _create_ready_content_page(database_url, slug="physics/lifecycle-ready")

    session_factory = get_session_factory(database_url)
    with session_factory() as db:
        report = run_content_lifecycle_drill(
            db,
            database_url=database_url,
            api_cache_control="no-store",
            render_url="https://astra.example/api/render/page/physics/lifecycle-ready",
            static_url="https://astra.example/physics/energy-conservation",
            request_id="content-drill-1",
            fetcher=_FakeFetcher(
                {
                    "https://astra.example/api/render/page/physics/lifecycle-ready": _response(
                        200,
                        {
                            "content-type": "application/json",
                            "cache-control": "no-store",
                            "x-request-id": "content-drill-1",
                        },
                        {"slug": "physics/lifecycle-ready", "version": "v1"},
                    ),
                    "https://astra.example/physics/energy-conservation": _response(
                        200,
                        {"content-type": "text/html; charset=utf-8"},
                        "<!doctype html><html><body>Energy</body></html>",
                    ),
                }
            ),
        )

    assert report["ok"] is True
    assert report["status"] == "ready_for_mysql_evidence"
    assert report["mode"] == "read_only"
    assert report["database"]["dialect"] == "sqlite"
    assert report["current_versions"]["ok"] is True
    assert report["version_lineage"]["counts"]["total_versions"] == 1
    assert report["script_mirrors"]["counts"]["total_external_references"] == 0
    assert report["api_cache_policy"]["render_page_inherits_api_no_store"] is True
    assert report["render_api"]["cache_no_store_ok"] is True
    assert report["static_fallback"]["html_detected"] is True
    assert report["mysql_concurrency_evidence"]["status"] == "external_evidence_required"
    assert report["sensitive_fields_returned"] is False
    report_text = json.dumps(report, ensure_ascii=False)
    assert "content_bytes" not in report_text
    assert "integrity" not in report_text
    assert "schema_json" not in report_text


def test_content_lifecycle_drill_require_mysql_rejects_sqlite():
    database_url = _database_url()
    _init_database(database_url)

    report = run_content_lifecycle_drill_report(database_url=database_url, require_mysql=True)

    assert report["ok"] is False
    assert report["database"]["status"] == "mysql_required"
    assert report["database"]["safe_database_url"].startswith("sqlite+pysqlite:///")


def test_content_lifecycle_drill_detects_lifecycle_drift():
    database_url = _database_url()
    admin_id, page_id, version_id = _create_ready_content_page(database_url, slug="physics/lifecycle-drift")
    session_factory = get_session_factory(database_url)
    with session_factory() as db:
        page = db.get(ContentPageRecord, page_id)
        assert page is not None
        page.schema_hash = "0" * 64
        db.add(
            ContentDraft(
                author_user_id=admin_id,
                target_slug=page.slug,
                title="Closed draft with active key",
                status="published",
                active_key="active",
                schema_json=_content_schema(page.slug, title="Closed Draft"),
                schema_hash="1" * 64,
                base_version_id=version_id,
                base_schema_hash="2" * 64,
                allow_script=False,
                script_risk_level="none",
                script_review_status="not_required",
            )
        )
        db.commit()

    with session_factory() as db:
        report = run_content_lifecycle_drill(
            db,
            database_url=database_url,
            api_cache_control="max-age=600",
        )

    assert report["ok"] is False
    assert report["current_versions"]["ok"] is False
    assert "current_schema_hash_mismatch" in report["current_versions"]["issue_counts_by_code"]
    assert "page_schema_hash_mismatch" in report["current_versions"]["issue_counts_by_code"]
    assert report["active_drafts"]["ok"] is False
    assert "closed_draft_has_active_key" in report["active_drafts"]["issue_counts_by_code"]
    assert report["api_cache_policy"]["ok"] is False


def test_content_lifecycle_drill_flags_stale_active_draft_without_failing():
    database_url = _database_url()
    admin_id, page_id, version_id = _create_ready_content_page(database_url, slug="physics/lifecycle-stale")
    session_factory = get_session_factory(database_url)
    with session_factory() as db:
        page = db.get(ContentPageRecord, page_id)
        assert page is not None
        newer_schema = _content_schema(page.slug, title="Newer Version", version="v2")
        newer_hash = _schema_hash(newer_schema)
        newer_version = ContentPageVersion(
            page_id=page.id,
            slug=page.slug,
            status="published",
            version="v2",
            schema_hash=newer_hash,
            schema_json=newer_schema,
            previous_version_id=version_id,
            published_by_user_id=admin_id,
            published_at=utc_now(),
        )
        db.add(newer_version)
        db.flush()
        page.version = "v2"
        page.schema_json = newer_schema
        page.schema_hash = newer_hash
        page.current_version_id = newer_version.id
        page.published_by_user_id = admin_id
        page.published_at = newer_version.published_at
        db.add(
            ContentDraft(
                author_user_id=admin_id,
                target_slug=page.slug,
                title="Stale draft",
                status="draft",
                active_key="active",
                schema_json=_content_schema(page.slug, title="Stale Draft"),
                schema_hash="3" * 64,
                base_version_id=version_id,
                base_schema_hash="4" * 64,
                allow_script=False,
                script_risk_level="none",
                script_review_status="not_required",
            )
        )
        db.commit()

    with session_factory() as db:
        report = run_content_lifecycle_drill(db, database_url=database_url, api_cache_control="no-store")

    assert report["ok"] is True
    assert report["active_drafts"]["ok"] is True
    assert report["active_drafts"]["issue_counts_by_code"] == {"stale_active_draft": 1}
    assert report["active_drafts"]["issue_counts_by_severity"] == {"warning": 1}


def _create_ready_content_page(database_url: str, *, slug: str) -> tuple[int, int, int]:
    _init_database(database_url)
    session_factory = get_session_factory(database_url)
    with session_factory() as db:
        admin = User(
            username=f"admin_{slug.replace('/', '_').replace('-', '_')}",
            normalized_username=f"admin_{slug.replace('/', '_').replace('-', '_')}",
            display_name="Lifecycle Admin",
            password_hash="hash",
            role="admin",
            status="active",
        )
        db.add(admin)
        db.flush()
        schema = _content_schema(slug)
        schema_hash = _schema_hash(schema)
        page = ContentPageRecord(
            slug=slug,
            status="published",
            version="v1",
            schema_json=schema,
            schema_hash=schema_hash,
        )
        db.add(page)
        db.flush()
        version = ContentPageVersion(
            page_id=page.id,
            slug=slug,
            status="published",
            version="v1",
            schema_hash=schema_hash,
            schema_json=schema,
            published_by_user_id=admin.id,
            published_at=utc_now(),
        )
        db.add(version)
        db.flush()
        page.current_version_id = version.id
        page.published_by_user_id = admin.id
        page.published_at = version.published_at
        db.commit()
        return admin.id, page.id, version.id


def _init_database(database_url: str) -> None:
    reset_database_state()
    init_db(database_url)


def _database_url() -> str:
    return "sqlite+pysqlite:///:memory:"


def _content_schema(slug: str, *, title: str = "Lifecycle Page", version: str = "v1") -> dict:
    return {
        "slug": slug,
        "galaxy": "englab",
        "subject": "physics",
        "title": title,
        "layout": "experiment-page",
        "status": "published",
        "version": version,
        "summary": f"{title} summary",
        "sections": [
            {
                "sectionId": "lifecycle-observe",
                "type": "learning-task",
                "title": "Observe",
                "summary": "Check the lifecycle evidence.",
                "props": {},
            }
        ],
        "sources": [],
    }


def _schema_hash(payload: dict) -> str:
    import hashlib

    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class _FakeFetcher:
    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses

    def __call__(self, url: str, headers: dict[str, str], timeout_seconds: float) -> dict:
        assert timeout_seconds > 0
        assert headers
        return self.responses.get(url, {"ok": False, "error": "NotFound"})


def _response(status_code: int, headers: dict[str, str], body: dict | str) -> dict:
    return {
        "ok": True,
        "status_code": status_code,
        "headers": {key.lower(): value for key, value in headers.items()},
        "body": json.dumps(body) if isinstance(body, dict) else body,
    }
