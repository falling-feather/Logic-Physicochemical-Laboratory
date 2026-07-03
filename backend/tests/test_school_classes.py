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
    teacher_token = _register_and_login(client, "teacher02", "teacher")
    student_token = _register_and_login(client, "student01", "student")

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
    assert join.json()["role"] == "student"

    student_classes = client.get(f"/api/classes?school_id={school_id}", headers=_auth_header(student_token))
    assert student_classes.status_code == 200
    assert student_classes.json()[0]["id"] == class_id

    teacher_classes = client.get(f"/api/schools/{school_id}/classes", headers=_auth_header(teacher_token))
    assert teacher_classes.status_code == 200
    assert teacher_classes.json()[0]["name"] == "Physics Class A"


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
