from datetime import datetime
from hashlib import sha256
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.api.endpoints.admin_presenters import admin_alert_outbox_write_response
from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    ContentDraft,
    ContentPageRecord,
    ContentPageVersion,
    ContentScriptAsset,
    ContentScriptAssetScanRun,
    User,
)
from app.schemas.admin import (
    AdminAlertOutboxWriteResponse,
    AdminContentDraftPage,
    AdminContentDraftRead,
    AdminContentPagePage,
    AdminContentPageRead,
    AdminContentPageVersionDiff,
    AdminContentPageVersionPage,
    AdminContentPageVersionRead,
    AdminContentScriptAssetAuditIssueRead,
    AdminContentScriptAssetAuditReport,
    AdminContentScriptAssetPage,
    AdminContentScriptAssetRead,
    AdminContentScriptAssetRemoteDriftIssueRead,
    AdminContentScriptAssetRemoteDriftReport,
    AdminContentScriptAssetRemoteDriftScanRequest,
    AdminContentScriptAssetScanAlertCandidate,
    AdminContentScriptAssetScanAlertOutboxRequest,
    AdminContentScriptAssetScanAlertReport,
    AdminContentScriptAssetScanHealthItem,
    AdminContentScriptAssetScanHealthReport,
    AdminContentScriptAssetScanQueueItem,
    AdminContentScriptAssetScanQueueReport,
    AdminContentScriptAssetScanRunPage,
    AdminContentScriptAssetScanRunRead,
    AdminContentScriptAssetScanRunStatusBucket,
    AdminContentScriptHostPolicyPage,
    AdminContentScriptHostPolicyRead,
    AdminContentScriptHostPolicyUpdate,
)
from app.services.admin_alert_outbox import (
    admin_alert_outbox_write_snapshot,
    enqueue_content_script_remote_drift_alert_outbox,
)
from app.services.admin_common import contains_pattern, next_offset, require_admin, statement_count
from app.services.audit import record_audit_log
from app.services.content_script_asset_scan_runs import (
    ContentScriptAssetScanAlertCandidate as ContentScriptAssetScanAlertCandidateRow,
    ContentScriptAssetScanAlertReport as ContentScriptAssetScanAlertReportRow,
    ContentScriptAssetScanHealthItem as ContentScriptAssetScanHealthItemRow,
    ContentScriptAssetScanHealthReport as ContentScriptAssetScanHealthReportRow,
    ContentScriptAssetScanQueueItem as ContentScriptAssetScanQueueItemRow,
    ContentScriptAssetScanQueueReport as ContentScriptAssetScanQueueReportRow,
    build_content_script_asset_scan_alert_report,
    build_content_script_asset_scan_health_report,
    build_content_script_asset_scan_queue_report,
    content_script_asset_scan_alert_snapshot,
    content_script_asset_scan_health_snapshot,
    content_script_asset_scan_queue_snapshot,
    content_script_asset_scan_run_snapshot,
    list_content_script_asset_scan_runs,
    run_content_script_asset_remote_drift_scan,
)
from app.services.content_script_assets import (
    ContentScriptAssetMirrorAuditIssue,
    ContentScriptAssetMirrorAuditReport,
    ContentScriptAssetRemoteDriftIssue,
    ContentScriptAssetRemoteDriftReport,
    audit_current_content_script_asset_mirrors,
)
from app.services.content_script_host_policies import (
    ContentScriptHostPolicyRow,
    content_script_host_policy_snapshot,
    list_content_script_host_policy_rows,
    normalize_content_script_source_host,
    upsert_content_script_host_policy,
)
from app.services.content_version_diff import build_content_schema_diff, build_content_schema_semantic_diff


router = APIRouter()


@router.get("/content/pages", response_model=AdminContentPagePage)
def list_admin_content_pages(
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentPagePage:
    require_admin(current_user)
    statement = select(ContentPageRecord).order_by(ContentPageRecord.slug)
    if status_filter is not None:
        statement = statement.where(ContentPageRecord.status == status_filter.strip().lower())
    if q is not None and q.strip():
        pattern = contains_pattern(q)
        searchable_fields = [
            ContentPageRecord.slug,
            _content_page_schema_text("title"),
            _content_page_schema_text("galaxy"),
            _content_page_schema_text("subject"),
            _content_page_schema_text("layout"),
        ]
        statement = statement.where(or_(*(field.ilike(pattern, escape="~") for field in searchable_fields)))

    total = statement_count(db, statement)
    records = list(db.scalars(statement.offset(offset).limit(limit)).all())
    items = [
        AdminContentPageRead(
            id=record.id,
            slug=record.slug,
            title=str(record.schema_json.get("title", record.slug)),
            galaxy=str(record.schema_json.get("galaxy", "")),
            subject=str(record.schema_json.get("subject", "")),
            layout=str(record.schema_json.get("layout", "")),
            status=record.status,
            version=record.version,
            schema_hash=record.schema_hash,
            current_version_id=record.current_version_id,
            published_by_user_id=record.published_by_user_id,
            published_at=record.published_at,
            updated_at=record.updated_at,
        )
        for record in records
    ]
    return AdminContentPagePage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(total, offset, len(items)),
    )


@router.get("/content/drafts", response_model=AdminContentDraftPage)
def list_admin_content_drafts(
    status_filter: str | None = Query(default=None, alias="status"),
    script_review_status: str | None = Query(default=None),
    script_risk_level: str | None = Query(default=None),
    author_user_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentDraftPage:
    require_admin(current_user)
    statement = (
        select(ContentDraft, User)
        .join(User, User.id == ContentDraft.author_user_id)
        .order_by(ContentDraft.created_at.desc(), ContentDraft.id.desc())
    )
    if status_filter is not None:
        statement = statement.where(ContentDraft.status == status_filter.strip().lower())
    if script_review_status is not None:
        statement = statement.where(ContentDraft.script_review_status == script_review_status.strip().lower())
    if script_risk_level is not None:
        statement = statement.where(ContentDraft.script_risk_level == script_risk_level.strip().lower())
    if author_user_id is not None:
        statement = statement.where(ContentDraft.author_user_id == author_user_id)
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                ContentDraft.target_slug.ilike(pattern),
                ContentDraft.title.ilike(pattern),
                User.username.ilike(pattern),
                User.display_name.ilike(pattern),
            )
        )
    total = statement_count(db, statement)
    rows = db.execute(statement.offset(offset).limit(limit)).all()
    items = [_admin_content_draft_read(draft, author) for draft, author in rows]
    return AdminContentDraftPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(total, offset, len(items)),
    )


