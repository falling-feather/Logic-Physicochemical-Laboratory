from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session

from app.models import ContentDraft, ContentPageRecord, ContentPageVersion
from app.services.content_script_assets import audit_current_content_script_asset_mirrors


ACTIVE_DRAFT_STATUSES = {"draft", "submitted", "changes_requested"}
ACTIVE_DRAFT_KEY = "active"
DEFAULT_REQUEST_ID = "astra-content-lifecycle-drill"
FetchResult = dict[str, Any]
Fetcher = Callable[[str, dict[str, str], float], FetchResult]


def run_content_lifecycle_drill(
    db: Session,
    *,
    database_url: str,
    api_cache_control: str,
    require_mysql: bool = False,
    render_url: str | None = None,
    static_url: str | None = None,
    request_id: str = DEFAULT_REQUEST_ID,
    timeout_seconds: float = 5.0,
    fetcher: Fetcher | None = None,
    max_issues: int = 100,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Run read-only production posture checks for content publish/rollback rollout."""

    generated = generated_at or datetime.now(UTC)
    fetch = fetcher or _fetch_url
    database = _database_report(database_url, require_mysql=require_mysql)
    sections = {
        "current_versions": _current_versions_report(db, max_issues=max_issues),
        "version_lineage": _version_lineage_report(db, max_issues=max_issues),
        "active_drafts": _active_drafts_report(db, max_issues=max_issues),
        "script_mirrors": _script_mirrors_report(db, max_issues=max_issues),
        "api_cache_policy": _api_cache_policy_report(api_cache_control),
        "render_api": _render_api_report(
            render_url,
            request_id=request_id,
            timeout_seconds=timeout_seconds,
            fetch=fetch,
        ),
        "static_fallback": _static_fallback_report(
            static_url,
            timeout_seconds=timeout_seconds,
            fetch=fetch,
        ),
        "mysql_concurrency_evidence": _mysql_concurrency_evidence_report(database["dialect"]),
    }
    ok = bool(database["ok"] and all(bool(section["ok"]) for section in sections.values()))
    return {
        "ok": ok,
        "status": "ready_for_mysql_evidence" if ok else "issues_found",
        "generated_at": _datetime_value(generated),
        "mode": "read_only",
        "database": database,
        **sections,
        "evidence_required": _evidence_required(),
        "sensitive_fields_returned": False,
    }


def _database_report(database_url: str, *, require_mysql: bool) -> dict[str, Any]:
    dialect = _database_dialect(database_url)
    mysql_ok = dialect == "mysql"
    ok = (not require_mysql) or mysql_ok
    return {
        "ok": ok,
        "status": "ready" if ok else "mysql_required",
        "dialect": dialect,
        "require_mysql": require_mysql,
        "mysql": mysql_ok,
        "safe_database_url": _safe_database_url(database_url),
    }


def _current_versions_report(db: Session, *, max_issues: int) -> dict[str, Any]:
    pages = list(db.scalars(select(ContentPageRecord).order_by(ContentPageRecord.slug)).all())
    issues: list[dict[str, Any]] = []
    published_pages = 0
    for page in pages:
        if page.status == "published":
            published_pages += 1
        if page.status != "published":
            continue
        if page.current_version_id is None:
            issues.append(_issue("missing_current_version", "critical", page=page))
            continue
        version = db.get(ContentPageVersion, page.current_version_id)
        if version is None:
            issues.append(
                _issue(
                    "missing_current_version",
                    "critical",
                    page=page,
                    page_version_id=page.current_version_id,
                )
            )
            continue
        if version.slug != page.slug:
            issues.append(_issue("current_version_slug_mismatch", "critical", page=page, version=version))
        if version.page_id != page.id:
            issues.append(_issue("current_version_page_mismatch", "critical", page=page, version=version))
        if version.status != page.status:
            issues.append(_issue("current_status_mismatch", "critical", page=page, version=version))
        if version.version != page.version:
            issues.append(_issue("current_version_label_mismatch", "critical", page=page, version=version))
        if version.schema_hash != page.schema_hash:
            issues.append(_issue("current_schema_hash_mismatch", "critical", page=page, version=version))
        page_hash = _schema_hash(page.schema_json)
        version_hash = _schema_hash(version.schema_json)
        if page.schema_hash != page_hash:
            issues.append(
                _issue(
                    "page_schema_hash_mismatch",
                    "critical",
                    page=page,
                    version=version,
                    computed_schema_hash=page_hash,
                )
            )
        if version.schema_hash != version_hash:
            issues.append(
                _issue(
                    "version_schema_hash_mismatch",
                    "critical",
                    page=page,
                    version=version,
                    computed_schema_hash=version_hash,
                )
            )
        if page.schema_json != version.schema_json:
            issues.append(_issue("current_schema_snapshot_mismatch", "critical", page=page, version=version))

    return _section_report(
        status="ready" if not issues else "issues_found",
        counts={
            "total_pages": len(pages),
            "published_pages": published_pages,
            "issues": len(issues),
        },
        issues=issues,
        max_issues=max_issues,
    )


def _version_lineage_report(db: Session, *, max_issues: int) -> dict[str, Any]:
    versions = list(
        db.scalars(
            select(ContentPageVersion).order_by(
                ContentPageVersion.slug,
                ContentPageVersion.published_at,
                ContentPageVersion.id,
            )
        ).all()
    )
    issues: list[dict[str, Any]] = []
    slug_version_counts: Counter[tuple[str, str]] = Counter((version.slug, version.version) for version in versions)
    source_draft_counts: Counter[int] = Counter(
        int(version.source_draft_id) for version in versions if version.source_draft_id is not None
    )
    for version in versions:
        page = db.get(ContentPageRecord, version.page_id)
        if page is None:
            issues.append(_issue("version_page_missing", "critical", version=version))
        elif page.slug != version.slug:
            issues.append(_issue("version_page_slug_mismatch", "critical", page=page, version=version))

        computed_hash = _schema_hash(version.schema_json)
        if version.schema_hash != computed_hash:
            issues.append(
                _issue(
                    "version_schema_hash_mismatch",
                    "critical",
                    version=version,
                    computed_schema_hash=computed_hash,
                )
            )
        if version.previous_version_id is not None:
            previous = db.get(ContentPageVersion, version.previous_version_id)
            if previous is None:
                issues.append(_issue("previous_version_missing", "critical", version=version))
            elif previous.slug != version.slug:
                issues.append(_issue("previous_version_slug_mismatch", "critical", version=version))
            elif previous.id == version.id:
                issues.append(_issue("previous_version_self_reference", "critical", version=version))
        if version.restored_from_version_id is not None:
            restored = db.get(ContentPageVersion, version.restored_from_version_id)
            if restored is None:
                issues.append(_issue("restored_from_version_missing", "critical", version=version))
            elif restored.slug != version.slug:
                issues.append(_issue("restored_from_version_slug_mismatch", "critical", version=version))
            elif restored.id == version.id:
                issues.append(_issue("restored_from_version_self_reference", "critical", version=version))

    for (slug, version_label), total in sorted(slug_version_counts.items()):
        if total > 1:
            issues.append(
                _issue(
                    "duplicate_slug_version",
                    "critical",
                    slug=slug,
                    version_label=version_label,
                    count=total,
                )
            )
    for source_draft_id, total in sorted(source_draft_counts.items()):
        if total > 1:
            issues.append(_issue("duplicate_source_draft_version", "critical", source_draft_id=source_draft_id, count=total))

    return _section_report(
        status="ready" if not issues else "issues_found",
        counts={
            "total_versions": len(versions),
            "versions_with_previous": sum(1 for version in versions if version.previous_version_id is not None),
            "rollback_versions": sum(1 for version in versions if version.restored_from_version_id is not None),
            "source_draft_versions": sum(1 for version in versions if version.source_draft_id is not None),
            "issues": len(issues),
        },
        issues=issues,
        max_issues=max_issues,
    )


def _active_drafts_report(db: Session, *, max_issues: int) -> dict[str, Any]:
    drafts = list(
        db.scalars(
            select(ContentDraft).order_by(
                ContentDraft.target_slug,
                ContentDraft.author_user_id,
                ContentDraft.id,
            )
        ).all()
    )
    pages = {page.slug: page for page in db.scalars(select(ContentPageRecord)).all()}
    issues: list[dict[str, Any]] = []
    active_drafts = [draft for draft in drafts if draft.status in ACTIVE_DRAFT_STATUSES]
    active_key_groups: defaultdict[tuple[int, str], list[ContentDraft]] = defaultdict(list)
    for draft in drafts:
        if draft.status in ACTIVE_DRAFT_STATUSES:
            if draft.active_key != ACTIVE_DRAFT_KEY:
                issues.append(_issue("active_draft_missing_active_key", "critical", draft=draft))
            else:
                active_key_groups[(draft.author_user_id, draft.target_slug)].append(draft)
            current_page = pages.get(draft.target_slug)
            if (
                current_page is not None
                and current_page.current_version_id is not None
                and draft.base_version_id is not None
                and draft.base_version_id != current_page.current_version_id
            ):
                issues.append(
                    _issue(
                        "stale_active_draft",
                        "warning",
                        draft=draft,
                        current_version_id=current_page.current_version_id,
                    )
                )
        elif draft.active_key is not None:
            issues.append(_issue("closed_draft_has_active_key", "critical", draft=draft))

    for (author_user_id, target_slug), grouped_drafts in sorted(active_key_groups.items()):
        if len(grouped_drafts) > 1:
            issues.append(
                _issue(
                    "duplicate_active_draft",
                    "critical",
                    author_user_id=author_user_id,
                    slug=target_slug,
                    draft_ids=[draft.id for draft in grouped_drafts],
                    count=len(grouped_drafts),
                )
            )

    return _section_report(
        status="ready" if not _has_critical_issue(issues) else "issues_found",
        counts={
            "total_drafts": len(drafts),
            "active_drafts": len(active_drafts),
            "duplicate_active_groups": sum(1 for grouped in active_key_groups.values() if len(grouped) > 1),
            "stale_active_drafts": sum(1 for issue in issues if issue["code"] == "stale_active_draft"),
            "issues": len(issues),
        },
        issues=issues,
        max_issues=max_issues,
        ok=not _has_critical_issue(issues),
    )


def _script_mirrors_report(db: Session, *, max_issues: int) -> dict[str, Any]:
    audit = audit_current_content_script_asset_mirrors(db)
    issues = [
        {
            "code": issue.code,
            "severity": issue.severity,
            "page_id": issue.page_id,
            "page_version_id": issue.page_version_id,
            "slug": issue.slug,
            "sandbox_id": issue.sandbox_id,
            "reference_key": issue.reference_key,
            "reference_value_sha256": issue.reference_value_sha256,
            "source_host": issue.source_host,
            "source_url_sha256": issue.source_url_sha256,
            "asset_id": issue.asset_id,
            "asset_sha256": issue.asset_sha256,
            "published_at": _datetime_value(issue.published_at),
        }
        for issue in audit.issues
    ]
    return _section_report(
        status="ready" if audit.total_issues == 0 else "issues_found",
        counts={
            "total_pages_scanned": audit.total_pages_scanned,
            "total_external_references": audit.total_external_references,
            "total_issues": audit.total_issues,
        },
        issues=issues,
        max_issues=max_issues,
        issue_counts_by_code=audit.issue_counts_by_code,
        issue_counts_by_severity=audit.issue_counts_by_severity,
    )


def _api_cache_policy_report(api_cache_control: str) -> dict[str, Any]:
    cache_value = (api_cache_control or "").strip()
    no_store = "no-store" in cache_value.lower()
    return {
        "ok": no_store,
        "status": "ready" if no_store else "api_cache_not_no_store",
        "api_cache_control": cache_value,
        "render_page_inherits_api_no_store": no_store,
        "policy": "content render APIs must keep Cache-Control: no-store to avoid stale published schema",
    }


def _render_api_report(
    render_url: str | None,
    *,
    request_id: str,
    timeout_seconds: float,
    fetch: Fetcher,
) -> dict[str, Any]:
    if not render_url:
        return {
            "ok": True,
            "status": "skipped_no_render_url",
            "url": None,
            "policy": "pass --render-url to capture live /api/render/page/{slug} no-store evidence",
        }
    response = fetch(render_url, {"Accept": "application/json", "X-Request-ID": request_id}, timeout_seconds)
    if not response["ok"]:
        return {
            "ok": False,
            "status": "unavailable",
            "url": render_url,
            "error": response.get("error"),
        }
    status_code = int(response["status_code"])
    cache_control = _header(response, "cache-control")
    response_request_id = _header(response, "x-request-id")
    content_type = _header(response, "content-type")
    no_store_ok = "no-store" in cache_control.lower()
    request_id_ok = response_request_id in {"", request_id}
    json_ok = "application/json" in content_type.lower() or isinstance(_json_payload(response.get("body", "")), dict)
    ok = 200 <= status_code < 300 and no_store_ok and request_id_ok and json_ok
    return {
        "ok": ok,
        "status": "ready" if ok else "unexpected_response",
        "url": render_url,
        "status_code": status_code,
        "content_type": content_type,
        "cache_control": cache_control,
        "cache_no_store_ok": no_store_ok,
        "request_id": response_request_id,
        "request_id_ok": request_id_ok,
        "json_detected": json_ok,
    }


def _static_fallback_report(
    static_url: str | None,
    *,
    timeout_seconds: float,
    fetch: Fetcher,
) -> dict[str, Any]:
    if not static_url:
        return {
            "ok": True,
            "status": "skipped_no_static_url",
            "url": None,
            "policy": "pass --static-url to prove legacy static fallback remains available",
        }
    parsed = urlparse(static_url)
    if parsed.path.startswith("/api/"):
        return {
            "ok": False,
            "status": "static_url_points_to_api_path",
            "url": static_url,
        }
    response = fetch(static_url, {"Accept": "text/html"}, timeout_seconds)
    if not response["ok"]:
        return {
            "ok": False,
            "status": "unavailable",
            "url": static_url,
            "error": response.get("error"),
        }
    status_code = int(response["status_code"])
    content_type = _header(response, "content-type")
    body_preview = str(response.get("body", ""))[:2048].lower()
    html_detected = "text/html" in content_type.lower() or "<html" in body_preview
    ok = 200 <= status_code < 300 and html_detected
    return {
        "ok": ok,
        "status": "ready" if ok else "unexpected_response",
        "url": static_url,
        "status_code": status_code,
        "content_type": content_type,
        "html_detected": html_detected,
    }


def _mysql_concurrency_evidence_report(dialect: str | None) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "external_evidence_required",
        "database_dialect": dialect,
        "read_only_drill": True,
        "required_checks": [
            "init_content_pages dry-run/apply report",
            "active draft uniqueness conflict under MySQL",
            "concurrent publish conflict returns or records 409",
            "concurrent rollback conflict returns or records 409",
            "publish/rollback/republish version chain before-after snapshot",
        ],
        "policy": "this script verifies stored lifecycle invariants; real MySQL concurrency evidence must be captured separately",
    }


def _section_report(
    *,
    status: str,
    counts: dict[str, int],
    issues: list[dict[str, Any]],
    max_issues: int,
    ok: bool | None = None,
    issue_counts_by_code: dict[str, int] | None = None,
    issue_counts_by_severity: dict[str, int] | None = None,
) -> dict[str, Any]:
    issue_counts_code = issue_counts_by_code or _counts(issues, "code")
    issue_counts_severity = issue_counts_by_severity or _counts(issues, "severity")
    return {
        "ok": (not _has_critical_issue(issues)) if ok is None else ok,
        "status": status,
        "counts": counts,
        "issue_counts_by_code": issue_counts_code,
        "issue_counts_by_severity": issue_counts_severity,
        "issues": issues[:max_issues],
        "truncated": len(issues) > max_issues,
    }


def _issue(
    code: str,
    severity: str,
    *,
    page: ContentPageRecord | None = None,
    version: ContentPageVersion | None = None,
    draft: ContentDraft | None = None,
    slug: str | None = None,
    page_version_id: int | None = None,
    version_label: str | None = None,
    computed_schema_hash: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "code": code,
        "severity": severity,
        "page_id": page.id if page is not None else (version.page_id if version is not None else None),
        "page_version_id": version.id if version is not None else page_version_id,
        "draft_id": draft.id if draft is not None else None,
        "slug": slug or (page.slug if page is not None else (version.slug if version is not None else None)),
        "version": version.version if version is not None else version_label,
        "author_user_id": draft.author_user_id if draft is not None else extra.pop("author_user_id", None),
        "target_slug": draft.target_slug if draft is not None else None,
        "current_schema_hash": page.schema_hash if page is not None else None,
        "version_schema_hash": version.schema_hash if version is not None else None,
        "computed_schema_hash": computed_schema_hash,
    }
    payload.update(extra)
    return {key: value for key, value in payload.items() if value is not None}


def _has_critical_issue(issues: list[dict[str, Any]]) -> bool:
    return any(issue.get("severity") == "critical" for issue in issues)


def _counts(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(item.get(key)) for item in items if item.get(key) is not None))


def _schema_hash(payload: dict) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _database_dialect(database_url: str) -> str | None:
    try:
        return make_url(database_url).get_backend_name()
    except ArgumentError:
        return None


def _safe_database_url(database_url: str) -> str:
    if "://" not in database_url or "@" not in database_url:
        return database_url
    scheme, rest = database_url.split("://", 1)
    _, host = rest.rsplit("@", 1)
    return f"{scheme}://***:***@{host}"


def _fetch_url(url: str, headers: dict[str, str], timeout_seconds: float) -> FetchResult:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return {
                "ok": True,
                "status_code": response.status,
                "headers": {key.lower(): value for key, value in response.headers.items()},
                "body": response.read().decode("utf-8", errors="replace"),
            }
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return {
            "ok": True,
            "status_code": exc.code,
            "headers": {key.lower(): value for key, value in exc.headers.items()},
            "body": body,
        }
    except (TimeoutError, URLError, OSError) as exc:
        return {
            "ok": False,
            "error": exc.__class__.__name__,
        }


def _header(response: FetchResult, name: str) -> str:
    headers = response.get("headers") or {}
    return str(headers.get(name.lower(), ""))


def _json_payload(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return None


def _datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _evidence_required() -> list[dict[str, str]]:
    return [
        {
            "code": "mysql_concurrency",
            "description": "真实 MySQL 下 active draft、publish、rollback 并发冲突和 409 结果分布。",
        },
        {
            "code": "init_content_pages_apply",
            "description": "`init_content_pages` dry-run/apply 命令、退出码和脱敏 JSON 报告。",
        },
        {
            "code": "render_no_store",
            "description": "真实 `/api/render/page/{slug}` 响应头包含 `Cache-Control: no-store`。",
        },
        {
            "code": "static_fallback",
            "description": "旧 C++/静态前端路径仍返回静态 HTML，且未被 `/api/*` 分流误伤。",
        },
    ]
