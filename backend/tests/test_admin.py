def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _bootstrap_admin(client) -> str:
    response = client.post(
        "/api/admin/bootstrap",
        json={
            "username": "admin_root",
            "password": "secret123",
            "display_name": "Root Admin",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "admin"

    login = client.post(
        "/api/auth/login",
        json={"username": "admin_root", "password": "secret123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _register_and_login(client, username: str, role: str) -> str:
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
    return login.json()["access_token"]


def test_admin_bootstrap_is_single_use(client):
    admin_token = _bootstrap_admin(client)

    second = client.post(
        "/api/admin/bootstrap",
        json={
            "username": "admin_second",
            "password": "secret123",
            "display_name": "Second Admin",
        },
    )
    assert second.status_code == 409

    me = client.get("/api/users/me", headers=_auth_header(admin_token))
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_admin_views_user_management_stats_and_bug_records(client):
    admin_token = _bootstrap_admin(client)
    teacher_token = _register_and_login(client, "teacher_admin_scope", "teacher")
    student_token = _register_and_login(client, "student_admin_scope", "student")

    forbidden = client.get("/api/admin/users", headers=_auth_header(teacher_token))
    assert forbidden.status_code == 403

    users = client.get("/api/admin/users", headers=_auth_header(admin_token))
    assert users.status_code == 200
    teacher = next(item for item in users.json() if item["username"] == "teacher_admin_scope")

    disable_teacher = client.patch(
        f"/api/admin/users/{teacher['id']}",
        headers=_auth_header(admin_token),
        json={"status": "disabled"},
    )
    assert disable_teacher.status_code == 200
    assert disable_teacher.json()["status"] == "disabled"

    disabled_login = client.post(
        "/api/auth/login",
        json={"username": "teacher_admin_scope", "password": "secret123"},
    )
    assert disabled_login.status_code == 403

    last_admin_demotion = client.patch(
        "/api/admin/users/1",
        headers=_auth_header(admin_token),
        json={"role": "teacher"},
    )
    assert last_admin_demotion.status_code == 409

    school = client.post(
        "/api/schools",
        headers=_auth_header(admin_token),
        json={"name": "Admin Visible School", "region": "Shanghai"},
    )
    assert school.status_code == 201
    school_id = school.json()["id"]

    class_group = client.post(
        "/api/classes",
        headers=_auth_header(admin_token),
        json={"school_id": school_id, "name": "Admin Visible Class", "grade": "10"},
    )
    assert class_group.status_code == 201

    admin_schools = client.get("/api/admin/schools", headers=_auth_header(admin_token))
    assert admin_schools.status_code == 200
    assert admin_schools.json()[0]["name"] == "Admin Visible School"

    admin_classes = client.get(
        f"/api/admin/classes?school_id={school_id}",
        headers=_auth_header(admin_token),
    )
    assert admin_classes.status_code == 200
    assert admin_classes.json()[0]["name"] == "Admin Visible Class"

    pages = client.get("/api/admin/content/pages", headers=_auth_header(admin_token))
    assert pages.status_code == 200
    assert pages.json()[0]["slug"] == "physics/energy-conservation"

    bug = client.post(
        "/api/admin/bugs",
        headers=_auth_header(admin_token),
        json={
            "title": "Admin smoke risk",
            "category": "BE",
            "severity": "P1",
            "source": "test_admin.py",
        },
    )
    assert bug.status_code == 201
    bug_id = bug.json()["id"]

    close_bug = client.patch(
        f"/api/admin/bugs/{bug_id}",
        headers=_auth_header(admin_token),
        json={"status": "closed", "notes": "covered by regression"},
    )
    assert close_bug.status_code == 200
    assert close_bug.json()["status"] == "closed"

    stats = client.get("/api/admin/stats", headers=_auth_header(admin_token))
    assert stats.status_code == 200
    assert stats.json()["total_users"] == 3
    assert stats.json()["users_by_role"]["admin"] == 1
    assert stats.json()["total_schools"] == 1
    assert stats.json()["total_classes"] == 1
    assert stats.json()["total_content_pages"] >= 1
    assert stats.json()["total_learning_events"] == 0
    assert stats.json()["total_bug_records"] == 1
    assert stats.json()["open_bug_records"] == 0
    assert stats.json()["total_audit_logs"] == 4

    audit_forbidden = client.get("/api/admin/audit-logs", headers=_auth_header(student_token))
    assert audit_forbidden.status_code == 403

    audit_logs = client.get("/api/admin/audit-logs?limit=10", headers=_auth_header(admin_token))
    assert audit_logs.status_code == 200
    actions = {item["action"] for item in audit_logs.json()}
    assert actions == {"admin.bootstrap", "admin.user.update", "admin.bug.create", "admin.bug.update"}

    update_audit = client.get(
        f"/api/admin/audit-logs?action=admin.user.update&resource_id={teacher['id']}",
        headers=_auth_header(admin_token),
    )
    assert update_audit.status_code == 200
    assert len(update_audit.json()) == 1
    update_snapshot = update_audit.json()[0]["snapshot_json"]
    assert update_snapshot["changes"]["status"] == {"from": "active", "to": "disabled"}

    student_forbidden = client.get("/api/admin/stats", headers=_auth_header(student_token))
    assert student_forbidden.status_code == 403
