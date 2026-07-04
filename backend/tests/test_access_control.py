from datetime import datetime


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client, username: str, role: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "secret123",
            "display_name": username.replace("_", " ").title(),
            "role": role,
        },
    )
    assert response.status_code == 201
    login = client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    assert login.status_code == 200
    me = client.get("/api/users/me", headers=_auth_header(login.json()["access_token"]))
    assert me.status_code == 200
    return {"token": login.json()["access_token"], "id": me.json()["id"]}


def _create_learning_scope(client) -> dict:
    teacher = _register_and_login(client, "scope_teacher", "teacher")
    student = _register_and_login(client, "scope_student", "student")

    school = client.post(
        "/api/schools",
        headers=_auth_header(teacher["token"]),
        json={"name": "Scope Matrix School", "region": "Shanghai"},
    )
    assert school.status_code == 201
    school_id = school.json()["id"]

    class_response = client.post(
        "/api/classes",
        headers=_auth_header(teacher["token"]),
        json={"school_id": school_id, "name": "Scope Matrix Class", "grade": "10", "term": "2026A"},
    )
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    course = client.post(
        "/api/courses",
        headers=_auth_header(teacher["token"]),
        json={"school_id": school_id, "title": "Scope Matrix Course", "status": "published"},
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    attach = client.post(
        f"/api/courses/{course_id}/classes",
        headers=_auth_header(teacher["token"]),
        json={"class_id": class_id},
    )
    assert attach.status_code == 201

    unit = client.post(
        f"/api/courses/{course_id}/units",
        headers=_auth_header(teacher["token"]),
        json={
            "title": "Scope Matrix Unit",
            "position": 1,
            "content_slug": "physics/energy-conservation",
            "status": "published",
        },
    )
    assert unit.status_code == 201
    unit_id = unit.json()["id"]

    assignment = client.post(
        f"/api/courses/{course_id}/units/{unit_id}/assignments",
        headers=_auth_header(teacher["token"]),
        json={"title": "Scope Matrix Assignment", "max_score": 20},
    )
    assert assignment.status_code == 201

    join = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(student["token"]),
        json={"role": "student"},
    )
    assert join.status_code == 201

    return {
        "teacher": teacher,
        "student": student,
        "school_id": school_id,
        "class_id": class_id,
        "course_id": course_id,
        "unit_id": unit_id,
        "assignment_id": assignment.json()["id"],
    }


def test_outside_users_cannot_cross_school_class_course_boundaries(client):
    scope = _create_learning_scope(client)
    outsider_student = _register_and_login(client, "scope_outside_student", "student")
    outsider_teacher = _register_and_login(client, "scope_outside_teacher", "teacher")

    class_id = scope["class_id"]
    course_id = scope["course_id"]
    assignment_id = scope["assignment_id"]
    outside_student_headers = _auth_header(outsider_student["token"])
    outside_teacher_headers = _auth_header(outsider_teacher["token"])

    denied_requests = [
        (
            "student cannot list outside school classes",
            lambda: client.get(f"/api/classes?school_id={scope['school_id']}", headers=outside_student_headers),
        ),
        (
            "student cannot list outside school class route",
            lambda: client.get(f"/api/schools/{scope['school_id']}/classes", headers=outside_student_headers),
        ),
        (
            "student cannot list outside class courses",
            lambda: client.get(f"/api/courses?class_id={class_id}", headers=outside_student_headers),
        ),
        (
            "student cannot read outside course units",
            lambda: client.get(f"/api/courses/{course_id}/units", headers=outside_student_headers),
        ),
        (
            "student cannot read outside course assignments",
            lambda: client.get(f"/api/courses/{course_id}/assignments", headers=outside_student_headers),
        ),
        (
            "student cannot create outside learning event",
            lambda: client.post(
                "/api/learning-events",
                headers=outside_student_headers,
                json={"course_id": course_id, "class_id": class_id, "event_type": "visit", "payload": {}},
            ),
        ),
        (
            "student cannot submit outside assignment",
            lambda: client.post(
                f"/api/assignments/{assignment_id}/submissions",
                headers=outside_student_headers,
                json={"class_id": class_id, "content": {"answer": "outside"}},
            ),
        ),
        (
            "teacher cannot read outside student progress",
            lambda: client.get(
                f"/api/progress/users/{scope['student']['id']}?class_id={class_id}",
                headers=outside_teacher_headers,
            ),
        ),
        (
            "teacher cannot read outside point ledger",
            lambda: client.get(f"/api/points/ledger?class_id={class_id}", headers=outside_teacher_headers),
        ),
        (
            "teacher cannot read outside class knowledge",
            lambda: client.get(f"/api/classes/{class_id}/knowledge", headers=outside_teacher_headers),
        ),
    ]

    for label, request in denied_requests:
        response = request()
        assert response.status_code == 403, label


def test_class_members_can_access_their_scoped_course_resources(client):
    scope = _create_learning_scope(client)
    student_headers = _auth_header(scope["student"]["token"])
    teacher_headers = _auth_header(scope["teacher"]["token"])
    now = datetime(2026, 7, 4, 12, 0, 0).isoformat()

    student_courses = client.get(f"/api/courses?class_id={scope['class_id']}", headers=student_headers)
    assert student_courses.status_code == 200
    assert [item["id"] for item in student_courses.json()] == [scope["course_id"]]

    learning_event = client.post(
        "/api/learning-events",
        headers=student_headers,
        json={
            "course_id": scope["course_id"],
            "class_id": scope["class_id"],
            "event_type": "visit",
            "payload": {"source": "access-control-test"},
            "occurred_at": now,
        },
    )
    assert learning_event.status_code == 201

    teacher_progress = client.get(
        f"/api/progress/users/{scope['student']['id']}?class_id={scope['class_id']}",
        headers=teacher_headers,
    )
    assert teacher_progress.status_code == 200

    class_knowledge = client.get(f"/api/classes/{scope['class_id']}/knowledge", headers=teacher_headers)
    assert class_knowledge.status_code == 200
