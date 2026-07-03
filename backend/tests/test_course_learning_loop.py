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
    course_class_id = attach.json()["id"]

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
    membership_id = join.json()["id"]

    duplicate_join = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(student_token),
        json={"role": "student"},
    )
    assert duplicate_join.status_code == 201
    assert duplicate_join.json()["id"] == membership_id

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

    admin_token = _bootstrap_admin(client, "admin_course_audit")
    pending_forbidden = client.get("/api/admin/submissions/pending", headers=_auth_header(student_token))
    assert pending_forbidden.status_code == 403

    pending = client.get(
        (
            "/api/admin/submissions/pending"
            f"?school_id={school_id}&class_id={class_id}&course_id={course_id}&assignment_id={assignment_id}"
        ),
        headers=_auth_header(admin_token),
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["total"] == 1
    assert pending_body["next_offset"] is None
    assert pending_body["items"][0]["id"] == submission_id
    assert pending_body["items"][0]["assignment_title"] == "Observe dissipation"
    assert pending_body["items"][0]["status"] == "submitted"

    school_stats_before_grade = client.get(
        f"/api/admin/schools/{school_id}/stats",
        headers=_auth_header(admin_token),
    )
    assert school_stats_before_grade.status_code == 200
    school_stats_before = school_stats_before_grade.json()
    assert school_stats_before["active_students"] == 1
    assert school_stats_before["active_teachers"] == 1
    assert school_stats_before["active_assignments"] == 1
    assert school_stats_before["pending_submissions"] == 1
    assert school_stats_before["graded_submissions"] == 0
    assert school_stats_before["total_points"] == 0

    class_stats_before_grade = client.get(
        f"/api/admin/classes/{class_id}/stats",
        headers=_auth_header(admin_token),
    )
    assert class_stats_before_grade.status_code == 200
    class_stats_before = class_stats_before_grade.json()
    assert class_stats_before["active_students"] == 1
    assert class_stats_before["active_teachers"] == 1
    assert class_stats_before["active_courses"] == 1
    assert class_stats_before["expected_submissions"] == 1
    assert class_stats_before["total_learning_events"] == 2
    assert class_stats_before["complete_learning_events"] == 1
    assert class_stats_before["pending_submissions"] == 1
    assert class_stats_before["pending_submission_ratio"] == 1
    assert class_stats_before["average_score_percent"] == 0

    grade = client.patch(
        f"/api/submissions/{submission_id}/grade",
        headers=_auth_header(teacher_token),
        json={"score": 18, "feedback": "Clear observation."},
    )
    assert grade.status_code == 200
    assert grade.json()["status"] == "graded"
    assert grade.json()["score"] == 18

    pending_after_grade = client.get(
        f"/api/admin/submissions/pending?class_id={class_id}",
        headers=_auth_header(admin_token),
    )
    assert pending_after_grade.status_code == 200
    assert pending_after_grade.json()["total"] == 0
    assert pending_after_grade.json()["items"] == []

    graded_queue = client.get(
        f"/api/admin/submissions/pending?class_id={class_id}&status=graded",
        headers=_auth_header(admin_token),
    )
    assert graded_queue.status_code == 200
    assert graded_queue.json()["total"] == 1
    assert graded_queue.json()["items"][0]["status"] == "graded"

    school_stats_after_grade = client.get(
        f"/api/admin/schools/{school_id}/stats",
        headers=_auth_header(admin_token),
    )
    assert school_stats_after_grade.status_code == 200
    school_stats_after = school_stats_after_grade.json()
    assert school_stats_after["total_submissions"] == 1
    assert school_stats_after["pending_submissions"] == 0
    assert school_stats_after["graded_submissions"] == 1
    assert school_stats_after["total_points"] == 18

    class_stats_after_grade = client.get(
        f"/api/admin/classes/{class_id}/stats",
        headers=_auth_header(admin_token),
    )
    assert class_stats_after_grade.status_code == 200
    class_stats_after = class_stats_after_grade.json()
    assert class_stats_after["pending_submissions"] == 0
    assert class_stats_after["pending_submission_ratio"] == 0
    assert class_stats_after["graded_submissions"] == 1
    assert class_stats_after["total_points"] == 18
    assert class_stats_after["average_points_per_student"] == 18
    assert class_stats_after["average_score_percent"] == 90

    grade_audit = client.get(
        f"/api/admin/audit-logs?action=submission.grade&resource_id={submission_id}",
        headers=_auth_header(admin_token),
    )
    assert grade_audit.status_code == 200
    grade_audit_items = grade_audit.json()["items"]
    assert grade_audit.json()["total"] == 1
    assert len(grade_audit_items) == 1
    grade_snapshot = grade_audit_items[0]["snapshot_json"]
    assert grade_snapshot["before"]["score"] is None
    assert grade_snapshot["after"]["score"] == 18
    assert grade_snapshot["after"]["score_delta"] == 18

    course_audit = client.get(
        f"/api/admin/audit-logs?action=course.create&resource_id={course_id}",
        headers=_auth_header(admin_token),
    )
    assert course_audit.status_code == 200
    course_audit_items = course_audit.json()["items"]
    assert course_audit.json()["total"] == 1
    assert len(course_audit_items) == 1
    assert course_audit_items[0]["snapshot_json"]["after"]["title"] == "Mechanics Path"

    course_class_audit = client.get(
        f"/api/admin/audit-logs?action=course.class.attach&resource_id={course_class_id}",
        headers=_auth_header(admin_token),
    )
    assert course_class_audit.status_code == 200
    course_class_audit_items = course_class_audit.json()["items"]
    assert course_class_audit.json()["total"] == 1
    assert len(course_class_audit_items) == 1
    assert course_class_audit_items[0]["snapshot_json"]["after"]["class_id"] == class_id

    unit_audit = client.get(
        f"/api/admin/audit-logs?action=course.unit.create&resource_id={unit_id}",
        headers=_auth_header(admin_token),
    )
    assert unit_audit.status_code == 200
    unit_audit_items = unit_audit.json()["items"]
    assert unit_audit.json()["total"] == 1
    assert len(unit_audit_items) == 1
    assert unit_audit_items[0]["snapshot_json"]["after"]["course_id"] == course_id

    assignment_audit = client.get(
        f"/api/admin/audit-logs?action=assignment.create&resource_id={assignment_id}",
        headers=_auth_header(admin_token),
    )
    assert assignment_audit.status_code == 200
    assignment_audit_items = assignment_audit.json()["items"]
    assert assignment_audit.json()["total"] == 1
    assert len(assignment_audit_items) == 1
    assert assignment_audit_items[0]["snapshot_json"]["after"]["unit_id"] == unit_id

    class_join_audit = client.get(
        f"/api/admin/audit-logs?action=class.join&class_id={class_id}",
        headers=_auth_header(admin_token),
    )
    assert class_join_audit.status_code == 200
    class_join_audit_items = class_join_audit.json()["items"]
    assert class_join_audit.json()["total"] == 1
    assert len(class_join_audit_items) == 1
    assert class_join_audit_items[0]["snapshot_json"]["after"]["role"] == "student"

    submission_create_audit = client.get(
        f"/api/admin/audit-logs?action=submission.create&resource_id={submission_id}",
        headers=_auth_header(admin_token),
    )
    assert submission_create_audit.status_code == 200
    submission_create_audit_items = submission_create_audit.json()["items"]
    assert submission_create_audit.json()["total"] == 1
    assert len(submission_create_audit_items) == 1
    assert submission_create_audit_items[0]["snapshot_json"]["after"]["content_keys"] == ["answer"]

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

    knowledge = client.get(
        f"/api/knowledge/me?class_id={class_id}&course_id={course_id}",
        headers=_auth_header(student_token),
    )
    assert knowledge.status_code == 200
    knowledge_body = knowledge.json()
    assert knowledge_body["assignment_count"] == 1
    assert knowledge_body["submitted_assignments"] == 1
    assert knowledge_body["graded_assignments"] == 1
    assert knowledge_body["total_events"] == 2
    assert knowledge_body["submit_events"] == 1
    assert knowledge_body["complete_events"] == 1
    assert knowledge_body["score_total"] == 18
    assert knowledge_body["max_score_total"] == 20
    assert knowledge_body["accuracy_percent"] == 90
    assert knowledge_body["completion_percent"] == 50
    assert knowledge_body["total_points"] == 18
    knowledge_stats = {item["rule_code"]: item for item in knowledge_body["knowledge_stats"]}
    assert knowledge_stats["assignment_completion"]["percent"] == 100
    assert knowledge_stats["graded_score"]["frequency"] == 18
    assert knowledge_stats["graded_score"]["sample_size"] == 20
    assert knowledge_stats["learning_completion"]["percent"] == 50

    snapshot_params = {
        "course_id": course_id,
        "class_id": class_id,
        "from": "2026-01-01T00:00:00",
        "to": "2026-12-31T23:59:59",
        "granularity": "day",
    }
    missing_period_user_snapshot = client.post(
        "/api/knowledge/me/snapshots",
        headers=_auth_header(student_token),
    )
    assert missing_period_user_snapshot.status_code == 422

    user_snapshot = client.post(
        "/api/knowledge/me/snapshots",
        headers=_auth_header(student_token),
        params=snapshot_params,
    )
    assert user_snapshot.status_code == 201
    user_snapshot_body = user_snapshot.json()
    assert user_snapshot_body["user_id"] == grade.json()["student_id"]
    assert user_snapshot_body["class_id"] == class_id
    assert user_snapshot_body["course_id"] == course_id
    assert user_snapshot_body["granularity"] == "day"
    assert user_snapshot_body["rule_version"] == "v1"
    assert user_snapshot_body["assignment_count"] == knowledge_body["assignment_count"]
    assert user_snapshot_body["submitted_assignments"] == knowledge_body["submitted_assignments"]
    assert user_snapshot_body["graded_assignments"] == knowledge_body["graded_assignments"]
    assert user_snapshot_body["total_events"] == knowledge_body["total_events"]
    assert user_snapshot_body["complete_events"] == knowledge_body["complete_events"]
    assert user_snapshot_body["score_total"] == knowledge_body["score_total"]
    assert user_snapshot_body["accuracy_percent"] == knowledge_body["accuracy_percent"]
    assert user_snapshot_body["completion_percent"] == knowledge_body["completion_percent"]
    assert user_snapshot_body["total_points"] == knowledge_body["total_points"]
    user_snapshot_stats = {item["rule_code"]: item for item in user_snapshot_body["knowledge_stats"]}
    assert user_snapshot_stats["assignment_completion"]["percent"] == 100
    assert user_snapshot_stats["graded_score"]["frequency"] == 18
    assert "Mechanical energy decreases" not in str(user_snapshot_body)
    assert "payload" not in str(user_snapshot_body)

    duplicate_user_snapshot = client.post(
        "/api/knowledge/me/snapshots",
        headers=_auth_header(student_token),
        params=snapshot_params,
    )
    assert duplicate_user_snapshot.status_code == 201
    assert duplicate_user_snapshot.json()["id"] == user_snapshot_body["id"]

    user_snapshot_list = client.get(
        "/api/knowledge/me/snapshots",
        headers=_auth_header(student_token),
        params={"course_id": course_id, "class_id": class_id, "granularity": "day", "limit": 10},
    )
    assert user_snapshot_list.status_code == 200
    user_snapshot_list_body = user_snapshot_list.json()
    assert user_snapshot_list_body["total"] == 1
    assert user_snapshot_list_body["next_offset"] is None
    assert user_snapshot_list_body["items"][0]["id"] == user_snapshot_body["id"]

    outsider_user_snapshot = client.post(
        "/api/knowledge/me/snapshots",
        headers=_auth_header(outsider_token),
        params=snapshot_params,
    )
    assert outsider_user_snapshot.status_code == 403

    class_knowledge = client.get(
        f"/api/classes/{class_id}/knowledge?course_id={course_id}",
        headers=_auth_header(teacher_token),
    )
    assert class_knowledge.status_code == 200
    class_knowledge_body = class_knowledge.json()
    assert class_knowledge_body["students_total"] == 1
    assert class_knowledge_body["students_active"] == 1
    assert class_knowledge_body["assignment_count"] == 1
    assert class_knowledge_body["expected_submissions"] == 1
    assert class_knowledge_body["submitted_assignments"] == 1
    assert class_knowledge_body["graded_assignments"] == 1
    assert class_knowledge_body["average_score_percent"] == 90
    assert class_knowledge_body["completion_percent"] == 50
    assert class_knowledge_body["total_points"] == 18
    assert class_knowledge_body["average_points_per_student"] == 18
    class_stats = {item["rule_code"]: item for item in class_knowledge_body["knowledge_stats"]}
    assert class_stats["assignment_completion"]["sample_size"] == 1
    assert class_stats["graded_score"]["percent"] == 90

    class_snapshot_params = {
        "course_id": course_id,
        "from": "2026-01-01T00:00:00",
        "to": "2026-12-31T23:59:59",
        "granularity": "day",
    }
    class_snapshot = client.post(
        f"/api/classes/{class_id}/knowledge/snapshots",
        headers=_auth_header(teacher_token),
        params=class_snapshot_params,
    )
    assert class_snapshot.status_code == 201
    class_snapshot_body = class_snapshot.json()
    assert class_snapshot_body["class_id"] == class_id
    assert class_snapshot_body["course_id"] == course_id
    assert class_snapshot_body["granularity"] == "day"
    assert class_snapshot_body["rule_version"] == "v1"
    assert class_snapshot_body["students_total"] == class_knowledge_body["students_total"]
    assert class_snapshot_body["students_active"] == class_knowledge_body["students_active"]
    assert class_snapshot_body["expected_submissions"] == class_knowledge_body["expected_submissions"]
    assert class_snapshot_body["submitted_assignments"] == class_knowledge_body["submitted_assignments"]
    assert class_snapshot_body["average_score_percent"] == class_knowledge_body["average_score_percent"]
    assert class_snapshot_body["completion_percent"] == class_knowledge_body["completion_percent"]
    assert class_snapshot_body["total_points"] == class_knowledge_body["total_points"]
    snapshot_stats = {item["rule_code"]: item for item in class_snapshot_body["knowledge_stats"]}
    assert snapshot_stats["assignment_completion"]["sample_size"] == 1
    assert snapshot_stats["graded_score"]["percent"] == 90
    assert "Mechanical energy decreases" not in str(class_snapshot_body)

    duplicate_snapshot = client.post(
        f"/api/classes/{class_id}/knowledge/snapshots",
        headers=_auth_header(teacher_token),
        params=class_snapshot_params,
    )
    assert duplicate_snapshot.status_code == 201
    assert duplicate_snapshot.json()["id"] == class_snapshot_body["id"]

    snapshot_list = client.get(
        f"/api/classes/{class_id}/knowledge/snapshots",
        headers=_auth_header(teacher_token),
        params={"course_id": course_id, "granularity": "day", "limit": 10},
    )
    assert snapshot_list.status_code == 200
    snapshot_list_body = snapshot_list.json()
    assert snapshot_list_body["total"] == 1
    assert snapshot_list_body["next_offset"] is None
    assert snapshot_list_body["items"][0]["id"] == class_snapshot_body["id"]

    student_class_knowledge = client.get(
        f"/api/classes/{class_id}/knowledge",
        headers=_auth_header(student_token),
    )
    assert student_class_knowledge.status_code == 403

    student_snapshot = client.get(
        f"/api/classes/{class_id}/knowledge/snapshots",
        headers=_auth_header(student_token),
    )
    assert student_snapshot.status_code == 403

    student_rebuild_snapshot = client.post(
        f"/api/classes/{class_id}/knowledge/snapshots",
        headers=_auth_header(student_token),
        params=class_snapshot_params,
    )
    assert student_rebuild_snapshot.status_code == 403

    outsider_class_knowledge = client.get(
        f"/api/classes/{class_id}/knowledge",
        headers=_auth_header(outsider_token),
    )
    assert outsider_class_knowledge.status_code == 403

    outsider_snapshot = client.get(
        f"/api/classes/{class_id}/knowledge/snapshots",
        headers=_auth_header(outsider_token),
    )
    assert outsider_snapshot.status_code == 403

    own_events = client.get("/api/learning-events", headers=_auth_header(student_token))
    assert own_events.status_code == 200
    assert own_events.json()[0]["payload"]["score"] == 18

    teacher_events = client.get(
        f"/api/learning-events?class_id={class_id}",
        headers=_auth_header(teacher_token),
    )
    assert teacher_events.status_code == 200
    assert teacher_events.json()[0]["user_id"] == event.json()["user_id"]
