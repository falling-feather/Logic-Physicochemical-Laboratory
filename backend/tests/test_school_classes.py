from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import ClassJoinRequest, ClassMembership, SchoolMembership, User


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Cookie": ""}


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
    same_school_teacher_token = _register_and_login(client, "teacher_same_school_scope", "teacher")
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

    same_school_teacher_me = client.get("/api/users/me", headers=_auth_header(same_school_teacher_token))
    assert same_school_teacher_me.status_code == 200
    same_school_teacher_id = same_school_teacher_me.json()["id"]
    with get_session_factory(get_settings().database_url)() as db:
        db.add(SchoolMembership(school_id=school_id, user_id=same_school_teacher_id, role="teacher"))
        db.commit()

    same_school_direct_join = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(same_school_teacher_token),
        json={"role": "teacher"},
    )
    assert same_school_direct_join.status_code == 403
    assert same_school_direct_join.json()["detail"] == "Teacher class join requires approval"

    teacher_join_request = client.post(
        f"/api/classes/{class_id}/join-requests",
        headers={**_auth_header(same_school_teacher_token), "X-Request-ID": "teacher-join-request"},
        json={"role": "teacher", "message": "  Please add me as co-teacher.  "},
    )
    assert teacher_join_request.status_code == 201
    assert teacher_join_request.json()["status"] == "pending"
    assert teacher_join_request.json()["message"] == "Please add me as co-teacher."

    approved_teacher = client.patch(
        f"/api/classes/{class_id}/join-requests/{teacher_join_request.json()['id']}",
        headers={**_auth_header(owner_token), "X-Request-ID": "teacher-join-approve"},
        json={"status": "approved", "note": "approved"},
    )
    assert approved_teacher.status_code == 200
    assert approved_teacher.json()["status"] == "approved"

    teacher_members = client.get(
        f"/api/classes/{class_id}/members?role=teacher",
        headers=_auth_header(owner_token),
    )
    assert teacher_members.status_code == 200
    assert {item["username"] for item in teacher_members.json()} == {
        "teacher_owner_scope",
        "teacher_same_school_scope",
    }

    join_as_teacher = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(outsider_teacher_token),
        json={"role": "teacher"},
    )
    assert join_as_teacher.status_code == 403


