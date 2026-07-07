from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import ClassJoinRequest, ClassMembership, SchoolMembership


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _bootstrap_admin(client, username: str = "admin_join_requests") -> str:
    response = client.post(
        "/api/admin/bootstrap",
        json={
            "username": username,
            "password": "secret123",
            "display_name": username.replace("_", " ").title(),
        },
    )
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    assert login.status_code == 200
    return login.json()["access_token"]


def _register_and_login(client, username: str, role: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "secret123",
            "display_name": username.title(),
            "role": role,
        },
    )
    assert response.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": username, "password": "secret123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _create_school_and_class(client, teacher_token: str, school_name: str, class_name: str) -> tuple[int, int]:
    school = client.post(
        "/api/schools",
        headers=_auth_header(teacher_token),
        json={"name": school_name, "region": "Shanghai"},
    )
    assert school.status_code == 201
    school_id = school.json()["id"]

    class_response = client.post(
        "/api/classes",
        headers=_auth_header(teacher_token),
        json={"school_id": school_id, "name": class_name, "grade": "10", "term": "2026A"},
    )
    assert class_response.status_code == 201
    return school_id, class_response.json()["id"]


def test_teacher_creates_school_class_and_student_joins(client):
    admin_token = _bootstrap_admin(client, "admin_class_members")
    teacher_token = _register_and_login(client, "teacher02", "teacher")
    student_token = _register_and_login(client, "student01", "student")
    outsider_teacher_token = _register_and_login(client, "teacher_member_outsider", "teacher")
    assistant_teacher_token = _register_and_login(client, "teacher_member_assistant", "teacher")

    school = client.post(
        "/api/schools",
        headers=_auth_header(teacher_token),
        json={"name": "Astra No.1 School", "region": "Shanghai"},
    )
    assert school.status_code == 201
    school_id = school.json()["id"]

    class_response = client.post(
        "/api/classes",
        headers=_auth_header(teacher_token),
        json={"school_id": school_id, "name": "Physics Class A", "grade": "10", "term": "2026A"},
    )
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    outsider_create = client.post(
        "/api/classes",
        headers=_auth_header(student_token),
        json={"school_id": school_id, "name": "Unauthorized Class"},
    )
    assert outsider_create.status_code == 403

    join = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(student_token),
        json={"role": "student"},
    )
    assert join.status_code == 201
    join_body = join.json()
    assert join_body["role"] == "student"
    student_membership_id = join_body["id"]
    student_me = client.get("/api/users/me", headers=_auth_header(student_token))
    assert student_me.status_code == 200
    student_id = student_me.json()["id"]
    assistant_teacher_me = client.get("/api/users/me", headers=_auth_header(assistant_teacher_token))
    assert assistant_teacher_me.status_code == 200
    assistant_teacher_id = assistant_teacher_me.json()["id"]

    with get_session_factory(get_settings().database_url)() as db:
        school_membership = db.scalar(
            select(SchoolMembership).where(
                SchoolMembership.school_id == school_id,
                SchoolMembership.user_id == student_id,
                SchoolMembership.role == "student",
            )
        )
        assert school_membership is not None
        class_membership = db.scalar(
            select(ClassMembership).where(
                ClassMembership.class_id == class_id,
                ClassMembership.user_id == student_id,
                ClassMembership.role == "student",
            )
        )
        assert class_membership is not None
        join_request = db.scalar(
            select(ClassJoinRequest).where(
                ClassJoinRequest.class_id == class_id,
                ClassJoinRequest.user_id == student_id,
                ClassJoinRequest.role == "student",
            )
        )
        assert join_request is None

    members = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(teacher_token))
    assert members.status_code == 200
    members_body = members.json()
    assert [(item["username"], item["role"]) for item in members_body] == [
        ("student01", "student"),
        ("teacher02", "teacher"),
    ]
    assert {item["username"]: item["user_status"] for item in members_body} == {
        "student01": "active",
        "teacher02": "active",
    }
    teacher_membership_id = next(item["id"] for item in members_body if item["username"] == "teacher02")

    student_members = client.get(
        f"/api/classes/{class_id}/members?role=student",
        headers=_auth_header(teacher_token),
    )
    assert student_members.status_code == 200
    assert [item["username"] for item in student_members.json()] == ["student01"]

    admin_members = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(admin_token))
    assert admin_members.status_code == 200
    assert {item["username"] for item in admin_members.json()} == {"teacher02", "student01"}

    student_forbidden = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(student_token))
    assert student_forbidden.status_code == 403
    assert student_forbidden.json()["detail"] == "Class members require class teacher scope"

    outsider_forbidden = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(outsider_teacher_token))
    assert outsider_forbidden.status_code == 403

    student_update_forbidden = client.patch(
        f"/api/classes/{class_id}/members/{student_membership_id}",
        headers=_auth_header(student_token),
        json={"status": "inactive"},
    )
    assert student_update_forbidden.status_code == 403
    assert student_update_forbidden.json()["detail"] == "Class member updates require class teacher scope"

    outsider_update_forbidden = client.patch(
        f"/api/classes/{class_id}/members/{student_membership_id}",
        headers=_auth_header(outsider_teacher_token),
        json={"status": "inactive"},
    )
    assert outsider_update_forbidden.status_code == 403

    teacher_member_update_forbidden = client.patch(
        f"/api/classes/{class_id}/members/{teacher_membership_id}",
        headers=_auth_header(teacher_token),
        json={"status": "inactive"},
    )
    assert teacher_member_update_forbidden.status_code == 403
    assert teacher_member_update_forbidden.json()["detail"] == "Only admins can update teacher class membership"

    unsupported_member_status = client.patch(
        f"/api/classes/{class_id}/members/{student_membership_id}",
        headers=_auth_header(teacher_token),
        json={"status": "archived"},
    )
    assert unsupported_member_status.status_code == 422

    missing_member_update = client.patch(
        f"/api/classes/{class_id}/members/999999",
        headers=_auth_header(admin_token),
        json={"status": "inactive"},
    )
    assert missing_member_update.status_code == 404

    other_class = client.post(
        "/api/classes",
        headers=_auth_header(teacher_token),
        json={"school_id": school_id, "name": "Physics Class B", "grade": "10", "term": "2026A"},
    )
    assert other_class.status_code == 201
    other_class_id = other_class.json()["id"]
    mismatched_member_update = client.patch(
        f"/api/classes/{other_class_id}/members/{student_membership_id}",
        headers=_auth_header(teacher_token),
        json={"status": "inactive"},
    )
    assert mismatched_member_update.status_code == 404

    inactive_update = client.patch(
        f"/api/classes/{class_id}/members/{student_membership_id}",
        headers={**_auth_header(teacher_token), "X-Request-ID": "class-member-inactive"},
        json={"status": "inactive", "note": "  roster cleanup  "},
    )
    assert inactive_update.status_code == 200
    inactive_update_body = inactive_update.json()
    assert inactive_update_body["id"] == student_membership_id
    assert inactive_update_body["status"] == "inactive"
    assert inactive_update_body["user_status"] == "active"

    update_audit = client.get(
        f"/api/admin/audit-logs?action=class.member.status.update&resource_id={student_membership_id}",
        headers=_auth_header(admin_token),
    )
    assert update_audit.status_code == 200
    assert update_audit.json()["total"] == 1
    audit_item = update_audit.json()["items"][0]
    assert audit_item["request_id"] == "class-member-inactive"
    assert audit_item["snapshot_json"]["before"]["status"] == "active"
    assert audit_item["snapshot_json"]["after"]["status"] == "inactive"
    assert audit_item["snapshot_json"]["after"]["has_note"] is True

    active_members = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(teacher_token))
    assert active_members.status_code == 200
    assert [item["username"] for item in active_members.json()] == ["teacher02"]

    inactive_members = client.get(
        f"/api/classes/{class_id}/members?status=inactive",
        headers=_auth_header(teacher_token),
    )
    assert inactive_members.status_code == 200
    assert [item["username"] for item in inactive_members.json()] == ["student01"]

    active_update = client.patch(
        f"/api/classes/{class_id}/members/{student_membership_id}",
        headers={**_auth_header(admin_token), "X-Request-ID": "class-member-active"},
        json={"status": "active"},
    )
    assert active_update.status_code == 200
    assert active_update.json()["status"] == "active"

    restored_active_members = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(teacher_token))
    assert restored_active_members.status_code == 200
    assert [(item["username"], item["role"]) for item in restored_active_members.json()] == [
        ("student01", "student"),
        ("teacher02", "teacher"),
    ]

    update_audits_after_restore = client.get(
        f"/api/admin/audit-logs?action=class.member.status.update&resource_id={student_membership_id}",
        headers=_auth_header(admin_token),
    )
    assert update_audits_after_restore.status_code == 200
    assert update_audits_after_restore.json()["total"] == 2

    unsupported_status = client.get(
        f"/api/classes/{class_id}/members?status=archived",
        headers=_auth_header(teacher_token),
    )
    assert unsupported_status.status_code == 400
    assert unsupported_status.json()["detail"] == "Unsupported class member status"

    missing_class_members = client.get("/api/classes/999999/members", headers=_auth_header(admin_token))
    assert missing_class_members.status_code == 404

    student_classes = client.get(f"/api/classes?school_id={school_id}", headers=_auth_header(student_token))
    assert student_classes.status_code == 200
    assert student_classes.json()[0]["id"] == class_id

    teacher_classes = client.get(f"/api/schools/{school_id}/classes", headers=_auth_header(teacher_token))
    assert teacher_classes.status_code == 200
    assert teacher_classes.json()[0]["name"] == "Physics Class A"

    last_teacher_blocked = client.patch(
        f"/api/classes/{class_id}/members/{teacher_membership_id}",
        headers=_auth_header(admin_token),
        json={"status": "inactive"},
    )
    assert last_teacher_blocked.status_code == 409
    assert last_teacher_blocked.json()["detail"] == "Cannot deactivate the last active class teacher"

    with get_session_factory(get_settings().database_url)() as db:
        db.add(SchoolMembership(school_id=school_id, user_id=assistant_teacher_id, role="teacher"))
        db.add(ClassMembership(class_id=class_id, user_id=assistant_teacher_id, role="teacher"))
        db.commit()

    teacher_inactive_update = client.patch(
        f"/api/classes/{class_id}/members/{teacher_membership_id}",
        headers={**_auth_header(admin_token), "X-Request-ID": "class-teacher-inactive"},
        json={"status": "inactive"},
    )
    assert teacher_inactive_update.status_code == 200
    assert teacher_inactive_update.json()["role"] == "teacher"
    assert teacher_inactive_update.json()["status"] == "inactive"

    inactive_teacher_members = client.get(
        f"/api/classes/{class_id}/members?role=teacher&status=inactive",
        headers=_auth_header(admin_token),
    )
    assert inactive_teacher_members.status_code == 200
    assert [item["username"] for item in inactive_teacher_members.json()] == ["teacher02"]

    active_teacher_members = client.get(
        f"/api/classes/{class_id}/members?role=teacher",
        headers=_auth_header(admin_token),
    )
    assert active_teacher_members.status_code == 200
    assert [item["username"] for item in active_teacher_members.json()] == ["teacher_member_assistant"]

    teacher_after_inactive = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(teacher_token))
    assert teacher_after_inactive.status_code == 403
    assert teacher_after_inactive.json()["detail"] == "Class members require class teacher scope"

    teacher_update_audit = client.get(
        f"/api/admin/audit-logs?action=class.member.status.update&resource_id={teacher_membership_id}",
        headers=_auth_header(admin_token),
    )
    assert teacher_update_audit.status_code == 200
    assert teacher_update_audit.json()["total"] == 1
    teacher_audit_item = teacher_update_audit.json()["items"][0]
    assert teacher_audit_item["request_id"] == "class-teacher-inactive"
    assert teacher_audit_item["snapshot_json"]["before"]["role"] == "teacher"
    assert teacher_audit_item["snapshot_json"]["before"]["status"] == "active"
    assert teacher_audit_item["snapshot_json"]["after"]["status"] == "inactive"


