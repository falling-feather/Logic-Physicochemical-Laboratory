def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


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