def test_admin_transfers_class_teacher_membership_scope(client):
    admin_token = _bootstrap_admin(client, "admin_teacher_transfer")
    owner_token = _register_and_login(client, "teacher_transfer_owner", "teacher")
    target_token = _register_and_login(client, "teacher_transfer_target", "teacher")
    outsider_token = _register_and_login(client, "teacher_transfer_outside", "teacher")
    student_token = _register_and_login(client, "student_transfer_target", "student")

    school_id, class_id = _create_school_and_class(
        client,
        owner_token,
        "Astra Teacher Transfer School",
        "Teacher Transfer Physics",
    )

    owner_members = client.get(
        f"/api/classes/{class_id}/members?role=teacher",
        headers=_auth_header(owner_token),
    )
    assert owner_members.status_code == 200
    owner_membership_id = owner_members.json()[0]["id"]

    target_me = client.get("/api/users/me", headers=_auth_header(target_token))
    assert target_me.status_code == 200
    target_user_id = target_me.json()["id"]
    outsider_me = client.get("/api/users/me", headers=_auth_header(outsider_token))
    assert outsider_me.status_code == 200
    outsider_user_id = outsider_me.json()["id"]
    student_me = client.get("/api/users/me", headers=_auth_header(student_token))
    assert student_me.status_code == 200
    student_user_id = student_me.json()["id"]

    with get_session_factory(get_settings().database_url)() as db:
        db.add(SchoolMembership(school_id=school_id, user_id=target_user_id, role="teacher", status="inactive"))
        db.add(SchoolMembership(school_id=school_id, user_id=student_user_id, role="student", status="active"))
        db.commit()

    teacher_forbidden = client.post(
        f"/api/classes/{class_id}/teachers/transfer",
        headers=_auth_header(owner_token),
        json={"source_membership_id": owner_membership_id, "target_user_id": target_user_id},
    )
    assert teacher_forbidden.status_code == 403
    assert teacher_forbidden.json()["detail"] == "Only admins can transfer class teacher membership"

    missing_target = client.post(
        f"/api/classes/{class_id}/teachers/transfer",
        headers=_auth_header(admin_token),
        json={"source_membership_id": owner_membership_id, "target_user_id": 999999},
    )
    assert missing_target.status_code == 404

    student_target = client.post(
        f"/api/classes/{class_id}/teachers/transfer",
        headers=_auth_header(admin_token),
        json={"source_membership_id": owner_membership_id, "target_user_id": student_user_id},
    )
    assert student_target.status_code == 403
    assert student_target.json()["detail"] == "Target teacher must be active same-school teacher/admin"

    outsider_target = client.post(
        f"/api/classes/{class_id}/teachers/transfer",
        headers=_auth_header(admin_token),
        json={"source_membership_id": owner_membership_id, "target_user_id": outsider_user_id},
    )
    assert outsider_target.status_code == 403

    inactive_school_target = client.post(
        f"/api/classes/{class_id}/teachers/transfer",
        headers=_auth_header(admin_token),
        json={"source_membership_id": owner_membership_id, "target_user_id": target_user_id},
    )
    assert inactive_school_target.status_code == 403

    with get_session_factory(get_settings().database_url)() as db:
        target_user = db.get(User, target_user_id)
        assert target_user is not None
        target_user.status = "disabled"
        db.commit()
    disabled_target = client.post(
        f"/api/classes/{class_id}/teachers/transfer",
        headers=_auth_header(admin_token),
        json={"source_membership_id": owner_membership_id, "target_user_id": target_user_id},
    )
    assert disabled_target.status_code == 403

    with get_session_factory(get_settings().database_url)() as db:
        target_user = db.get(User, target_user_id)
        assert target_user is not None
        target_user.status = "active"
        target_school_membership = db.scalar(
            select(SchoolMembership).where(
                SchoolMembership.school_id == school_id,
                SchoolMembership.user_id == target_user_id,
                SchoolMembership.role == "teacher",
            )
        )
        assert target_school_membership is not None
        target_school_membership.status = "active"
        db.add(ClassMembership(class_id=class_id, user_id=target_user_id, role="teacher", status="inactive"))
        db.commit()

    transferred = client.post(
        f"/api/classes/{class_id}/teachers/transfer",
        headers={**_auth_header(admin_token), "X-Request-ID": "class-teacher-transfer"},
        json={
            "source_membership_id": owner_membership_id,
            "target_user_id": target_user_id,
            "deactivate_source": True,
            "note": "  hand off class owner  ",
        },
    )
    assert transferred.status_code == 200
    transferred_body = transferred.json()
    assert transferred_body["source_membership"]["status"] == "inactive"
    assert transferred_body["target_membership"]["status"] == "active"
    assert transferred_body["target_membership"]["username"] == "teacher_transfer_target"
    target_membership_id = transferred_body["target_membership"]["id"]

    old_teacher_members = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(owner_token))
    assert old_teacher_members.status_code == 403
    new_teacher_members = client.get(f"/api/classes/{class_id}/members", headers=_auth_header(target_token))
    assert new_teacher_members.status_code == 200
    assert [item["username"] for item in new_teacher_members.json()] == ["teacher_transfer_target"]

    duplicate_source = client.post(
        f"/api/classes/{class_id}/teachers/transfer",
        headers=_auth_header(admin_token),
        json={"source_membership_id": target_membership_id, "target_user_id": target_user_id},
    )
    assert duplicate_source.status_code == 409

    transfer_audit = client.get(
        f"/api/admin/audit-logs?action=class.teacher.transfer&class_id={class_id}",
        headers=_auth_header(admin_token),
    )
    assert transfer_audit.status_code == 200
    assert transfer_audit.json()["total"] == 1
    audit_item = transfer_audit.json()["items"][0]
    assert audit_item["request_id"] == "class-teacher-transfer"
    assert audit_item["snapshot_json"]["before"]["source"]["status"] == "active"
    assert audit_item["snapshot_json"]["before"]["target"]["status"] == "inactive"
    assert audit_item["snapshot_json"]["after"]["source"]["status"] == "inactive"
    assert audit_item["snapshot_json"]["after"]["target"]["created"] is False
    assert audit_item["snapshot_json"]["after"]["has_note"] is True