def test_teacher_cannot_self_join_other_school_class_as_teacher(client):
    owner_token = _register_and_login(client, "teacher_owner_scope", "teacher")
    outsider_teacher_token = _register_and_login(client, "teacher_outside_scope", "teacher")

    school = client.post(
        "/api/schools",
        headers=_auth_header(owner_token),
        json={"name": "Astra Scoped School", "region": "Shanghai"},
    )
    assert school.status_code == 201
    school_id = school.json()["id"]

    class_response = client.post(
        "/api/classes",
        headers=_auth_header(owner_token),
        json={"school_id": school_id, "name": "Scoped Class", "grade": "10"},
    )
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    join_as_teacher = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(outsider_teacher_token),
        json={"role": "teacher"},
    )
    assert join_as_teacher.status_code == 403


def test_class_join_request_requires_teacher_approval(client):
    admin_token = _bootstrap_admin(client, "admin_join_request_audit")
    teacher_token = _register_and_login(client, "teacher_join_request", "teacher")
    outsider_teacher_token = _register_and_login(client, "teacher_join_outsider", "teacher")
    student_token = _register_and_login(client, "student_join_request", "student")

    school_id, class_id = _create_school_and_class(
        client,
        teacher_token,
        "Astra Approval School",
        "Approval Physics",
    )

    invisible_before = client.get(f"/api/classes?school_id={school_id}", headers=_auth_header(student_token))
    assert invisible_before.status_code == 403

    join_request = client.post(
        f"/api/classes/{class_id}/join-requests",
        headers={**_auth_header(student_token), "X-Request-ID": "join-request-create"},
        json={"role": "student", "message": "  Please add me.  "},
    )
    assert join_request.status_code == 201
    join_request_body = join_request.json()
    assert join_request_body["role"] == "student"
    assert join_request_body["status"] == "pending"
    assert join_request_body["message"] == "Please add me."

    duplicate = client.post(
        f"/api/classes/{class_id}/join-requests",
        headers=_auth_header(student_token),
        json={"role": "student"},
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == join_request_body["id"]

    student_list = client.get(f"/api/classes/{class_id}/join-requests", headers=_auth_header(student_token))
    assert student_list.status_code == 403

    outsider_list = client.get(f"/api/classes/{class_id}/join-requests", headers=_auth_header(outsider_teacher_token))
    assert outsider_list.status_code == 403

    pending_requests = client.get(f"/api/classes/{class_id}/join-requests", headers=_auth_header(teacher_token))
    assert pending_requests.status_code == 200
    assert [item["id"] for item in pending_requests.json()] == [join_request_body["id"]]

    members_before_approval = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(teacher_token))
    assert members_before_approval.status_code == 200
    assert [item["username"] for item in members_before_approval.json()] == ["teacher_join_request"]

    approval = client.patch(
        f"/api/classes/{class_id}/join-requests/{join_request_body['id']}",
        headers={**_auth_header(teacher_token), "X-Request-ID": "join-request-approve"},
        json={"status": "approved", "note": "Welcome"},
    )
    assert approval.status_code == 200
    approval_body = approval.json()
    assert approval_body["status"] == "approved"
    assert approval_body["reviewed_by_user_id"] is not None
    assert approval_body["reviewed_at"] is not None

    members_after_approval = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(teacher_token))
    assert members_after_approval.status_code == 200
    assert {item["username"] for item in members_after_approval.json()} == {
        "teacher_join_request",
        "student_join_request",
    }

    repeat_approval = client.patch(
        f"/api/classes/{class_id}/join-requests/{join_request_body['id']}",
        headers=_auth_header(teacher_token),
        json={"status": "approved", "note": "Already approved"},
    )
    assert repeat_approval.status_code == 200
    assert repeat_approval.json()["id"] == join_request_body["id"]
    assert repeat_approval.json()["status"] == "approved"

    reverse_rejection = client.patch(
        f"/api/classes/{class_id}/join-requests/{join_request_body['id']}",
        headers=_auth_header(teacher_token),
        json={"status": "rejected", "note": "Too late"},
    )
    assert reverse_rejection.status_code == 409

    student_classes = client.get(f"/api/classes?school_id={school_id}", headers=_auth_header(student_token))
    assert student_classes.status_code == 200
    assert student_classes.json()[0]["id"] == class_id

    create_audit = client.get(
        f"/api/admin/audit-logs?action=class.join.request.create&class_id={class_id}",
        headers=_auth_header(admin_token),
    )
    assert create_audit.status_code == 200
    assert create_audit.json()["total"] == 1
    assert create_audit.json()["items"][0]["request_id"] == "join-request-create"

    review_audit = client.get(
        f"/api/admin/audit-logs?action=class.join.request.approve&class_id={class_id}",
        headers=_auth_header(admin_token),
    )
    assert review_audit.status_code == 200
    assert review_audit.json()["total"] == 1
    assert review_audit.json()["items"][0]["request_id"] == "join-request-approve"
    assert review_audit.json()["items"][0]["snapshot_json"]["after"]["status"] == "approved"

    join_audit = client.get(
        f"/api/admin/audit-logs?action=class.join&class_id={class_id}",
        headers=_auth_header(admin_token),
    )
    assert join_audit.status_code == 200
    assert join_audit.json()["total"] == 1
    assert join_audit.json()["items"][0]["snapshot_json"]["after"]["source_join_request_id"] == join_request_body["id"]


