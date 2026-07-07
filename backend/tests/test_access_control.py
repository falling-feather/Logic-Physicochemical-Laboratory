from datetime import datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import Course, CourseUnit, SchoolMembership, UserKnowledgeSnapshot
from app.services import knowledge_snapshot_runs


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


def _bootstrap_admin(client, username: str) -> str:
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


def _grant_school_teacher_membership(user_id: int, school_id: int) -> None:
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(SchoolMembership(school_id=school_id, user_id=user_id, role="teacher", status="active"))
        db.commit()


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
            "student cannot read outside assignment review",
            lambda: client.get(f"/api/assignments/{assignment_id}/review", headers=outside_student_headers),
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


def test_school_teacher_without_class_scope_cannot_manage_class_assignments(client):
    scope = _create_learning_scope(client)
    peer_teacher = _register_and_login(client, "scope_peer_school_teacher", "teacher")
    _grant_school_teacher_membership(peer_teacher["id"], scope["school_id"])

    student_headers = _auth_header(scope["student"]["token"])
    teacher_headers = _auth_header(scope["teacher"]["token"])
    peer_headers = _auth_header(peer_teacher["token"])

    peer_attach = client.post(
        f"/api/courses/{scope['course_id']}/classes",
        headers=peer_headers,
        json={"class_id": scope["class_id"]},
    )
    assert peer_attach.status_code == 403
    assert peer_attach.json()["detail"] == "Course class attachment requires class teacher role"

    submission = client.post(
        f"/api/assignments/{scope['assignment_id']}/submissions",
        headers=student_headers,
        json={"class_id": scope["class_id"], "content": {"answer": "scoped submission"}},
    )
    assert submission.status_code == 201
    submission_id = submission.json()["id"]

    event = client.post(
        "/api/learning-events",
        headers=student_headers,
        json={"class_id": scope["class_id"], "assignment_id": scope["assignment_id"], "event_type": "complete"},
    )
    assert event.status_code == 201

    peer_unscoped_list = client.get(
        f"/api/assignments/{scope['assignment_id']}/submissions",
        headers=peer_headers,
    )
    assert peer_unscoped_list.status_code == 200
    assert peer_unscoped_list.json() == []

    peer_class_list = client.get(
        f"/api/assignments/{scope['assignment_id']}/submissions?class_id={scope['class_id']}",
        headers=peer_headers,
    )
    assert peer_class_list.status_code == 403
    assert peer_class_list.json()["detail"] == "Assignment submissions require class teacher scope"

    peer_pending_queue = client.get("/api/admin/submissions/pending", headers=peer_headers)
    assert peer_pending_queue.status_code == 200
    assert peer_pending_queue.json()["total"] == 0
    assert peer_pending_queue.json()["items"] == []

    peer_course_pending_queue = client.get(
        f"/api/admin/submissions/pending?course_id={scope['course_id']}",
        headers=peer_headers,
    )
    assert peer_course_pending_queue.status_code == 200
    assert peer_course_pending_queue.json()["total"] == 0

    peer_class_pending_queue = client.get(
        f"/api/admin/submissions/pending?class_id={scope['class_id']}",
        headers=peer_headers,
    )
    assert peer_class_pending_queue.status_code == 403
    assert peer_class_pending_queue.json()["detail"] == "Pending submissions require class teacher scope"

    student_pending_queue = client.get("/api/admin/submissions/pending", headers=student_headers)
    assert student_pending_queue.status_code == 403
    assert student_pending_queue.json()["detail"] == "Pending submissions require class teacher scope"

    peer_grade = client.patch(
        f"/api/submissions/{submission_id}/grade",
        headers=peer_headers,
        json={"score": 12, "feedback": "out of scope"},
    )
    assert peer_grade.status_code == 403
    assert peer_grade.json()["detail"] == "Submission grading requires class teacher scope"

    peer_unscoped_events = client.get("/api/learning-events", headers=peer_headers)
    assert peer_unscoped_events.status_code == 200
    assert peer_unscoped_events.json() == []

    peer_class_events = client.get(f"/api/learning-events?class_id={scope['class_id']}", headers=peer_headers)
    assert peer_class_events.status_code == 403
    assert peer_class_events.json()["detail"] == "Learning events require class teacher scope"

    peer_progress = client.get(
        f"/api/progress/users/{scope['student']['id']}?class_id={scope['class_id']}",
        headers=peer_headers,
    )
    assert peer_progress.status_code == 403
    assert peer_progress.json()["detail"] == "Student progress requires class teacher scope"

    owner_class_list = client.get(
        f"/api/assignments/{scope['assignment_id']}/submissions?class_id={scope['class_id']}",
        headers=teacher_headers,
    )
    assert owner_class_list.status_code == 200
    assert [item["id"] for item in owner_class_list.json()] == [submission_id]

    owner_pending_queue = client.get("/api/admin/submissions/pending", headers=teacher_headers)
    assert owner_pending_queue.status_code == 200
    assert owner_pending_queue.json()["total"] == 1
    assert [item["id"] for item in owner_pending_queue.json()["items"]] == [submission_id]

    owner_class_pending_queue = client.get(
        f"/api/admin/submissions/pending?class_id={scope['class_id']}",
        headers=teacher_headers,
    )
    assert owner_class_pending_queue.status_code == 200
    assert owner_class_pending_queue.json()["total"] == 1

    owner_grade = client.patch(
        f"/api/submissions/{submission_id}/grade",
        headers=teacher_headers,
        json={"score": 12, "feedback": "in scope"},
    )
    assert owner_grade.status_code == 200
    assert owner_grade.json()["score"] == 12

    owner_graded_queue = client.get(
        f"/api/admin/submissions/pending?class_id={scope['class_id']}&status=graded",
        headers=teacher_headers,
    )
    assert owner_graded_queue.status_code == 403
    assert owner_graded_queue.json()["detail"] == "Graded submission queue requires admin role"

    peer_unscoped_points = client.get("/api/points/ledger", headers=peer_headers)
    assert peer_unscoped_points.status_code == 200
    assert peer_unscoped_points.json() == []

    peer_class_points = client.get(f"/api/points/ledger?class_id={scope['class_id']}", headers=peer_headers)
    assert peer_class_points.status_code == 403
    assert peer_class_points.json()["detail"] == "Point ledger requires class teacher scope"

    owner_events = client.get(f"/api/learning-events?class_id={scope['class_id']}", headers=teacher_headers)
    assert owner_events.status_code == 200
    assert event.json()["id"] in {item["id"] for item in owner_events.json()}

    owner_points = client.get(f"/api/points/ledger?class_id={scope['class_id']}", headers=teacher_headers)
    assert owner_points.status_code == 200
    assert [item["delta"] for item in owner_points.json()] == [12]

    owner_progress = client.get(
        f"/api/progress/users/{scope['student']['id']}?class_id={scope['class_id']}",
        headers=teacher_headers,
    )
    assert owner_progress.status_code == 200
    assert owner_progress.json()["total_points"] == 12


