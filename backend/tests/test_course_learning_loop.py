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


def test_teacher_course_assignment_and_student_learning_event_loop(client):
    teacher_token = _register_and_login(client, "teacher_course", "teacher")
    student_token = _register_and_login(client, "student_course", "student")
    outsider_token = _register_and_login(client, "student_outside_course", "student")

    school = client.post(
        "/api/schools",
        headers=_auth_header(teacher_token),
        json={"name": "Astra Course School", "region": "Shanghai"},
    )
    assert school.status_code == 201
    school_id = school.json()["id"]

    class_response = client.post(
        "/api/classes",
        headers=_auth_header(teacher_token),
        json={"school_id": school_id, "name": "Physics Loop Class", "grade": "10", "term": "2026A"},
    )
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]

    rejected_course = client.post(
        "/api/courses",
        headers=_auth_header(student_token),
        json={"school_id": school_id, "title": "Unauthorized Course"},
    )
    assert rejected_course.status_code == 403

    course = client.post(
        "/api/courses",
        headers=_auth_header(teacher_token),
        json={
            "school_id": school_id,
            "title": "Mechanics Path",
            "summary": "Energy and motion",
            "status": "published",
        },
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    teacher_courses = client.get("/api/courses", headers=_auth_header(teacher_token))
    assert teacher_courses.status_code == 200
    assert [item["id"] for item in teacher_courses.json()] == [course_id]

    attach = client.post(
        f"/api/courses/{course_id}/classes",
        headers=_auth_header(teacher_token),
        json={"class_id": class_id},
    )
    assert attach.status_code == 201
    assert attach.json()["class_id"] == class_id

    unit = client.post(
        f"/api/courses/{course_id}/units",
        headers=_auth_header(teacher_token),
        json={
            "title": "Energy Conservation",
            "position": 1,
            "content_slug": "physics/energy-conservation",
            "status": "published",
        },
    )
    assert unit.status_code == 201
    unit_id = unit.json()["id"]

    duplicate_unit = client.post(
        f"/api/courses/{course_id}/units",
        headers=_auth_header(teacher_token),
        json={"title": "Duplicate Position", "position": 1},
    )
    assert duplicate_unit.status_code == 409

    assignment = client.post(
        f"/api/courses/{course_id}/units/{unit_id}/assignments",
        headers=_auth_header(teacher_token),
        json={
            "title": "Observe dissipation",
            "description": "Compare total energy with mechanical energy.",
            "max_score": 20,
        },
    )
    assert assignment.status_code == 201
    assignment_id = assignment.json()["id"]

    outsider_class_courses = client.get(
        f"/api/courses?class_id={class_id}",
        headers=_auth_header(outsider_token),
    )
    assert outsider_class_courses.status_code == 403

    join = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(student_token),
        json={"role": "student"},
    )
    assert join.status_code == 201

    student_courses = client.get("/api/courses", headers=_auth_header(student_token))
    assert student_courses.status_code == 200
    assert [item["id"] for item in student_courses.json()] == [course_id]

    student_assignments = client.get(
        f"/api/courses/{course_id}/assignments",
        headers=_auth_header(student_token),
    )
    assert student_assignments.status_code == 200
    assert student_assignments.json()[0]["id"] == assignment_id

    event = client.post(
        "/api/learning-events",
        headers=_auth_header(student_token),
        json={
            "class_id": class_id,
            "assignment_id": assignment_id,
            "event_type": "complete",
            "payload": {"score": 18, "sample_size": 1},
        },
    )
    assert event.status_code == 201
    assert event.json()["assignment_id"] == assignment_id
    assert event.json()["event_type"] == "complete"
    assert event.json()["school_id"] == school_id

    unscoped_assignment_event = client.post(
        "/api/learning-events",
        headers=_auth_header(student_token),
        json={
            "assignment_id": assignment_id,
            "event_type": "submit",
            "payload": {"missing": "class"},
        },
    )
    assert unscoped_assignment_event.status_code == 422

    submission = client.post(
        f"/api/assignments/{assignment_id}/submissions",
        headers=_auth_header(student_token),
        json={
            "class_id": class_id,
            "content": {"answer": "Mechanical energy decreases; total energy stays conserved."},
        },
    )
    assert submission.status_code == 201
    submission_id = submission.json()["id"]

    duplicate_submission = client.post(
        f"/api/assignments/{assignment_id}/submissions",
        headers=_auth_header(student_token),
        json={"class_id": class_id, "content": {"answer": "duplicate"}},
    )
    assert duplicate_submission.status_code == 409

    outsider_submission = client.post(
        f"/api/assignments/{assignment_id}/submissions",
        headers=_auth_header(outsider_token),
        json={"class_id": class_id, "content": {"answer": "out of scope"}},
    )
    assert outsider_submission.status_code == 403

    outsider_submission_list = client.get(
        f"/api/assignments/{assignment_id}/submissions",
        headers=_auth_header(outsider_token),
    )
    assert outsider_submission_list.status_code == 403

    grade = client.patch(
        f"/api/submissions/{submission_id}/grade",
        headers=_auth_header(teacher_token),
        json={"score": 18, "feedback": "Clear observation."},
    )
    assert grade.status_code == 200
    assert grade.json()["status"] == "graded"
    assert grade.json()["score"] == 18

    student_points = client.get("/api/points/ledger", headers=_auth_header(student_token))
    assert student_points.status_code == 200
    assert student_points.json()[0]["delta"] == 18
    assert student_points.json()[0]["submission_id"] == submission_id

    teacher_points = client.get(
        f"/api/points/ledger?class_id={class_id}",
        headers=_auth_header(teacher_token),
    )
    assert teacher_points.status_code == 200
    assert teacher_points.json()[0]["user_id"] == grade.json()["student_id"]

    progress = client.get(f"/api/progress/me?class_id={class_id}", headers=_auth_header(student_token))
    assert progress.status_code == 200
    assert progress.json()["submitted_assignments"] == 1
    assert progress.json()["graded_assignments"] == 1
    assert progress.json()["total_points"] == 18

    teacher_progress = client.get(
        f"/api/progress/users/{grade.json()['student_id']}?class_id={class_id}",
        headers=_auth_header(teacher_token),
    )
    assert teacher_progress.status_code == 200
    assert teacher_progress.json()["user_id"] == grade.json()["student_id"]

    own_events = client.get("/api/learning-events", headers=_auth_header(student_token))
    assert own_events.status_code == 200
    assert own_events.json()[0]["payload"]["score"] == 18

    teacher_events = client.get(
        f"/api/learning-events?class_id={class_id}",
        headers=_auth_header(teacher_token),
    )
    assert teacher_events.status_code == 200
    assert teacher_events.json()[0]["user_id"] == event.json()["user_id"]
