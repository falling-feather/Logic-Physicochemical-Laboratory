from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import ContentPageRecord


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _bootstrap_admin(client, username: str = "admin_content") -> str:
    response = client.post(
        "/api/admin/bootstrap",
        json={
            "username": username,
            "password": "secret123",
            "display_name": "Content Admin",
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


def _draft_payload(slug: str, *, allow_script: bool = False) -> dict:
    return {
        "target_slug": slug,
        "allow_script": allow_script,
        "schema": {
            "slug": slug,
            "galaxy": "englab",
            "subject": "physics",
            "title": "Teacher Draft Energy",
            "layout": "experiment-page",
            "status": "draft",
            "version": "draft-1",
            "summary": "A teacher-authored draft that is not public yet.",
            "sections": [
                {
                    "type": "learning-task",
                    "title": "Observe",
                    "summary": "Explain what changes when friction is introduced.",
                    "props": {"scriptPath": "drafts/custom-energy.js"} if allow_script else {},
                }
            ],
            "sources": [],
        },
    }


def _draft_update_payload(slug: str, *, allow_script: bool | None = None) -> dict:
    payload = {"schema": _draft_payload(slug, allow_script=bool(allow_script))["schema"]}
    if allow_script is not None:
        payload["allow_script"] = allow_script
    return payload


def test_teacher_creates_content_draft_without_publishing(client):
    unauthenticated = client.post("/api/content/drafts", json=_draft_payload("physics/private-energy"))
    assert unauthenticated.status_code == 401

    admin_token = _bootstrap_admin(client)
    teacher_id, teacher_token = _register_and_login(client, "teacher_content_draft", "teacher")
    _, student_token = _register_and_login(client, "student_content_draft", "student")
    before_page_count = _table_count(ContentPageRecord)

    student_forbidden = client.post(
        "/api/content/drafts",
        headers=_auth_header(student_token),
        json=_draft_payload("physics/private-energy"),
    )
    assert student_forbidden.status_code == 403

    create = client.post(
        "/api/content/drafts",
        headers={**_auth_header(teacher_token), "X-Request-ID": "draft-create-request"},
        json=_draft_payload("physics/private-energy"),
    )
    assert create.status_code == 201
    draft = create.json()
    draft_id = draft["id"]
    assert draft["author_user_id"] == teacher_id
    assert draft["target_slug"] == "physics/private-energy"
    assert draft["status"] == "draft"
    assert draft["allow_script"] is False
    assert len(draft["schema_hash"]) == 64
    assert draft["base_version_id"] is None
    assert draft["base_schema_hash"] is None
    assert draft["script_risk_level"] == "none"
    assert draft["script_analysis"]["status"] == "clean"
    assert draft["script_analysis"]["schema_hash"] == draft["schema_hash"]
    assert draft["script_analysis"]["finding_count"] == 0
    assert draft["script_review_status"] == "not_required"
    assert draft["submitted_at"] is None
    assert draft["withdrawn_at"] is None
    assert draft["change_requested_at"] is None
    assert draft["published_version_id"] is None
    assert draft["schema"]["slug"] == "physics/private-energy"

    duplicate = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload("physics/private-energy"),
    )
    assert duplicate.status_code == 409

    render = client.get("/api/render/page/physics/private-energy")
    assert render.status_code == 404
    content_page = client.get("/api/content/pages/physics/private-energy")
    assert content_page.status_code == 404
    assert _table_count(ContentPageRecord) == before_page_count

    teacher_queue_forbidden = client.get("/api/admin/content/drafts", headers=_auth_header(teacher_token))
    assert teacher_queue_forbidden.status_code == 403

    admin_queue = client.get("/api/admin/content/drafts?q=private-energy", headers=_auth_header(admin_token))
    assert admin_queue.status_code == 200
    assert admin_queue.json()["total"] == 1
    queue_item = admin_queue.json()["items"][0]
    assert queue_item["id"] == draft_id
    assert queue_item["author_username"] == "teacher_content_draft"

    audit = client.get(
        f"/api/admin/audit-logs?action=content.draft.create&resource_id={draft_id}",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    audit_item = audit.json()["items"][0]
    assert audit_item["request_id"] == "draft-create-request"
    assert audit_item["resource_type"] == "content_draft"
    assert audit_item["event_result"] == "success"
    assert audit_item["snapshot_json"]["after"]["target_slug"] == "physics/private-energy"
    assert "schema" not in audit_item["snapshot_json"]["after"]

    review_no_script = client.patch(
        f"/api/content/drafts/{draft_id}/script-review",
        headers=_auth_header(admin_token),
        json={"status": "approved", "note": "No script to review"},
    )
    assert review_no_script.status_code == 409


def test_content_draft_submit_request_changes_resubmit_and_withdraw(client):
    admin_token = _bootstrap_admin(client, username="admin_workflow")
    _, teacher_token = _register_and_login(client, "teacher_workflow", "teacher")
    _, other_teacher_token = _register_and_login(client, "teacher_workflow_other", "teacher")
    slug = "physics/workflow-draft"

    create = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload(slug),
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]

    non_author_submit = client.post(
        f"/api/content/drafts/{draft_id}/submit",
        headers=_auth_header(other_teacher_token),
        json={"note": "I should not submit this"},
    )
    assert non_author_submit.status_code == 403

    submit = client.post(
        f"/api/content/drafts/{draft_id}/submit",
        headers={**_auth_header(teacher_token), "X-Request-ID": "draft-submit-request"},
        json={"note": "Ready for review"},
    )
    assert submit.status_code == 200
    submitted = submit.json()
    assert submitted["status"] == "submitted"
    assert submitted["submitted_at"] is not None

    duplicate_active = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload(slug),
    )
    assert duplicate_active.status_code == 409

    queue = client.get(
        "/api/admin/content/drafts?status=submitted&q=workflow-draft",
        headers=_auth_header(admin_token),
    )
    assert queue.status_code == 200
    assert queue.json()["total"] == 1
    assert queue.json()["items"][0]["submitted_at"] is not None

    teacher_request_changes = client.post(
        f"/api/content/drafts/{draft_id}/request-changes",
        headers=_auth_header(teacher_token),
        json={"note": "please revise"},
    )
    assert teacher_request_changes.status_code == 403

    request_changes = client.post(
        f"/api/content/drafts/{draft_id}/request-changes",
        headers={**_auth_header(admin_token), "X-Request-ID": "draft-request-changes"},
        json={"note": "Add clearer evidence prompts"},
    )
    assert request_changes.status_code == 200
    changed = request_changes.json()
    assert changed["status"] == "changes_requested"
    assert changed["change_requested_by_user_id"] is not None
    assert changed["change_requested_at"] is not None
    assert changed["change_request_note"] == "Add clearer evidence prompts"

    publish_changes_requested = client.post(
        f"/api/content/drafts/{draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "publish too soon"},
    )
    assert publish_changes_requested.status_code == 409

    resubmit = client.post(
        f"/api/content/drafts/{draft_id}/submit",
        headers=_auth_header(teacher_token),
        json={"note": "Revised"},
    )
    assert resubmit.status_code == 200
    assert resubmit.json()["status"] == "submitted"

    withdraw = client.post(
        f"/api/content/drafts/{draft_id}/withdraw",
        headers=_auth_header(teacher_token),
        json={"note": "Use a fresh version instead"},
    )
    assert withdraw.status_code == 200
    assert withdraw.json()["status"] == "withdrawn"
    assert withdraw.json()["withdrawn_at"] is not None

    submit_withdrawn = client.post(
        f"/api/content/drafts/{draft_id}/submit",
        headers=_auth_header(teacher_token),
        json={"note": "revive"},
    )
    assert submit_withdrawn.status_code == 409

    publish_withdrawn = client.post(
        f"/api/content/drafts/{draft_id}/publish",
        headers=_auth_header(admin_token),
        json={"note": "cannot publish"},
    )
    assert publish_withdrawn.status_code == 409

    replacement = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload(slug),
    )
    assert replacement.status_code == 201

    audit = client.get(
        f"/api/admin/audit-logs?action=content.draft.request_changes&resource_id={draft_id}",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    audit_item = audit.json()["items"][0]
    assert audit_item["request_id"] == "draft-request-changes"
    assert audit_item["snapshot_json"]["note"] == "Add clearer evidence prompts"
    assert "schema" not in audit_item["snapshot_json"]["before"]
    assert "schema" not in audit_item["snapshot_json"]["after"]


def test_content_draft_update_resets_script_review_and_records_audit(client):
    admin_token = _bootstrap_admin(client, username="admin_update_draft")
    _, teacher_token = _register_and_login(client, "teacher_update_draft", "teacher")
    _, other_teacher_token = _register_and_login(client, "teacher_update_other", "teacher")
    slug = "physics/update-draft"

    create = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload(slug, allow_script=True),
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]
    original_hash = create.json()["schema_hash"]

    approve = client.patch(
        f"/api/content/drafts/{draft_id}/script-review",
        headers=_auth_header(admin_token),
        json={"status": "approved", "note": "Temporary script approved"},
    )
    assert approve.status_code == 200
    assert approve.json()["script_review_status"] == "approved"
    assert approve.json()["script_reviewed_by_user_id"] is not None

    other_teacher_update = client.patch(
        f"/api/content/drafts/{draft_id}",
        headers=_auth_header(other_teacher_token),
        json=_draft_update_payload(slug) | {"note": "Out of scope"},
    )
    assert other_teacher_update.status_code == 403

    submit = client.post(
        f"/api/content/drafts/{draft_id}/submit",
        headers=_auth_header(teacher_token),
        json={"note": "Ready"},
    )
    assert submit.status_code == 200
    submitted_update = client.patch(
        f"/api/content/drafts/{draft_id}",
        headers=_auth_header(teacher_token),
        json=_draft_update_payload(slug) | {"note": "Edit during review"},
    )
    assert submitted_update.status_code == 409
    assert submitted_update.json()["detail"] == "Content draft cannot be updated from its current status"

    request_changes = client.post(
        f"/api/content/drafts/{draft_id}/request-changes",
        headers=_auth_header(admin_token),
        json={"note": "Remove custom script before publishing"},
    )
    assert request_changes.status_code == 200
    assert request_changes.json()["status"] == "changes_requested"

    revised_payload = _draft_update_payload(slug, allow_script=False)
    revised_payload["schema"]["title"] = "Revised Teacher Draft Energy"
    revised_payload["schema"]["summary"] = "A script-free revision after review feedback."
    revised_payload["schema"]["sections"][0]["summary"] = "Explain the friction tradeoff without custom code."
    revised_payload["note"] = "Removed script and clarified task"
    update = client.patch(
        f"/api/content/drafts/{draft_id}",
        headers={**_auth_header(teacher_token), "X-Request-ID": "draft-update-request"},
        json=revised_payload,
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["status"] == "changes_requested"
    assert updated["title"] == "Revised Teacher Draft Energy"
    assert updated["schema_hash"] != original_hash
    assert updated["schema"]["summary"] == "A script-free revision after review feedback."
    assert updated["base_version_id"] is None
    assert updated["base_schema_hash"] is None
    assert updated["allow_script"] is False
    assert updated["script_risk_level"] == "none"
    assert updated["script_analysis"]["status"] == "clean"
    assert updated["script_analysis"]["schema_hash"] == updated["schema_hash"]
    assert updated["script_review_status"] == "not_required"
    assert updated["script_reviewed_by_user_id"] is None
    assert updated["script_reviewed_at"] is None
    assert updated["script_review_note"] is None

    blocked_payload = _draft_update_payload(slug, allow_script=True)
    blocked_payload["schema"]["sections"][0]["props"]["scriptUrl"] = "javascript:alert(1)"
    blocked_update = client.patch(
        f"/api/content/drafts/{draft_id}",
        headers=_auth_header(teacher_token),
        json=blocked_payload,
    )
    assert blocked_update.status_code == 422
    assert blocked_update.json()["detail"] == "Content schema contains blocked script policy findings"

    audit = client.get(
        f"/api/admin/audit-logs?action=content.draft.update&resource_id={draft_id}",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    audit_item = audit.json()["items"][0]
    assert audit_item["request_id"] == "draft-update-request"
    assert audit_item["snapshot_json"]["note"] == "Removed script and clarified task"
    assert audit_item["snapshot_json"]["changes"]["schema_hash"]["from"] == original_hash
    assert audit_item["snapshot_json"]["changes"]["script_review_status"] == {
        "from": "approved",
        "to": "not_required",
    }
    assert "schema" not in audit_item["snapshot_json"]["before"]
    assert "schema" not in audit_item["snapshot_json"]["after"]


def test_content_draft_validates_schema_and_slug(client):
    _, teacher_token = _register_and_login(client, "teacher_content_validation", "teacher")

    mismatch = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload("physics/target-mismatch") | {"schema": _draft_payload("physics/schema-mismatch")["schema"]},
    )
    assert mismatch.status_code == 422

    invalid_slug = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload("../private"),
    )
    assert invalid_slug.status_code == 422

    invalid_section = _draft_payload("physics/invalid-section")
    invalid_section["schema"]["sections"][0]["type"] = "script"
    invalid_schema = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=invalid_section,
    )
    assert invalid_schema.status_code == 422

    hidden_script = _draft_payload("physics/hidden-script")
    hidden_script["schema"]["sections"][0]["props"]["scriptPath"] = "drafts/hidden.js"
    hidden_script_response = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=hidden_script,
    )
    assert hidden_script_response.status_code == 422

    blocked_script = _draft_payload("physics/blocked-script", allow_script=True)
    blocked_script["schema"]["sections"][0]["props"]["scriptUrl"] = "javascript:alert(1)"
    blocked_script_response = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=blocked_script,
    )
    assert blocked_script_response.status_code == 422
    assert blocked_script_response.json()["detail"] == "Content schema contains blocked script policy findings"

    create = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload("physics/update-validation"),
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]

    update_mismatch = _draft_update_payload("physics/retargeted-update")
    update_slug_mismatch = client.patch(
        f"/api/content/drafts/{draft_id}",
        headers=_auth_header(teacher_token),
        json=update_mismatch,
    )
    assert update_slug_mismatch.status_code == 422
    assert update_slug_mismatch.json()["detail"] == "schema.slug must match draft target_slug"

    forbidden_field = _draft_update_payload("physics/update-validation") | {"target_slug": "physics/other-target"}
    forbidden_field_response = client.patch(
        f"/api/content/drafts/{draft_id}",
        headers=_auth_header(teacher_token),
        json=forbidden_field,
    )
    assert forbidden_field_response.status_code == 422


