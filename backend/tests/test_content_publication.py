from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import ContentPageRecord, ContentPageVersion


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
                    "props": {"scriptPath": "drafts/custom-publish.js"} if allow_script else {},
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

    versions = client.get(f"/api/admin/content/page-versions?slug={slug}", headers=_auth_header(admin_token))
    assert versions.status_code == 200
    assert versions.json()["total"] == 1
    version_item = versions.json()["items"][0]
    assert version_item["id"] == publication["version_id"]
    assert version_item["schema_hash"] == publication["schema_hash"]
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
    assert first_publish.json()["version"] == "v1"

    second_draft_id = _create_draft(client, teacher_token, slug, "Experimental Energy Page")
    _submit_draft(client, teacher_token, second_draft_id)
    second_publish = client.post(
        f"/api/content/drafts/{second_draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "experiment"},
    )
    assert second_publish.status_code == 200
    second_version_id = second_publish.json()["version_id"]
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
    assert versions.json()["items"][0]["restored_from_version_id"] == first_version_id

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


def _create_draft(client, teacher_token: str, slug: str, title: str) -> int:
    create = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload(slug, title=title),
    )
    assert create.status_code == 201
    return int(create.json()["id"])


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