def test_class_member_batch_status_is_atomic_and_role_scoped(client):
    admin_token = _bootstrap_admin(client, "admin_member_batch")
    teacher_token = _register_and_login(client, "teacher_member_batch", "teacher")
    assistant_token = _register_and_login(client, "teacher_member_batch_assistant", "teacher")
    student_one_token = _register_and_login(client, "student_member_batch_one", "student")
    student_two_token = _register_and_login(client, "student_member_batch_two", "student")

    school_id, class_id = _create_school_and_class(
        client,
        teacher_token,
        "Astra Batch School",
        "Batch Physics",
    )
    student_one_join = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(student_one_token),
        json={"role": "student"},
    )
    assert student_one_join.status_code == 201
    student_one_membership_id = student_one_join.json()["id"]
    student_two_join = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(student_two_token),
        json={"role": "student"},
    )
    assert student_two_join.status_code == 201
    student_two_membership_id = student_two_join.json()["id"]

    teacher_members = client.get(
        f"/api/classes/{class_id}/members?role=teacher",
        headers=_auth_header(teacher_token),
    )
    assert teacher_members.status_code == 200
    teacher_membership_id = teacher_members.json()[0]["id"]

    assistant_me = client.get("/api/users/me", headers=_auth_header(assistant_token))
    assert assistant_me.status_code == 200
    assistant_user_id = assistant_me.json()["id"]
    with get_session_factory(get_settings().database_url)() as db:
        db.add(SchoolMembership(school_id=school_id, user_id=assistant_user_id, role="teacher", status="active"))
        db.add(ClassMembership(class_id=class_id, user_id=assistant_user_id, role="teacher", status="active"))
        db.commit()

    teacher_only_student_batch = client.patch(
        f"/api/classes/{class_id}/members/batch-status",
        headers={**_auth_header(teacher_token), "X-Request-ID": "class-student-batch"},
        json={
            "items": [
                {"membership_id": student_one_membership_id, "status": "inactive", "note": "  absent  "},
                {"membership_id": student_two_membership_id, "status": "inactive"},
            ]
        },
    )
    assert teacher_only_student_batch.status_code == 200
    assert {item["status"] for item in teacher_only_student_batch.json()} == {"inactive"}

    active_student_members = client.get(
        f"/api/classes/{class_id}/members?role=student",
        headers=_auth_header(teacher_token),
    )
    assert active_student_members.status_code == 200
    assert active_student_members.json() == []

    teacher_batch_forbidden = client.patch(
        f"/api/classes/{class_id}/members/batch-status",
        headers=_auth_header(teacher_token),
        json={
            "items": [
                {"membership_id": teacher_membership_id, "status": "inactive"},
            ]
        },
    )
    assert teacher_batch_forbidden.status_code == 403
    assert teacher_batch_forbidden.json()["detail"] == "Only admins can update teacher class membership"

    assistant_members = client.get(
        f"/api/classes/{class_id}/members?role=teacher",
        headers=_auth_header(admin_token),
    )
    assert assistant_members.status_code == 200
    assistant_membership_id = next(
        item["id"] for item in assistant_members.json() if item["username"] == "teacher_member_batch_assistant"
    )

    blocked_all_teachers = client.patch(
        f"/api/classes/{class_id}/members/batch-status",
        headers=_auth_header(admin_token),
        json={
            "items": [
                {"membership_id": teacher_membership_id, "status": "inactive"},
                {"membership_id": assistant_membership_id, "status": "inactive"},
                {"membership_id": student_one_membership_id, "status": "active"},
            ]
        },
    )
    assert blocked_all_teachers.status_code == 409
    assert blocked_all_teachers.json()["detail"] == "Cannot deactivate the last active class teacher"

    student_one_after_blocked = client.get(
        f"/api/classes/{class_id}/members?role=student&status=active",
        headers=_auth_header(admin_token),
    )
    assert student_one_after_blocked.status_code == 200
    assert student_one_after_blocked.json() == []

    admin_batch = client.patch(
        f"/api/classes/{class_id}/members/batch-status",
        headers={**_auth_header(admin_token), "X-Request-ID": "class-mixed-batch"},
        json={
            "items": [
                {"membership_id": teacher_membership_id, "status": "inactive"},
                {"membership_id": student_one_membership_id, "status": "active"},
            ]
        },
    )
    assert admin_batch.status_code == 200
    assert {item["id"]: item["status"] for item in admin_batch.json()} == {
        teacher_membership_id: "inactive",
        student_one_membership_id: "active",
    }

    duplicate_batch = client.patch(
        f"/api/classes/{class_id}/members/batch-status",
        headers=_auth_header(admin_token),
        json={
            "items": [
                {"membership_id": student_two_membership_id, "status": "active"},
                {"membership_id": student_two_membership_id, "status": "inactive"},
            ]
        },
    )
    assert duplicate_batch.status_code == 422

    batch_audit = client.get(
        f"/api/admin/audit-logs?action=class.member.status.batch_update&class_id={class_id}",
        headers=_auth_header(admin_token),
    )
    assert batch_audit.status_code == 200
    assert batch_audit.json()["total"] == 2
    request_ids = {item["request_id"] for item in batch_audit.json()["items"]}
    assert request_ids == {"class-student-batch", "class-mixed-batch"}
    mixed_audit = next(item for item in batch_audit.json()["items"] if item["request_id"] == "class-mixed-batch")
    assert mixed_audit["snapshot_json"]["changed_count"] == 2
    assert mixed_audit["snapshot_json"]["item_count"] == 2


