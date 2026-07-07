import base64
import csv
import hashlib
import io
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models import (
    AuditLog,
    AuthSession,
    ContentPageRecord,
    ContentPageVersion,
    ContentScriptAsset,
    KnowledgeSnapshotRun,
    LoginAttempt,
    SchoolMembership,
    User,
)
from app.services.content_script_assets import external_script_references
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


def _current_user_id(client, token: str) -> int:
    response = client.get("/api/users/me", headers=_auth_header(token))
    assert response.status_code == 200
    return response.json()["id"]


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
    audit_retention_forbidden = client.get(
        "/api/admin/audit-logs/retention-plan",
        headers=_auth_header(student_token),
    )
    assert audit_retention_forbidden.status_code == 403
    audit_chain_forbidden = client.get(
        "/api/admin/audit-logs/chain-integrity",
        headers=_auth_header(student_token),
    )
    assert audit_chain_forbidden.status_code == 403
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


def test_school_and_class_stats_are_available_to_scoped_teachers(client):
    admin_token = _bootstrap_admin(client)
    owner_teacher_token = _register_and_login(client, "stats_owner_teacher", "teacher")
    school_peer_token = _register_and_login(client, "stats_school_peer", "teacher")
    outside_teacher_token = _register_and_login(client, "stats_outside_teacher", "teacher")
    student_token = _register_and_login(client, "stats_scoped_student", "student")

    school = client.post(
        "/api/schools",
        headers=_auth_header(owner_teacher_token),
        json={"name": "Scoped Stats School", "region": "Hangzhou"},
    )
    assert school.status_code == 201
    school_id = school.json()["id"]

    class_group = client.post(
        "/api/classes",
        headers=_auth_header(owner_teacher_token),
        json={"school_id": school_id, "name": "Scoped Stats Class", "grade": "11"},
    )
    assert class_group.status_code == 201
    class_id = class_group.json()["id"]

    student_join = client.post(
        f"/api/classes/{class_id}/join",
        headers=_auth_header(student_token),
        json={"role": "student"},
    )
    assert student_join.status_code == 201

    peer_user_id = _current_user_id(client, school_peer_token)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        db.add(SchoolMembership(school_id=school_id, user_id=peer_user_id, role="teacher", status="active"))
        db.commit()

    owner_school_stats = client.get(f"/api/admin/schools/{school_id}/stats", headers=_auth_header(owner_teacher_token))
    assert owner_school_stats.status_code == 200
    assert owner_school_stats.json()["school_id"] == school_id
    assert owner_school_stats.json()["active_students"] == 1

    peer_school_stats = client.get(f"/api/admin/schools/{school_id}/stats", headers=_auth_header(school_peer_token))
    assert peer_school_stats.status_code == 200
    assert peer_school_stats.json()["school_id"] == school_id

    admin_school_stats = client.get(f"/api/admin/schools/{school_id}/stats", headers=_auth_header(admin_token))
    assert admin_school_stats.status_code == 200
    admin_missing_school = client.get("/api/admin/schools/999999/stats", headers=_auth_header(admin_token))
    assert admin_missing_school.status_code == 404

    owner_class_stats = client.get(f"/api/admin/classes/{class_id}/stats", headers=_auth_header(owner_teacher_token))
    assert owner_class_stats.status_code == 200
    assert owner_class_stats.json()["class_id"] == class_id
    assert owner_class_stats.json()["active_students"] == 1

    admin_class_stats = client.get(f"/api/admin/classes/{class_id}/stats", headers=_auth_header(admin_token))
    assert admin_class_stats.status_code == 200

    peer_class_stats = client.get(f"/api/admin/classes/{class_id}/stats", headers=_auth_header(school_peer_token))
    assert peer_class_stats.status_code == 403
    assert peer_class_stats.json()["detail"] == "Class statistics require class teacher scope"

    outside_school_stats = client.get(
        f"/api/admin/schools/{school_id}/stats",
        headers=_auth_header(outside_teacher_token),
    )
    assert outside_school_stats.status_code == 403
    assert outside_school_stats.json()["detail"] == "School statistics require school teacher scope"
    outside_missing_school = client.get("/api/admin/schools/999999/stats", headers=_auth_header(outside_teacher_token))
    assert outside_missing_school.status_code == 403

    outside_class_stats = client.get(
        f"/api/admin/classes/{class_id}/stats",
        headers=_auth_header(outside_teacher_token),
    )
    assert outside_class_stats.status_code == 403
    outside_missing_class = client.get("/api/admin/classes/999999/stats", headers=_auth_header(outside_teacher_token))
    assert outside_missing_class.status_code == 403

    student_school_stats = client.get(f"/api/admin/schools/{school_id}/stats", headers=_auth_header(student_token))
    assert student_school_stats.status_code == 403

    student_class_stats = client.get(f"/api/admin/classes/{class_id}/stats", headers=_auth_header(student_token))
    assert student_class_stats.status_code == 403

    global_stats_forbidden = client.get("/api/admin/stats", headers=_auth_header(owner_teacher_token))
    assert global_stats_forbidden.status_code == 403


def test_admin_audit_retention_plan_summarizes_candidates_without_deleting(client):
    admin_token = _bootstrap_admin(client)
    now = datetime.now(UTC)
    old_created_at = now - timedelta(days=45)
    expiring_created_at = now - timedelta(days=20)
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        old_log = AuditLog(
            action="legacy.audit",
            resource="legacy:old",
            resource_type="legacy",
            resource_id="old",
            event_result="success",
            prev_hash="a" * 64,
            current_hash="b" * 64,
            snapshot_json={"sensitive": "kept-out-of-plan"},
            created_at=old_created_at,
            updated_at=old_created_at,
        )
        expiring_log = AuditLog(
            action="legacy.audit",
            resource="legacy:expiring",
            resource_type="legacy",
            resource_id="expiring",
            event_result="failure",
            failure_reason="legacy_check",
            prev_hash="b" * 64,
            current_hash="c" * 64,
            snapshot_json={"sensitive": "also-kept-out-of-plan"},
            created_at=expiring_created_at,
            updated_at=expiring_created_at,
        )
        db.add_all([old_log, expiring_log])
        db.commit()
        old_log_id = old_log.id
        expiring_log_id = expiring_log.id

    plan_response = client.get(
        "/api/admin/audit-logs/retention-plan?action=legacy.audit&retention_days=30&warning_days=15&bucket_limit=5",
        headers={**_auth_header(admin_token), "X-Request-ID": "audit-retention-plan-request"},
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["filters"] == {"action": "legacy.audit"}
    assert plan["capabilities"] == {
        "archive_export": False,
        "delete": False,
        "worm": False,
        "external_anchor": False,
    }
    assert plan["policy"]["source"] == "query"
    assert plan["policy"]["retention_days"] == 30
    assert plan["policy"]["warning_days"] == 15
    assert plan["summary"]["total"] == 2
    assert plan["summary"]["archive_candidates"] == 1
    assert plan["summary"]["expiring_soon"] == 1
    assert plan["summary"]["retained"] == 1
    assert plan["summary"]["first_candidate_id"] == old_log_id
    assert plan["summary"]["last_candidate_id"] == old_log_id
    assert plan["summary"]["chain_start_prev_hash"] == "a" * 64
    assert plan["summary"]["chain_start_current_hash"] == "b" * 64
    assert plan["summary"]["chain_end_current_hash"] == "b" * 64
    assert plan["by_action"] == [{"key": "legacy.audit", "total": 1}]
    assert plan["by_resource_type"] == [{"key": "legacy", "total": 1}]
    assert plan["by_event_result"] == [{"key": "success", "total": 1}]
    assert "items" not in plan
    assert "snapshot_json" not in json.dumps(plan)

    retention_audit = client.get(
        "/api/admin/audit-logs?action=admin.audit.retention_plan"
        "&resource_type=audit_log&request_id=audit-retention-plan-request",
        headers=_auth_header(admin_token),
    )
    assert retention_audit.status_code == 200
    assert retention_audit.json()["total"] == 1
    retention_snapshot = retention_audit.json()["items"][0]["snapshot_json"]
    assert retention_snapshot["format"] == "retention_plan"
    assert retention_snapshot["filters"] == {"action": "legacy.audit"}
    assert retention_snapshot["capabilities"]["delete"] is False
    assert retention_snapshot["policy"]["retention_days"] == 30
    assert retention_snapshot["archive_candidates"] == 1
    assert retention_snapshot["expiring_soon"] == 1
    assert retention_snapshot["first_candidate_id"] == old_log_id
    assert retention_snapshot["last_candidate_id"] == old_log_id
    assert "by_action" not in retention_snapshot
    assert "items" not in retention_snapshot

    with session_factory() as db:
        assert db.get(AuditLog, old_log_id) is not None
        assert db.get(AuditLog, expiring_log_id) is not None
        assert (
            db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "legacy.audit"))
            == 2
        )

    default_plan = client.get(
        "/api/admin/audit-logs/retention-plan?action=legacy.audit",
        headers=_auth_header(admin_token),
    )
    assert default_plan.status_code == 200
    assert default_plan.json()["policy"]["source"] == "config"
    assert default_plan.json()["policy"]["retention_days"] == 365

    before_plan = client.get(
        "/api/admin/audit-logs/retention-plan",
        params={"action": "legacy.audit", "before": expiring_created_at.isoformat()},
        headers=_auth_header(admin_token),
    )
    assert before_plan.status_code == 200
    assert before_plan.json()["policy"]["source"] == "before"
    assert before_plan.json()["policy"]["retention_days"] is None
    assert before_plan.json()["summary"]["archive_candidates"] == 2

    invalid_policy = client.get(
        "/api/admin/audit-logs/retention-plan?before=2026-07-01T00:00:00Z&retention_days=30",
        headers=_auth_header(admin_token),
    )
    assert invalid_policy.status_code == 422

    invalid_window = client.get(
        "/api/admin/audit-logs/retention-plan?from=2026-07-06T10:00:00Z&to=2026-07-05T10:00:00Z",
        headers=_auth_header(admin_token),
    )
    assert invalid_window.status_code == 422


