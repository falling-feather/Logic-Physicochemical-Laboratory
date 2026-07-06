import json
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory, make_engine, reset_database_state
from app.models import ContentDraft, ContentPageRecord, ContentPageVersion, User
from app.models.base import utc_now
from app.schemas.content import ContentPage
from app.services.content_catalog import ensure_seed_pages
from scripts.init_content_pages import main as init_content_pages_main
from scripts.init_content_pages import run_content_initialization


def test_init_content_pages_creates_versioned_seed_after_migrations(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        admin_id = _create_user(database_url, "admin")

        report = run_content_initialization(
            database_url=database_url,
            backend_root=backend_root,
            allow_reviewed_scripts=True,
        )

        assert report["ok"] is True
        assert report["content"]["publisher_user_id"] == admin_id
        assert report["content"]["counts"]["created_pages"] == 1
        assert report["content"]["counts"]["created_versions"] == 1
        page, version = _content_page_and_version(database_url)
        assert page.slug == "physics/energy-conservation"
        assert page.status == "published"
        assert page.current_version_id == version.id
        assert page.schema_hash == version.schema_hash
        assert page.published_by_user_id == admin_id
        assert version.published_by_user_id == admin_id
        assert version.source_draft_id is None
        assert version.previous_version_id is None
        assert version.note == "Built-in content initialization"
        assert report["content"]["items"][0]["script_policy"]["status"] == "review_required"
        assert report["content"]["items"][0]["script_policy"]["finding_count"] == 1
    finally:
        _dispose_and_remove(database_url, database_path)


def test_init_content_pages_requires_reviewed_script_confirmation(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        _create_user(database_url, "admin")

        report = run_content_initialization(database_url=database_url, backend_root=backend_root)

        assert report["ok"] is False
        item = report["content"]["items"][0]
        assert item["action"] == "script_review_required"
        assert item["error"] == "reviewed_scripts_not_confirmed"
        assert item["script_policy"]["status"] == "review_required"
        assert _table_count(database_url, ContentPageRecord) == 0
        assert _table_count(database_url, ContentPageVersion) == 0
    finally:
        _dispose_and_remove(database_url, database_path)


def test_init_content_pages_is_idempotent(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        admin_id = _create_user(database_url, "admin")
        first = run_content_initialization(
            database_url=database_url,
            backend_root=backend_root,
            publisher_user_id=admin_id,
            allow_reviewed_scripts=True,
        )
        second = run_content_initialization(
            database_url=database_url,
            backend_root=backend_root,
            publisher_user_id=admin_id,
            allow_reviewed_scripts=True,
        )

        assert first["ok"] is True
        assert second["ok"] is True
        assert second["content"]["counts"]["changed"] == 0
        assert second["content"]["counts"]["skipped"] == 1
        assert second["content"]["items"][0]["action"] == "skipped"
        assert _table_count(database_url, ContentPageRecord) == 1
        assert _table_count(database_url, ContentPageVersion) == 1
    finally:
        _dispose_and_remove(database_url, database_path)


def test_init_content_pages_repairs_unversioned_seed(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        admin_id = _create_user(database_url, "admin")
        session_factory = get_session_factory(database_url)
        with session_factory() as db:
            ensure_seed_pages(db)
        assert _table_count(database_url, ContentPageRecord) == 1
        assert _table_count(database_url, ContentPageVersion) == 0

        report = run_content_initialization(
            database_url=database_url,
            backend_root=backend_root,
            publisher_user_id=admin_id,
            allow_reviewed_scripts=True,
        )

        assert report["ok"] is True
        assert report["content"]["items"][0]["action"] == "version_created"
        assert report["content"]["counts"]["created_pages"] == 0
        assert report["content"]["counts"]["created_versions"] == 1
        page, version = _content_page_and_version(database_url)
        assert page.current_version_id == version.id
        assert page.published_by_user_id == admin_id
    finally:
        _dispose_and_remove(database_url, database_path)


def test_init_content_pages_dry_run_does_not_write(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        admin_id = _create_user(database_url, "admin")

        report = run_content_initialization(
            database_url=database_url,
            backend_root=backend_root,
            publisher_user_id=admin_id,
            dry_run=True,
        )

        assert report["ok"] is True
        assert report["status"] == "dry_run"
        assert report["content"]["counts"]["changed"] == 1
        assert report["content"]["items"][0]["action"] == "created"
        assert _table_count(database_url, ContentPageRecord) == 0
        assert _table_count(database_url, ContentPageVersion) == 0
    finally:
        _dispose_and_remove(database_url, database_path)


def test_init_content_pages_reports_conflict_for_existing_current_schema(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        admin_id = _create_user(database_url, "admin")
        _create_custom_published_page(database_url)

        report = run_content_initialization(
            database_url=database_url,
            backend_root=backend_root,
            publisher_user_id=admin_id,
            allow_reviewed_scripts=True,
        )

        assert report["ok"] is False
        item = report["content"]["items"][0]
        assert item["action"] == "conflict"
        assert item["error"] == "current_schema_differs_from_seed"
        assert item["current_schema_hash"] != item["seed_schema_hash"]
        assert _table_count(database_url, ContentPageVersion) == 1
    finally:
        _dispose_and_remove(database_url, database_path)


def test_init_content_pages_upgrade_existing_appends_version(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        admin_id = _create_user(database_url, "admin")
        previous_version_id = _create_custom_published_page(database_url)

        report = run_content_initialization(
            database_url=database_url,
            backend_root=backend_root,
            publisher_user_id=admin_id,
            allow_reviewed_scripts=True,
            upgrade_existing=True,
        )

        assert report["ok"] is True
        item = report["content"]["items"][0]
        assert item["action"] == "upgraded"
        assert item["previous_version_id"] == previous_version_id
        assert report["content"]["counts"]["upgraded"] == 1
        page, version = _content_page_and_version(database_url)
        assert page.current_version_id == version.id
        assert version.previous_version_id == previous_version_id
        assert version.schema_hash == item["seed_schema_hash"]
        assert _table_count(database_url, ContentPageVersion) == 2
    finally:
        _dispose_and_remove(database_url, database_path)


def test_init_content_pages_upgrade_blocks_active_drafts_by_default(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        admin_id = _create_user(database_url, "admin")
        teacher_id = _create_user(database_url, "teacher")
        _create_custom_published_page(database_url)
        _create_active_draft(database_url, teacher_id)

        report = run_content_initialization(
            database_url=database_url,
            backend_root=backend_root,
            publisher_user_id=admin_id,
            allow_reviewed_scripts=True,
            upgrade_existing=True,
        )

        assert report["ok"] is False
        item = report["content"]["items"][0]
        assert item["action"] == "stale_drafts_blocked"
        assert item["error"] == "active_drafts_would_become_stale"
        assert item["active_drafts"] == 1
        assert _table_count(database_url, ContentPageVersion) == 1
    finally:
        _dispose_and_remove(database_url, database_path)


def test_init_content_pages_requires_active_admin_publisher(monkeypatch):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        teacher_id = _create_user(database_url, "teacher")

        missing_report = run_content_initialization(database_url=database_url, backend_root=backend_root)
        teacher_report = run_content_initialization(
            database_url=database_url,
            backend_root=backend_root,
            publisher_user_id=teacher_id,
        )

        assert missing_report["ok"] is False
        assert missing_report["status"] == "publisher_not_found"
        assert teacher_report["ok"] is False
        assert teacher_report["status"] == "publisher_not_found"
        assert _table_count(database_url, ContentPageRecord) == 0
    finally:
        _dispose_and_remove(database_url, database_path)


def test_init_content_pages_cli_outputs_json_report(monkeypatch, capsys):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(monkeypatch, backend_root)
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        admin_id = _create_user(database_url, "admin")

        exit_code = init_content_pages_main(
            [
                "--database-url",
                database_url,
                "--publisher-user-id",
                str(admin_id),
                "--allow-reviewed-scripts",
            ]
        )

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert exit_code == 0
        assert payload["ok"] is True
        assert payload["content"]["counts"]["created_pages"] == 1
        assert payload["content"]["items"][0]["script_policy"]["status"] == "review_required"
    finally:
        _dispose_and_remove(database_url, database_path)


def test_init_content_pages_cli_handles_unicode_database_path(monkeypatch, capsys):
    backend_root = Path(__file__).resolve().parents[1]
    database_path = _migrated_sqlite_database(
        monkeypatch,
        backend_root,
        runtime_dir_name="pytest-cache-files-content-init-中文路径",
        database_name=f"内容初始化-{uuid4().hex}.db",
    )
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    try:
        admin_id = _create_user(database_url, "admin")

        exit_code = init_content_pages_main(
            [
                "--database-url",
                database_url,
                "--publisher-user-id",
                str(admin_id),
                "--allow-reviewed-scripts",
            ]
        )

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert exit_code == 0
        assert payload["ok"] is True
        assert payload["content"]["publisher_user_id"] == admin_id
        assert payload["content"]["items"][0]["slug"] == "physics/energy-conservation"
        assert database_path.exists()
        page, version = _content_page_and_version(database_url)
        assert page.current_version_id == version.id
        assert page.schema_hash == version.schema_hash
    finally:
        _dispose_and_remove(database_url, database_path)


def _migrated_sqlite_database(
    monkeypatch,
    backend_root: Path,
    *,
    runtime_dir_name: str = "pytest-cache-files-content-init",
    database_name: str | None = None,
) -> Path:
    runtime_dir = backend_root / runtime_dir_name
    runtime_dir.mkdir(exist_ok=True)
    database_path = runtime_dir / (database_name or f"content-init-{uuid4().hex}.db")
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("ASTRA_DATABASE_URL", database_url)
    monkeypatch.setenv("ASTRA_AUTO_CREATE_TABLES", "false")
    get_settings.cache_clear()
    reset_database_state()

    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(config, "head")
    return database_path


def _create_user(database_url: str, role: str, *, status: str = "active") -> int:
    session_factory = get_session_factory(database_url)
    with session_factory() as db:
        username = f"{role}_{uuid4().hex[:10]}"
        user = User(
            username=username,
            normalized_username=username,
            display_name=role.title(),
            password_hash="not-used-in-test",
            role=role,
            status=status,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return int(user.id)


def _create_custom_published_page(database_url: str) -> int:
    custom_schema = _custom_page_schema()
    payload = custom_schema.model_dump(mode="json")
    schema_hash = _schema_hash(payload)
    session_factory = get_session_factory(database_url)
    with session_factory() as db:
        admin = db.scalar(select(User).where(User.role == "admin").order_by(User.id).limit(1))
        assert admin is not None
        page = ContentPageRecord(
            slug=custom_schema.slug,
            status="published",
            version="custom-v1",
            schema_json=payload,
            schema_hash=schema_hash,
            published_by_user_id=admin.id,
            published_at=utc_now(),
        )
        db.add(page)
        db.flush()
        version = ContentPageVersion(
            page_id=page.id,
            slug=page.slug,
            status=page.status,
            version=page.version,
            schema_hash=schema_hash,
            schema_json=payload,
            published_by_user_id=admin.id,
            published_at=utc_now(),
            note="custom existing page",
        )
        db.add(version)
        db.flush()
        page.current_version_id = version.id
        db.commit()
        return int(version.id)


def _create_active_draft(database_url: str, teacher_id: int) -> int:
    schema = _custom_page_schema().model_copy(update={"title": "Active Custom Draft"})
    payload = schema.model_dump(mode="json")
    session_factory = get_session_factory(database_url)
    with session_factory() as db:
        draft = ContentDraft(
            author_user_id=teacher_id,
            target_slug=schema.slug,
            title=schema.title,
            status="draft",
            active_key="active",
            schema_json=payload,
            schema_hash=_schema_hash(payload),
            allow_script=False,
            script_risk_level="none",
            script_analysis_json=None,
            script_review_status="not_required",
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return int(draft.id)


def _custom_page_schema() -> ContentPage:
    return ContentPage(
        slug="physics/energy-conservation",
        galaxy="englab",
        subject="physics",
        title="Custom Existing Energy",
        layout="experiment-page",
        status="published",
        version="custom-v1",
        summary="Existing production content with a different schema hash.",
        sections=[
            {
                "type": "learning-task",
                "title": "Custom",
                "summary": "Do not overwrite without explicit upgrade.",
                "props": {},
            }
        ],
        sources=[],
    )


def _content_page_and_version(database_url: str) -> tuple[ContentPageRecord, ContentPageVersion]:
    session_factory = get_session_factory(database_url)
    with session_factory() as db:
        page = db.scalar(select(ContentPageRecord).where(ContentPageRecord.slug == "physics/energy-conservation"))
        assert page is not None
        version = db.get(ContentPageVersion, page.current_version_id)
        assert version is not None
        return page, version


def _table_count(database_url: str, model) -> int:
    session_factory = get_session_factory(database_url)
    with session_factory() as db:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)


def _schema_hash(payload: dict) -> str:
    import hashlib
    import json

    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _dispose_and_remove(database_url: str, database_path: Path) -> None:
    make_engine(database_url).dispose()
    get_settings.cache_clear()
    reset_database_state()
    if database_path.exists():
        database_path.unlink()