def test_student_transfer_is_same_school_dual_scope_idempotent_and_audited(client):
    admin_token = _bootstrap_admin(client, "admin_student_transfer")
    teacher_token = _register_and_login(client, "teacher_student_transfer", "teacher")
    target_teacher_token = _register_and_login(client, "teacher_target_only", "teacher")
    student_token = _register_and_login(client, "student_class_transfer", "student")

    school_id, source_class_id = _create_school_and_class(
        client,
        teacher_token,
        "Astra Student Transfer School",
        "Transfer Source",
    )
    target_class = client.post(
        "/api/classes",
        headers=_auth_header(teacher_token),
        json={"school_id": school_id, "name": "Transfer Target"},
    )
    assert target_class.status_code == 201
    target_class_id = target_class.json()["id"]
    student_join = client.post(
        f"/api/classes/{source_class_id}/join",
        headers=_auth_header(student_token),
        json={"role": "student"},
    )
    assert student_join.status_code == 201
    source_membership_id = student_join.json()["id"]
    student_me = client.get("/api/users/me", headers=_auth_header(student_token)).json()

    with get_session_factory(get_settings().database_url)() as db:
        inactive_target = ClassMembership(
            class_id=target_class_id,
            user_id=student_me["id"],
            role="student",
            status="inactive",
        )
        db.add(inactive_target)
        db.commit()
        inactive_target_id = inactive_target.id

    transferred = client.post(
        f"/api/classes/{source_class_id}/students/{source_membership_id}/transfer",
        headers={**_auth_header(teacher_token), "X-Request-ID": "student-transfer-applied"},
        json={"target_class_id": target_class_id, "note": "  approved transfer  "},
    )
    assert transferred.status_code == 200
    transferred_body = transferred.json()
    assert transferred_body["applied"] is True
    assert transferred_body["source_membership"]["status"] == "inactive"
    assert transferred_body["target_membership"]["id"] == inactive_target_id
    assert transferred_body["target_membership"]["status"] == "active"

    replay = client.post(
        f"/api/classes/{source_class_id}/students/{source_membership_id}/transfer",
        headers={**_auth_header(teacher_token), "X-Request-ID": "student-transfer-replay"},
        json={"target_class_id": target_class_id},
    )
    assert replay.status_code == 200
    assert replay.json()["applied"] is False

    transfer_audit = client.get(
        f"/api/admin/audit-logs?action=class.student.transfer&class_id={source_class_id}",
        headers=_auth_header(admin_token),
    )
    assert transfer_audit.status_code == 200
    assert transfer_audit.json()["total"] == 1
    audit_item = transfer_audit.json()["items"][0]
    assert audit_item["request_id"] == "student-transfer-applied"
    assert audit_item["snapshot_json"]["before"]["source"]["status"] == "active"
    assert audit_item["snapshot_json"]["before"]["target"]["status"] == "inactive"
    assert audit_item["snapshot_json"]["after"]["target"]["created"] is False
    assert audit_item["snapshot_json"]["after"]["has_note"] is True

    same_class = client.post(
        f"/api/classes/{target_class_id}/students/{inactive_target_id}/transfer",
        headers=_auth_header(teacher_token),
        json={"target_class_id": target_class_id},
    )
    assert same_class.status_code == 409

    other_school_id, other_school_class_id = _create_school_and_class(
        client,
        teacher_token,
        "Astra Other Transfer School",
        "Other School Target",
    )
    assert other_school_id != school_id
    cross_school = client.post(
        f"/api/classes/{target_class_id}/students/{inactive_target_id}/transfer",
        headers=_auth_header(teacher_token),
        json={"target_class_id": other_school_class_id},
    )
    assert cross_school.status_code == 422
    assert cross_school.json()["detail"] == "Student transfer requires classes in the same school"

    target_teacher_me = client.get("/api/users/me", headers=_auth_header(target_teacher_token)).json()
    with get_session_factory(get_settings().database_url)() as db:
        target_only_class = ClassMembership(
            class_id=target_class_id,
            user_id=target_teacher_me["id"],
            role="teacher",
            status="active",
        )
        db.add(SchoolMembership(school_id=school_id, user_id=target_teacher_me["id"], role="teacher"))
        db.add(target_only_class)
        db.commit()
        target_only_membership_id = target_only_class.id

    source_teacher_members = client.get(
        f"/api/classes/{source_class_id}/members?role=teacher",
        headers=_auth_header(teacher_token),
    ).json()
    source_teacher_membership_id = source_teacher_members[0]["id"]
    teacher_membership_is_not_student = client.post(
        f"/api/classes/{source_class_id}/students/{source_teacher_membership_id}/transfer",
        headers=_auth_header(teacher_token),
        json={"target_class_id": target_class_id},
    )
    assert teacher_membership_is_not_student.status_code == 404

    teacher_without_source_scope = client.post(
        f"/api/classes/{source_class_id}/students/{source_membership_id}/transfer",
        headers=_auth_header(target_teacher_token),
        json={"target_class_id": target_class_id},
    )
    assert teacher_without_source_scope.status_code == 403
    assert target_only_membership_id > 0

    student_forbidden = client.post(
        f"/api/classes/{source_class_id}/students/{source_membership_id}/transfer",
        headers=_auth_header(student_token),
        json={"target_class_id": target_class_id},
    )
    assert student_forbidden.status_code == 403