def test_admin_audit_chain_integrity_reports_hash_and_link_issues(client):
    admin_token = _bootstrap_admin(client)
    session_factory = get_session_factory(get_settings().database_url)

    def audit_log(
        *,
        action: str,
        resource: str,
        created_at: datetime,
        prev_hash: str | None = None,
        current_hash: str | None = "computed",
    ) -> AuditLog:
        log = AuditLog(
            action=action,
            resource=resource,
            resource_type="chain_test",
            resource_id=resource.rsplit(":", 1)[-1],
            event_result="success",
            request_id=f"{resource}-request",
            prev_hash=prev_hash,
            snapshot_json={"resource": resource},
            created_at=created_at,
            updated_at=created_at,
        )
        if current_hash == "computed":
            log.current_hash = audit_log_chain_hash(log)
        else:
            log.current_hash = current_hash
        return log

    valid_base = datetime.now(UTC) + timedelta(minutes=1)
    with session_factory() as db:
        first = audit_log(action="chain.valid", resource="chain:valid:first", created_at=valid_base)
        second = audit_log(
            action="chain.valid",
            resource="chain:valid:second",
            created_at=valid_base + timedelta(seconds=1),
            prev_hash=first.current_hash,
        )
        db.add_all([first, second])
        db.commit()
        first_id = first.id
        second_id = second.id

    valid_report = client.get(
        "/api/admin/audit-logs/chain-integrity",
        params={
            "from": (valid_base - timedelta(seconds=1)).isoformat(),
            "to": (valid_base + timedelta(seconds=5)).isoformat(),
        },
        headers={**_auth_header(admin_token), "X-Request-ID": "audit-chain-valid-request"},
    )
    assert valid_report.status_code == 200
    valid_body = valid_report.json()
    assert valid_body["status"] == "valid"
    assert valid_body["valid"] is True
    assert valid_body["total"] == 2
    assert valid_body["scanned_count"] == 2
    assert valid_body["truncated"] is False
    assert valid_body["issue_count"] == 0
    assert valid_body["first_id"] == first_id
    assert valid_body["last_id"] == second_id

    invalid_base = datetime.now(UTC) + timedelta(minutes=2)
    with session_factory() as db:
        intact_first = audit_log(action="chain.invalid", resource="chain:invalid:first", created_at=invalid_base)
        intact_second = audit_log(
            action="chain.invalid",
            resource="chain:invalid:second",
            created_at=invalid_base + timedelta(seconds=1),
            prev_hash=intact_first.current_hash,
        )
        broken_prev = audit_log(
            action="chain.invalid",
            resource="chain:invalid:broken-prev",
            created_at=invalid_base + timedelta(seconds=2),
            prev_hash="9" * 64,
        )
        broken_current = audit_log(
            action="chain.invalid",
            resource="chain:invalid:broken-current",
            created_at=invalid_base + timedelta(seconds=3),
            prev_hash=broken_prev.current_hash,
            current_hash="f" * 64,
        )
        legacy = audit_log(
            action="chain.invalid",
            resource="chain:invalid:legacy",
            created_at=invalid_base + timedelta(seconds=4),
            current_hash=None,
        )
        db.add_all([intact_first, intact_second, broken_prev, broken_current, legacy])
        db.commit()

    truncated_report = client.get(
        "/api/admin/audit-logs/chain-integrity",
        params={
            "from": (invalid_base - timedelta(seconds=1)).isoformat(),
            "to": (invalid_base + timedelta(seconds=10)).isoformat(),
            "limit": 2,
        },
        headers=_auth_header(admin_token),
    )
    assert truncated_report.status_code == 200
    assert truncated_report.json()["total"] == 5
    assert truncated_report.json()["scanned_count"] == 2
    assert truncated_report.json()["truncated"] is True
    assert truncated_report.json()["status"] == "partial"
    assert truncated_report.json()["valid"] is False

    invalid_report = client.get(
        "/api/admin/audit-logs/chain-integrity",
        params={
            "from": (invalid_base - timedelta(seconds=1)).isoformat(),
            "to": (invalid_base + timedelta(seconds=10)).isoformat(),
            "issue_limit": 2,
        },
        headers={**_auth_header(admin_token), "X-Request-ID": "audit-chain-invalid-request"},
    )
    assert invalid_report.status_code == 200
    invalid_body = invalid_report.json()
    assert invalid_body["status"] == "invalid"
    assert invalid_body["valid"] is False
    assert invalid_body["total"] == 5
    assert invalid_body["scanned_count"] == 5
    assert invalid_body["truncated"] is False
    assert invalid_body["issue_count"] == 3
    assert invalid_body["issues_truncated"] is True
    assert invalid_body["current_hash_mismatch_count"] == 1
    assert invalid_body["prev_hash_mismatch_count"] == 1
    assert invalid_body["null_current_hash_count"] == 1
    assert {issue["type"] for issue in invalid_body["issues"]} == {
        "prev_hash_mismatch",
        "current_hash_mismatch",
    }
    assert "snapshot_json" not in json.dumps(invalid_body)

    chain_audit = client.get(
        "/api/admin/audit-logs?action=admin.audit.chain_integrity&resource_type=audit_log&request_id=audit-chain-invalid-request",
        headers=_auth_header(admin_token),
    )
    assert chain_audit.status_code == 200
    assert chain_audit.json()["total"] == 1
    chain_snapshot = chain_audit.json()["items"][0]["snapshot_json"]
    assert chain_snapshot["format"] == "chain_integrity"
    assert chain_snapshot["status"] == "invalid"
    assert chain_snapshot["issue_count"] == 3
    assert chain_snapshot["current_hash_mismatch_count"] == 1
    assert chain_snapshot["prev_hash_mismatch_count"] == 1
    assert chain_snapshot["null_current_hash_count"] == 1
    assert "issues" not in chain_snapshot
    assert "snapshot_json" not in json.dumps(chain_snapshot)

    invalid_window = client.get(
        "/api/admin/audit-logs/chain-integrity?from=2026-07-06T10:00:00Z&to=2026-07-05T10:00:00Z",
        headers=_auth_header(admin_token),
    )
    assert invalid_window.status_code == 422


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