def test_school_teacher_without_course_author_scope_cannot_edit_course_structure(client):
    scope = _create_learning_scope(client)
    peer_teacher = _register_and_login(client, "scope_peer_course_editor", "teacher")
    _grant_school_teacher_membership(peer_teacher["id"], scope["school_id"])
    admin_token = _bootstrap_admin(client, "admin_course_author_scope")

    teacher_headers = _auth_header(scope["teacher"]["token"])
    peer_headers = _auth_header(peer_teacher["token"])
    admin_headers = _auth_header(admin_token)

    peer_units = client.get(f"/api/courses/{scope['course_id']}/units", headers=peer_headers)
    assert peer_units.status_code == 200
    assert [item["id"] for item in peer_units.json()] == [scope["unit_id"]]

    peer_assignments = client.get(f"/api/courses/{scope['course_id']}/assignments", headers=peer_headers)
    assert peer_assignments.status_code == 200
    assert [item["id"] for item in peer_assignments.json()] == [scope["assignment_id"]]

    peer_unit_create = client.post(
        f"/api/courses/{scope['course_id']}/units",
        headers=peer_headers,
        json={"title": "Peer Edited Unit", "position": 2, "status": "published"},
    )
    assert peer_unit_create.status_code == 403
    assert peer_unit_create.json()["detail"] == "Course unit creation requires course author role"

    peer_assignment_create = client.post(
        f"/api/courses/{scope['course_id']}/units/{scope['unit_id']}/assignments",
        headers=peer_headers,
        json={"title": "Peer Edited Assignment", "max_score": 20},
    )
    assert peer_assignment_create.status_code == 403
    assert peer_assignment_create.json()["detail"] == "Assignment creation requires course author role"

    owner_unit = client.post(
        f"/api/courses/{scope['course_id']}/units",
        headers=teacher_headers,
        json={"title": "Owner Edited Unit", "position": 2, "status": "published"},
    )
    assert owner_unit.status_code == 201

    owner_assignment = client.post(
        f"/api/courses/{scope['course_id']}/units/{owner_unit.json()['id']}/assignments",
        headers=teacher_headers,
        json={"title": "Owner Edited Assignment", "max_score": 20},
    )
    assert owner_assignment.status_code == 201

    admin_unit = client.post(
        f"/api/courses/{scope['course_id']}/units",
        headers=admin_headers,
        json={"title": "Admin Edited Unit", "position": 3, "status": "published"},
    )
    assert admin_unit.status_code == 201

    admin_assignment = client.post(
        f"/api/courses/{scope['course_id']}/units/{admin_unit.json()['id']}/assignments",
        headers=admin_headers,
        json={"title": "Admin Edited Assignment", "max_score": 20},
    )
    assert admin_assignment.status_code == 201


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

    review = client.get(f"/api/assignments/{scope['assignment_id']}/review", headers=student_headers)
    assert review.status_code == 200
    review_body = review.json()
    assert review_body["assignment"]["id"] == scope["assignment_id"]
    assert review_body["submission"] is None
    assert review_body["can_submit"] is True
    assert review_body["read_only"] is False
    assert review_body["submit_block_reason"] is None

    closed_assignment = client.post(
        f"/api/courses/{scope['course_id']}/units/{scope['unit_id']}/assignments",
        headers=teacher_headers,
        json={"title": "Closed Empty Assignment", "max_score": 20, "status": "closed"},
    )
    assert closed_assignment.status_code == 201
    closed_review = client.get(f"/api/assignments/{closed_assignment.json()['id']}/review", headers=student_headers)
    assert closed_review.status_code == 200
    closed_review_body = closed_review.json()
    assert closed_review_body["submission"] is None
    assert closed_review_body["can_submit"] is False
    assert closed_review_body["read_only"] is True
    assert closed_review_body["submit_block_reason"] == "assignment_closed"

    archived_assignment = client.post(
        f"/api/courses/{scope['course_id']}/units/{scope['unit_id']}/assignments",
        headers=teacher_headers,
        json={"title": "Archived Empty Assignment", "max_score": 20, "status": "archived"},
    )
    assert archived_assignment.status_code == 201
    archived_review = client.get(f"/api/assignments/{archived_assignment.json()['id']}/review", headers=student_headers)
    assert archived_review.status_code == 200
    archived_review_body = archived_review.json()
    assert archived_review_body["submission"] is None
    assert archived_review_body["can_submit"] is False
    assert archived_review_body["read_only"] is True
    assert archived_review_body["submit_block_reason"] == "assignment_archived"