@router.get("/content/page-versions", response_model=AdminContentPageVersionPage)
def list_admin_content_page_versions(
    slug: str | None = Query(default=None, max_length=180),
    source_draft_id: int | None = Query(default=None),
    restored_from_version_id: int | None = Query(default=None),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentPageVersionPage:
    require_admin(current_user)
    statement = select(ContentPageVersion).order_by(
        ContentPageVersion.published_at.desc(),
        ContentPageVersion.id.desc(),
    )
    if slug is not None and slug.strip():
        statement = statement.where(ContentPageVersion.slug == slug.strip("/"))
    if source_draft_id is not None:
        statement = statement.where(ContentPageVersion.source_draft_id == source_draft_id)
    if restored_from_version_id is not None:
        statement = statement.where(ContentPageVersion.restored_from_version_id == restored_from_version_id)
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                ContentPageVersion.slug.ilike(pattern),
                ContentPageVersion.version.ilike(pattern),
                ContentPageVersion.note.ilike(pattern),
            )
        )
    total = statement_count(db, statement)
    versions = list(db.scalars(statement.offset(offset).limit(limit)).all())
    items = [_admin_content_page_version_read(version) for version in versions]
    return AdminContentPageVersionPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(total, offset, len(items)),
    )


@router.get("/content/script-assets", response_model=AdminContentScriptAssetPage)
def list_admin_content_script_assets(
    request: Request,
    slug: str | None = Query(default=None, max_length=180),
    source_host: str | None = Query(default=None, max_length=255),
    sandbox_id: str | None = Query(default=None, max_length=32),
    page_id: int | None = Query(default=None, ge=1),
    page_version_id: int | None = Query(default=None, ge=1),
    published_by_user_id: int | None = Query(default=None, ge=1),
    policy_version: str | None = Query(default=None, max_length=64),
    policy_context_hash: str | None = Query(default=None, min_length=64, max_length=64),
    asset_sha256: str | None = Query(default=None, min_length=64, max_length=64),
    reference_value_sha256: str | None = Query(default=None, min_length=64, max_length=64),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetPage:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")

    filters = _content_script_asset_filters(
        slug=slug,
        source_host=source_host,
        sandbox_id=sandbox_id,
        page_id=page_id,
        page_version_id=page_version_id,
        published_by_user_id=published_by_user_id,
        policy_version=policy_version,
        policy_context_hash=policy_context_hash,
        asset_sha256=asset_sha256,
        reference_value_sha256=reference_value_sha256,
        from_at=from_at,
        to_at=to_at,
        q=q,
    )
    statement = select(ContentScriptAsset).order_by(
        ContentScriptAsset.published_at.desc(),
        ContentScriptAsset.id.desc(),
    )
    statement = _apply_content_script_asset_filters(statement, filters)
    total = statement_count(db, statement)
    assets = list(db.scalars(statement.offset(offset).limit(limit)).all())
    items = [_admin_content_script_asset_read(asset) for asset in assets]

    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.inventory",
        resource_type="content_script_asset",
        event_result="success",
        request=request,
        snapshot=_content_script_asset_inventory_snapshot(
            assets,
            filters=filters,
            total=total,
            limit=limit,
            offset=offset,
        ),
    )
    db.commit()
    return AdminContentScriptAssetPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(total, offset, len(items)),
    )