def test_admin_reviews_script_draft_and_records_audit(client):
    first_admin_token = _bootstrap_admin(client, username="admin_content_first")
    second_admin_id, second_admin_token = _register_and_login(client, "admin_content_second", "teacher")
    promote_second_admin = client.patch(
        f"/api/admin/users/{second_admin_id}",
        headers=_auth_header(first_admin_token),
        json={"role": "admin"},
    )
    assert promote_second_admin.status_code == 200
    teacher_id, teacher_token = _register_and_login(client, "teacher_script_draft", "teacher")
    _, student_token = _register_and_login(client, "student_script_draft", "student")

    create = client.post(
        "/api/content/drafts",
        headers=_auth_header(teacher_token),
        json=_draft_payload("physics/script-draft", allow_script=True),
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]
    assert create.json()["script_review_status"] == "pending"
    assert create.json()["script_risk_level"] == "medium"
    assert create.json()["script_analysis"]["status"] == "review_required"
    assert create.json()["script_analysis"]["schema_hash"] == create.json()["schema_hash"]
    assert create.json()["script_analysis"]["finding_count"] == 1
    finding = create.json()["script_analysis"]["findings"][0]
    assert finding["code"] == "script_reference"
    assert finding["path"] == "$.sections[0].props.scriptPath"
    assert finding["value_preview"] == "drafts/custom-energy.js"
    assert create.json()["author_user_id"] == teacher_id

    teacher_review = client.patch(
        f"/api/content/drafts/{draft_id}/script-review",
        headers=_auth_header(teacher_token),
        json={"status": "approved", "note": "self review"},
    )
    assert teacher_review.status_code == 403

    student_review = client.patch(
        f"/api/content/drafts/{draft_id}/script-review",
        headers=_auth_header(student_token),
        json={"status": "approved", "note": "student review"},
    )
    assert student_review.status_code == 403

    approve = client.patch(
        f"/api/content/drafts/{draft_id}/script-review",
        headers={**_auth_header(second_admin_token), "X-Request-ID": "script-review-approve"},
        json={"status": "approved", "note": "Script path approved for controlled trial"},
    )
    assert approve.status_code == 200
    reviewed = approve.json()
    assert reviewed["script_review_status"] == "approved"
    assert reviewed["script_reviewed_by_user_id"] == second_admin_id
    assert reviewed["script_reviewed_at"] is not None
    assert reviewed["script_review_note"] == "Script path approved for controlled trial"

    queue = client.get(
        "/api/admin/content/drafts?script_review_status=approved&script_risk_level=medium&q=script-draft",
        headers=_auth_header(first_admin_token),
    )
    assert queue.status_code == 200
    assert queue.json()["total"] == 1
    assert queue.json()["items"][0]["id"] == draft_id
    assert queue.json()["items"][0]["script_risk_level"] == "medium"
    assert queue.json()["items"][0]["script_analysis"]["finding_count"] == 1

    stats = client.get("/api/admin/stats", headers=_auth_header(first_admin_token))
    assert stats.status_code == 200
    assert stats.json()["total_content_drafts"] == 1
    assert stats.json()["pending_script_reviews"] == 0

    audit = client.get(
        f"/api/admin/audit-logs?action=content.draft.script_review.approved&resource_id={draft_id}",
        headers=_auth_header(first_admin_token),
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    audit_item = audit.json()["items"][0]
    assert audit_item["request_id"] == "script-review-approve"
    assert audit_item["snapshot_json"]["changes"]["script_review_status"] == {
        "from": "pending",
        "to": "approved",
    }
    assert audit_item["snapshot_json"]["before"]["script_analysis"]["finding_count"] == 1
    assert "schema" not in audit_item["snapshot_json"]["before"]
    assert "schema" not in audit_item["snapshot_json"]["after"]


def test_admin_cannot_review_own_script_draft(client):
    admin_token = _bootstrap_admin(client, username="admin_own_draft")
    create = client.post(
        "/api/content/drafts",
        headers=_auth_header(admin_token),
        json=_draft_payload("physics/admin-script-draft", allow_script=True),
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]

    review = client.patch(
        f"/api/content/drafts/{draft_id}/script-review",
        headers=_auth_header(admin_token),
        json={"status": "approved", "note": "own script"},
    )
    assert review.status_code == 403


def _table_count(model) -> int:
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)