def test_student_batch_import_has_partial_results_state_idempotency_and_scope(client):
    admin_token = _bootstrap_admin(client, "admin_student_import")
    teacher_token = _register_and_login(client, "teacher_student_import", "teacher")
    outsider_teacher_token = _register_and_login(client, "teacher_import_outside", "teacher")
    created_token = _register_and_login(client, "student_import_created", "student")
    restored_token = _register_and_login(client, "student_import_restored", "student")
    unchanged_token = _register_and_login(client, "student_import_unchanged", "student")
    outsider_student_token = _register_and_login(client, "student_import_outside", "student")

    school_id, class_id = _create_school_and_class(
        client,
        teacher_token,
        "Astra Student Import School",
        "Batch Import Class",
    )
    users = {}
    for label, token in (
        ("created", created_token),
        ("restored", restored_token),
        ("unchanged", unchanged_token),
        ("outside", outsider_student_token),
    ):
        users[label] = client.get("/api/users/me", headers=_auth_header(token)).json()

    with get_session_factory(get_settings().database_url)() as db:
        for label in ("created", "restored", "unchanged"):
            db.add(SchoolMembership(school_id=school_id, user_id=users[label]["id"], role="student"))
        db.add(
            ClassMembership(
                class_id=class_id,
                user_id=users["restored"]["id"],
                role="student",
                status="inactive",
            )
        )
        db.add(
            ClassMembership(
                class_id=class_id,
                user_id=users["unchanged"]["id"],
                role="student",
                status="active",
            )
        )
        db.commit()

    payload = {
        "items": [
            {"username": " STUDENT_IMPORT_CREATED ", "client_ref": "create"},
            {"username": "student_import_restored", "client_ref": "restore"},
            {"username": "student_import_unchanged", "client_ref": "unchanged"},
            {"username": "student_import_outside", "client_ref": "outside"},
            {"username": "student_import_created", "client_ref": "duplicate"},
            {"username": "   ", "client_ref": "invalid"},
        ]
    }
    imported = client.post(
        f"/api/classes/{class_id}/students/batch-import",
        headers={**_auth_header(teacher_token), "X-Request-ID": "student-import-partial"},
        json=payload,
    )
    assert imported.status_code == 200
    body = imported.json()
    assert (body["created_count"], body["restored_count"], body["unchanged_count"], body["failed_count"]) == (
        1,
        1,
        1,
        3,
    )
    assert [item["outcome"] for item in body["items"]] == [
        "created",
        "restored",
        "unchanged",
        "failed",
        "failed",
        "failed",
    ]
    assert [item["error_code"] for item in body["items"][3:]] == [
        "student_not_eligible",
        "duplicate_item",
        "invalid_username",
    ]
    assert all(item["membership"]["status"] == "active" for item in body["items"][:3])

    replay = client.post(
        f"/api/classes/{class_id}/students/batch-import",
        headers={**_auth_header(teacher_token), "X-Request-ID": "student-import-replay"},
        json=payload,
    )
    assert replay.status_code == 200
    replay_body = replay.json()
    assert replay_body["created_count"] == 0
    assert replay_body["restored_count"] == 0
    assert replay_body["unchanged_count"] == 3
    assert replay_body["failed_count"] == 3

    import_audits = client.get(
        f"/api/admin/audit-logs?action=class.student.batch_import&class_id={class_id}",
        headers=_auth_header(admin_token),
    )
    assert import_audits.status_code == 200
    assert import_audits.json()["total"] == 2
    first_audit = next(
        item for item in import_audits.json()["items"] if item["request_id"] == "student-import-partial"
    )
    assert first_audit["snapshot_json"]["partial_failure"] is True
    assert first_audit["snapshot_json"]["created_count"] == 1
    assert first_audit["snapshot_json"]["failed_count"] == 3
    assert "username" not in first_audit["snapshot_json"]["items"][0]

    outsider_forbidden = client.post(
        f"/api/classes/{class_id}/students/batch-import",
        headers=_auth_header(outsider_teacher_token),
        json={"items": [{"username": "student_import_created"}]},
    )
    assert outsider_forbidden.status_code == 403
    student_forbidden = client.post(
        f"/api/classes/{class_id}/students/batch-import",
        headers=_auth_header(created_token),
        json={"items": [{"username": "student_import_created"}]},
    )
    assert student_forbidden.status_code == 403


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