def test_admin_can_list_and_cancel_knowledge_snapshot_runs(client):
    admin_token = _bootstrap_admin(client)
    teacher_token = _register_and_login(client, "snapshot_run_teacher", "teacher")
    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        run = KnowledgeSnapshotRun(
            run_key="knowledge:day:2026-07-01",
            granularity="day",
            period_start=datetime(2026, 7, 1, tzinfo=UTC),
            period_end=datetime(2026, 7, 1, 23, 59, 59, tzinfo=UTC),
            trigger_source="scheduler",
            status="running",
            started_at=datetime(2026, 7, 2, 3, 0, tzinfo=UTC),
            scheduler_lease_owner="worker-admin-cancel",
            scheduler_lease_token="secret-lease-token",
            scheduler_lease_expires_at=datetime(2026, 7, 2, 4, 0, tzinfo=UTC),
            scheduler_heartbeat_at=datetime(2026, 7, 2, 3, 30, tzinfo=UTC),
            attempt_count=1,
            user_snapshot_count=0,
            class_snapshot_count=0,
            metadata_json={"trigger_source": "scheduler"},
        )
        success_run = KnowledgeSnapshotRun(
            run_key="knowledge:day:2026-07-02",
            granularity="day",
            period_start=datetime(2026, 7, 2, tzinfo=UTC),
            period_end=datetime(2026, 7, 2, 23, 59, 59, tzinfo=UTC),
            trigger_source="script",
            status="success",
            started_at=datetime(2026, 7, 3, 3, 0, tzinfo=UTC),
            finished_at=datetime(2026, 7, 3, 3, 1, tzinfo=UTC),
            attempt_count=1,
            user_snapshot_count=0,
            class_snapshot_count=0,
            metadata_json={"trigger_source": "script"},
        )
        failed_run = KnowledgeSnapshotRun(
            run_key="knowledge:day:2026-07-03",
            granularity="day",
            period_start=datetime(2026, 7, 3, tzinfo=UTC),
            period_end=datetime(2026, 7, 3, 23, 59, 59, tzinfo=UTC),
            trigger_source="scheduler",
            status="failed",
            started_at=datetime(2026, 7, 4, 3, 0, tzinfo=UTC),
            finished_at=datetime(2026, 7, 4, 3, 1, tzinfo=UTC),
            attempt_count=1,
            user_snapshot_count=0,
            class_snapshot_count=0,
            error_message="RuntimeError",
            metadata_json={"trigger_source": "scheduler"},
        )
        legacy_running_run = KnowledgeSnapshotRun(
            run_key="knowledge:day:2026-07-04",
            granularity="day",
            period_start=datetime(2026, 7, 4, tzinfo=UTC),
            period_end=datetime(2026, 7, 4, 23, 59, 59, tzinfo=UTC),
            trigger_source="script",
            status="running",
            started_at=datetime(2026, 7, 5, 3, 0, tzinfo=UTC),
            attempt_count=1,
            user_snapshot_count=0,
            class_snapshot_count=0,
            metadata_json={"trigger_source": "script"},
        )
        db.add_all([run, success_run, failed_run, legacy_running_run])
        db.commit()
        run_id = run.id
        success_run_id = success_run.id
        failed_run_id = failed_run.id
        legacy_running_run_id = legacy_running_run.id

    forbidden = client.get("/api/admin/knowledge-snapshot-runs", headers=_auth_header(teacher_token))
    assert forbidden.status_code == 403

    page = client.get(
        "/api/admin/knowledge-snapshot-runs?status=running&trigger_source=scheduler",
        headers=_auth_header(admin_token),
    )
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == run_id
    assert body["items"][0]["scheduler_lease_owner"] == "worker-admin-cancel"
    assert "scheduler_lease_token" not in body["items"][0]
    assert "secret-lease-token" not in json.dumps(body, ensure_ascii=False)

    cancelled = client.post(
        f"/api/admin/knowledge-snapshot-runs/{run_id}/cancel",
        headers=_auth_header(admin_token),
    )
    assert cancelled.status_code == 200
    cancelled_body = cancelled.json()
    assert cancelled_body["status"] == "cancelled"
    assert cancelled_body["finished_at"] is not None
    assert cancelled_body["error_message"] == "cancelled_by_admin"
    assert cancelled_body["scheduler_lease_owner"] is None
    assert cancelled_body["scheduler_lease_expires_at"] is None
    assert cancelled_body["scheduler_heartbeat_at"] is None
    assert cancelled_body["metadata_json"]["previous_status"] == "running"
    assert "scheduler_lease_token" not in cancelled_body

    second_cancel = client.post(
        f"/api/admin/knowledge-snapshot-runs/{run_id}/cancel",
        headers=_auth_header(admin_token),
    )
    assert second_cancel.status_code == 409

    success_cancel = client.post(
        f"/api/admin/knowledge-snapshot-runs/{success_run_id}/cancel",
        headers=_auth_header(admin_token),
    )
    assert success_cancel.status_code == 409

    failed_cancel = client.post(
        f"/api/admin/knowledge-snapshot-runs/{failed_run_id}/cancel",
        headers=_auth_header(admin_token),
    )
    assert failed_cancel.status_code == 409

    legacy_cancel = client.post(
        f"/api/admin/knowledge-snapshot-runs/{legacy_running_run_id}/cancel",
        headers=_auth_header(admin_token),
    )
    assert legacy_cancel.status_code == 409

    audit = client.get(
        f"/api/admin/audit-logs?action=admin.knowledge_snapshot_run.cancel&resource_id={run_id}",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    audit_item = audit.json()["items"][0]
    assert audit_item["snapshot_json"]["previous_status"] == "running"
    assert audit_item["snapshot_json"]["status"] == "cancelled"
    assert audit_item["snapshot_json"]["cleared_lease"] is True
    assert "secret-lease-token" not in json.dumps(audit_item["snapshot_json"], ensure_ascii=False)

    with session_factory() as db:
        stored = db.get(KnowledgeSnapshotRun, run_id)
        assert stored is not None
        assert stored.status == "cancelled"
        assert stored.scheduler_lease_token is None
        assert stored.metadata_json["previous_status"] == "running"


def test_admin_can_read_knowledge_snapshot_run_health(client):
    admin_token = _bootstrap_admin(client)
    teacher_token = _register_and_login(client, "snapshot_health_teacher", "teacher")
    session_factory = get_session_factory(get_settings().database_url)
    settings = get_settings()
    now = datetime.now(UTC).replace(microsecond=0)
    retryable_attempts = max(settings.knowledge_snapshot_retry_attempts - 1, 0)
    with session_factory() as db:
        runs = [
            KnowledgeSnapshotRun(
                run_key="knowledge:health:active",
                granularity="day",
                period_start=now - timedelta(days=8),
                period_end=now - timedelta(days=8) + timedelta(hours=23, minutes=59),
                trigger_source="scheduler",
                status="running",
                started_at=now - timedelta(minutes=10),
                scheduler_lease_owner="worker-active",
                scheduler_lease_token="secret-active-token",
                scheduler_lease_expires_at=now + timedelta(hours=1),
                scheduler_heartbeat_at=now - timedelta(minutes=1),
                attempt_count=1,
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:health:expiring",
                granularity="day",
                period_start=now - timedelta(days=7),
                period_end=now - timedelta(days=7) + timedelta(hours=23, minutes=59),
                trigger_source="scheduler",
                status="running",
                started_at=now - timedelta(minutes=20),
                scheduler_lease_owner="worker-expiring",
                scheduler_lease_token="secret-expiring-token",
                scheduler_lease_expires_at=now + timedelta(minutes=5),
                scheduler_heartbeat_at=now - timedelta(minutes=1),
                attempt_count=1,
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:health:stale",
                granularity="day",
                period_start=now - timedelta(days=6),
                period_end=now - timedelta(days=6) + timedelta(hours=23, minutes=59),
                trigger_source="scheduler",
                status="running",
                started_at=now - timedelta(hours=2),
                scheduler_lease_owner="worker-stale",
                scheduler_lease_token="secret-stale-token",
                scheduler_lease_expires_at=now - timedelta(minutes=1),
                scheduler_heartbeat_at=now - timedelta(hours=1),
                attempt_count=1,
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:health:legacy",
                granularity="day",
                period_start=now - timedelta(days=5),
                period_end=now - timedelta(days=5) + timedelta(hours=23, minutes=59),
                trigger_source="script",
                status="running",
                started_at=now - timedelta(seconds=settings.knowledge_snapshot_scheduler_lease_seconds + 60),
                attempt_count=1,
                metadata_json={"trigger_source": "script"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:health:retryable",
                granularity="day",
                period_start=now - timedelta(days=4),
                period_end=now - timedelta(days=4) + timedelta(hours=23, minutes=59),
                trigger_source="scheduler",
                status="failed",
                started_at=now - timedelta(hours=4),
                finished_at=now - timedelta(hours=3, minutes=59),
                attempt_count=retryable_attempts,
                error_message="SnapshotRunLeaseLost",
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:health:exhausted",
                granularity="day",
                period_start=now - timedelta(days=3),
                period_end=now - timedelta(days=3) + timedelta(hours=23, minutes=59),
                trigger_source="scheduler",
                status="failed",
                started_at=now - timedelta(hours=3),
                finished_at=now - timedelta(hours=2, minutes=59),
                attempt_count=settings.knowledge_snapshot_retry_attempts,
                error_message="RuntimeError",
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:health:pending",
                granularity="week",
                period_start=now - timedelta(days=14),
                period_end=now - timedelta(days=8),
                trigger_source="queue",
                status="pending",
                started_at=now - timedelta(hours=2),
                attempt_count=0,
                metadata_json={"trigger_source": "queue"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:health:success",
                granularity="day",
                period_start=now - timedelta(days=2),
                period_end=now - timedelta(days=2) + timedelta(hours=23, minutes=59),
                trigger_source="scheduler",
                status="success",
                started_at=now - timedelta(hours=2),
                finished_at=now - timedelta(hours=1),
                attempt_count=1,
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:health:cancelled",
                granularity="day",
                period_start=now - timedelta(days=1),
                period_end=now - timedelta(days=1) + timedelta(hours=23, minutes=59),
                trigger_source="scheduler",
                status="cancelled",
                started_at=now - timedelta(hours=1),
                finished_at=now - timedelta(minutes=30),
                attempt_count=1,
                error_message="cancelled_by_admin",
                metadata_json={"trigger_source": "scheduler"},
            ),
        ]
        db.add_all(runs)
        db.commit()

    forbidden = client.get("/api/admin/knowledge-snapshot-runs/health", headers=_auth_header(teacher_token))
    assert forbidden.status_code == 403

    response = client.get(
        "/api/admin/knowledge-snapshot-runs/health?lease_expiring_seconds=600&problem_limit=3",
        headers={**_auth_header(admin_token), "X-Request-ID": "snapshot-health-request"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["health_status"] == "attention"
    assert body["total"] == 9
    by_status = {item["status"]: item["total"] for item in body["by_status"]}
    assert by_status == {
        "cancelled": 1,
        "failed": 2,
        "pending": 1,
        "running": 4,
        "success": 1,
    }
    assert body["running_count"] == 4
    assert body["active_running_count"] == 2
    assert body["stale_running_count"] == 2
    assert body["lease_expiring_count"] == 1
    assert body["legacy_running_without_lease_count"] == 1
    assert body["failed_count"] == 2
    assert body["retryable_failed_count"] == 1
    assert body["exhausted_failed_count"] == 1
    assert body["claimable_count"] == 4
    assert body["pending_count"] == 1
    assert body["cancelled_count"] == 1
    assert body["needs_attention_count"] == 5
    assert body["problem_count"] == 6
    assert len(body["problem_runs"]) == 3
    assert body["latest_success_by_granularity"]["day"] is not None
    problem_flags = {flag for item in body["problem_runs"] for flag in item["health_flags"]}
    assert "stale_running" in problem_flags
    serialized = json.dumps(body, ensure_ascii=False)
    assert "scheduler_lease_token" not in serialized
    assert "secret-active-token" not in serialized
    assert "secret-expiring-token" not in serialized
    assert "secret-stale-token" not in serialized

    invalid_window = client.get(
        "/api/admin/knowledge-snapshot-runs/health?from=2026-07-06T10:00:00Z&to=2026-07-05T10:00:00Z",
        headers=_auth_header(admin_token),
    )
    assert invalid_window.status_code == 422

    audit = client.get(
        "/api/admin/audit-logs?action=admin.knowledge_snapshot_run.health_report"
        "&resource_type=knowledge_snapshot_run&request_id=snapshot-health-request",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    audit_item = audit.json()["items"][0]
    assert audit_item["snapshot_json"]["health_status"] == "attention"
    assert audit_item["snapshot_json"]["problem_count"] == 6
    assert audit_item["snapshot_json"]["claimable_count"] == 4
    assert "secret-" not in json.dumps(audit_item["snapshot_json"], ensure_ascii=False)
    assert "problem_runs" not in audit_item["snapshot_json"]


def test_admin_can_read_knowledge_snapshot_run_queue(client):
    admin_token = _bootstrap_admin(client)
    teacher_token = _register_and_login(client, "snapshot_queue_teacher", "teacher")
    session_factory = get_session_factory(get_settings().database_url)
    settings = get_settings()
    now = datetime(2026, 7, 20, 4, 30, tzinfo=UTC)
    with session_factory() as db:
        runs = [
            KnowledgeSnapshotRun(
                run_key="knowledge:queue:pending",
                granularity="day",
                period_start=datetime(2026, 7, 10),
                period_end=datetime(2026, 7, 10, 23, 59),
                trigger_source="admin_requeue",
                status="pending",
                started_at=datetime(2026, 7, 20, 1, 0),
                attempt_count=0,
                metadata_json={"trigger_source": "admin_requeue", "requeue_reason": "secret-reason"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:queue:retryable",
                granularity="day",
                period_start=datetime(2026, 7, 9),
                period_end=datetime(2026, 7, 9, 23, 59),
                trigger_source="scheduler",
                status="failed",
                started_at=datetime(2026, 7, 19, 1, 0),
                finished_at=datetime(2026, 7, 19, 1, 1),
                attempt_count=max(settings.knowledge_snapshot_retry_attempts - 1, 0),
                error_message="SnapshotRunLeaseLost",
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:queue:exhausted",
                granularity="day",
                period_start=datetime(2026, 7, 8),
                period_end=datetime(2026, 7, 8, 23, 59),
                trigger_source="scheduler",
                status="failed",
                started_at=datetime(2026, 7, 18, 1, 0),
                finished_at=datetime(2026, 7, 18, 1, 1),
                attempt_count=settings.knowledge_snapshot_retry_attempts,
                error_message="RuntimeError",
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:queue:cancelled",
                granularity="week",
                period_start=datetime(2026, 7, 7),
                period_end=datetime(2026, 7, 13, 23, 59),
                trigger_source="admin",
                status="cancelled",
                started_at=datetime(2026, 7, 19, 2, 0),
                finished_at=datetime(2026, 7, 19, 2, 1),
                attempt_count=1,
                error_message="cancelled_by_admin",
                metadata_json={"trigger_source": "admin", "cancelled_by_user_id": 1},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:queue:active",
                granularity="day",
                period_start=datetime(2026, 7, 6),
                period_end=datetime(2026, 7, 6, 23, 59),
                trigger_source="scheduler",
                status="running",
                started_at=datetime(2026, 7, 20, 3, 50),
                scheduler_lease_owner="worker-active-queue",
                scheduler_lease_token="secret-active-queue-token",
                scheduler_lease_expires_at=datetime(2026, 7, 20, 5, 0),
                scheduler_heartbeat_at=datetime(2026, 7, 20, 4, 20),
                attempt_count=1,
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:queue:stale",
                granularity="day",
                period_start=datetime(2026, 7, 5),
                period_end=datetime(2026, 7, 5, 23, 59),
                trigger_source="scheduler",
                status="running",
                started_at=datetime(2026, 7, 20, 1, 30),
                scheduler_lease_owner="worker-stale-queue",
                scheduler_lease_token="secret-stale-queue-token",
                scheduler_lease_expires_at=datetime(2026, 7, 20, 3, 0),
                scheduler_heartbeat_at=datetime(2026, 7, 20, 2, 0),
                attempt_count=1,
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:queue:legacy",
                granularity="day",
                period_start=datetime(2026, 7, 4),
                period_end=datetime(2026, 7, 4, 23, 59),
                trigger_source="script",
                status="running",
                started_at=datetime(2026, 7, 20, 1, 0),
                attempt_count=1,
                metadata_json={"trigger_source": "script"},
            ),
        ]
        db.add_all(runs)
        db.commit()

    forbidden = client.get(
        "/api/admin/knowledge-snapshot-runs/queue",
        headers=_auth_header(teacher_token),
        params={"now": now.isoformat()},
    )
    assert forbidden.status_code == 403

    response = client.get(
        "/api/admin/knowledge-snapshot-runs/queue",
        headers={**_auth_header(admin_token), "X-Request-ID": "snapshot-queue-request"},
        params={"now": now.isoformat(), "item_limit": "10"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["queue_status"] == "ready"
    assert body["due_count"] == 2
    assert body["pending_count"] == 1
    assert body["ready_count"] == 3
    assert body["dispatchable_now_count"] == 3
    assert body["manual_requeue_count"] == 4
    assert body["blocked_count"] == 2
    assert body["retryable_failed_count"] == 1
    assert body["exhausted_failed_count"] == 1
    assert body["cancelled_count"] == 1
    assert body["stale_running_count"] == 2
    assert body["active_running_count"] == 1
    assert body["legacy_running_without_lease_count"] == 1
    assert body["claimable_by_lease_rule_count"] == 4
    ready_sources = [item["source"] for item in body["ready_jobs"]]
    assert ready_sources.count("due") == 2
    assert "pending" in ready_sources
    manual_sources = {item["source"] for item in body["manual_requeue_runs"]}
    assert {"retryable_failed", "exhausted_failed", "cancelled", "stale_running"} <= manual_sources
    blocked_sources = {item["source"] for item in body["blocked_runs"]}
    assert {"active_running", "legacy_running"} <= blocked_sources
    serialized = json.dumps(body, ensure_ascii=False)
    assert "scheduler_lease_token" not in serialized
    assert "secret-" not in serialized
    assert "metadata_json" not in serialized
    assert "secret-reason" not in serialized

    invalid_window = client.get(
        "/api/admin/knowledge-snapshot-runs/queue",
        headers=_auth_header(admin_token),
        params={"from": "2026-07-06T10:00:00Z", "to": "2026-07-05T10:00:00Z"},
    )
    assert invalid_window.status_code == 422

    audit = client.get(
        "/api/admin/audit-logs?action=admin.knowledge_snapshot_run.queue_report"
        "&resource_type=knowledge_snapshot_run&request_id=snapshot-queue-request",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    audit_snapshot = audit.json()["items"][0]["snapshot_json"]
    assert audit_snapshot["queue_status"] == "ready"
    assert audit_snapshot["ready_count"] == 3
    assert audit_snapshot["manual_requeue_count"] == 4
    assert audit_snapshot["blocked_count"] == 2
    assert "ready_jobs" not in audit_snapshot
    assert "manual_requeue_runs" not in audit_snapshot
    assert "blocked_runs" not in audit_snapshot
    assert "secret-" not in json.dumps(audit_snapshot, ensure_ascii=False)


def test_admin_can_read_knowledge_snapshot_run_alert_candidates(client):
    admin_token = _bootstrap_admin(client)
    teacher_token = _register_and_login(client, "snapshot_alert_teacher", "teacher")
    session_factory = get_session_factory(get_settings().database_url)
    settings = get_settings()
    now = datetime(2026, 7, 21, 4, 30, tzinfo=UTC)
    with session_factory() as db:
        runs = [
            KnowledgeSnapshotRun(
                run_key="knowledge:alerts:pending",
                granularity="day",
                period_start=datetime(2026, 7, 10),
                period_end=datetime(2026, 7, 10, 23, 59),
                trigger_source="admin_requeue",
                status="pending",
                started_at=datetime(2026, 7, 21, 1, 0),
                attempt_count=0,
                metadata_json={"trigger_source": "admin_requeue", "requeue_reason": "secret-alert-reason"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:alerts:retryable",
                granularity="day",
                period_start=datetime(2026, 7, 9),
                period_end=datetime(2026, 7, 9, 23, 59),
                trigger_source="scheduler",
                status="failed",
                started_at=datetime(2026, 7, 20, 1, 0),
                finished_at=datetime(2026, 7, 20, 1, 1),
                attempt_count=max(settings.knowledge_snapshot_retry_attempts - 1, 0),
                error_message="SnapshotRunLeaseLost",
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:alerts:exhausted",
                granularity="day",
                period_start=datetime(2026, 7, 8),
                period_end=datetime(2026, 7, 8, 23, 59),
                trigger_source="scheduler",
                status="failed",
                started_at=datetime(2026, 7, 20, 2, 0),
                finished_at=datetime(2026, 7, 20, 2, 1),
                attempt_count=settings.knowledge_snapshot_retry_attempts,
                error_message="RuntimeError",
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:alerts:expiring",
                granularity="day",
                period_start=datetime(2026, 7, 7),
                period_end=datetime(2026, 7, 7, 23, 59),
                trigger_source="scheduler",
                status="running",
                started_at=datetime(2026, 7, 21, 3, 50),
                scheduler_lease_owner="worker-alert-expiring",
                scheduler_lease_token="secret-alert-expiring-token",
                scheduler_lease_expires_at=datetime(2026, 7, 21, 4, 35),
                scheduler_heartbeat_at=datetime(2026, 7, 21, 4, 25),
                attempt_count=1,
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:alerts:stale",
                granularity="day",
                period_start=datetime(2026, 7, 6),
                period_end=datetime(2026, 7, 6, 23, 59),
                trigger_source="scheduler",
                status="running",
                started_at=datetime(2026, 7, 21, 1, 30),
                scheduler_lease_owner="worker-alert-stale",
                scheduler_lease_token="secret-alert-stale-token",
                scheduler_lease_expires_at=datetime(2026, 7, 21, 3, 0),
                scheduler_heartbeat_at=datetime(2026, 7, 21, 2, 0),
                attempt_count=1,
                metadata_json={"trigger_source": "scheduler"},
            ),
            KnowledgeSnapshotRun(
                run_key="knowledge:alerts:cancelled",
                granularity="week",
                period_start=datetime(2026, 7, 7),
                period_end=datetime(2026, 7, 13, 23, 59),
                trigger_source="admin",
                status="cancelled",
                started_at=datetime(2026, 7, 20, 3, 0),
                finished_at=datetime(2026, 7, 20, 3, 1),
                attempt_count=1,
                error_message="cancelled_by_admin",
                metadata_json={"trigger_source": "admin", "cancelled_by_user_id": 1},
            ),
        ]
        db.add_all(runs)
        db.commit()

    forbidden = client.get(
        "/api/admin/knowledge-snapshot-runs/alerts",
        headers=_auth_header(teacher_token),
        params={"now": now.isoformat()},
    )
    assert forbidden.status_code == 403

    response = client.get(
        "/api/admin/knowledge-snapshot-runs/alerts",
        headers={**_auth_header(admin_token), "X-Request-ID": "snapshot-alert-request"},
        params={"now": now.isoformat(), "lease_expiring_seconds": "600", "candidate_limit": "100"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["alert_status"] == "critical"
    assert body["health_status"] == "attention"
    assert body["candidate_count"] >= 6
    assert body["critical_count"] >= 2
    assert body["warning_count"] >= 3
    assert body["manual_requeue_count"] >= 3
    assert body["dispatchable_now_count"] >= 1
    codes = {item["code"] for item in body["candidates"]}
    assert {"stale_running", "exhausted_failed", "retryable_failed", "pending", "lease_expiring"} <= codes
    assert "manual_cancelled" in codes
    severities = [item["severity"] for item in body["candidates"]]
    assert severities[: body["critical_count"]] == ["critical"] * body["critical_count"]
    serialized = json.dumps(body, ensure_ascii=False)
    assert "scheduler_lease_token" not in serialized
    assert "secret-" not in serialized
    assert "metadata_json" not in serialized
    assert "secret-alert-reason" not in serialized

    limited = client.get(
        "/api/admin/knowledge-snapshot-runs/alerts",
        headers=_auth_header(admin_token),
        params={"now": now.isoformat(), "candidate_limit": "2"},
    )
    assert limited.status_code == 200
    assert len(limited.json()["candidates"]) == 2
    assert limited.json()["candidate_count"] >= 6

    invalid_window = client.get(
        "/api/admin/knowledge-snapshot-runs/alerts",
        headers=_auth_header(admin_token),
        params={"from": "2026-07-06T10:00:00Z", "to": "2026-07-05T10:00:00Z"},
    )
    assert invalid_window.status_code == 422

    audit = client.get(
        "/api/admin/audit-logs?action=admin.knowledge_snapshot_run.alert_report"
        "&resource_type=knowledge_snapshot_run&request_id=snapshot-alert-request",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    audit_snapshot = audit.json()["items"][0]["snapshot_json"]
    assert audit_snapshot["format"] == "alert_candidates"
    assert audit_snapshot["alert_status"] == "critical"
    assert audit_snapshot["candidate_count"] >= 6
    assert audit_snapshot["candidate_codes"]["stale_running"] >= 1
    assert "candidates" not in audit_snapshot
    assert "secret-" not in json.dumps(audit_snapshot, ensure_ascii=False)


def test_admin_can_requeue_knowledge_snapshot_runs(client):
    admin_token = _bootstrap_admin(client)
    teacher_token = _register_and_login(client, "snapshot_requeue_teacher", "teacher")
    session_factory = get_session_factory(get_settings().database_url)
    settings = get_settings()
    now = datetime.now(UTC).replace(microsecond=0)
    with session_factory() as db:
        failed_run = KnowledgeSnapshotRun(
            run_key="knowledge:requeue:failed",
            granularity="day",
            period_start=now - timedelta(days=5),
            period_end=now - timedelta(days=5) + timedelta(hours=23, minutes=59),
            trigger_source="scheduler",
            status="failed",
            started_at=now - timedelta(hours=5),
            finished_at=now - timedelta(hours=4, minutes=59),
            scheduler_lease_owner="old-worker",
            scheduler_lease_token="secret-requeue-token",
            scheduler_lease_expires_at=now - timedelta(hours=4),
            scheduler_heartbeat_at=now - timedelta(hours=5),
            attempt_count=settings.knowledge_snapshot_retry_attempts,
            error_message="RuntimeError",
            metadata_json={"trigger_source": "scheduler"},
        )
        pending_run = KnowledgeSnapshotRun(
            run_key="knowledge:requeue:pending",
            granularity="day",
            period_start=now - timedelta(days=4),
            period_end=now - timedelta(days=4) + timedelta(hours=23, minutes=59),
            trigger_source="admin",
            status="pending",
            started_at=now - timedelta(hours=4),
            attempt_count=0,
            metadata_json={"trigger_source": "admin"},
        )
        cancelled_run = KnowledgeSnapshotRun(
            run_key="knowledge:requeue:cancelled",
            granularity="day",
            period_start=now - timedelta(days=7),
            period_end=now - timedelta(days=7) + timedelta(hours=23, minutes=59),
            trigger_source="admin",
            status="cancelled",
            started_at=now - timedelta(days=7, hours=1),
            finished_at=now - timedelta(days=7),
            attempt_count=1,
            error_message="cancelled_by_admin",
            metadata_json={"trigger_source": "admin", "cancelled_by_user_id": 1},
        )
        active_running_run = KnowledgeSnapshotRun(
            run_key="knowledge:requeue:active",
            granularity="day",
            period_start=now - timedelta(days=3),
            period_end=now - timedelta(days=3) + timedelta(hours=23, minutes=59),
            trigger_source="scheduler",
            status="running",
            started_at=now - timedelta(minutes=10),
            scheduler_lease_owner="worker-active-requeue",
            scheduler_lease_token="secret-active-requeue-token",
            scheduler_lease_expires_at=now + timedelta(hours=1),
            scheduler_heartbeat_at=now - timedelta(minutes=1),
            attempt_count=1,
            metadata_json={"trigger_source": "scheduler"},
        )
        stale_running_run = KnowledgeSnapshotRun(
            run_key="knowledge:requeue:stale",
            granularity="day",
            period_start=now - timedelta(days=2),
            period_end=now - timedelta(days=2) + timedelta(hours=23, minutes=59),
            trigger_source="scheduler",
            status="running",
            started_at=now - timedelta(hours=3),
            scheduler_lease_owner="worker-stale-requeue",
            scheduler_lease_token="secret-stale-requeue-token",
            scheduler_lease_expires_at=now - timedelta(minutes=1),
            scheduler_heartbeat_at=now - timedelta(hours=2),
            attempt_count=1,
            metadata_json={"trigger_source": "scheduler"},
        )
        legacy_running_run = KnowledgeSnapshotRun(
            run_key="knowledge:requeue:legacy-running",
            granularity="day",
            period_start=now - timedelta(days=1),
            period_end=now - timedelta(days=1) + timedelta(hours=23, minutes=59),
            trigger_source="scheduler",
            status="running",
            started_at=now - timedelta(hours=3),
            attempt_count=1,
            metadata_json={"trigger_source": "scheduler"},
        )
        success_run = KnowledgeSnapshotRun(
            run_key="knowledge:requeue:success",
            granularity="day",
            period_start=now - timedelta(days=6),
            period_end=now - timedelta(days=6) + timedelta(hours=23, minutes=59),
            trigger_source="scheduler",
            status="success",
            started_at=now - timedelta(days=6, hours=1),
            finished_at=now - timedelta(days=6),
            attempt_count=1,
            user_snapshot_count=2,
            class_snapshot_count=1,
            metadata_json={"trigger_source": "scheduler"},
        )
        db.add_all(
            [
                failed_run,
                pending_run,
                cancelled_run,
                active_running_run,
                stale_running_run,
                legacy_running_run,
                success_run,
            ]
        )
        db.commit()
        failed_run_id = failed_run.id
        pending_run_id = pending_run.id
        cancelled_run_id = cancelled_run.id
        active_running_run_id = active_running_run.id
        stale_running_run_id = stale_running_run.id
        legacy_running_run_id = legacy_running_run.id
        success_run_id = success_run.id

    forbidden = client.post(
        f"/api/admin/knowledge-snapshot-runs/{failed_run_id}/requeue",
        headers=_auth_header(teacher_token),
        json={"reason": "retry after data fix"},
    )
    assert forbidden.status_code == 403

    requeued = client.post(
        f"/api/admin/knowledge-snapshot-runs/{failed_run_id}/requeue",
        headers={**_auth_header(admin_token), "X-Request-ID": "snapshot-requeue-request"},
        json={"reason": " retry after data fix "},
    )
    assert requeued.status_code == 200
    requeued_body = requeued.json()
    assert requeued_body["status"] == "pending"
    assert requeued_body["trigger_source"] == "admin_requeue"
    assert requeued_body["attempt_count"] == 0
    assert requeued_body["finished_at"] is None
    assert requeued_body["error_message"] is None
    assert requeued_body["scheduler_lease_owner"] is None
    assert requeued_body["scheduler_lease_expires_at"] is None
    assert requeued_body["scheduler_heartbeat_at"] is None
    assert requeued_body["metadata_json"]["trigger_source"] == "admin_requeue"
    assert requeued_body["metadata_json"]["previous_status"] == "failed"
    assert requeued_body["metadata_json"]["previous_attempt_count"] == settings.knowledge_snapshot_retry_attempts
    assert requeued_body["metadata_json"]["cleared_lease"] is True
    assert requeued_body["metadata_json"]["requeue_reason"] == "retry after data fix"
    assert "scheduler_lease_token" not in requeued_body
    assert "secret-requeue-token" not in json.dumps(requeued_body, ensure_ascii=False)

    pending_requeue = client.post(
        f"/api/admin/knowledge-snapshot-runs/{pending_run_id}/requeue",
        headers=_auth_header(admin_token),
        json={},
    )
    assert pending_requeue.status_code == 200
    pending_body = pending_requeue.json()
    assert pending_body["status"] == "pending"
    assert pending_body["trigger_source"] == "admin"
    assert pending_body["metadata_json"] == {"trigger_source": "admin"}

    cancelled_requeue = client.post(
        f"/api/admin/knowledge-snapshot-runs/{cancelled_run_id}/requeue",
        headers=_auth_header(admin_token),
        json={},
    )
    assert cancelled_requeue.status_code == 200
    cancelled_body = cancelled_requeue.json()
    assert cancelled_body["status"] == "pending"
    assert cancelled_body["trigger_source"] == "admin_requeue"
    assert cancelled_body["metadata_json"]["previous_status"] == "cancelled"
    assert cancelled_body["metadata_json"]["cleared_lease"] is False

    active_requeue = client.post(
        f"/api/admin/knowledge-snapshot-runs/{active_running_run_id}/requeue",
        headers=_auth_header(admin_token),
        json={},
    )
    assert active_requeue.status_code == 409

    legacy_running_requeue = client.post(
        f"/api/admin/knowledge-snapshot-runs/{legacy_running_run_id}/requeue",
        headers=_auth_header(admin_token),
        json={},
    )
    assert legacy_running_requeue.status_code == 409

    success_requeue = client.post(
        f"/api/admin/knowledge-snapshot-runs/{success_run_id}/requeue",
        headers=_auth_header(admin_token),
        json={},
    )
    assert success_requeue.status_code == 409

    stale_requeue = client.post(
        f"/api/admin/knowledge-snapshot-runs/{stale_running_run_id}/requeue",
        headers=_auth_header(admin_token),
        json={},
    )
    assert stale_requeue.status_code == 200
    stale_body = stale_requeue.json()
    assert stale_body["status"] == "pending"
    assert stale_body["metadata_json"]["previous_status"] == "running"
    assert "secret-stale-requeue-token" not in json.dumps(stale_body, ensure_ascii=False)

    audit = client.get(
        "/api/admin/audit-logs?action=admin.knowledge_snapshot_run.requeue"
        "&resource_type=knowledge_snapshot_run&request_id=snapshot-requeue-request",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    audit_item = audit.json()["items"][0]
    assert audit_item["snapshot_json"]["previous_status"] == "failed"
    assert audit_item["snapshot_json"]["status"] == "pending"
    assert audit_item["snapshot_json"]["attempt_count"] == 0
    assert audit_item["snapshot_json"]["cleared_lease"] is True
    assert audit_item["snapshot_json"]["reason_provided"] is True
    assert "secret-" not in json.dumps(audit_item["snapshot_json"], ensure_ascii=False)

    with session_factory() as db:
        stored = db.get(KnowledgeSnapshotRun, failed_run_id)
        assert stored is not None
        assert stored.status == "pending"
        assert stored.scheduler_lease_token is None
        assert stored.error_message is None
        assert stored.trigger_source == "admin_requeue"
        assert stored.metadata_json["requeue_reason"] == "retry after data fix"


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


def test_admin_lists_content_script_asset_inventory_with_redaction_and_audit(client):
    admin_token = _bootstrap_admin(client)
    teacher_token = _register_and_login(client, "teacher_script_assets", "teacher")
    admin_user_id = _current_user_id(client, admin_token)
    published_at = datetime(2026, 7, 8, 9, 30, tzinfo=UTC)

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        schema = {
            "slug": "physics/script-asset-inventory",
            "galaxy": "englab",
            "subject": "physics",
            "title": "Energy Conservation",
            "layout": "experiment-page",
            "status": "published",
            "version": "v-test",
            "sections": [],
            "sources": [],
        }
        page = ContentPageRecord(
            slug="physics/script-asset-inventory",
            status="published",
            version="v-test",
            schema_json=schema,
            schema_hash="d" * 64,
            published_by_user_id=admin_user_id,
            published_at=published_at,
        )
        db.add(page)
        db.flush()
        version = ContentPageVersion(
            page_id=page.id,
            slug=page.slug,
            status="published",
            version="v-test",
            schema_hash="d" * 64,
            schema_json=schema,
            published_by_user_id=admin_user_id,
            published_at=published_at,
            note="content script asset inventory fixture",
        )
        db.add(version)
        db.flush()
        page.current_version_id = version.id
        db.add_all(
            [
                ContentScriptAsset(
                    page_id=page.id,
                    page_version_id=version.id,
                    slug=page.slug,
                    sandbox_id="sb_energy",
                    reference_key="scriptUrl",
                    reference_value_sha256="a" * 64,
                    source_url="https://cdn.example.test/assets/secret-token-tool.js",
                    source_host="cdn.example.test",
                    integrity="sha384-secret-integrity-token",
                    matched_algorithm="sha384",
                    asset_sha256="b" * 64,
                    asset_size_bytes=18,
                    content_bytes=b"secret-asset-bytes",
                    policy_version="v6.6.20",
                    policy_context_hash="c" * 64,
                    published_by_user_id=admin_user_id,
                    published_at=published_at + timedelta(minutes=1),
                ),
                ContentScriptAsset(
                    page_id=page.id,
                    page_version_id=version.id,
                    slug=page.slug,
                    sandbox_id="sb_energy",
                    reference_key="workerUrl",
                    reference_value_sha256="e" * 64,
                    source_url="https://static.other.test/assets/worker.js",
                    source_host="static.other.test",
                    integrity="sha384-other-integrity-token",
                    matched_algorithm="sha384",
                    asset_sha256="f" * 64,
                    asset_size_bytes=12,
                    content_bytes=b"other-asset-bytes",
                    policy_version="v6.6.20",
                    policy_context_hash="c" * 64,
                    published_by_user_id=admin_user_id,
                    published_at=published_at,
                ),
            ]
        )
        db.commit()
        page_id = page.id
        version_id = version.id

    forbidden = client.get("/api/admin/content/script-assets", headers=_auth_header(teacher_token))
    assert forbidden.status_code == 403

    first_page = client.get("/api/admin/content/script-assets?limit=1", headers=_auth_header(admin_token))
    assert first_page.status_code == 200
    first_page_body = first_page.json()
    assert first_page_body["total"] == 2
    assert first_page_body["next_offset"] == 1
    assert first_page_body["items"][0]["source_host"] == "cdn.example.test"

    response = client.get(
        "/api/admin/content/script-assets"
        "?source_host=cdn.example.test"
        "&q=energy"
        "&limit=50",
        headers={**_auth_header(admin_token), "X-Request-ID": "script-asset-inventory"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["next_offset"] is None
    item = body["items"][0]
    assert item["page_id"] == page_id
    assert item["page_version_id"] == version_id
    assert item["slug"] == "physics/script-asset-inventory"
    assert item["sandbox_id"] == "sb_energy"
    assert item["reference_key"] == "scriptUrl"
    assert item["reference_value_sha256"] == "a" * 64
    assert item["asset_sha256"] == "b" * 64
    assert item["asset_size_bytes"] == 18
    assert item["policy_context_hash"] == "c" * 64
    assert item["source_url_sha256"]
    response_text = json.dumps(body, ensure_ascii=False)
    assert "source_url" not in item
    assert "integrity" not in item
    assert "content_bytes" not in item
    assert "secret-token" not in response_text
    assert "secret-integrity-token" not in response_text
    assert "secret-asset-bytes" not in response_text

    invalid_window = client.get(
        "/api/admin/content/script-assets?from=2026-07-09T00:00:00Z&to=2026-07-08T00:00:00Z",
        headers=_auth_header(admin_token),
    )
    assert invalid_window.status_code == 422

    audit = client.get(
        "/api/admin/audit-logs?action=admin.content_script_asset.inventory"
        "&resource_type=content_script_asset&request_id=script-asset-inventory",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    snapshot = audit.json()["items"][0]["snapshot_json"]
    assert snapshot["filters"]["source_host"] == "cdn.example.test"
    assert snapshot["filters"]["has_q"] is True
    assert snapshot["total"] == 1
    assert snapshot["item_count"] == 1
    assert snapshot["host_counts"] == {"cdn.example.test": 1}
    audit_text = json.dumps(snapshot, ensure_ascii=False)
    assert "source_url" not in audit_text
    assert "integrity" not in audit_text
    assert "content_bytes" not in audit_text
    assert "secret-token" not in audit_text
    assert "secret-integrity-token" not in audit_text
    assert "secret-asset-bytes" not in audit_text


def test_admin_reads_content_script_asset_mirror_audit_with_redaction(client):
    admin_token = _bootstrap_admin(client)
    teacher_token = _register_and_login(client, "teacher_script_asset_audit", "teacher")
    admin_user_id = _current_user_id(client, admin_token)
    published_at = datetime(2026, 7, 8, 10, 45, tzinfo=UTC)
    ok_bytes = b"console.log('mirror audit ok');\n"
    stale_bytes = b"console.log('mirror audit stale actual');\n"
    expected_stale_bytes = b"console.log('mirror audit stale expected');\n"

    ok_schema = _script_asset_schema(
        "physics/script-asset-audit-ok",
        "https://cdn-audit.example.test/ok.js",
        _sri_sha384(ok_bytes),
    )
    missing_schema = _script_asset_schema(
        "physics/script-asset-audit-missing",
        "https://cdn-audit.example.test/missing.js",
        _sri_sha384(b"console.log('missing mirror');\n"),
    )
    stale_schema = _script_asset_schema(
        "physics/script-asset-audit-stale",
        "https://cdn-audit.example.test/stale.js",
        _sri_sha384(expected_stale_bytes),
    )

    session_factory = get_session_factory(get_settings().database_url)
    with session_factory() as db:
        ok_page, ok_version = _insert_published_script_page(
            db,
            schema=ok_schema,
            publisher_user_id=admin_user_id,
            published_at=published_at,
        )
        missing_page, missing_version = _insert_published_script_page(
            db,
            schema=missing_schema,
            publisher_user_id=admin_user_id,
            published_at=published_at + timedelta(minutes=1),
        )
        stale_page, stale_version = _insert_published_script_page(
            db,
            schema=stale_schema,
            publisher_user_id=admin_user_id,
            published_at=published_at + timedelta(minutes=2),
        )

        ok_ref = external_script_references(ok_schema)[0]
        stale_ref = external_script_references(stale_schema)[0]
        db.add(
            ContentScriptAsset(
                page_id=ok_page.id,
                page_version_id=ok_version.id,
                slug=ok_page.slug,
                sandbox_id=ok_ref.sandbox_id,
                reference_key=ok_ref.reference_key,
                reference_value_sha256=ok_ref.reference_value_sha256,
                source_url=ok_ref.source_url,
                source_host=ok_ref.source_host,
                integrity=ok_ref.integrity,
                matched_algorithm="sha384",
                asset_sha256=hashlib.sha256(ok_bytes).hexdigest(),
                asset_size_bytes=len(ok_bytes),
                content_bytes=ok_bytes,
                policy_version="v6.6.23",
                policy_context_hash="a" * 64,
                published_by_user_id=admin_user_id,
                published_at=ok_version.published_at,
            )
        )
        db.add(
            ContentScriptAsset(
                page_id=stale_page.id,
                page_version_id=stale_version.id,
                slug=stale_page.slug,
                sandbox_id=stale_ref.sandbox_id,
                reference_key=stale_ref.reference_key,
                reference_value_sha256=stale_ref.reference_value_sha256,
                source_url="https://cdn-audit.example.test/secret-stale-token.js",
                source_host=stale_ref.source_host,
                integrity=stale_ref.integrity,
                matched_algorithm="sha384",
                asset_sha256="b" * 64,
                asset_size_bytes=1,
                content_bytes=stale_bytes,
                policy_version="v6.6.23",
                policy_context_hash="a" * 64,
                published_by_user_id=admin_user_id,
                published_at=stale_version.published_at,
            )
        )
        db.commit()
        missing_version_id = missing_version.id

    forbidden = client.get("/api/admin/content/script-assets/mirror-audit", headers=_auth_header(teacher_token))
    assert forbidden.status_code == 403

    first_page = client.get(
        "/api/admin/content/script-assets/mirror-audit?source_host=cdn-audit.example.test&limit=2",
        headers=_auth_header(admin_token),
    )
    assert first_page.status_code == 200
    first_page_body = first_page.json()
    assert first_page_body["total_pages_scanned"] >= 3
    assert first_page_body["total_external_references"] == 3
    assert first_page_body["total_issues"] == 5
    assert first_page_body["next_offset"] == 2
    assert first_page_body["issue_counts_by_code"]["missing_mirror"] == 1
    assert first_page_body["issue_counts_by_code"]["source_mismatch"] == 1
    assert first_page_body["issue_counts_by_code"]["asset_hash_mismatch"] == 1
    assert first_page_body["issue_counts_by_code"]["asset_size_mismatch"] == 1
    assert first_page_body["issue_counts_by_code"]["sri_mismatch"] == 1
    assert first_page_body["issue_counts_by_severity"] == {"critical": 5}

    filtered = client.get(
        "/api/admin/content/script-assets/mirror-audit"
        "?source_host=cdn-audit.example.test"
        "&issue_code=missing_mirror",
        headers={**_auth_header(admin_token), "X-Request-ID": "script-mirror-audit"},
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total_issues"] == 1
    assert body["items"][0]["code"] == "missing_mirror"
    assert body["items"][0]["page_version_id"] == missing_version_id
    assert body["items"][0]["source_host"] == "cdn-audit.example.test"
    response_text = json.dumps(body, ensure_ascii=False)
    assert "source_url" not in body["items"][0]
    assert "integrity" not in body["items"][0]
    assert "content_bytes" not in body["items"][0]
    assert "secret-stale-token" not in response_text
    assert "mirror audit stale actual" not in response_text
    assert "mirror audit stale expected" not in response_text

    audit = client.get(
        "/api/admin/audit-logs?action=admin.content_script_asset.mirror_audit"
        "&resource_type=content_script_asset&request_id=script-mirror-audit",
        headers=_auth_header(admin_token),
    )
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
    snapshot = audit.json()["items"][0]["snapshot_json"]
    assert snapshot["filters"]["issue_code"] == "missing_mirror"
    assert snapshot["total_issues"] == 1
    assert snapshot["item_count"] == 1
    assert snapshot["capabilities"] == {
        "external_network": False,
        "cdn_scan": False,
        "external_alerts": False,
        "repair": False,
    }
    audit_text = json.dumps(snapshot, ensure_ascii=False)
    assert "source_url" not in audit_text
    assert "integrity" not in audit_text
    assert "content_bytes" not in audit_text
    assert "secret-stale-token" not in audit_text


def _script_asset_schema(slug: str, source_url: str, integrity: str) -> dict:
    return {
        "slug": slug,
        "galaxy": "englab",
        "subject": "physics",
        "title": "Script Asset Audit",
        "layout": "experiment-page",
        "status": "published",
        "version": "v-test",
        "sections": [
            {
                "sectionId": f"{slug.rsplit('/', 1)[-1]}-section",
                "type": "experiment",
                "title": "Script Asset Audit",
                "props": {
                    "scriptUrl": source_url,
                    "scriptIntegrity": integrity,
                    "scriptCrossorigin": "anonymous",
                    "scriptSandbox": {
                        "mode": "isolated-iframe",
                        "network": "same-origin",
                    },
                },
            }
        ],
        "sources": [],
    }


def _insert_published_script_page(
    db,
    *,
    schema: dict,
    publisher_user_id: int,
    published_at: datetime,
) -> tuple[ContentPageRecord, ContentPageVersion]:
    page = ContentPageRecord(
        slug=schema["slug"],
        status="published",
        version="v-test",
        schema_json=schema,
        schema_hash=hashlib.sha256(json.dumps(schema, sort_keys=True).encode("utf-8")).hexdigest(),
        published_by_user_id=publisher_user_id,
        published_at=published_at,
    )
    db.add(page)
    db.flush()
    version = ContentPageVersion(
        page_id=page.id,
        slug=page.slug,
        status="published",
        version="v-test",
        schema_hash=page.schema_hash,
        schema_json=schema,
        published_by_user_id=publisher_user_id,
        published_at=published_at,
        note="content script asset mirror audit fixture",
    )
    db.add(version)
    db.flush()
    page.current_version_id = version.id
    return page, version


def _sri_sha384(payload: bytes) -> str:
    digest = hashlib.sha384(payload).digest()
    return "sha384-" + base64.b64encode(digest).decode("ascii").rstrip("=")