@router.get("/content/script-host-policies", response_model=AdminContentScriptHostPolicyPage)
def list_admin_content_script_host_policies(
    request: Request,
    source_host: str | None = Query(default=None, max_length=255),
    policy_status: Literal["trusted", "watch", "blocked", "unreviewed"] | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptHostPolicyPage:
    require_admin(current_user)
    try:
        page = list_content_script_host_policy_rows(
            db,
            allowed_hosts=get_settings().content_script_allowed_host_list,
            source_host=source_host,
            status=policy_status,
            q=q,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    items = [_admin_content_script_host_policy_read(item) for item in page.items]
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_host_policy.list",
        resource_type="content_script_host_policy",
        event_result="success",
        request=request,
        snapshot={
            "filters": _content_script_host_policy_filters(
                source_host=source_host,
                policy_status=policy_status,
                q=q,
            ),
            "total": page.total,
            "limit": limit,
            "offset": offset,
            "item_count": len(items),
            "capabilities": {
                "mutation": False,
                "allows_host": False,
                "blocks_publish_when_status_blocked": True,
            },
        },
    )
    db.commit()
    return AdminContentScriptHostPolicyPage(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(page.total, offset, len(items)),
    )


@router.patch("/content/script-host-policies/{source_host}", response_model=AdminContentScriptHostPolicyRead)
def update_admin_content_script_host_policy(
    request: Request,
    source_host: str = Path(..., min_length=1, max_length=255),
    payload: AdminContentScriptHostPolicyUpdate = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptHostPolicyRead:
    require_admin(current_user)
    try:
        normalized_host = normalize_content_script_source_host(source_host)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    before_page = list_content_script_host_policy_rows(
        db,
        allowed_hosts=get_settings().content_script_allowed_host_list,
        source_host=normalized_host,
        limit=1,
        offset=0,
    )
    before = (
        _admin_content_script_host_policy_read(before_page.items[0]).model_dump(mode="json")
        if before_page.items
        else None
    )
    try:
        policy = upsert_content_script_host_policy(
            db,
            source_host=normalized_host,
            status=payload.status,
            reason=payload.reason,
            reviewer=current_user,
        )
        db.flush()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    after_page = list_content_script_host_policy_rows(
        db,
        allowed_hosts=get_settings().content_script_allowed_host_list,
        source_host=normalized_host,
        limit=1,
        offset=0,
    )
    after = _admin_content_script_host_policy_read(after_page.items[0])
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_host_policy.update",
        resource_type="content_script_host_policy",
        resource_id=policy.id,
        event_result="success",
        request=request,
        snapshot={
            "before": before,
            "after": after.model_dump(mode="json"),
            "policy": content_script_host_policy_snapshot(policy),
            "capabilities": {
                "allows_host": False,
                "blocks_publish_when_status_blocked": policy.status == "blocked",
                "external_network": False,
                "mutation": True,
            },
        },
    )
    db.commit()
    db.refresh(policy)
    return after


@router.get("/content/script-assets/mirror-audit", response_model=AdminContentScriptAssetAuditReport)
def read_admin_content_script_asset_audit(
    request: Request,
    slug: str | None = Query(default=None, max_length=180),
    source_host: str | None = Query(default=None, max_length=255),
    issue_code: str | None = Query(default=None, max_length=80),
    severity: Literal["critical", "warning", "info"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetAuditReport:
    require_admin(current_user)
    report = audit_current_content_script_asset_mirrors(
        db,
        slug=slug,
        source_host=source_host,
        issue_code=issue_code,
        severity=severity,
    )
    issues = report.issues[offset : offset + limit]
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.mirror_audit",
        resource_type="content_script_asset",
        event_result="success",
        request=request,
        snapshot=_content_script_asset_mirror_audit_snapshot(
            report,
            slug=slug,
            source_host=source_host,
            issue_code=issue_code,
            severity=severity,
            limit=limit,
            offset=offset,
            item_count=len(issues),
        ),
    )
    db.commit()
    return AdminContentScriptAssetAuditReport(
        generated_at=report.generated_at,
        total_pages_scanned=report.total_pages_scanned,
        total_external_references=report.total_external_references,
        total_issues=report.total_issues,
        issue_counts_by_code=report.issue_counts_by_code,
        issue_counts_by_severity=report.issue_counts_by_severity,
        items=[_admin_content_script_asset_audit_issue_read(issue) for issue in issues],
        limit=limit,
        offset=offset,
        next_offset=next_offset(report.total_issues, offset, len(issues)),
    )


@router.get("/content/script-assets/remote-drift-scan-runs", response_model=AdminContentScriptAssetScanRunPage)
def list_admin_content_script_asset_remote_drift_scan_runs(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    trigger_source: str | None = Query(default=None, max_length=32),
    alert_status: Literal["ok", "warning", "critical"] | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetScanRunPage:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    page = list_content_script_asset_scan_runs(
        db,
        status=status_filter,
        trigger_source=trigger_source,
        alert_status=alert_status,
        from_at=from_at,
        to_at=to_at,
        limit=limit,
        offset=offset,
    )
    items = [_admin_content_script_asset_scan_run_read(run) for run in page.items]
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.remote_drift_scan_run.list",
        resource_type="content_script_asset_scan_run",
        event_result="success",
        request=request,
        snapshot={
            "filters": _content_script_asset_scan_run_filters(
                status_filter=status_filter,
                trigger_source=trigger_source,
                alert_status=alert_status,
                from_at=from_at,
                to_at=to_at,
            ),
            "total": page.total,
            "limit": limit,
            "offset": offset,
            "item_count": len(items),
            "capabilities": {
                "mutation": False,
                "external_network": False,
                "external_alerts": False,
                "automatic_actions": False,
            },
        },
    )
    db.commit()
    return AdminContentScriptAssetScanRunPage(
        items=items,
        total=page.total,
        limit=limit,
        offset=offset,
        next_offset=next_offset(page.total, offset, len(items)),
    )


@router.get(
    "/content/script-assets/remote-drift-scan-runs/health",
    response_model=AdminContentScriptAssetScanHealthReport,
)
def read_admin_content_script_asset_remote_drift_scan_run_health(
    request: Request,
    trigger_source: str | None = Query(default=None, max_length=32),
    alert_status: Literal["ok", "warning", "critical"] | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    now_at: datetime | None = Query(default=None, alias="now"),
    lease_expiring_seconds: int = Query(default=900, ge=0, le=24 * 60 * 60),
    problem_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetScanHealthReport:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    report = build_content_script_asset_scan_health_report(
        db,
        trigger_source=trigger_source,
        alert_status=alert_status,
        from_at=from_at,
        to_at=to_at,
        lease_seconds=get_settings().content_script_remote_drift_scheduler_lease_seconds,
        lease_expiring_seconds=lease_expiring_seconds,
        problem_limit=problem_limit,
        generated_at=now_at,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.remote_drift_scan_run.health_report",
        resource_type="content_script_asset_scan_run",
        event_result="success",
        request=request,
        snapshot=content_script_asset_scan_health_snapshot(report),
    )
    db.commit()
    return _admin_content_script_asset_scan_health_report(report)


@router.get(
    "/content/script-assets/remote-drift-scan-runs/queue",
    response_model=AdminContentScriptAssetScanQueueReport,
)
def read_admin_content_script_asset_remote_drift_scan_run_queue(
    request: Request,
    trigger_source: str | None = Query(default=None, max_length=32),
    alert_status: Literal["ok", "warning", "critical"] | None = Query(default=None),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    now_at: datetime | None = Query(default=None, alias="now"),
    item_limit: int = Query(default=20, ge=0, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetScanQueueReport:
    require_admin(current_user)
    if from_at is not None and to_at is not None and from_at > to_at:
        raise HTTPException(status_code=422, detail="from must be earlier than to")
    settings = get_settings()
    report = build_content_script_asset_scan_queue_report(
        db,
        trigger_source=trigger_source,
        alert_status=alert_status,
        from_at=from_at,
        to_at=to_at,
        generated_at=now_at,
        scheduler_enabled=settings.content_script_remote_drift_scheduler_enabled,
        scheduler_interval_seconds=settings.content_script_remote_drift_scheduler_interval_seconds,
        scheduler_lease_seconds=settings.content_script_remote_drift_scheduler_lease_seconds,
        scheduler_scan_limit=settings.content_script_remote_drift_scheduler_scan_limit,
        scheduler_source_host=settings.content_script_remote_drift_scheduler_source_host,
        scheduler_slug=settings.content_script_remote_drift_scheduler_slug,
        scheduler_actor_user_id=settings.content_script_remote_drift_scheduler_actor_user_id,
        item_limit=item_limit,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.remote_drift_scan_run.queue_report",
        resource_type="content_script_asset_scan_run",
        event_result="success",
        request=request,
        snapshot=content_script_asset_scan_queue_snapshot(report),
    )
    db.commit()
    return _admin_content_script_asset_scan_queue_report(report)


@router.get("/content/script-assets/remote-drift-alerts", response_model=AdminContentScriptAssetScanAlertReport)
def read_admin_content_script_asset_remote_drift_alerts(
    request: Request,
    trigger_source: str | None = Query(default=None, max_length=32),
    alert_status: Literal["ok", "warning", "critical"] | None = Query(default=None),
    recent_run_limit: int = Query(default=20, ge=1, le=100),
    candidate_limit: int = Query(default=20, ge=0, le=100),
    now_at: datetime | None = Query(default=None, alias="now"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetScanAlertReport:
    require_admin(current_user)
    report = build_content_script_asset_scan_alert_report(
        db,
        recent_run_limit=recent_run_limit,
        candidate_limit=candidate_limit,
        generated_at=now_at,
        trigger_source=trigger_source,
        alert_status=alert_status,
        lease_seconds=get_settings().content_script_remote_drift_scheduler_lease_seconds,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.remote_drift_alert_report",
        resource_type="content_script_asset_scan_run",
        event_result="success",
        request=request,
        snapshot=content_script_asset_scan_alert_snapshot(report),
    )
    db.commit()
    return _admin_content_script_asset_scan_alert_report(report)


@router.post("/content/script-assets/remote-drift-alerts/outbox", response_model=AdminAlertOutboxWriteResponse)
def enqueue_admin_content_script_asset_remote_drift_alert_outbox(
    request_body: AdminContentScriptAssetScanAlertOutboxRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminAlertOutboxWriteResponse:
    require_admin(current_user)
    if not request_body.confirm_observe_only:
        raise HTTPException(status_code=422, detail="confirm_observe_only must be true")
    report = build_content_script_asset_scan_alert_report(
        db,
        recent_run_limit=request_body.recent_run_limit,
        candidate_limit=request_body.candidate_limit,
        generated_at=request_body.now_at,
        trigger_source=request_body.trigger_source,
        alert_status=request_body.alert_status,
        lease_seconds=get_settings().content_script_remote_drift_scheduler_lease_seconds,
    )
    write_result = enqueue_content_script_remote_drift_alert_outbox(
        db,
        report=report,
        actor=current_user,
        status=request_body.status,
    )
    record_audit_log(
        db,
        actor=current_user,
        action="admin.alert_outbox.content_script_asset_remote_drift.enqueue",
        resource_type="admin_alert_outbox",
        event_result="success",
        request=request,
        snapshot=admin_alert_outbox_write_snapshot(write_result),
    )
    db.commit()
    for entry in write_result.entries:
        db.refresh(entry)
    return admin_alert_outbox_write_response(write_result)


@router.post("/content/script-assets/remote-drift-scan", response_model=AdminContentScriptAssetRemoteDriftReport)
def scan_admin_content_script_asset_remote_drift(
    request_body: AdminContentScriptAssetRemoteDriftScanRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentScriptAssetRemoteDriftReport:
    require_admin(current_user)
    if not request_body.confirm_external_network:
        raise HTTPException(status_code=422, detail="confirm_external_network must be true")
    execution = run_content_script_asset_remote_drift_scan(
        creator=current_user,
        db=db,
        trigger_source="manual",
        slug=request_body.slug,
        source_host=request_body.source_host,
        issue_code=request_body.issue_code,
        severity=request_body.severity,
        scan_limit=request_body.limit,
        scan_offset=request_body.offset,
    )
    report = execution.report
    scan_run = execution.run
    audit_snapshot = _content_script_asset_remote_drift_scan_snapshot(
        report,
        request_body=request_body,
        item_count=len(report.issues),
    )
    audit_snapshot["scan_run"] = content_script_asset_scan_run_snapshot(scan_run)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.content_script_asset.remote_drift_scan",
        resource_type="content_script_asset",
        event_result="success",
        request=request,
        snapshot=audit_snapshot,
    )
    db.commit()
    return AdminContentScriptAssetRemoteDriftReport(
        scan_run_id=scan_run.id,
        scan_run_key=scan_run.run_key,
        generated_at=report.generated_at,
        total_pages_scanned=report.total_pages_scanned,
        total_external_references=report.total_external_references,
        total_scanned_references=report.total_scanned_references,
        total_remote_fetches=report.total_remote_fetches,
        total_skipped_references=report.total_skipped_references,
        total_issues=report.total_issues,
        issue_counts_by_code=report.issue_counts_by_code,
        issue_counts_by_severity=report.issue_counts_by_severity,
        items=[_admin_content_script_asset_remote_drift_issue_read(issue) for issue in report.issues],
        limit=request_body.limit,
        offset=request_body.offset,
        next_offset=next_offset(
            report.total_external_references,
            request_body.offset,
            report.total_scanned_references,
        ),
    )


@router.get("/content/page-versions/{version_id}/diff", response_model=AdminContentPageVersionDiff)
def read_admin_content_page_version_diff(
    version_id: int,
    base_version_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminContentPageVersionDiff:
    require_admin(current_user)
    target_version = db.get(ContentPageVersion, version_id)
    if target_version is None:
        raise HTTPException(status_code=404, detail="Content page version not found")

    if base_version_id is None:
        base_version = _linked_previous_content_page_version(db, target_version) or target_version
    else:
        base_version = db.get(ContentPageVersion, base_version_id)
    if base_version is None:
        raise HTTPException(status_code=404, detail="Base content page version not found")
    if base_version.slug != target_version.slug:
        raise HTTPException(status_code=422, detail="Content page versions must share the same slug")

    changes = build_content_schema_diff(base_version.schema_json, target_version.schema_json)
    semantic = build_content_schema_semantic_diff(base_version.schema_json, target_version.schema_json)
    return AdminContentPageVersionDiff(
        slug=target_version.slug,
        base_version_id=base_version.id,
        base_version=base_version.version,
        base_schema_hash=base_version.schema_hash,
        target_version_id=target_version.id,
        target_version=target_version.version,
        target_schema_hash=target_version.schema_hash,
        change_count=len(changes),
        changes=changes,
        semantic=semantic,
    )




def _admin_content_draft_read(draft: ContentDraft, author: User) -> AdminContentDraftRead:
    return AdminContentDraftRead(
        id=draft.id,
        author_user_id=draft.author_user_id,
        author_username=author.username,
        author_display_name=author.display_name,
        target_slug=draft.target_slug,
        title=draft.title,
        status=draft.status,
        allow_script=draft.allow_script,
        schema_hash=draft.schema_hash,
        base_version_id=draft.base_version_id,
        base_schema_hash=draft.base_schema_hash,
        script_risk_level=draft.script_risk_level,
        script_analysis=draft.script_analysis_json,
        script_review_status=draft.script_review_status,
        script_reviewed_by_user_id=draft.script_reviewed_by_user_id,
        script_reviewed_at=draft.script_reviewed_at,
        script_review_note=draft.script_review_note,
        submitted_at=draft.submitted_at,
        withdrawn_at=draft.withdrawn_at,
        change_requested_by_user_id=draft.change_requested_by_user_id,
        change_requested_at=draft.change_requested_at,
        change_request_note=draft.change_request_note,
        published_page_id=draft.published_page_id,
        published_version_id=draft.published_version_id,
        published_by_user_id=draft.published_by_user_id,
        published_at=draft.published_at,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _admin_content_page_version_read(version: ContentPageVersion) -> AdminContentPageVersionRead:
    return AdminContentPageVersionRead(
        id=version.id,
        page_id=version.page_id,
        slug=version.slug,
        title=str(version.schema_json.get("title", version.slug)),
        status=version.status,
        version=version.version,
        schema_hash=version.schema_hash,
        previous_version_id=version.previous_version_id,
        source_draft_id=version.source_draft_id,
        restored_from_version_id=version.restored_from_version_id,
        published_by_user_id=version.published_by_user_id,
        published_at=version.published_at,
        note=version.note,
        created_at=version.created_at,
    )


def _admin_content_script_asset_read(asset: ContentScriptAsset) -> AdminContentScriptAssetRead:
    return AdminContentScriptAssetRead(
        id=asset.id,
        page_id=asset.page_id,
        page_version_id=asset.page_version_id,
        slug=asset.slug,
        sandbox_id=asset.sandbox_id,
        reference_key=asset.reference_key,
        reference_value_sha256=asset.reference_value_sha256,
        source_host=asset.source_host,
        source_url_sha256=sha256(asset.source_url.encode("utf-8")).hexdigest(),
        matched_algorithm=asset.matched_algorithm,
        asset_sha256=asset.asset_sha256,
        asset_size_bytes=asset.asset_size_bytes,
        policy_version=asset.policy_version,
        policy_context_hash=asset.policy_context_hash,
        published_by_user_id=asset.published_by_user_id,
        published_at=asset.published_at,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _admin_content_script_host_policy_read(row: ContentScriptHostPolicyRow) -> AdminContentScriptHostPolicyRead:
    return AdminContentScriptHostPolicyRead(
        id=row.policy_id,
        source_host=row.source_host,
        status=row.status,
        reason=row.reason,
        configured_allowed=row.configured_allowed,
        observed_asset_count=row.observed_asset_count,
        observed_page_count=row.observed_page_count,
        last_observed_at=row.last_observed_at,
        reviewed_by_user_id=row.reviewed_by_user_id,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _admin_content_script_asset_audit_issue_read(
    issue: ContentScriptAssetMirrorAuditIssue,
) -> AdminContentScriptAssetAuditIssueRead:
    return AdminContentScriptAssetAuditIssueRead(
        code=issue.code,
        severity=issue.severity,
        message=issue.message,
        page_id=issue.page_id,
        page_version_id=issue.page_version_id,
        slug=issue.slug,
        sandbox_id=issue.sandbox_id,
        reference_key=issue.reference_key,
        reference_value_sha256=issue.reference_value_sha256,
        source_host=issue.source_host,
        source_url_sha256=issue.source_url_sha256,
        asset_id=issue.asset_id,
        asset_sha256=issue.asset_sha256,
        published_at=issue.published_at,
    )


def _admin_content_script_asset_remote_drift_issue_read(
    issue: ContentScriptAssetRemoteDriftIssue,
) -> AdminContentScriptAssetRemoteDriftIssueRead:
    return AdminContentScriptAssetRemoteDriftIssueRead(
        code=issue.code,
        severity=issue.severity,
        message=issue.message,
        page_id=issue.page_id,
        page_version_id=issue.page_version_id,
        slug=issue.slug,
        sandbox_id=issue.sandbox_id,
        reference_key=issue.reference_key,
        reference_value_sha256=issue.reference_value_sha256,
        source_host=issue.source_host,
        source_url_sha256=issue.source_url_sha256,
        asset_id=issue.asset_id,
        asset_sha256=issue.asset_sha256,
        remote_asset_sha256=issue.remote_asset_sha256,
        remote_asset_size_bytes=issue.remote_asset_size_bytes,
        published_at=issue.published_at,
    )


def _admin_content_script_asset_scan_run_read(run: ContentScriptAssetScanRun) -> AdminContentScriptAssetScanRunRead:
    return AdminContentScriptAssetScanRunRead(
        id=run.id,
        run_key=run.run_key,
        scan_type=run.scan_type,
        trigger_source=run.trigger_source,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_by_user_id=run.created_by_user_id,
        attempt_count=run.attempt_count,
        scheduler_lease_owner=run.scheduler_lease_owner,
        scheduler_lease_expires_at=run.scheduler_lease_expires_at,
        scheduler_heartbeat_at=run.scheduler_heartbeat_at,
        filters_json=run.filters_json,
        totals_json=run.totals_json,
        issue_counts_json=run.issue_counts_json,
        alert_status=run.alert_status,
        error_message=run.error_message,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _admin_content_script_asset_scan_health_report(
    report: ContentScriptAssetScanHealthReportRow,
) -> AdminContentScriptAssetScanHealthReport:
    return AdminContentScriptAssetScanHealthReport(
        generated_at=report.generated_at,
        filters=report.filters,
        policy=report.policy,
        health_status=report.health_status,
        total=report.total,
        by_status=[
            AdminContentScriptAssetScanRunStatusBucket(status=item.status, total=item.total)
            for item in report.by_status
        ],
        running_count=report.running_count,
        active_running_count=report.active_running_count,
        stale_running_count=report.stale_running_count,
        lease_expiring_count=report.lease_expiring_count,
        legacy_running_without_lease_count=report.legacy_running_without_lease_count,
        claimable_count=report.claimable_count,
        success_count=report.success_count,
        failed_count=report.failed_count,
        warning_run_count=report.warning_run_count,
        critical_run_count=report.critical_run_count,
        issue_run_count=report.issue_run_count,
        needs_attention_count=report.needs_attention_count,
        problem_count=report.problem_count,
        problem_runs=[_admin_content_script_asset_scan_health_item(item) for item in report.problem_runs],
        newest_finished_at=report.newest_finished_at,
        oldest_running_started_at=report.oldest_running_started_at,
        next_lease_expires_at=report.next_lease_expires_at,
    )


def _admin_content_script_asset_scan_health_item(
    item: ContentScriptAssetScanHealthItemRow,
) -> AdminContentScriptAssetScanHealthItem:
    return AdminContentScriptAssetScanHealthItem(
        id=item.id,
        run_key=item.run_key,
        scan_type=item.scan_type,
        trigger_source=item.trigger_source,
        status=item.status,
        alert_status=item.alert_status,
        started_at=item.started_at,
        finished_at=item.finished_at,
        scheduler_lease_owner=item.scheduler_lease_owner,
        scheduler_lease_expires_at=item.scheduler_lease_expires_at,
        scheduler_heartbeat_at=item.scheduler_heartbeat_at,
        attempt_count=item.attempt_count,
        error_message=item.error_message,
        health_flags=item.health_flags,
        retryable=item.retryable,
        claimable=item.claimable,
        lease_seconds_remaining=item.lease_seconds_remaining,
    )


def _admin_content_script_asset_scan_queue_report(
    report: ContentScriptAssetScanQueueReportRow,
) -> AdminContentScriptAssetScanQueueReport:
    return AdminContentScriptAssetScanQueueReport(
        generated_at=report.generated_at,
        filters=report.filters,
        policy=report.policy,
        queue_status=report.queue_status,
        backlog_count=report.backlog_count,
        ready_count=report.ready_count,
        dispatchable_now_count=report.dispatchable_now_count,
        claimable_by_lease_rule_count=report.claimable_by_lease_rule_count,
        manual_review_count=report.manual_review_count,
        blocked_count=report.blocked_count,
        failed_count=report.failed_count,
        stale_running_count=report.stale_running_count,
        active_running_count=report.active_running_count,
        legacy_running_without_lease_count=report.legacy_running_without_lease_count,
        by_trigger_source=report.by_trigger_source,
        ready_jobs=[_admin_content_script_asset_scan_queue_item(item) for item in report.ready_jobs],
        manual_review_runs=[_admin_content_script_asset_scan_queue_item(item) for item in report.manual_review_runs],
        blocked_runs=[_admin_content_script_asset_scan_queue_item(item) for item in report.blocked_runs],
        current_window=[_admin_content_script_asset_scan_queue_item(item) for item in report.current_window],
        oldest_ready_at=report.oldest_ready_at,
        oldest_manual_review_at=report.oldest_manual_review_at,
        next_lease_expires_at=report.next_lease_expires_at,
    )


def _admin_content_script_asset_scan_queue_item(
    item: ContentScriptAssetScanQueueItemRow,
) -> AdminContentScriptAssetScanQueueItem:
    return AdminContentScriptAssetScanQueueItem(
        source=item.source,
        reason=item.reason,
        ready=item.ready,
        claimable=item.claimable,
        run_id=item.run_id,
        run_key=item.run_key,
        scan_type=item.scan_type,
        status=item.status,
        trigger_source=item.trigger_source,
        alert_status=item.alert_status,
        started_at=item.started_at,
        finished_at=item.finished_at,
        scheduler_lease_owner=item.scheduler_lease_owner,
        scheduler_lease_expires_at=item.scheduler_lease_expires_at,
        scheduler_heartbeat_at=item.scheduler_heartbeat_at,
        attempt_count=item.attempt_count,
    )


def _admin_content_script_asset_scan_alert_report(
    report: ContentScriptAssetScanAlertReportRow,
) -> AdminContentScriptAssetScanAlertReport:
    return AdminContentScriptAssetScanAlertReport(
        generated_at=report.generated_at,
        filters=report.filters,
        policy=report.policy,
        alert_status=report.alert_status,
        candidate_count=report.candidate_count,
        critical_count=report.critical_count,
        warning_count=report.warning_count,
        info_count=report.info_count,
        recent_run_count=report.recent_run_count,
        issue_run_count=report.issue_run_count,
        candidates=[_admin_content_script_asset_scan_alert_candidate(item) for item in report.candidates],
    )


def _admin_content_script_asset_scan_alert_candidate(
    item: ContentScriptAssetScanAlertCandidateRow,
) -> AdminContentScriptAssetScanAlertCandidate:
    return AdminContentScriptAssetScanAlertCandidate(
        severity=item.severity,
        code=item.code,
        source=item.source,
        action_hint=item.action_hint,
        run_id=item.run_id,
        run_key=item.run_key,
        scan_type=item.scan_type,
        trigger_source=item.trigger_source,
        status=item.status,
        alert_status=item.alert_status,
        started_at=item.started_at,
        finished_at=item.finished_at,
        slug=item.slug,
        page_id=item.page_id,
        page_version_id=item.page_version_id,
        sandbox_id=item.sandbox_id,
        reference_key=item.reference_key,
        reference_value_sha256=item.reference_value_sha256,
        source_host=item.source_host,
        source_url_sha256=item.source_url_sha256,
        asset_id=item.asset_id,
        asset_sha256=item.asset_sha256,
        remote_asset_sha256=item.remote_asset_sha256,
        remote_asset_size_bytes=item.remote_asset_size_bytes,
        published_at=item.published_at,
    )




def _content_script_asset_filters(
    *,
    slug: str | None,
    source_host: str | None,
    sandbox_id: str | None,
    page_id: int | None,
    page_version_id: int | None,
    published_by_user_id: int | None,
    policy_version: str | None,
    policy_context_hash: str | None,
    asset_sha256: str | None,
    reference_value_sha256: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
    q: str | None,
) -> dict[str, Any]:
    return {
        "slug": slug.strip("/") if slug is not None and slug.strip("/") else None,
        "source_host": source_host.strip().lower() if source_host is not None and source_host.strip() else None,
        "sandbox_id": sandbox_id.strip() if sandbox_id is not None and sandbox_id.strip() else None,
        "page_id": page_id,
        "page_version_id": page_version_id,
        "published_by_user_id": published_by_user_id,
        "policy_version": policy_version.strip() if policy_version is not None and policy_version.strip() else None,
        "policy_context_hash": policy_context_hash.strip().lower()
        if policy_context_hash is not None and policy_context_hash.strip()
        else None,
        "asset_sha256": asset_sha256.strip().lower() if asset_sha256 is not None and asset_sha256.strip() else None,
        "reference_value_sha256": reference_value_sha256.strip().lower()
        if reference_value_sha256 is not None and reference_value_sha256.strip()
        else None,
        "from": from_at,
        "to": to_at,
        "q": q.strip() if q is not None and q.strip() else None,
    }


def _content_script_host_policy_filters(
    *,
    source_host: str | None,
    policy_status: str | None,
    q: str | None,
) -> dict[str, Any]:
    filters = {
        "source_host": source_host.strip().lower() if source_host is not None and source_host.strip() else None,
        "status": policy_status.strip().lower() if policy_status is not None and policy_status.strip() else None,
        "q": q.strip() if q is not None and q.strip() else None,
    }
    return {key: value for key, value in filters.items() if value is not None}


def _content_script_asset_scan_run_filters(
    *,
    status_filter: str | None,
    trigger_source: str | None,
    alert_status: str | None,
    from_at: datetime | None,
    to_at: datetime | None,
) -> dict[str, Any]:
    filters = {
        "scan_type": "remote_drift",
        "status": status_filter.strip().lower() if status_filter is not None and status_filter.strip() else None,
        "trigger_source": trigger_source.strip().lower()
        if trigger_source is not None and trigger_source.strip()
        else None,
        "alert_status": alert_status.strip().lower() if alert_status is not None and alert_status.strip() else None,
        "from": from_at.isoformat() if from_at is not None else None,
        "to": to_at.isoformat() if to_at is not None else None,
    }
    return {key: value for key, value in filters.items() if value is not None}


def _content_script_asset_remote_drift_scan_request_filters(
    request_body: AdminContentScriptAssetRemoteDriftScanRequest,
) -> dict[str, Any]:
    filters = {
        "slug": (
            request_body.slug.strip("/")
            if request_body.slug is not None and request_body.slug.strip("/")
            else None
        ),
        "source_host": (
            request_body.source_host.strip().lower()
            if request_body.source_host is not None and request_body.source_host.strip()
            else None
        ),
        "issue_code": (
            request_body.issue_code.strip().lower()
            if request_body.issue_code is not None and request_body.issue_code.strip()
            else None
        ),
        "severity": request_body.severity,
        "limit": request_body.limit,
        "offset": request_body.offset,
        "confirm_external_network": bool(request_body.confirm_external_network),
    }
    return {key: value for key, value in filters.items() if value is not None}


def _content_script_asset_mirror_audit_snapshot(
    report: ContentScriptAssetMirrorAuditReport,
    *,
    slug: str | None,
    source_host: str | None,
    issue_code: str | None,
    severity: str | None,
    limit: int,
    offset: int,
    item_count: int,
) -> dict[str, Any]:
    filters = {
        "slug": slug.strip("/") if slug is not None and slug.strip("/") else None,
        "source_host": source_host.strip().lower() if source_host is not None and source_host.strip() else None,
        "issue_code": issue_code.strip().lower() if issue_code is not None and issue_code.strip() else None,
        "severity": severity,
    }
    return {
        "filters": {key: value for key, value in filters.items() if value is not None},
        "generated_at": report.generated_at.isoformat(),
        "total_pages_scanned": report.total_pages_scanned,
        "total_external_references": report.total_external_references,
        "total_issues": report.total_issues,
        "issue_counts_by_code": report.issue_counts_by_code,
        "issue_counts_by_severity": report.issue_counts_by_severity,
        "limit": limit,
        "offset": offset,
        "item_count": item_count,
        "capabilities": {
            "external_network": False,
            "cdn_scan": False,
            "external_alerts": False,
            "repair": False,
        },
    }


def _content_script_asset_remote_drift_scan_snapshot(
    report: ContentScriptAssetRemoteDriftReport,
    *,
    request_body: AdminContentScriptAssetRemoteDriftScanRequest,
    item_count: int,
) -> dict[str, Any]:
    filters = _content_script_asset_remote_drift_scan_request_filters(request_body)
    filters.pop("limit", None)
    filters.pop("offset", None)
    filters.pop("confirm_external_network", None)
    return {
        "filters": filters,
        "generated_at": report.generated_at.isoformat(),
        "total_pages_scanned": report.total_pages_scanned,
        "total_external_references": report.total_external_references,
        "total_scanned_references": report.total_scanned_references,
        "total_remote_fetches": report.total_remote_fetches,
        "total_skipped_references": report.total_skipped_references,
        "total_issues": report.total_issues,
        "issue_counts_by_code": report.issue_counts_by_code,
        "issue_counts_by_severity": report.issue_counts_by_severity,
        "limit": request_body.limit,
        "offset": request_body.offset,
        "item_count": item_count,
        "capabilities": {
            "external_network": True,
            "cdn_scan": True,
            "external_alerts": False,
            "repair": False,
            "mutation": False,
        },
    }


def _apply_content_script_asset_filters(statement: Any, filters: dict[str, Any]) -> Any:
    if filters["slug"] is not None:
        statement = statement.where(ContentScriptAsset.slug == filters["slug"])
    if filters["source_host"] is not None:
        statement = statement.where(ContentScriptAsset.source_host == filters["source_host"])
    if filters["sandbox_id"] is not None:
        statement = statement.where(ContentScriptAsset.sandbox_id == filters["sandbox_id"])
    if filters["page_id"] is not None:
        statement = statement.where(ContentScriptAsset.page_id == filters["page_id"])
    if filters["page_version_id"] is not None:
        statement = statement.where(ContentScriptAsset.page_version_id == filters["page_version_id"])
    if filters["published_by_user_id"] is not None:
        statement = statement.where(ContentScriptAsset.published_by_user_id == filters["published_by_user_id"])
    if filters["policy_version"] is not None:
        statement = statement.where(ContentScriptAsset.policy_version == filters["policy_version"])
    if filters["policy_context_hash"] is not None:
        statement = statement.where(ContentScriptAsset.policy_context_hash == filters["policy_context_hash"])
    if filters["asset_sha256"] is not None:
        statement = statement.where(ContentScriptAsset.asset_sha256 == filters["asset_sha256"])
    if filters["reference_value_sha256"] is not None:
        statement = statement.where(ContentScriptAsset.reference_value_sha256 == filters["reference_value_sha256"])
    if filters["from"] is not None:
        statement = statement.where(ContentScriptAsset.published_at >= filters["from"])
    if filters["to"] is not None:
        statement = statement.where(ContentScriptAsset.published_at <= filters["to"])
    if filters["q"] is not None:
        pattern = contains_pattern(filters["q"])
        statement = statement.where(
            or_(
                ContentScriptAsset.slug.ilike(pattern, escape="~"),
                ContentScriptAsset.source_host.ilike(pattern, escape="~"),
                ContentScriptAsset.sandbox_id.ilike(pattern, escape="~"),
                ContentScriptAsset.reference_key.ilike(pattern, escape="~"),
                ContentScriptAsset.reference_value_sha256.ilike(pattern, escape="~"),
                ContentScriptAsset.asset_sha256.ilike(pattern, escape="~"),
                ContentScriptAsset.policy_version.ilike(pattern, escape="~"),
                ContentScriptAsset.policy_context_hash.ilike(pattern, escape="~"),
            )
        )
    return statement


def _content_script_asset_inventory_snapshot(
    assets: list[ContentScriptAsset],
    *,
    filters: dict[str, Any],
    total: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    host_counts: dict[str, int] = {}
    policy_version_counts: dict[str, int] = {}
    for asset in assets:
        host_counts[asset.source_host] = host_counts.get(asset.source_host, 0) + 1
        policy_version_counts[asset.policy_version] = policy_version_counts.get(asset.policy_version, 0) + 1
    audit_filters = {
        key: (value.isoformat() if isinstance(value, datetime) else value)
        for key, value in filters.items()
        if value is not None and key != "q"
    }
    audit_filters["has_q"] = filters["q"] is not None
    return {
        "filters": audit_filters,
        "total": total,
        "item_count": len(assets),
        "limit": limit,
        "offset": offset,
        "host_counts": host_counts,
        "policy_version_counts": policy_version_counts,
    }


def _previous_content_page_version(db: Session, version: ContentPageVersion) -> ContentPageVersion | None:
    return db.scalar(
        select(ContentPageVersion)
        .where(
            ContentPageVersion.slug == version.slug,
            ContentPageVersion.id < version.id,
        )
        .order_by(ContentPageVersion.id.desc())
    )


def _linked_previous_content_page_version(db: Session, version: ContentPageVersion) -> ContentPageVersion | None:
    if version.previous_version_id is not None:
        linked_version = db.get(ContentPageVersion, version.previous_version_id)
        if linked_version is not None:
            return linked_version
    return _previous_content_page_version(db, version)




def _content_page_schema_text(field: str) -> Any:
    return func.coalesce(ContentPageRecord.schema_json[field].as_string(), "")