def test_rejected_class_join_request_can_be_reopened(client):
    teacher_token = _register_and_login(client, "teacher_reopen_request", "teacher")
    student_token = _register_and_login(client, "student_reopen_request", "student")
    school_id, class_id = _create_school_and_class(
        client,
        teacher_token,
        "Astra Reopen School",
        "Reopen Physics",
    )

    join_request = client.post(
        f"/api/classes/{class_id}/join-requests",
        headers=_auth_header(student_token),
        json={"role": "student", "message": "First try"},
    )
    assert join_request.status_code == 201
    join_request_id = join_request.json()["id"]

    rejected = client.patch(
        f"/api/classes/{class_id}/join-requests/{join_request_id}",
        headers=_auth_header(teacher_token),
        json={"status": "rejected", "note": "Need school code"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    still_invisible = client.get(f"/api/classes?school_id={school_id}", headers=_auth_header(student_token))
    assert still_invisible.status_code == 403

    reopened = client.post(
        f"/api/classes/{class_id}/join-requests",
        headers=_auth_header(student_token),
        json={"role": "student", "message": "School code confirmed"},
    )
    assert reopened.status_code == 201
    reopened_body = reopened.json()
    assert reopened_body["id"] == join_request_id
    assert reopened_body["status"] == "pending"
    assert reopened_body["message"] == "School code confirmed"
    assert reopened_body["reviewed_by_user_id"] is None
    assert reopened_body["reviewed_at"] is None
    assert reopened_body["review_note"] is None

    rejected_requests = client.get(
        f"/api/classes/{class_id}/join-requests?status=rejected",
        headers=_auth_header(teacher_token),
    )
    assert rejected_requests.status_code == 200
    assert rejected_requests.json() == []


def test_legacy_join_approves_existing_pending_join_request(client):
    admin_token = _bootstrap_admin(client, "admin_legacy_direct_join")
    teacher_token = _register_and_login(client, "teacher_legacy_join", "teacher")
    student_token = _register_and_login(client, "student_legacy_join", "student")
    _, class_id = _create_school_and_class(
        client,
        teacher_token,
        "Astra Legacy Join School",
        "Legacy Join Physics",
    )

    join_request = client.post(
        f"/api/classes/{class_id}/join-requests",
        headers=_auth_header(student_token),
        json={"role": "student"},
    )
    assert join_request.status_code == 201
    join_request_id = join_request.json()["id"]

    pending_stats = client.get("/api/admin/stats", headers=_auth_header(admin_token))
    assert pending_stats.status_code == 200
    assert pending_stats.json()["pending_class_join_requests"] == 1

    legacy_join = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(student_token),
        json={"role": "student"},
    )
    assert legacy_join.status_code == 201
    assert legacy_join.json()["role"] == "student"

    approved_requests = client.get(
        f"/api/classes/{class_id}/join-requests?status=approved",
        headers=_auth_header(teacher_token),
    )
    assert approved_requests.status_code == 200
    assert len(approved_requests.json()) == 1
    assert approved_requests.json()[0]["id"] == join_request_id
    assert approved_requests.json()[0]["status"] == "approved"
    assert approved_requests.json()[0]["reviewed_by_user_id"] is not None
    assert approved_requests.json()[0]["reviewed_at"] is not None
    assert approved_requests.json()[0]["review_note"] == "approved by legacy direct join"

    pending_stats_after_join = client.get("/api/admin/stats", headers=_auth_header(admin_token))
    assert pending_stats_after_join.status_code == 200
    assert pending_stats_after_join.json()["pending_class_join_requests"] == 0

    approval_audit = client.get(
        f"/api/admin/audit-logs?action=class.join.request.approve&resource_id={join_request_id}",
        headers=_auth_header(admin_token),
    )
    assert approval_audit.status_code == 200
    assert approval_audit.json()["total"] == 1
    approval_snapshot = approval_audit.json()["items"][0]["snapshot_json"]
    assert approval_snapshot["after"]["approval_source"] == "legacy_direct_join"
    assert approval_snapshot["after"]["membership_created"] is True