def test_class_join_approval_rechecks_applicant_global_role(client):
    teacher_token = _register_and_login(client, "teacher_join_role_recheck", "teacher")
    student_token = _register_and_login(client, "student_join_role_recheck", "student")
    _, class_id = _create_school_and_class(
        client,
        teacher_token,
        "Astra Role Recheck School",
        "Role Recheck Physics",
    )
    requested = client.post(
        f"/api/classes/{class_id}/join-requests",
        headers=_auth_header(student_token),
        json={"role": "student"},
    )
    assert requested.status_code == 201

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        applicant = db.scalar(select(User).where(User.username == "student_join_role_recheck"))
        applicant.role = "teacher"
        db.commit()
        applicant_id = applicant.id

    approval = client.patch(
        f"/api/classes/{class_id}/join-requests/{requested.json()['id']}",
        headers=_auth_header(teacher_token),
        json={"status": "approved", "note": "stale request"},
    )
    assert approval.status_code == 409
    assert approval.json()["detail"] == "Class join applicant is no longer eligible"
    with session_factory() as db:
        membership = db.scalar(
            select(ClassMembership).where(
                ClassMembership.class_id == class_id,
                ClassMembership.user_id == applicant_id,
                ClassMembership.role == "student",
            )
        )
        assert membership is None


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