def test_students_only_see_published_course_content_and_active_assignments(client):
    teacher = _register_and_login(client, "visibility_teacher", "teacher")
    student = _register_and_login(client, "visibility_student", "student")
    teacher_headers = _auth_header(teacher["token"])
    student_headers = _auth_header(student["token"])

    school = client.post("/api/schools", headers=teacher_headers, json={"name": "Visibility School"})
    assert school.status_code == 201
    school_id = school.json()["id"]
    class_response = client.post(
        "/api/classes",
        headers=teacher_headers,
        json={"school_id": school_id, "name": "Visibility Class"},
    )
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]
    join = client.post(f"/api/classes/{class_id}/join", headers=student_headers, json={"role": "student"})
    assert join.status_code == 201

    published_course = client.post(
        "/api/courses",
        headers=teacher_headers,
        json={"school_id": school_id, "title": "Published Visibility Course", "status": "published"},
    )
    assert published_course.status_code == 201
    published_course_id = published_course.json()["id"]
    draft_course = client.post(
        "/api/courses",
        headers=teacher_headers,
        json={"school_id": school_id, "title": "Draft Visibility Course", "status": "draft"},
    )
    assert draft_course.status_code == 201
    draft_course_id = draft_course.json()["id"]
    unattached_course = client.post(
        "/api/courses",
        headers=teacher_headers,
        json={"school_id": school_id, "title": "Unattached Published Course", "status": "published"},
    )
    assert unattached_course.status_code == 201

    for course_id in (published_course_id, draft_course_id):
        attach = client.post(
            f"/api/courses/{course_id}/classes",
            headers=teacher_headers,
            json={"class_id": class_id},
        )
        assert attach.status_code == 201

    published_unit = client.post(
        f"/api/courses/{published_course_id}/units",
        headers=teacher_headers,
        json={"title": "Visible Unit", "position": 1, "status": "published"},
    )
    assert published_unit.status_code == 201
    published_unit_id = published_unit.json()["id"]
    draft_unit = client.post(
        f"/api/courses/{published_course_id}/units",
        headers=teacher_headers,
        json={"title": "Hidden Draft Unit", "position": 2, "status": "draft"},
    )
    assert draft_unit.status_code == 201
    draft_unit_id = draft_unit.json()["id"]
    draft_course_unit = client.post(
        f"/api/courses/{draft_course_id}/units",
        headers=teacher_headers,
        json={"title": "Draft Course Unit", "position": 1, "status": "published"},
    )
    assert draft_course_unit.status_code == 201
    draft_course_unit_id = draft_course_unit.json()["id"]

    visible_assignment = client.post(
        f"/api/courses/{published_course_id}/units/{published_unit_id}/assignments",
        headers=teacher_headers,
        json={"title": "Visible Active Assignment", "max_score": 20, "status": "active"},
    )
    assert visible_assignment.status_code == 201
    visible_assignment_id = visible_assignment.json()["id"]
    closed_assignment = client.post(
        f"/api/courses/{published_course_id}/units/{published_unit_id}/assignments",
        headers=teacher_headers,
        json={"title": "Closed Assignment", "max_score": 20, "status": "closed"},
    )
    assert closed_assignment.status_code == 201
    closed_assignment_id = closed_assignment.json()["id"]
    hidden_unit_assignment = client.post(
        f"/api/courses/{published_course_id}/units/{draft_unit_id}/assignments",
        headers=teacher_headers,
        json={"title": "Hidden Unit Assignment", "max_score": 20, "status": "active"},
    )
    assert hidden_unit_assignment.status_code == 201
    hidden_unit_assignment_id = hidden_unit_assignment.json()["id"]
    draft_course_assignment = client.post(
        f"/api/courses/{draft_course_id}/units/{draft_course_unit_id}/assignments",
        headers=teacher_headers,
        json={"title": "Draft Course Assignment", "max_score": 20, "status": "active"},
    )
    assert draft_course_assignment.status_code == 201
    draft_course_assignment_id = draft_course_assignment.json()["id"]

    for path in ("/api/courses", f"/api/courses?school_id={school_id}", f"/api/courses?class_id={class_id}"):
        student_courses = client.get(path, headers=student_headers)
        assert student_courses.status_code == 200
        assert [item["id"] for item in student_courses.json()] == [published_course_id]

    teacher_class_courses = client.get(f"/api/courses?class_id={class_id}", headers=teacher_headers)
    assert teacher_class_courses.status_code == 200
    assert [item["id"] for item in teacher_class_courses.json()] == [published_course_id, draft_course_id]

    student_units = client.get(f"/api/courses/{published_course_id}/units", headers=student_headers)
    assert student_units.status_code == 200
    assert [item["id"] for item in student_units.json()] == [published_unit_id]
    teacher_units = client.get(f"/api/courses/{published_course_id}/units", headers=teacher_headers)
    assert teacher_units.status_code == 200
    assert [item["id"] for item in teacher_units.json()] == [published_unit_id, draft_unit_id]
    draft_course_units = client.get(f"/api/courses/{draft_course_id}/units", headers=student_headers)
    assert draft_course_units.status_code == 403
    assert draft_course_units.json()["detail"] == "Course is not published"

    student_assignments = client.get(f"/api/courses/{published_course_id}/assignments", headers=student_headers)
    assert student_assignments.status_code == 200
    assert [item["id"] for item in student_assignments.json()] == [visible_assignment_id]
    teacher_assignments = client.get(f"/api/courses/{published_course_id}/assignments", headers=teacher_headers)
    assert teacher_assignments.status_code == 200
    assert [item["id"] for item in teacher_assignments.json()] == [
        visible_assignment_id,
        closed_assignment_id,
        hidden_unit_assignment_id,
    ]

    visible_event = client.post(
        "/api/learning-events",
        headers=student_headers,
        json={"class_id": class_id, "assignment_id": visible_assignment_id, "event_type": "complete", "payload": {}},
    )
    assert visible_event.status_code == 201
    hidden_unit_event = client.post(
        "/api/learning-events",
        headers=student_headers,
        json={"class_id": class_id, "assignment_id": hidden_unit_assignment_id, "event_type": "complete", "payload": {}},
    )
    assert hidden_unit_event.status_code == 403
    assert hidden_unit_event.json()["detail"] == "Course unit is not published"
    closed_event = client.post(
        "/api/learning-events",
        headers=student_headers,
        json={"class_id": class_id, "assignment_id": closed_assignment_id, "event_type": "complete", "payload": {}},
    )
    assert closed_event.status_code == 409
    assert closed_event.json()["detail"] == "Assignment is not active"
    draft_course_event = client.post(
        "/api/learning-events",
        headers=student_headers,
        json={"class_id": class_id, "assignment_id": draft_course_assignment_id, "event_type": "complete", "payload": {}},
    )
    assert draft_course_event.status_code == 403
    assert draft_course_event.json()["detail"] == "Course is not published"

    hidden_unit_submission = client.post(
        f"/api/assignments/{hidden_unit_assignment_id}/submissions",
        headers=student_headers,
        json={"class_id": class_id, "content": {"answer": "hidden unit"}},
    )
    assert hidden_unit_submission.status_code == 403
    assert hidden_unit_submission.json()["detail"] == "Course unit is not published"
    closed_submission = client.post(
        f"/api/assignments/{closed_assignment_id}/submissions",
        headers=student_headers,
        json={"class_id": class_id, "content": {"answer": "closed"}},
    )
    assert closed_submission.status_code == 409
    assert closed_submission.json()["detail"] == "Assignment is not active"
    draft_course_submission = client.post(
        f"/api/assignments/{draft_course_assignment_id}/submissions",
        headers=student_headers,
        json={"class_id": class_id, "content": {"answer": "draft course"}},
    )
    assert draft_course_submission.status_code == 403
    assert draft_course_submission.json()["detail"] == "Course is not published"

    hidden_review = client.get(f"/api/assignments/{hidden_unit_assignment_id}/review", headers=student_headers)
    assert hidden_review.status_code == 403
    assert hidden_review.json()["detail"] == "Course unit is not published"
    closed_review = client.get(f"/api/assignments/{closed_assignment_id}/review", headers=student_headers)
    assert closed_review.status_code == 200
    assert closed_review.json()["submit_block_reason"] == "assignment_closed"
    draft_course_review = client.get(f"/api/assignments/{draft_course_assignment_id}/review", headers=student_headers)
    assert draft_course_review.status_code == 403
    assert draft_course_review.json()["detail"] == "Course is not published"


