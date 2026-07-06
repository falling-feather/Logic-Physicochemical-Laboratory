import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.endpoints import content as content_endpoint
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import ContentDraft, ContentPageRecord, ContentPageVersion
from app.models.base import utc_now


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _bootstrap_admin(client, username: str = "admin_publish") -> str:
    response = client.post(
        "/api/admin/bootstrap",
        json={
            "username": username,
            "password": "secret123",
            "display_name": "Content Publisher",
        },
    )
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    assert login.status_code == 200
    return login.json()["access_token"]


def _register_and_login(client, username: str, role: str) -> tuple[int, str]:
    register = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "secret123",
            "display_name": username.replace("_", " ").title(),
            "role": role,
        },
    )
    assert register.status_code == 201
    login = client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    assert login.status_code == 200
    return register.json()["id"], login.json()["access_token"]


def _draft_payload(slug: str, *, title: str, allow_script: bool = False) -> dict:
    script_props = {
        "scriptPath": "drafts/custom-publish.js",
        "scriptSandbox": {"mode": "isolated-iframe", "network": "same-origin", "storage": "none"},
    }
    return {
        "target_slug": slug,
        "allow_script": allow_script,
        "schema": {
            "slug": slug,
            "galaxy": "englab",
            "subject": "physics",
            "title": title,
            "layout": "experiment-page",
            "status": "draft",
            "version": "draft-local",
            "summary": f"{title} summary",
            "sections": [
                {
                    "type": "learning-task",
                    "title": "Observe",
                    "summary": "Compare the observed trend and explain the evidence.",
                    "props": script_props if allow_script else {},
                }
            ],
            "sources": [],
        },
    }


