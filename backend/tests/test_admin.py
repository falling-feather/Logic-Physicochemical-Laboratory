import csv
import io
import json

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import AuditLog, AuthSession, ContentPageRecord, LoginAttempt, User
from app.services.audit import audit_log_chain_hash, record_audit_log


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


def test_admin_bootstrap_rejects_weak_password(client):
    response = client.post(
        "/api/admin/bootstrap",
        json={
            "username": "admin_weak",
            "password": "12345678",
            "display_name": "Weak Admin",
        },
    )

    assert response.status_code == 422
    assert "Password must include at least one letter" in response.json()["detail"]["password"]


def test_admin_bootstrap_rejects_blank_display_name_after_trimming(client):
    response = client.post(
        "/api/admin/bootstrap",
        json={
            "username": "admin_blank_display",
            "password": "secret123",
            "display_name": "   ",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Display name is required"


def test_admin_bootstrap_normalizes_username(client):
    response = client.post(
        "/api/admin/bootstrap",
        json={
            "username": "AdminRootCase",
            "password": "secret123",
            "display_name": "Root Admin",
        },
    )
    assert response.status_code == 201
    assert response.json()["username"] == "adminrootcase"
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        stored = db.scalar(select(User).where(User.username == "adminrootcase"))
        assert stored is not None
        assert stored.normalized_username == "adminrootcase"

    login = client.post(
        "/api/auth/login",
        json={"username": "ADMINROOTCASE", "password": "secret123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["username"] == "adminrootcase"


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
    users_body = users.json()
    assert users_body["total"] == 3
    assert users_body["next_offset"] is None
    teacher = next(item for item in users_body["items"] if item["username"] == "teacher_admin_scope")

    paged_users = client.get("/api/admin/users?limit=2", headers=_auth_header(admin_token))
    assert paged_users.status_code == 200
    assert paged_users.json()["total"] == 3
    assert paged_users.json()["next_offset"] == 2

    searched_users = client.get("/api/admin/users?q=student_admin_scope", headers=_auth_header(admin_token))
    assert searched_users.status_code == 200
    assert searched_users.json()["total"] == 1
    assert searched_users.json()["items"][0]["username"] == "student_admin_scope"

    disable_teacher = client.patch(
        f"/api/admin/users/{teacher['id']}",
        headers=_auth_header(admin_token),
        json={"status": "disabled"},
    )
    assert disable_teacher.status_code == 200
    assert disable_teacher.json()["status"] == "disabled"
    disabled_teacher_me = client.get("/api/users/me", headers=_auth_header(teacher_token))
    assert disabled_teacher_me.status_code == 401
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        teacher_session = db.scalar(select(AuthSession).where(AuthSession.user_id == teacher["id"]))
        assert teacher_session is not None
        assert teacher_session.revoked_at is not None

    blank_display = client.patch(
        f"/api/admin/users/{teacher['id']}",
        headers=_auth_header(admin_token),
        json={"display_name": "   "},
    )
    assert blank_display.status_code == 422
    assert blank_display.json()["detail"] == "Display name is required"

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

    school_request_id = "school-create-request"
    school = client.post(
        "/api/schools",
        headers={**_auth_header(admin_token), "X-Request-ID": school_request_id, "User-Agent": "=audit-csv-risk"},
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
    assert admin_schools.json()["total"] == 1
    assert admin_schools.json()["items"][0]["name"] == "Admin Visible School"

    searched_schools = client.get("/api/admin/schools?q=Visible", headers=_auth_header(admin_token))
    assert searched_schools.status_code == 200
    assert searched_schools.json()["total"] == 1

    admin_classes = client.get(
        f"/api/admin/classes?school_id={school_id}",
        headers=_auth_header(admin_token),
    )
    assert admin_classes.status_code == 200
    assert admin_classes.json()["total"] == 1
    assert admin_classes.json()["items"][0]["name"] == "Admin Visible Class"

    searched_classes = client.get("/api/admin/classes?q=Visible", headers=_auth_header(admin_token))
    assert searched_classes.status_code == 200
    assert searched_classes.json()["total"] == 1

    pages = client.get("/api/admin/content/pages?q=energy", headers=_auth_header(admin_token))
    assert pages.status_code == 200
    assert pages.json()["total"] >= 1
    assert pages.json()["items"][0]["slug"] == "physics/energy-conservation"

    bug = client.post(
        "/api/admin/bugs",
        headers=_auth_header(admin_token),
        json={
            "title": "Admin smoke risk",
            "category": "BE",
            "severity": "P1",
            "source": "test_admin.py",
            "external_issue_provider": " Manual ",
            "external_issue_id": " DOC-001 ",
            "external_issue_url": " https://tracker.local/issues/DOC-001 ",
        },
    )
    assert bug.status_code == 201
    bug_id = bug.json()["id"]
    assert bug.json()["external_issue_provider"] == "manual"
    assert bug.json()["external_issue_id"] == "DOC-001"
    assert bug.json()["external_issue_url"] == "https://tracker.local/issues/DOC-001"

    blank_bug_title = client.post(
        "/api/admin/bugs",
        headers=_auth_header(admin_token),
        json={"title": "   ", "category": "BE"},
    )
    assert blank_bug_title.status_code == 422
    assert blank_bug_title.json()["detail"] == "Bug title is required"

    blank_bug_category = client.post(
        "/api/admin/bugs",
        headers=_auth_header(admin_token),
        json={"title": "Category blank risk", "category": "   "},
    )
    assert blank_bug_category.status_code == 422
    assert blank_bug_category.json()["detail"] == "Bug category is required"

    blank_bug_title_update = client.patch(
        f"/api/admin/bugs/{bug_id}",
        headers=_auth_header(admin_token),
        json={"title": "   "},
    )
    assert blank_bug_title_update.status_code == 422
    assert blank_bug_title_update.json()["detail"] == "Bug title is required"

    blank_bug_category_update = client.patch(
        f"/api/admin/bugs/{bug_id}",
        headers=_auth_header(admin_token),
        json={"category": "   "},
    )
    assert blank_bug_category_update.status_code == 422
    assert blank_bug_category_update.json()["detail"] == "Bug category is required"

    close_bug = client.patch(
        f"/api/admin/bugs/{bug_id}",
        headers=_auth_header(admin_token),
        json={
            "status": "closed",
            "notes": "covered by regression",
            "external_issue_provider": " GitHub ",
            "external_issue_id": " ASTRA-42 ",
            "external_issue_url": " https://github.com/example/astra/issues/42 ",
        },
    )
    assert close_bug.status_code == 200
    assert close_bug.json()["status"] == "closed"
    assert close_bug.json()["external_issue_provider"] == "github"
    assert close_bug.json()["external_issue_id"] == "ASTRA-42"
    assert close_bug.json()["external_issue_url"] == "https://github.com/example/astra/issues/42"

    stats = client.get("/api/admin/stats", headers=_auth_header(admin_token))
    assert stats.status_code == 200
    assert stats.json()["total_users"] == 3
    assert stats.json()["users_by_role"]["admin"] == 1
    assert stats.json()["total_schools"] == 1
    assert stats.json()["total_classes"] == 1
    assert stats.json()["pending_class_join_requests"] == 0
    assert stats.json()["total_content_pages"] >= 1
    assert stats.json()["total_learning_events"] == 0
    assert stats.json()["total_bug_records"] == 1
    assert stats.json()["open_bug_records"] == 0
    assert stats.json()["total_audit_logs"] == 10

    audit_forbidden = client.get("/api/admin/audit-logs", headers=_auth_header(student_token))
    assert audit_forbidden.status_code == 403
    audit_export_forbidden = client.get("/api/admin/audit-logs/export", headers=_auth_header(student_token))
    assert audit_export_forbidden.status_code == 403
    audit_csv_export_forbidden = client.get("/api/admin/audit-logs/export.csv", headers=_auth_header(student_token))
    assert audit_csv_export_forbidden.status_code == 403
    audit_report_forbidden = client.get("/api/admin/audit-logs/report", headers=_auth_header(student_token))
    assert audit_report_forbidden.status_code == 403
    audit_report_csv_forbidden = client.get("/api/admin/audit-logs/report.csv", headers=_auth_header(student_token))
    assert audit_report_csv_forbidden.status_code == 403
    audit_frequency_forbidden = client.get("/api/admin/audit-logs/high-frequency", headers=_auth_header(student_token))
    assert audit_frequency_forbidden.status_code == 403

    audit_logs = client.get("/api/admin/audit-logs?limit=10", headers=_auth_header(admin_token))
    assert audit_logs.status_code == 200
    assert audit_logs.json()["total"] == 10
    ordered_chain_items = sorted(audit_logs.json()["items"], key=lambda item: item["id"])
    assert ordered_chain_items[0]["prev_hash"] is None
    for previous, current in zip(ordered_chain_items, ordered_chain_items[1:], strict=False):
        assert previous["current_hash"]
        assert len(previous["current_hash"]) == 64
        assert current["prev_hash"] == previous["current_hash"]
        assert current["current_hash"]
        assert len(current["current_hash"]) == 64
    actions = {item["action"] for item in audit_logs.json()["items"]}
    assert actions == {
        "admin.bootstrap",
        "admin.user.update",
        "auth.login.success",
        "auth.login.failed",
        "school.create",
        "class.create",
        "admin.bug.create",
        "admin.bug.update",
    }
    export_request_headers = {**_auth_header(admin_token), "X-Request-ID": "audit-export-request"}
    limited_export = client.get("/api/admin/audit-logs/export?limit=2", headers=export_request_headers)
    assert limited_export.status_code == 200
    assert limited_export.json()["total"] == 10
    assert limited_export.json()["limit"] == 2
    assert limited_export.json()["truncated"] is True
    assert len(limited_export.json()["items"]) == 2
    assert limited_export.json()["include_snapshot"] is False
    assert all(item["snapshot_json"] is None for item in limited_export.json()["items"])
    assert [item["id"] for item in limited_export.json()["items"]] == [
        item["id"] for item in audit_logs.json()["items"][:2]
    ]
    first_export_audit = client.get(
        "/api/admin/audit-logs?action=admin.audit.export&resource_type=audit_log&request_id=audit-export-request",
        headers=_auth_header(admin_token),
    )
    assert first_export_audit.status_code == 200
    assert first_export_audit.json()["total"] == 1
    first_export_item = first_export_audit.json()["items"][0]
    assert first_export_item["actor_role"] == "admin"
    assert first_export_item["resource_type"] == "audit_log"
    assert first_export_item["resource_id"] is None
    assert first_export_item["request_id"] == "audit-export-request"
    first_export_snapshot = first_export_item["snapshot_json"]
    assert first_export_snapshot["filters"] == {}
    assert first_export_snapshot["include_snapshot"] is False
    assert first_export_snapshot["limit"] == limited_export.json()["limit"]
    assert first_export_snapshot["total"] == limited_export.json()["total"]
    assert first_export_snapshot["exported_count"] == len(limited_export.json()["items"])
    assert first_export_snapshot["truncated"] == limited_export.json()["truncated"]
    assert "items" not in first_export_snapshot

    export_limit_too_large = client.get("/api/admin/audit-logs/export?limit=5001", headers=_auth_header(admin_token))
    assert export_limit_too_large.status_code == 422

    export_invalid_window = client.get(
        "/api/admin/audit-logs/export?from=2026-07-06T10:00:00Z&to=2026-07-05T10:00:00Z",
        headers=_auth_header(admin_token),
    )
    assert export_invalid_window.status_code == 422

    school_audit = client.get(
        f"/api/admin/audit-logs?action=school.create&resource_id={school_id}",
        headers=_auth_header(admin_token),
    )
    assert school_audit.status_code == 200
    assert school_audit.json()["total"] == 1
    school_audit_item = school_audit.json()["items"][0]
    assert school_audit_item["snapshot_json"]["after"]["name"] == "Admin Visible School"
    assert school_audit_item["event_result"] == "success"
    assert school_audit_item["request_id"] == school_request_id
    assert school_audit_item["request_method"] == "POST"
    assert school_audit_item["request_path"] == "/api/schools"
    assert school_audit_item["client_ip_hash"]
    assert school_audit_item["current_hash"]
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        stored_school_audit = db.get(AuditLog, school_audit_item["id"])
        assert stored_school_audit is not None
        assert stored_school_audit.current_hash == audit_log_chain_hash(stored_school_audit)

    school_export = client.get(
        f"/api/admin/audit-logs/export?action=school.create&resource_id={school_id}",
        headers=_auth_header(admin_token),
    )
    assert school_export.status_code == 200
    assert school_export.json()["total"] == 1
    assert school_export.json()["truncated"] is False
    assert school_export.json()["items"][0]["action"] == "school.create"
    assert school_export.json()["items"][0]["snapshot_json"] is None

    school_export_with_snapshot = client.get(
        f"/api/admin/audit-logs/export?action=school.create&resource_id={school_id}&include_snapshot=true",
        headers=_auth_header(admin_token),
    )
    assert school_export_with_snapshot.status_code == 200
    assert school_export_with_snapshot.json()["include_snapshot"] is True
    assert school_export_with_snapshot.json()["items"][0]["snapshot_json"]["after"]["name"] == "Admin Visible School"

    school_csv_export = client.get(
        f"/api/admin/audit-logs/export.csv?action=school.create&resource_id={school_id}",
        headers={**_auth_header(admin_token), "X-Request-ID": "audit-export-csv-request"},
    )
    assert school_csv_export.status_code == 200
    assert school_csv_export.headers["content-type"].startswith("text/csv")
    assert school_csv_export.headers["content-disposition"].startswith('attachment; filename="audit-logs-')
    assert school_csv_export.headers["x-audit-export-total"] == "1"
    assert school_csv_export.headers["x-audit-export-limit"] == "1000"
    assert school_csv_export.headers["x-audit-export-truncated"] == "false"
    assert school_csv_export.headers["x-audit-export-include-snapshot"] == "false"
    assert school_csv_export.headers["x-audit-exported-at"]
    school_csv_rows = list(csv.DictReader(io.StringIO(school_csv_export.text)))
    assert len(school_csv_rows) == 1
    assert school_csv_rows[0]["action"] == "school.create"
    assert school_csv_rows[0]["resource_id"] == str(school_id)
    assert school_csv_rows[0]["user_agent"] == "'=audit-csv-risk"
    assert school_csv_rows[0]["current_hash"] == school_audit_item["current_hash"]
    assert school_csv_rows[0]["prev_hash"] == school_audit_item["prev_hash"]
    assert school_csv_rows[0]["snapshot_json"] == ""

    school_csv_export_with_snapshot = client.get(
        f"/api/admin/audit-logs/export.csv?action=school.create&resource_id={school_id}&include_snapshot=true",
        headers=_auth_header(admin_token),
    )
    assert school_csv_export_with_snapshot.status_code == 200
    school_csv_snapshot_rows = list(csv.DictReader(io.StringIO(school_csv_export_with_snapshot.text)))
    assert json.loads(school_csv_snapshot_rows[0]["snapshot_json"])["after"]["name"] == "Admin Visible School"

    csv_export_audit = client.get(
        "/api/admin/audit-logs?action=admin.audit.export&resource_type=audit_log&request_id=audit-export-csv-request",
        headers=_auth_header(admin_token),
    )
    assert csv_export_audit.status_code == 200
    assert csv_export_audit.json()["total"] == 1
    csv_export_snapshot = csv_export_audit.json()["items"][0]["snapshot_json"]
    assert csv_export_snapshot["format"] == "csv"
    assert csv_export_snapshot["filters"] == {"action": "school.create", "resource_id": str(school_id)}
    assert csv_export_snapshot["include_snapshot"] is False
    assert csv_export_snapshot["exported_count"] == 1
    assert "items" not in csv_export_snapshot

    request_filtered_audit = client.get(
        f"/api/admin/audit-logs?request_id={school_request_id}",
        headers=_auth_header(admin_token),
    )
    assert request_filtered_audit.status_code == 200
    assert request_filtered_audit.json()["total"] == 1
    assert request_filtered_audit.json()["items"][0]["action"] == "school.create"
    request_filtered_export = client.get(
        f"/api/admin/audit-logs/export?request_id={school_request_id}",
        headers=_auth_header(admin_token),
    )
    assert request_filtered_export.status_code == 200
    assert request_filtered_export.json()["total"] == 1
    assert request_filtered_export.json()["items"][0]["request_id"] == school_request_id

    disabled_login_audit = client.get(
        "/api/admin/audit-logs?action=auth.login.failed&failure_reason=user_disabled&event_result=failure",
        headers=_auth_header(admin_token),
    )
    assert disabled_login_audit.status_code == 200
    assert disabled_login_audit.json()["total"] == 1
    disabled_login_export = client.get(
        "/api/admin/audit-logs/export?action=auth.login.failed&failure_reason=user_disabled&event_result=failure",
        headers=_auth_header(admin_token),
    )
    assert disabled_login_export.status_code == 200
    assert disabled_login_export.json()["total"] == 1
    assert disabled_login_export.json()["items"][0]["event_result"] == "failure"

    report_base_total = client.get("/api/admin/audit-logs?limit=1", headers=_auth_header(admin_token)).json()["total"]
    audit_report = client.get(
        "/api/admin/audit-logs/report?bucket_limit=20",
        headers={**_auth_header(admin_token), "X-Request-ID": "audit-report-request"},
    )
    assert audit_report.status_code == 200
    audit_report_body = audit_report.json()
    assert audit_report_body["total"] == report_base_total
    assert audit_report_body["bucket_limit"] == 20
    assert audit_report_body["filters"] == {}
    actions_report = {item["action"]: item for item in audit_report_body["by_action"]}
    assert actions_report["school.create"]["total"] == 1
    assert actions_report["school.create"]["success"] == 1
    assert actions_report["auth.login.failed"]["failure"] == 1
    assert actions_report["admin.audit.export"]["success"] == 7
    event_results_report = {item["key"]: item["total"] for item in audit_report_body["by_event_result"]}
    assert event_results_report["success"] >= 1
    assert event_results_report["failure"] >= 1
    failure_reasons_report = {item["key"]: item["total"] for item in audit_report_body["by_failure_reason"]}
    assert failure_reasons_report["user_disabled"] == 1

    report_audit = client.get(
        "/api/admin/audit-logs?action=admin.audit.report&resource_type=audit_log&request_id=audit-report-request",
        headers=_auth_header(admin_token),
    )
    assert report_audit.status_code == 200
    assert report_audit.json()["total"] == 1
    report_snapshot = report_audit.json()["items"][0]["snapshot_json"]
    assert report_snapshot["format"] == "json"
    assert report_snapshot["filters"] == {}
    assert report_snapshot["total"] == report_base_total
    assert report_snapshot["bucket_limit"] == 20
    assert "by_action" not in report_snapshot

    school_report_csv = client.get(
        f"/api/admin/audit-logs/report.csv?action=school.create&resource_id={school_id}&bucket_limit=5",
        headers={**_auth_header(admin_token), "X-Request-ID": "audit-report-csv-request"},
    )
    assert school_report_csv.status_code == 200
    assert school_report_csv.headers["content-type"].startswith("text/csv")
    assert school_report_csv.headers["content-disposition"].startswith('attachment; filename="audit-log-report-')
    assert school_report_csv.headers["x-audit-report-total"] == "1"
    assert school_report_csv.headers["x-audit-report-bucket-limit"] == "5"
    school_report_rows = list(csv.DictReader(io.StringIO(school_report_csv.text)))
    school_action_row = next(row for row in school_report_rows if row["section"] == "action")
    assert school_action_row["key"] == "school.create"
    assert school_action_row["total"] == "1"
    assert school_action_row["success"] == "1"
    assert school_action_row["failure"] == "0"
    assert any(row["section"] == "resource_type" and row["key"] == "school" for row in school_report_rows)

    csv_report_audit = client.get(
        "/api/admin/audit-logs?action=admin.audit.report&resource_type=audit_log&request_id=audit-report-csv-request",
        headers=_auth_header(admin_token),
    )
    assert csv_report_audit.status_code == 200
    assert csv_report_audit.json()["total"] == 1
    csv_report_snapshot = csv_report_audit.json()["items"][0]["snapshot_json"]
    assert csv_report_snapshot["format"] == "csv"
    assert csv_report_snapshot["filters"] == {"action": "school.create", "resource_id": str(school_id)}
    assert csv_report_snapshot["total"] == 1
    assert csv_report_snapshot["bucket_limit"] == 5
    assert "items" not in csv_report_snapshot

    report_bucket_limit_too_large = client.get(
        "/api/admin/audit-logs/report?bucket_limit=101",
        headers=_auth_header(admin_token),
    )
    assert report_bucket_limit_too_large.status_code == 422

    report_invalid_window = client.get(
        "/api/admin/audit-logs/report.csv?from=2026-07-06T10:00:00Z&to=2026-07-05T10:00:00Z",
        headers=_auth_header(admin_token),
    )
    assert report_invalid_window.status_code == 422

    audit_high_frequency = client.get(
        "/api/admin/audit-logs/high-frequency?min_count=2&bucket_limit=10&window_hours=24",
        headers={**_auth_header(admin_token), "X-Request-ID": "audit-high-frequency-request"},
    )
    assert audit_high_frequency.status_code == 200
    audit_high_frequency_body = audit_high_frequency.json()
    assert audit_high_frequency_body["thresholds"] == {
        "min_count": 2,
        "min_failure_count": 3,
        "min_failure_ratio": 0.5,
        "bucket_limit": 10,
    }
    assert audit_high_frequency_body["window"]["window_hours"] == 24
    assert audit_high_frequency_body["filters"] == {}
    frequency_actions = {
        item["action"]: item for item in audit_high_frequency_body["candidates"] if item["dimension"] == "action"
    }
    assert frequency_actions["admin.audit.export"]["total"] == 7
    assert frequency_actions["admin.audit.export"]["success"] == 7
    assert "count_threshold" in frequency_actions["admin.audit.export"]["reasons"]

    failure_frequency = client.get(
        "/api/admin/audit-logs/high-frequency?action=auth.login.failed"
        "&failure_reason=user_disabled&min_failure_count=1&min_failure_ratio=1&bucket_limit=10",
        headers=_auth_header(admin_token),
    )
    assert failure_frequency.status_code == 200
    failure_candidate = next(
        item for item in failure_frequency.json()["candidates"] if item["dimension"] == "failure_reason"
    )
    assert failure_candidate["failure_reason"] == "user_disabled"
    assert failure_candidate["failure"] == 1
    assert failure_candidate["failure_ratio"] == 1
    assert "failure_count_threshold" in failure_candidate["reasons"]
    assert "failure_ratio_threshold" in failure_candidate["reasons"]

    path_frequency = client.get(
        f"/api/admin/audit-logs/high-frequency?action=school.create&resource_id={school_id}&min_count=1",
        headers=_auth_header(admin_token),
    )
    assert path_frequency.status_code == 200
    path_frequency_body = path_frequency.json()
    assert path_frequency_body["filters"] == {"action": "school.create", "resource_id": str(school_id)}
    resource_candidate = next(
        item for item in path_frequency_body["candidates"] if item["dimension"] == "resource_action"
    )
    assert resource_candidate["key"] == f"school:{school_id}"
    assert resource_candidate["action"] == "school.create"
    assert resource_candidate["resource_type"] == "school"
    assert resource_candidate["resource_id"] == str(school_id)
    assert resource_candidate["total"] == 1
    assert resource_candidate["success"] == 1

    frequency_audit = client.get(
        "/api/admin/audit-logs?action=admin.audit.high_frequency&resource_type=audit_log&request_id=audit-high-frequency-request",
        headers=_auth_header(admin_token),
    )
    assert frequency_audit.status_code == 200
    assert frequency_audit.json()["total"] == 1
    frequency_snapshot = frequency_audit.json()["items"][0]["snapshot_json"]
    assert frequency_snapshot["format"] == "high_frequency"
    assert frequency_snapshot["filters"] == {}
    assert frequency_snapshot["thresholds"]["min_count"] == 2
    assert frequency_snapshot["thresholds"]["bucket_limit"] == 10
    assert frequency_snapshot["candidate_count"] == len(audit_high_frequency_body["candidates"])
    assert frequency_snapshot["dimension_counts"]["action"] >= 1
    assert "candidates" not in frequency_snapshot

    frequency_threshold_too_large = client.get(
        "/api/admin/audit-logs/high-frequency?min_count=10001",
        headers=_auth_header(admin_token),
    )
    assert frequency_threshold_too_large.status_code == 422

    frequency_ratio_invalid = client.get(
        "/api/admin/audit-logs/high-frequency?min_failure_ratio=1.1",
        headers=_auth_header(admin_token),
    )
    assert frequency_ratio_invalid.status_code == 422

    frequency_invalid_window = client.get(
        "/api/admin/audit-logs/high-frequency?from=2026-07-06T10:00:00Z&to=2026-07-05T10:00:00Z",
        headers=_auth_header(admin_token),
    )
    assert frequency_invalid_window.status_code == 422

    export_audit = client.get(
        "/api/admin/audit-logs?action=admin.audit.export&limit=10",
        headers=_auth_header(admin_token),
    )
    assert export_audit.status_code == 200
    assert export_audit.json()["total"] == 7
    latest_export = export_audit.json()["items"][0]
    assert latest_export["resource_type"] == "audit_log"
    assert latest_export["event_result"] == "success"
    assert latest_export["request_method"] == "GET"
    assert latest_export["request_path"] == "/api/admin/audit-logs/export"
    export_snapshot = latest_export["snapshot_json"]
    assert export_snapshot["filters"] == {
        "action": "auth.login.failed",
        "event_result": "failure",
        "failure_reason": "user_disabled",
    }
    assert export_snapshot["include_snapshot"] is False
    assert export_snapshot["limit"] == 1000
    assert export_snapshot["total"] == 1
    assert export_snapshot["exported_count"] == 1
    assert export_snapshot["truncated"] is False
    assert "items" not in export_snapshot

    class_audit = client.get(
        f"/api/admin/audit-logs?action=class.create&resource_id={class_group.json()['id']}",
        headers=_auth_header(admin_token),
    )
    assert class_audit.status_code == 200
    assert class_audit.json()["total"] == 1
    assert class_audit.json()["items"][0]["snapshot_json"]["after"]["name"] == "Admin Visible Class"

    update_audit = client.get(
        f"/api/admin/audit-logs?action=admin.user.update&resource_id={teacher['id']}",
        headers=_auth_header(admin_token),
    )
    assert update_audit.status_code == 200
    assert update_audit.json()["total"] == 1
    update_snapshot = update_audit.json()["items"][0]["snapshot_json"]
    assert update_snapshot["changes"]["status"] == {"from": "active", "to": "disabled"}
    assert update_snapshot["revoked_sessions"] == 1

    bug_page = client.get("/api/admin/bugs?q=smoke&limit=1", headers=_auth_header(admin_token))
    assert bug_page.status_code == 200
    assert bug_page.json()["total"] == 1
    assert bug_page.json()["items"][0]["id"] == bug_id
    assert bug_page.json()["next_offset"] is None

    bug_issue_page = client.get("/api/admin/bugs?q=ASTRA-42&limit=1", headers=_auth_header(admin_token))
    assert bug_issue_page.status_code == 200
    assert bug_issue_page.json()["total"] == 1
    assert bug_issue_page.json()["items"][0]["external_issue_provider"] == "github"

    bug_update_audit = client.get(
        f"/api/admin/audit-logs?action=admin.bug.update&resource_id={bug_id}",
        headers=_auth_header(admin_token),
    )
    assert bug_update_audit.status_code == 200
    assert bug_update_audit.json()["total"] == 1
    bug_update_snapshot = bug_update_audit.json()["items"][0]["snapshot_json"]
    assert bug_update_snapshot["changes"]["external_issue_provider"] == {"from": "manual", "to": "github"}
    assert bug_update_snapshot["changes"]["external_issue_id"] == {"from": "DOC-001", "to": "ASTRA-42"}

    student_forbidden = client.get("/api/admin/stats", headers=_auth_header(student_token))
    assert student_forbidden.status_code == 403


def test_audit_hash_chain_links_multiple_logs_in_one_transaction(client):
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        first = record_audit_log(
            db,
            action="test.audit.first",
            resource_type="test_resource",
            event_result="success",
            snapshot={"value": 1},
        )
        second = record_audit_log(
            db,
            action="test.audit.second",
            resource_type="test_resource",
            event_result="success",
            snapshot={"value": 2},
        )

        assert first.prev_hash is None
        assert first.current_hash
        assert len(first.current_hash) == 64
        assert second.prev_hash == first.current_hash
        assert second.current_hash
        assert second.current_hash != first.current_hash
        assert first.current_hash == audit_log_chain_hash(first)
        assert second.current_hash == audit_log_chain_hash(second)

        original_second_hash = second.current_hash
        second.snapshot_json = {"value": "tampered"}
        assert audit_log_chain_hash(second) != original_second_hash


def test_admin_can_reset_user_password_and_revoke_sessions(client):
    admin_token = _bootstrap_admin(client)
    teacher_token = _register_and_login(client, "teacher_password_reset", "teacher")

    users = client.get("/api/admin/users?q=teacher_password_reset", headers=_auth_header(admin_token))
    assert users.status_code == 200
    teacher = users.json()["items"][0]

    weak_reset = client.post(
        f"/api/admin/users/{teacher['id']}/password-reset",
        headers=_auth_header(admin_token),
        json={"password": "12345678"},
    )
    assert weak_reset.status_code == 422
    assert "Password must include at least one letter" in weak_reset.json()["detail"]["password"]

    forbidden_reset = client.post(
        f"/api/admin/users/{teacher['id']}/password-reset",
        headers=_auth_header(teacher_token),
        json={"password": "ResetPass123"},
    )
    assert forbidden_reset.status_code == 403

    missing_user_reset = client.post(
        "/api/admin/users/9999/password-reset",
        headers=_auth_header(admin_token),
        json={"password": "ResetPass123"},
    )
    assert missing_user_reset.status_code == 404

    failed_login = client.post(
        "/api/auth/login",
        json={"username": "teacher_password_reset", "password": "wrong-secret"},
    )
    assert failed_login.status_code == 401

    reset = client.post(
        f"/api/admin/users/{teacher['id']}/password-reset",
        headers={**_auth_header(admin_token), "X-Request-ID": "admin-password-reset-request"},
        json={"password": "ResetPass123"},
    )
    assert reset.status_code == 200
    assert reset.json() == {
        "status": "ok",
        "user_id": teacher["id"],
        "revoked_sessions": 1,
        "cleared_login_attempt": True,
    }

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        cleared_attempt = db.scalar(
            select(LoginAttempt).where(LoginAttempt.normalized_username == "teacher_password_reset")
        )
        assert cleared_attempt is None

    old_token_me = client.get("/api/users/me", headers=_auth_header(teacher_token))
    assert old_token_me.status_code == 401
    old_password_login = client.post(
        "/api/auth/login",
        json={"username": "teacher_password_reset", "password": "secret123"},
    )
    assert old_password_login.status_code == 401
    new_password_login = client.post(
        "/api/auth/login",
        json={"username": "teacher_password_reset", "password": "ResetPass123"},
    )
    assert new_password_login.status_code == 200

    with session_factory() as db:
        revoked_session = db.scalar(
            select(AuthSession).where(AuthSession.user_id == teacher["id"], AuthSession.revoked_at.is_not(None))
        )
        assert revoked_session is not None
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "admin.user.password_reset"))
        assert audit is not None
        assert audit.resource_type == "user"
        assert audit.resource_id == str(teacher["id"])
        assert audit.request_id == "admin-password-reset-request"
        assert audit.snapshot_json["revoked_sessions"] == 1
        assert audit.snapshot_json["cleared_login_attempt"] is True
        assert audit.snapshot_json["user"]["username"] == "teacher_password_reset"
        assert "password" not in audit.snapshot_json
        assert "ResetPass123" not in str(audit.snapshot_json)
        assert "secret123" not in str(audit.snapshot_json)


def test_admin_content_pages_filter_count_and_paginate_in_database(client):
    admin_token = _bootstrap_admin(client)
    _insert_content_page("physics/db-page-alpha", "DBPage Alpha", status="published")
    _insert_content_page("physics/db-page-beta", "DBPage Beta", status="published")
    _insert_content_page("physics/db-page-draft", "DBPage Draft", status="draft")
    _insert_content_page("physics/db-page-percent", "100% Energy", status="published")
    _insert_content_page("physics/db-page-percent-decoy", "100X Energy", status="published")
    _insert_content_page("physics/db-page_under", "Underscore Search", status="published")
    _insert_content_page("physics/db-page-galaxy", "Galaxy Field", status="published", galaxy="db-galaxy-token")
    _insert_content_page("physics/db-page-subject", "Subject Field", status="published", subject="db-subject-token")
    _insert_content_page("physics/db-page-layout", "Layout Field", status="published", layout="db-layout-token")

    first_page = client.get(
        "/api/admin/content/pages?q=DBPage&limit=2",
        headers=_auth_header(admin_token),
    )
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body["total"] == 3
    assert first_body["next_offset"] == 2
    assert [item["slug"] for item in first_body["items"]] == [
        "physics/db-page-alpha",
        "physics/db-page-beta",
    ]

    second_page = client.get(
        "/api/admin/content/pages?q=DBPage&limit=2&offset=2",
        headers=_auth_header(admin_token),
    )
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert second_body["total"] == 3
    assert second_body["next_offset"] is None
    assert [item["slug"] for item in second_body["items"]] == ["physics/db-page-draft"]

    draft_only = client.get(
        "/api/admin/content/pages?q=DBPage&status=draft",
        headers=_auth_header(admin_token),
    )
    assert draft_only.status_code == 200
    assert draft_only.json()["total"] == 1
    assert draft_only.json()["items"][0]["slug"] == "physics/db-page-draft"

    literal_percent = client.get(
        "/api/admin/content/pages",
        params={"q": "100%"},
        headers=_auth_header(admin_token),
    )
    assert literal_percent.status_code == 200
    assert literal_percent.json()["total"] == 1
    assert literal_percent.json()["items"][0]["slug"] == "physics/db-page-percent"

    literal_underscore = client.get(
        "/api/admin/content/pages",
        params={"q": "_"},
        headers=_auth_header(admin_token),
    )
    assert literal_underscore.status_code == 200
    assert literal_underscore.json()["total"] == 1
    assert literal_underscore.json()["items"][0]["slug"] == "physics/db-page_under"

    for query, slug in [
        ("db-galaxy-token", "physics/db-page-galaxy"),
        ("db-subject-token", "physics/db-page-subject"),
        ("db-layout-token", "physics/db-page-layout"),
    ]:
        field_search = client.get(
            "/api/admin/content/pages",
            params={"q": query},
            headers=_auth_header(admin_token),
        )
        assert field_search.status_code == 200
        assert field_search.json()["total"] == 1
        assert field_search.json()["items"][0]["slug"] == slug


def test_admin_class_join_request_queue_and_review(client):
    admin_token = _bootstrap_admin(client)
    teacher_token = _register_and_login(client, "teacher_join_queue", "teacher")
    first_student_token = _register_and_login(client, "student_join_queue_one", "student")
    second_student_token = _register_and_login(client, "student_join_queue_two", "student")

    school = client.post(
        "/api/schools",
        headers=_auth_header(admin_token),
        json={"name": "Admin Join Queue School", "region": "Shanghai"},
    )
    assert school.status_code == 201
    school_id = school.json()["id"]

    class_group = client.post(
        "/api/classes",
        headers=_auth_header(admin_token),
        json={"school_id": school_id, "name": "Admin Join Queue Class", "grade": "10"},
    )
    assert class_group.status_code == 201
    class_id = class_group.json()["id"]

    first_request = client.post(
        f"/api/classes/{class_id}/join-requests",
        headers=_auth_header(first_student_token),
        json={"role": "student", "message": "Queue alpha applicant"},
    )
    assert first_request.status_code == 201
    first_request_id = first_request.json()["id"]
    first_student_id = first_request.json()["user_id"]

    second_request = client.post(
        f"/api/classes/{class_id}/join-requests",
        headers=_auth_header(second_student_token),
        json={"role": "student", "message": "Queue beta applicant"},
    )
    assert second_request.status_code == 201
    second_request_id = second_request.json()["id"]

    forbidden_queue = client.get("/api/admin/class-join-requests", headers=_auth_header(teacher_token))
    assert forbidden_queue.status_code == 403

    stats = client.get("/api/admin/stats", headers=_auth_header(admin_token))
    assert stats.status_code == 200
    assert stats.json()["pending_class_join_requests"] == 2

    queue = client.get("/api/admin/class-join-requests?limit=1", headers=_auth_header(admin_token))
    assert queue.status_code == 200
    assert queue.json()["total"] == 2
    assert queue.json()["next_offset"] == 1
    queue_item = queue.json()["items"][0]
    assert queue_item["school_name"] == "Admin Join Queue School"
    assert queue_item["class_name"] == "Admin Join Queue Class"
    assert queue_item["status"] == "pending"

    filtered = client.get(
        f"/api/admin/class-join-requests?school_id={school_id}&class_id={class_id}&user_id={first_student_id}&q=alpha",
        headers=_auth_header(admin_token),
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["id"] == first_request_id

    approve = client.patch(
        f"/api/admin/class-join-requests/{first_request_id}",
        headers={**_auth_header(admin_token), "X-Request-ID": "admin-join-approve"},
        json={"status": "approved", "note": "Approved from admin queue"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"
    assert approve.json()["reviewed_by_user_id"] is not None

    reject = client.patch(
        f"/api/admin/class-join-requests/{second_request_id}",
        headers=_auth_header(admin_token),
        json={"status": "rejected", "note": "Missing confirmation"},
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    pending = client.get("/api/admin/class-join-requests", headers=_auth_header(admin_token))
    assert pending.status_code == 200
    assert pending.json()["total"] == 0

    approved = client.get("/api/admin/class-join-requests?status=approved", headers=_auth_header(admin_token))
    assert approved.status_code == 200
    assert approved.json()["total"] == 1
    assert approved.json()["items"][0]["id"] == first_request_id

    rejected = client.get("/api/admin/class-join-requests?status=rejected", headers=_auth_header(admin_token))
    assert rejected.status_code == 200
    assert rejected.json()["total"] == 1
    assert rejected.json()["items"][0]["id"] == second_request_id

    stats_after_review = client.get("/api/admin/stats", headers=_auth_header(admin_token))
    assert stats_after_review.status_code == 200
    assert stats_after_review.json()["pending_class_join_requests"] == 0

    approved_student_classes = client.get(f"/api/classes?school_id={school_id}", headers=_auth_header(first_student_token))
    assert approved_student_classes.status_code == 200
    assert approved_student_classes.json()[0]["id"] == class_id

    rejected_student_classes = client.get(f"/api/classes?school_id={school_id}", headers=_auth_header(second_student_token))
    assert rejected_student_classes.status_code == 403

    approve_audit = client.get(
        f"/api/admin/audit-logs?action=class.join.request.approve&resource_id={first_request_id}",
        headers=_auth_header(admin_token),
    )
    assert approve_audit.status_code == 200
    assert approve_audit.json()["total"] == 1
    approve_audit_item = approve_audit.json()["items"][0]
    assert approve_audit_item["request_id"] == "admin-join-approve"
    assert approve_audit_item["snapshot_json"]["after"]["approval_source"] == "admin_queue"

    join_audit = client.get(
        f"/api/admin/audit-logs?action=class.join&class_id={class_id}",
        headers=_auth_header(admin_token),
    )
    assert join_audit.status_code == 200
    assert join_audit.json()["total"] == 1
    assert join_audit.json()["items"][0]["snapshot_json"]["after"]["source_join_request_id"] == first_request_id


def _insert_content_page(
    slug: str,
    title: str,
    *,
    status: str,
    galaxy: str = "englab",
    subject: str = "physics",
    layout: str = "experiment-page",
) -> None:
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(
            ContentPageRecord(
                slug=slug,
                status=status,
                version="test",
                schema_json={
                    "slug": slug,
                    "galaxy": galaxy,
                    "subject": subject,
                    "title": title,
                    "layout": layout,
                    "status": status,
                    "version": "test",
                    "sections": [],
                    "sources": [],
                },
                schema_hash=None,
            )
        )
        db.commit()