def test_student_personal_progress_and_knowledge_exclude_hidden_resource_history(client):
    teacher = _register_and_login(client, "visibility_history_teacher", "teacher")
    student = _register_and_login(client, "visibility_history_student", "student")
    teacher_headers = _auth_header(teacher["token"])
    student_headers = _auth_header(student["token"])

    school = client.post("/api/schools", headers=teacher_headers, json={"name": "Visibility History School"})
    assert school.status_code == 201
    school_id = school.json()["id"]
    class_response = client.post(
        "/api/classes",
        headers=teacher_headers,
        json={"school_id": school_id, "name": "Visibility History Class"},
    )
    assert class_response.status_code == 201
    class_id = class_response.json()["id"]
    join = client.post(f"/api/classes/{class_id}/join", headers=student_headers, json={"role": "student"})
    assert join.status_code == 201

    course = client.post(
        "/api/courses",
        headers=teacher_headers,
        json={"school_id": school_id, "title": "Visible History Course", "status": "published"},
    )
    assert course.status_code == 201
    course_id = course.json()["id"]
    soon_hidden_course = client.post(
        "/api/courses",
        headers=teacher_headers,
        json={"school_id": school_id, "title": "Soon Hidden Course", "status": "published"},
    )
    assert soon_hidden_course.status_code == 201
    soon_hidden_course_id = soon_hidden_course.json()["id"]
    for course_to_attach in (course_id, soon_hidden_course_id):
        attach = client.post(
            f"/api/courses/{course_to_attach}/classes",
            headers=teacher_headers,
            json={"class_id": class_id},
        )
        assert attach.status_code == 201

    visible_unit = client.post(
        f"/api/courses/{course_id}/units",
        headers=teacher_headers,
        json={"title": "Visible History Unit", "position": 1, "status": "published"},
    )
    assert visible_unit.status_code == 201
    hidden_unit = client.post(
        f"/api/courses/{course_id}/units",
        headers=teacher_headers,
        json={"title": "Soon Hidden Unit", "position": 2, "status": "published"},
    )
    assert hidden_unit.status_code == 201
    hidden_course_unit = client.post(
        f"/api/courses/{soon_hidden_course_id}/units",
        headers=teacher_headers,
        json={"title": "Soon Hidden Course Unit", "position": 1, "status": "published"},
    )
    assert hidden_course_unit.status_code == 201

    visible_assignment = client.post(
        f"/api/courses/{course_id}/units/{visible_unit.json()['id']}/assignments",
        headers=teacher_headers,
        json={"title": "Visible History Assignment", "max_score": 10, "status": "active"},
    )
    assert visible_assignment.status_code == 201
    visible_assignment_id = visible_assignment.json()["id"]
    hidden_assignment = client.post(
        f"/api/courses/{course_id}/units/{hidden_unit.json()['id']}/assignments",
        headers=teacher_headers,
        json={"title": "Soon Hidden Assignment", "max_score": 10, "status": "active"},
    )
    assert hidden_assignment.status_code == 201
    hidden_assignment_id = hidden_assignment.json()["id"]
    hidden_course_assignment = client.post(
        f"/api/courses/{soon_hidden_course_id}/units/{hidden_course_unit.json()['id']}/assignments",
        headers=teacher_headers,
        json={"title": "Soon Hidden Course Assignment", "max_score": 10, "status": "active"},
    )
    assert hidden_course_assignment.status_code == 201

    for assignment_id, score in ((visible_assignment_id, 7), (hidden_assignment_id, 9)):
        event = client.post(
            "/api/learning-events",
            headers=student_headers,
            json={"class_id": class_id, "assignment_id": assignment_id, "event_type": "complete", "payload": {}},
        )
        assert event.status_code == 201
        submission = client.post(
            f"/api/assignments/{assignment_id}/submissions",
            headers=student_headers,
            json={"class_id": class_id, "content": {"answer": f"score {score}"}},
        )
        assert submission.status_code == 201
        grade = client.patch(
            f"/api/submissions/{submission.json()['id']}/grade",
            headers=teacher_headers,
            json={"score": score, "feedback": "graded"},
        )
        assert grade.status_code == 200

    snapshot_params = {
        "course_id": soon_hidden_course_id,
        "class_id": class_id,
        "from": "2026-01-01T00:00:00",
        "to": "2026-12-31T23:59:59",
        "granularity": "day",
    }
    hidden_course_snapshot = client.post(
        "/api/knowledge/me/snapshots",
        headers=student_headers,
        params=snapshot_params,
    )
    assert hidden_course_snapshot.status_code == 201

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        stored_unit = db.get(CourseUnit, hidden_unit.json()["id"])
        assert stored_unit is not None
        stored_unit.status = "draft"
        stored_course = db.get(Course, soon_hidden_course_id)
        assert stored_course is not None
        stored_course.status = "draft"
        db.commit()

    own_events = client.get("/api/learning-events", headers=student_headers)
    assert own_events.status_code == 200
    assert {item["assignment_id"] for item in own_events.json()} == {visible_assignment_id}

    progress = client.get(f"/api/progress/me?class_id={class_id}", headers=student_headers)
    assert progress.status_code == 200
    assert progress.json()["submitted_assignments"] == 1
    assert progress.json()["graded_assignments"] == 1
    assert progress.json()["learning_events"] == 2
    assert progress.json()["completed_events"] == 1
    assert progress.json()["total_points"] == 7

    teacher_progress = client.get(
        f"/api/progress/users/{student['id']}?class_id={class_id}",
        headers=teacher_headers,
    )
    assert teacher_progress.status_code == 200
    assert teacher_progress.json()["submitted_assignments"] == 2
    assert teacher_progress.json()["graded_assignments"] == 2
    assert teacher_progress.json()["learning_events"] == 4
    assert teacher_progress.json()["completed_events"] == 2
    assert teacher_progress.json()["total_points"] == 16

    knowledge = client.get(f"/api/knowledge/me?class_id={class_id}&course_id={course_id}", headers=student_headers)
    assert knowledge.status_code == 200
    assert knowledge.json()["assignment_count"] == 1
    assert knowledge.json()["submitted_assignments"] == 1
    assert knowledge.json()["graded_assignments"] == 1
    assert knowledge.json()["total_events"] == 2
    assert knowledge.json()["complete_events"] == 1
    assert knowledge.json()["score_total"] == 7
    assert knowledge.json()["max_score_total"] == 10
    assert knowledge.json()["total_points"] == 7

    visible_snapshot = client.post(
        "/api/knowledge/me/snapshots",
        headers=student_headers,
        params={
            "course_id": course_id,
            "class_id": class_id,
            "from": "2026-01-01T00:00:00",
            "to": "2026-12-31T23:59:59",
            "granularity": "day",
        },
    )
    assert visible_snapshot.status_code == 201
    assert visible_snapshot.json()["assignment_count"] == 1
    assert visible_snapshot.json()["total_points"] == 7

    hidden_course_knowledge = client.get(
        f"/api/knowledge/me?class_id={class_id}&course_id={soon_hidden_course_id}",
        headers=student_headers,
    )
    assert hidden_course_knowledge.status_code == 403
    assert hidden_course_knowledge.json()["detail"] == "Course is not published"
    hidden_course_snapshot_retry = client.post(
        "/api/knowledge/me/snapshots",
        headers=student_headers,
        params=snapshot_params,
    )
    assert hidden_course_snapshot_retry.status_code == 403
    assert hidden_course_snapshot_retry.json()["detail"] == "Course is not published"

    snapshot_list = client.get(
        "/api/knowledge/me/snapshots",
        headers=student_headers,
        params={"class_id": class_id, "limit": 10},
    )
    assert snapshot_list.status_code == 200
    assert [item["course_id"] for item in snapshot_list.json()["items"]] == [course_id]

    with session_factory() as db:
        run = knowledge_snapshot_runs.rebuild_periodic_knowledge_snapshots(
            db,
            granularity="day",
            reference_date=datetime(2026, 7, 6),
            trigger_source="pytest",
        )
        assert run.status == "success"
        assert run.class_snapshot_count == 2
        assert run.user_snapshot_count == 1
        hidden_user_snapshot = db.scalar(
            select(UserKnowledgeSnapshot).where(
                UserKnowledgeSnapshot.user_id == student["id"],
                UserKnowledgeSnapshot.course_id == soon_hidden_course_id,
                UserKnowledgeSnapshot.period_start == run.period_start,
                UserKnowledgeSnapshot.period_end == run.period_end,
            )
        )
        assert hidden_user_snapshot is None