def test_admin_publishes_draft_to_public_page_and_version_history(client):
    admin_token = _bootstrap_admin(client)
    teacher_id, teacher_token = _register_and_login(client, "teacher_publish", "teacher")
    slug = "physics/published-energy"

    create = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload(slug, title="First Published Energy"),
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]
    assert create.json()["author_user_id"] == teacher_id

    render_before = client.get(f"/api/render/page/{slug}")
    assert render_before.status_code == 404

    teacher_publish = client.post(
        f"/api/content/drafts/{draft_id}/publish",
        headers=_auth_header(teacher_token),
        json={"note": "teachers cannot publish"},
    )
    assert teacher_publish.status_code == 403

    publish_before_submit = client.post(
        f"/api/content/drafts/{draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "too early"},
    )
    assert publish_before_submit.status_code == 409

    submit = _submit_draft(client, teacher_token, draft_id, note="Ready for publication")
    assert submit["status"] == "submitted"
    assert submit["submitted_at"] is not None

    publish = client.post(
        f"/api/content/drafts/{draft_id}/publish",
        headers={**_auth_header(admin_token), "X-Request-ID": "content-publish-request"},
        json={"note": "Ship first version"},
    )
    assert publish.status_code == 200
    publication = publish.json()
    assert publication["slug"] == slug
    assert publication["title"] == "First Published Energy"
    assert publication["status"] == "published"
    assert publication["version"] == "v1"
    assert len(publication["schema_hash"]) == 64
    assert publication["previous_version_id"] is None
    assert publication["source_draft_id"] == draft_id
    assert publication["restored_from_version_id"] is None

    duplicate_publish = client.post(
        f"/api/content/drafts/{draft_id}/publish",
        headers=_auth_header(admin_token),
        json={},
    )
    assert duplicate_publish.status_code == 409

    render_after = client.get(f"/api/render/page/{slug}")
    assert render_after.status_code == 200
    assert render_after.json()["title"] == "First Published Energy"
    assert render_after.json()["status"] == "published"
    assert render_after.json()["version"] == "v1"

    draft_read = client.get(f"/api/content/drafts/{draft_id}", headers=_auth_header(teacher_token))
    assert draft_read.status_code == 200
    draft_after_publish = draft_read.json()
    assert draft_after_publish["status"] == "published"
    assert draft_after_publish["published_page_id"] == publication["id"]
    assert draft_after_publish["published_version_id"] == publication["version_id"]
    assert draft_after_publish["published_by_user_id"] is not None
    assert draft_after_publish["published_at"] is not None
    assert draft_after_publish["base_version_id"] is None
    assert draft_after_publish["base_schema_hash"] is None
    assert len(draft_after_publish["schema_hash"]) == 64

    versions = client.get(f"/api/admin/content/page-versions?slug={slug}", headers=_auth_header(admin_token))
    assert versions.status_code == 200
    assert versions.json()["total"] == 1
    version_item = versions.json()["items"][0]
    assert version_item["id"] == publication["version_id"]
    assert version_item["schema_hash"] == publication["schema_hash"]
    assert version_item["previous_version_id"] is None
    assert version_item["source_draft_id"] == draft_id
    assert version_item["restored_from_version_id"] is None
    assert version_item["note"] == "Ship first version"

    first_diff = client.get(
        f"/api/admin/content/page-versions/{publication['version_id']}/diff",
        headers=_auth_header(admin_token),
    )
    assert first_diff.status_code == 200
    assert first_diff.json()["base_version_id"] == publication["version_id"]
    assert first_diff.json()["change_count"] == 0

    pages = client.get(f"/api/admin/content/pages?q={slug}", headers=_auth_header(admin_token))
    assert pages.status_code == 200
    page_item = pages.json()["items"][0]
    assert page_item["current_version_id"] == publication["version_id"]
    assert page_item["schema_hash"] == publication["schema_hash"]
    assert page_item["published_by_user_id"] is not None
    assert page_item["published_at"] is not None

    stats = client.get("/api/admin/stats", headers=_auth_header(admin_token))
    assert stats.status_code == 200
    assert stats.json()["total_content_page_versions"] == 1

    audit = client.get(
        f"/api/admin/audit-logs?action=content.draft.publish&resource_id={draft_id}",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    audit_item = audit.json()["items"][0]
    assert audit_item["request_id"] == "content-publish-request"
    assert audit_item["snapshot_json"]["draft"]["changes"]["status"] == {"from": "submitted", "to": "published"}
    assert audit_item["snapshot_json"]["version"]["version"] == "v1"
    assert audit_item["snapshot_json"]["version"]["schema_hash"] == publication["schema_hash"]
    assert "schema" not in audit_item["snapshot_json"]["version"]
    assert "schema_json" not in audit_item["snapshot_json"]["version"]
    assert _table_count(ContentPageRecord) >= 2
    assert _table_count(ContentPageVersion) == 1


def test_stale_parallel_draft_cannot_overwrite_newer_published_version(client):
    admin_token = _bootstrap_admin(client, username="admin_stale_publish")
    _, first_teacher_token = _register_and_login(client, "teacher_stale_one", "teacher")
    _, second_teacher_token = _register_and_login(client, "teacher_stale_two", "teacher")
    slug = "physics/stale-parallel"

    first_draft_id = _create_draft(client, first_teacher_token, slug, "First Parallel Page")
    second_draft_id = _create_draft(client, second_teacher_token, slug, "Second Parallel Page")
    _submit_draft(client, first_teacher_token, first_draft_id)
    _submit_draft(client, second_teacher_token, second_draft_id)

    first_publish = client.post(
        f"/api/content/drafts/{first_draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "publish first"},
    )
    assert first_publish.status_code == 200

    stale_publish = client.post(
        f"/api/content/drafts/{second_draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "should conflict"},
    )
    assert stale_publish.status_code == 409

    render = client.get(f"/api/render/page/{slug}")
    assert render.status_code == 200
    assert render.json()["title"] == "First Parallel Page"
    assert _table_count(ContentPageVersion) == 1


def test_publish_integrity_conflict_returns_409(client, monkeypatch):
    admin_token = _bootstrap_admin(client, username="admin_publish_conflict")
    _, first_teacher_token = _register_and_login(client, "teacher_publish_conflict_one", "teacher")
    _, second_teacher_token = _register_and_login(client, "teacher_publish_conflict_two", "teacher")
    slug = "physics/publish-integrity-conflict"

    first_publish = _create_submit_publish(client, admin_token, first_teacher_token, slug, "Published Conflict Base")
    second_draft_id = _create_draft(client, second_teacher_token, slug, "Concurrent Conflict Draft")
    _submit_draft(client, second_teacher_token, second_draft_id)

    monkeypatch.setattr(content_endpoint, "_next_content_version", lambda db, target_slug: first_publish["version"])
    conflict = client.post(
        f"/api/content/drafts/{second_draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "simulate concurrent version insert"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Content publication conflict; refresh the current version and retry"

    render = client.get(f"/api/render/page/{slug}")
    assert render.status_code == 200
    assert render.json()["title"] == "Published Conflict Base"
    assert _table_count(ContentPageVersion) == 1

    draft_after_conflict = client.get(f"/api/content/drafts/{second_draft_id}", headers=_auth_header(second_teacher_token))
    assert draft_after_conflict.status_code == 200
    assert draft_after_conflict.json()["status"] == "submitted"
    assert draft_after_conflict.json()["published_version_id"] is None

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        draft = db.get(ContentDraft, second_draft_id)
        assert draft is not None
        assert draft.status == "submitted"
        assert draft.active_key == "active"
        page = db.scalar(select(ContentPageRecord).where(ContentPageRecord.slug == slug))
        assert page is not None
        assert page.current_version_id == first_publish["version_id"]

    audit = client.get(
        f"/api/admin/audit-logs?action=content.draft.publish&resource_id={second_draft_id}",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 0


def test_draft_bound_to_previous_base_version_cannot_publish_after_current_advances(client):
    admin_token = _bootstrap_admin(client, username="admin_stale_base")
    _, first_teacher_token = _register_and_login(client, "teacher_stale_base_one", "teacher")
    _, second_teacher_token = _register_and_login(client, "teacher_stale_base_two", "teacher")
    slug = "physics/stale-base-version"

    first_draft_id = _create_draft(client, first_teacher_token, slug, "Stable Base Version")
    _submit_draft(client, first_teacher_token, first_draft_id)
    first_publish = client.post(
        f"/api/content/drafts/{first_draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "publish base"},
    )
    assert first_publish.status_code == 200
    base_version_id = first_publish.json()["version_id"]
    base_schema_hash = first_publish.json()["schema_hash"]

    stale_create = _create_draft_body(client, first_teacher_token, slug, "Stale Base Edit")
    fresh_create = _create_draft_body(client, second_teacher_token, slug, "Fresh Base Edit")
    assert stale_create["base_version_id"] == base_version_id
    assert stale_create["base_schema_hash"] == base_schema_hash
    assert fresh_create["base_version_id"] == base_version_id
    assert fresh_create["base_schema_hash"] == base_schema_hash

    _submit_draft(client, second_teacher_token, fresh_create["id"])
    fresh_publish = client.post(
        f"/api/content/drafts/{fresh_create['id']}/publish",
        headers=_auth_header(admin_token),
        json={"note": "advance current"},
    )
    assert fresh_publish.status_code == 200
    assert fresh_publish.json()["previous_version_id"] == base_version_id

    _submit_draft(client, first_teacher_token, stale_create["id"])
    stale_publish = client.post(
        f"/api/content/drafts/{stale_create['id']}/publish",
        headers=_auth_header(admin_token),
        json={"note": "should conflict with v2"},
    )
    assert stale_publish.status_code == 409
    assert stale_publish.json()["detail"] == "Content draft is based on an older published version"

    render = client.get(f"/api/render/page/{slug}")
    assert render.status_code == 200
    assert render.json()["title"] == "Fresh Base Edit"
    assert _table_count(ContentPageVersion) == 2


def test_content_draft_update_preserves_base_version_after_current_advances(client):
    admin_token = _bootstrap_admin(client, username="admin_update_stale_base")
    _, first_teacher_token = _register_and_login(client, "teacher_update_stale_one", "teacher")
    _, second_teacher_token = _register_and_login(client, "teacher_update_stale_two", "teacher")
    slug = "physics/update-stale-base"

    first_draft_id = _create_draft(client, first_teacher_token, slug, "Update Base Version")
    _submit_draft(client, first_teacher_token, first_draft_id)
    first_publish = client.post(
        f"/api/content/drafts/{first_draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "publish base"},
    )
    assert first_publish.status_code == 200
    base_version_id = first_publish.json()["version_id"]
    base_schema_hash = first_publish.json()["schema_hash"]

    stale_create = _create_draft_body(client, first_teacher_token, slug, "Editable Stale Draft")
    fresh_create = _create_draft_body(client, second_teacher_token, slug, "Fresh Current Draft")
    _submit_draft(client, second_teacher_token, fresh_create["id"])
    fresh_publish = client.post(
        f"/api/content/drafts/{fresh_create['id']}/publish",
        headers=_auth_header(admin_token),
        json={"note": "advance current before stale edit"},
    )
    assert fresh_publish.status_code == 200
    assert fresh_publish.json()["previous_version_id"] == base_version_id

    update = client.patch(
        f"/api/content/drafts/{stale_create['id']}",
        headers=_auth_header(first_teacher_token),
        json=_draft_update_payload(slug, title="Edited Stale Draft"),
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["title"] == "Edited Stale Draft"
    assert updated["base_version_id"] == base_version_id
    assert updated["base_schema_hash"] == base_schema_hash
    assert updated["schema_hash"] != stale_create["schema_hash"]

    _submit_draft(client, first_teacher_token, stale_create["id"])
    stale_publish = client.post(
        f"/api/content/drafts/{stale_create['id']}/publish",
        headers=_auth_header(admin_token),
        json={"note": "should still conflict"},
    )
    assert stale_publish.status_code == 409
    assert stale_publish.json()["detail"] == "Content draft is based on an older published version"


def test_content_page_version_source_draft_id_is_unique(client):
    admin_token = _bootstrap_admin(client, username="admin_source_draft_unique")
    _, teacher_token = _register_and_login(client, "teacher_source_draft_unique", "teacher")
    slug = "physics/source-draft-unique"

    publish = _create_submit_publish(client, admin_token, teacher_token, slug, "Unique Source Draft")

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        original = db.get(ContentPageVersion, publish["version_id"])
        assert original is not None
        assert original.source_draft_id is not None
        duplicate = ContentPageVersion(
            page_id=original.page_id,
            slug=original.slug,
            status=original.status,
            version="v-source-duplicate",
            schema_hash=original.schema_hash,
            schema_json=original.schema_json,
            source_draft_id=original.source_draft_id,
            restored_from_version_id=None,
            previous_version_id=original.id,
            published_by_user_id=original.published_by_user_id,
            published_at=original.published_at,
            note="duplicate source draft should fail",
        )
        db.add(duplicate)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_publish_source_draft_integrity_conflict_returns_409(client):
    admin_token = _bootstrap_admin(client, username="admin_source_draft_conflict")
    teacher_id, teacher_token = _register_and_login(client, "teacher_source_draft_conflict", "teacher")
    slug = "physics/source-draft-api-conflict"

    draft_id = _create_draft(client, teacher_token, slug, "Source Draft API Conflict")
    _submit_draft(client, teacher_token, draft_id)

    reserved_slug = "physics/source-draft-api-reserved"
    reserved_schema = _draft_payload(reserved_slug, title="Reserved Source Draft")["schema"]
    reserved_schema["status"] = "published"
    reserved_schema["version"] = "v1"
    reserved_hash = content_endpoint._schema_hash(reserved_schema)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        page = ContentPageRecord(
            slug=reserved_slug,
            status="published",
            version="v1",
            schema_json=reserved_schema,
            schema_hash=reserved_hash,
            published_by_user_id=teacher_id,
            published_at=utc_now(),
        )
        db.add(page)
        db.flush()
        version = ContentPageVersion(
            page_id=page.id,
            slug=reserved_slug,
            status="published",
            version="v1",
            schema_hash=reserved_hash,
            schema_json=reserved_schema,
            source_draft_id=draft_id,
            restored_from_version_id=None,
            previous_version_id=None,
            published_by_user_id=teacher_id,
            published_at=page.published_at,
            note="reserve source draft id",
        )
        db.add(version)
        db.flush()
        page.current_version_id = version.id
        db.commit()

    conflict = client.post(
        f"/api/content/drafts/{draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "source draft id already used"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Content publication conflict; refresh the current version and retry"

    draft_after_conflict = client.get(f"/api/content/drafts/{draft_id}", headers=_auth_header(teacher_token))
    assert draft_after_conflict.status_code == 200
    assert draft_after_conflict.json()["status"] == "submitted"
    assert draft_after_conflict.json()["published_version_id"] is None

    audit = client.get(
        f"/api/admin/audit-logs?action=content.draft.publish&resource_id={draft_id}",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 0


def test_script_draft_requires_approved_review_before_publish(client):
    first_admin_token = _bootstrap_admin(client, username="admin_publish_first")
    second_admin_id, second_admin_token = _register_and_login(client, "admin_publish_second", "teacher")
    promote_second_admin = client.patch(
        f"/api/admin/users/{second_admin_id}",
        headers=_auth_header(first_admin_token),
        json={"role": "admin"},
    )
    assert promote_second_admin.status_code == 200
    _, teacher_token = _register_and_login(client, "teacher_script_publish", "teacher")
    slug = "physics/script-publish"

    create = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload(slug, title="Script Draft Energy", allow_script=True),
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]
    assert create.json()["script_review_status"] == "pending"
    assert create.json()["script_risk_level"] == "medium"
    assert create.json()["script_analysis"]["status"] == "review_required"
    assert create.json()["script_analysis"]["sandbox"]["status"] == "isolated"
    _submit_draft(client, teacher_token, draft_id)

    publish_before_review = client.post(
        f"/api/content/drafts/{draft_id}/publish",
        headers=_auth_header(first_admin_token),
        json={"note": "try before review"},
    )
    assert publish_before_review.status_code == 409

    approve = client.patch(
        f"/api/content/drafts/{draft_id}/script-review",
        headers=_auth_header(second_admin_token),
        json={"status": "approved", "note": "Script path reviewed"},
    )
    assert approve.status_code == 200

    publish_after_review = client.post(
        f"/api/content/drafts/{draft_id}/publish",
        headers=_auth_header(first_admin_token),
        json={"note": "publish after approval"},
    )
    assert publish_after_review.status_code == 200
    assert publish_after_review.json()["version"] == "v1"


def test_scripted_content_version_requires_new_review_before_rollback(client):
    first_admin_token = _bootstrap_admin(client, username="admin_script_rollback_first")
    second_admin_id, second_admin_token = _register_and_login(client, "admin_script_rollback_second", "teacher")
    promote_second_admin = client.patch(
        f"/api/admin/users/{second_admin_id}",
        headers=_auth_header(first_admin_token),
        json={"role": "admin"},
    )
    assert promote_second_admin.status_code == 200
    _, teacher_token = _register_and_login(client, "teacher_script_rollback", "teacher")
    slug = "physics/script-rollback"

    script_draft_id = _create_draft_from_payload(
        client,
        teacher_token,
        _draft_payload(slug, title="Scripted Version", allow_script=True),
    )
    approve = client.patch(
        f"/api/content/drafts/{script_draft_id}/script-review",
        headers=_auth_header(second_admin_token),
        json={"status": "approved", "note": "Sandbox contract reviewed"},
    )
    assert approve.status_code == 200
    _submit_draft(client, teacher_token, script_draft_id)
    script_publish = _publish_draft(client, first_admin_token, script_draft_id, note="publish scripted version")
    assert script_publish["version"] == "v1"

    plain_draft_id = _create_draft(client, teacher_token, slug, "Plain Version")
    _submit_draft(client, teacher_token, plain_draft_id)
    plain_publish = _publish_draft(client, first_admin_token, plain_draft_id, note="publish plain version")
    assert plain_publish["version"] == "v2"

    rollback = client.post(
        f"/api/content/page-versions/{script_publish['version_id']}/rollback",
        headers=_auth_header(first_admin_token),
        json={"note": "restore scripted version"},
    )

    assert rollback.status_code == 409
    assert rollback.json()["detail"] == (
        "Content page version includes script policy findings; create a reviewed draft before rollback"
    )
    render = client.get(f"/api/render/page/{slug}")
    assert render.status_code == 200
    assert render.json()["title"] == "Plain Version"
    assert render.json()["version"] == "v2"


def test_admin_rolls_back_by_creating_new_content_version(client):
    admin_token = _bootstrap_admin(client, username="admin_rollback")
    _, teacher_token = _register_and_login(client, "teacher_rollback", "teacher")
    slug = "physics/rollback-energy"

    first_draft_id = _create_draft(client, teacher_token, slug, "Stable Energy Page")
    _submit_draft(client, teacher_token, first_draft_id)
    first_publish = client.post(
        f"/api/content/drafts/{first_draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "stable"},
    )
    assert first_publish.status_code == 200
    first_version_id = first_publish.json()["version_id"]
    first_schema_hash = first_publish.json()["schema_hash"]
    assert first_publish.json()["version"] == "v1"

    second_create = _create_draft_body(client, teacher_token, slug, "Experimental Energy Page")
    second_draft_id = second_create["id"]
    assert second_create["base_version_id"] == first_version_id
    assert second_create["base_schema_hash"] == first_schema_hash
    assert len(second_create["schema_hash"]) == 64
    _submit_draft(client, teacher_token, second_draft_id)
    second_publish = client.post(
        f"/api/content/drafts/{second_draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "experiment"},
    )
    assert second_publish.status_code == 200
    second_version_id = second_publish.json()["version_id"]
    assert second_publish.json()["previous_version_id"] == first_version_id
    assert second_publish.json()["version"] == "v2"

    teacher_diff = client.get(
        f"/api/admin/content/page-versions/{second_version_id}/diff?base_version_id={first_version_id}",
        headers=_auth_header(teacher_token),
    )
    assert teacher_diff.status_code == 403

    diff = client.get(
        f"/api/admin/content/page-versions/{second_version_id}/diff?base_version_id={first_version_id}",
        headers=_auth_header(admin_token),
    )
    assert diff.status_code == 200
    diff_body = diff.json()
    assert diff_body["slug"] == slug
    assert diff_body["base_version_id"] == first_version_id
    assert diff_body["target_version_id"] == second_version_id
    assert diff_body["change_count"] >= 1
    title_change = next(change for change in diff_body["changes"] if change["path"] == "$.title")
    assert title_change["before"] == "Stable Energy Page"
    assert title_change["after"] == "Experimental Energy Page"

    default_diff = client.get(
        f"/api/admin/content/page-versions/{second_version_id}/diff",
        headers=_auth_header(admin_token),
    )
    assert default_diff.status_code == 200
    assert default_diff.json()["base_version_id"] == first_version_id

    render_second = client.get(f"/api/render/page/{slug}")
    assert render_second.status_code == 200
    assert render_second.json()["title"] == "Experimental Energy Page"
    assert render_second.json()["version"] == "v2"

    teacher_rollback = client.post(
        f"/api/content/page-versions/{first_version_id}/rollback",
        headers=_auth_header(teacher_token),
        json={"note": "teacher rollback"},
    )
    assert teacher_rollback.status_code == 403

    rollback = client.post(
        f"/api/content/page-versions/{first_version_id}/rollback",
        headers={**_auth_header(admin_token), "X-Request-ID": "content-rollback-request"},
        json={"note": "restore stable"},
    )
    assert rollback.status_code == 200
    rollback_body = rollback.json()
    assert rollback_body["version"] == "v3"
    assert rollback_body["title"] == "Stable Energy Page"
    assert rollback_body["previous_version_id"] == second_version_id
    assert rollback_body["source_draft_id"] is None
    assert rollback_body["restored_from_version_id"] == first_version_id

    render_after_rollback = client.get(f"/api/render/page/{slug}")
    assert render_after_rollback.status_code == 200
    assert render_after_rollback.json()["title"] == "Stable Energy Page"
    assert render_after_rollback.json()["version"] == "v3"

    versions = client.get(f"/api/admin/content/page-versions?slug={slug}", headers=_auth_header(admin_token))
    assert versions.status_code == 200
    assert versions.json()["total"] == 3
    assert versions.json()["items"][0]["version"] == "v3"
    assert versions.json()["items"][0]["previous_version_id"] == second_version_id
    assert versions.json()["items"][0]["restored_from_version_id"] == first_version_id
    assert versions.json()["items"][1]["version"] == "v2"
    assert versions.json()["items"][1]["previous_version_id"] == first_version_id
    assert versions.json()["items"][2]["version"] == "v1"
    assert versions.json()["items"][2]["previous_version_id"] is None

    rollback_audit = client.get(
        f"/api/admin/audit-logs?action=content.page.rollback&request_id=content-rollback-request",
        headers=_auth_header(admin_token),
    )
    assert rollback_audit.status_code == 200
    assert rollback_audit.json()["total"] == 1
    snapshot = rollback_audit.json()["items"][0]["snapshot_json"]
    assert snapshot["page"]["after"]["version"] == "v3"
    assert snapshot["restored_from"]["id"] == first_version_id
    assert "schema" not in snapshot["version"]
    assert "schema_json" not in snapshot["version"]
    assert _table_count(ContentPageVersion) == 3


def test_rollback_integrity_conflict_returns_409(client, monkeypatch):
    admin_token = _bootstrap_admin(client, username="admin_rollback_conflict")
    _, teacher_token = _register_and_login(client, "teacher_rollback_conflict", "teacher")
    slug = "physics/rollback-integrity-conflict"

    first_publish = _create_submit_publish(client, admin_token, teacher_token, slug, "Rollback Conflict Base")
    second_publish = _create_submit_publish(client, admin_token, teacher_token, slug, "Rollback Conflict Current")

    monkeypatch.setattr(content_endpoint, "_next_content_version", lambda db, target_slug: second_publish["version"])
    rollback = client.post(
        f"/api/content/page-versions/{first_publish['version_id']}/rollback",
        headers=_auth_header(admin_token),
        json={"note": "simulate concurrent rollback version insert"},
    )
    assert rollback.status_code == 409
    assert rollback.json()["detail"] == "Content publication conflict; refresh the current version and retry"

    render = client.get(f"/api/render/page/{slug}")
    assert render.status_code == 200
    assert render.json()["title"] == "Rollback Conflict Current"
    assert render.json()["version"] == "v2"
    assert _table_count(ContentPageVersion) == 2

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        page = db.scalar(select(ContentPageRecord).where(ContentPageRecord.slug == slug))
        assert page is not None
        assert page.current_version_id == second_publish["version_id"]
        assert page.version == "v2"


def test_admin_content_page_version_diff_rejects_cross_slug_base(client):
    admin_token = _bootstrap_admin(client, username="admin_diff_cross_slug")
    _, teacher_token = _register_and_login(client, "teacher_diff_cross_slug", "teacher")

    first_version_id = _create_submit_publish(
        client,
        admin_token,
        teacher_token,
        "physics/diff-a",
        "Diff A First",
    )["version_id"]
    second_version_id = _create_submit_publish(
        client,
        admin_token,
        teacher_token,
        "physics/diff-a",
        "Diff A Second",
    )["version_id"]
    other_version_id = _create_submit_publish(
        client,
        admin_token,
        teacher_token,
        "physics/diff-b",
        "Diff B First",
    )["version_id"]

    diff = client.get(
        f"/api/admin/content/page-versions/{second_version_id}/diff?base_version_id={first_version_id}",
        headers=_auth_header(admin_token),
    )
    assert diff.status_code == 200

    cross_slug = client.get(
        f"/api/admin/content/page-versions/{second_version_id}/diff?base_version_id={other_version_id}",
        headers=_auth_header(admin_token),
    )
    assert cross_slug.status_code == 422


def test_admin_content_page_version_diff_includes_semantic_schema_summary(client):
    admin_token = _bootstrap_admin(client, username="admin_semantic_diff")
    _, teacher_token = _register_and_login(client, "teacher_semantic_diff", "teacher")
    slug = "physics/semantic-diff"

    base_payload = _draft_payload(slug, title="Semantic Base")
    base_payload["schema"]["summary"] = "Base learning path."
    base_payload["schema"]["courseUnit"] = {
        "courseId": "physics-course",
        "unitId": "energy-unit",
        "order": 1,
        "title": "Energy",
    }
    base_payload["schema"]["sections"] = [
        {
            "type": "learning-task",
            "title": "Observe",
            "summary": "Compare the baseline observation.",
            "props": {},
        },
        {
            "type": "experiment",
            "title": "Energy Lab",
            "summary": "Run the basic model.",
            "experimentId": "energy-conservation",
            "props": {"mode": "basic"},
        },
    ]
    base_payload["schema"]["sources"] = [
        {"label": "Teacher Guide", "url": "https://example.com/guide-v1"},
    ]
    base_draft_id = _create_draft_from_payload(client, teacher_token, base_payload)
    _submit_draft(client, teacher_token, base_draft_id)
    base_publish = _publish_draft(client, admin_token, base_draft_id, note="base semantic")

    target_payload = _draft_payload(slug, title="Semantic Target")
    target_payload["schema"]["summary"] = "Target learning path."
    target_payload["schema"]["courseUnit"] = {
        "courseId": "physics-course",
        "unitId": "energy-unit",
        "order": 2,
        "title": "Energy Extension",
    }
    target_payload["schema"]["sections"] = [
        {
            "type": "experiment",
            "title": "Energy Lab",
            "summary": "Run the guided model.",
            "experimentId": "energy-conservation",
            "props": {"mode": "guided"},
        },
        {
            "type": "assessment",
            "title": "Checkpoint",
            "summary": "Check conservation evidence.",
            "questionSetId": "energy-check",
            "props": {},
        },
        {
            "type": "learning-task",
            "title": "Observe",
            "summary": "Compare the baseline observation.",
            "props": {},
        },
    ]
    target_payload["schema"]["sources"] = [
        {"label": "Teacher Guide", "url": "https://example.com/guide-v2"},
        {"label": "Simulation Notes", "url": "https://example.com/sim-notes"},
    ]
    target_draft_id = _create_draft_from_payload(client, teacher_token, target_payload)
    _submit_draft(client, teacher_token, target_draft_id)
    target_publish = _publish_draft(client, admin_token, target_draft_id, note="target semantic")

    diff = client.get(
        f"/api/admin/content/page-versions/{target_publish['version_id']}/diff"
        f"?base_version_id={base_publish['version_id']}",
        headers=_auth_header(admin_token),
    )

    assert diff.status_code == 200
    body = diff.json()
    assert body["change_count"] >= 1
    semantic = body["semantic"]
    assert semantic["summary"]["semantic_changes"] >= 6
    assert {"field": "title", "before": "Semantic Base", "after": "Semantic Target"} in semantic["metadata_changes"]
    assert {"field": "summary", "before": "Base learning path.", "after": "Target learning path."} in semantic[
        "metadata_changes"
    ]
    assert {"field": "order", "before": 1, "after": 2} in semantic["course_unit_changes"]
    assert {"field": "title", "before": "Energy", "after": "Energy Extension"} in semantic["course_unit_changes"]

    sections = {change["key"]: change for change in semantic["section_changes"]}
    experiment = sections["section:experiment:energy-conservation"]
    assert experiment["action"] == "modified"
    assert experiment["moved"] is True
    assert experiment["index_before"] == 1
    assert experiment["index_after"] == 0
    assert {"field": "summary", "before": "Run the basic model.", "after": "Run the guided model."} in experiment[
        "field_changes"
    ]
    assert {"field": "props.mode", "before": "basic", "after": "guided"} in experiment["prop_changes"]
    assert sections["section:question-set:energy-check"]["action"] == "added"
    assert sections["section:learning-task:observe"]["action"] == "moved"

    sources = {change["key"]: change for change in semantic["source_changes"]}
    guide = sources["source:label:teacher guide"]
    assert guide["action"] == "modified"
    assert {
        "field": "url",
        "before": "https://example.com/guide-v1",
        "after": "https://example.com/guide-v2",
    } in guide["field_changes"]
    assert sources["source:label:simulation notes"]["action"] == "added"


def _create_draft(client, teacher_token: str, slug: str, title: str) -> int:
    return int(_create_draft_body(client, teacher_token, slug, title)["id"])


def _create_draft_body(client, teacher_token: str, slug: str, title: str) -> dict:
    return _create_draft_from_payload(client, teacher_token, _draft_payload(slug, title=title), return_id=False)


def _create_draft_from_payload(client, teacher_token: str, payload: dict, *, return_id: bool = True) -> int | dict:
    create = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=payload,
    )
    assert create.status_code == 201
    return int(create.json()["id"]) if return_id else create.json()


def _draft_update_payload(slug: str, title: str) -> dict:
    payload = _draft_payload(slug, title=title)
    return {"schema": payload["schema"], "allow_script": payload["allow_script"]}


def _submit_draft(client, teacher_token: str, draft_id: int, note: str = "Ready") -> dict:
    submit = client.post(
        f"/api/content/drafts/{draft_id}/submit",
        headers=_auth_header(teacher_token),
        json={"note": note},
    )
    assert submit.status_code == 200
    return submit.json()


def _publish_draft(client, admin_token: str, draft_id: int, note: str = "Publish") -> dict:
    publish = client.post(
        f"/api/content/drafts/{draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": note},
    )
    assert publish.status_code == 200
    return publish.json()


def _create_submit_publish(
    client,
    admin_token: str,
    teacher_token: str,
    slug: str,
    title: str,
) -> dict:
    draft_id = _create_draft(client, teacher_token, slug, title)
    _submit_draft(client, teacher_token, draft_id)
    return _publish_draft(client, admin_token, draft_id, note=title)


def _table_count(model) -> int:
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)
