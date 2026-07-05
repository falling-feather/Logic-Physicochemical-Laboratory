import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentDraft, ContentPageRecord, ContentPageVersion, User
from app.models.base import utc_now
from app.schemas.content import ContentPage
from app.services.audit import record_audit_log
from app.services.content_script_policy import analyze_content_script_policy, public_content_page_schema


ENERGY_CONSERVATION_PAGE = ContentPage(
    slug="physics/energy-conservation",
    galaxy="englab",
    subject="physics",
    title="机械能守恒",
    layout="experiment-page",
    status="published",
    version="2026.07-v6.5-schema.1",
    summary="以物理能量守恒实验为后端内容协议第一试点，保留现有实验交互并由后端提供页面结构。",
    sections=[
        {
            "type": "hero",
            "title": "机械能守恒",
            "summary": "观察动能、势能和耗散之间的转换，理解机械能守恒的适用条件。",
        },
        {
            "type": "learning-task",
            "title": "观察任务",
            "summary": "打开耗散后，比较机械能和能量总量的变化趋势。",
            "props": {
                "tier": "核心",
                "scope": "基础主线",
                "concepts": ["动能", "势能", "非保守力做功", "能量守恒"],
            },
        },
        {
            "type": "experiment",
            "title": "交互实验",
            "experimentId": "energy-conservation",
            "props": {
                "moduleSelectorId": "energy-conservation",
                "scriptPath": "pages/physics/energy-conservation.js",
                "scriptSandbox": {
                    "mode": "isolated-iframe",
                    "network": "same-origin",
                    "storage": "none",
                },
                "defaultFriction": 0.1,
                "fallbackHash": "#physics/energy-conservation",
            },
        },
        {
            "type": "assessment",
            "title": "章节小测",
            "questionSetId": "energy-conservation",
            "summary": "沿用现有工科试验室题库，后续迁入数据库题组。",
        },
        {
            "type": "source-list",
            "title": "参考资料",
            "summary": "首批 schema 保留来源引用，后续进入内容审核与来源索引模型。",
        },
    ],
    courseUnit={
        "courseId": "englab-physics-foundation",
        "unitId": "physics-energy-conservation",
        "order": 10,
        "title": "机械能守恒",
    },
    sources=[
        {
            "label": "OpenStax College Physics 2e · Conservation of Energy",
            "url": "https://openstax.org/books/college-physics-2e/pages/7-introduction-to-work-energy-and-energy-resources",
        }
    ],
)


_SEED_PAGES = {
    ENERGY_CONSERVATION_PAGE.slug: ENERGY_CONSERVATION_PAGE,
}

_ACTIVE_DRAFT_STATUSES = {"draft", "submitted", "changes_requested"}


def ensure_seed_pages(db: Session) -> None:
    for page in _SEED_PAGES.values():
        page_payload = page.model_dump(mode="json")
        schema_hash = _schema_hash(page_payload)
        existing = db.scalar(select(ContentPageRecord).where(ContentPageRecord.slug == page.slug))
        if existing is None:
            db.add(
                ContentPageRecord(
                    slug=page.slug,
                    status=page.status,
                    version=page.version,
                    schema_json=page_payload,
                    schema_hash=schema_hash,
                )
            )
        elif existing.version != page.version and not _has_published_versions(db, page.slug):
            existing.status = page.status
            existing.version = page.version
            existing.schema_json = page_payload
            existing.schema_hash = schema_hash
        elif existing.schema_hash is None:
            existing.schema_hash = schema_hash
    db.commit()


def initialize_builtin_content_pages(
    db: Session,
    *,
    publisher: User,
    dry_run: bool = False,
    note: str | None = None,
    allow_reviewed_scripts: bool = False,
    upgrade_existing: bool = False,
    allow_stale_drafts: bool = False,
) -> dict[str, Any]:
    if publisher.role != "admin" or publisher.status != "active":
        return {
            "ok": False,
            "status": "invalid_publisher",
            "publisher_user_id": publisher.id,
            "items": [],
            "counts": _initialization_counts([]),
        }

    items = [
        _initialize_builtin_content_page(
            db,
            page,
            publisher=publisher,
            dry_run=dry_run,
            note=note,
            allow_reviewed_scripts=allow_reviewed_scripts,
            upgrade_existing=upgrade_existing,
            allow_stale_drafts=allow_stale_drafts,
        )
        for page in _SEED_PAGES.values()
    ]
    ok = all(item.get("ok", False) for item in items)
    if ok and not dry_run:
        db.commit()
    else:
        db.rollback()
    counts = _initialization_counts(items)
    status = "dry_run" if dry_run else "initialized"
    if not ok:
        status = "failed"
    return {
        "ok": ok,
        "status": status,
        "dry_run": dry_run,
        "publisher_user_id": publisher.id,
        "items": items,
        "counts": counts,
    }


def get_page_schema(db: Session, slug: str) -> ContentPage | None:
    record = db.scalar(
        select(ContentPageRecord).where(
            ContentPageRecord.slug == slug.strip("/"),
            ContentPageRecord.status == "published",
        )
    )
    if record is None:
        return None
    return public_content_page_schema(ContentPage.model_validate(record.schema_json))


def list_page_summaries(db: Session) -> list[dict]:
    records = db.scalars(
        select(ContentPageRecord).where(ContentPageRecord.status == "published").order_by(ContentPageRecord.slug)
    ).all()
    return [
        {
            "slug": page.slug,
            "title": page.schema_json.get("title", page.slug),
            "galaxy": page.schema_json.get("galaxy", ""),
            "subject": page.schema_json.get("subject", ""),
            "layout": page.schema_json.get("layout", ""),
            "status": page.status,
            "version": page.version,
        }
        for page in records
    ]


def _initialize_builtin_content_page(
    db: Session,
    seed_page: ContentPage,
    *,
    publisher: User,
    dry_run: bool,
    note: str | None,
    allow_reviewed_scripts: bool,
    upgrade_existing: bool,
    allow_stale_drafts: bool,
) -> dict[str, Any]:
    page_payload = seed_page.model_dump(mode="json")
    seed_schema_hash = _schema_hash(page_payload)
    script_policy = analyze_content_script_policy(seed_page)
    active_drafts = _active_content_draft_count(db, seed_page.slug)
    context = _initialization_context(seed_page, seed_schema_hash, script_policy, active_drafts)
    if script_policy.has_blocking_findings:
        return _initialization_item(
            slug=seed_page.slug,
            action="script_policy_blocked",
            changed=False,
            page=None,
            version=None,
            ok=False,
            error="blocked_script_policy",
            **context,
        )
    if script_policy.has_script_findings and not allow_reviewed_scripts and not dry_run:
        return _initialization_item(
            slug=seed_page.slug,
            action="script_review_required",
            changed=False,
            page=None,
            version=None,
            ok=False,
            error="reviewed_scripts_not_confirmed",
            **context,
        )
    existing = db.scalar(select(ContentPageRecord).where(ContentPageRecord.slug == seed_page.slug))
    if existing is None:
        return _create_initialized_page(
            db,
            seed_page,
            page_payload,
            seed_schema_hash,
            publisher=publisher,
            dry_run=dry_run,
            note=note,
            context=context,
        )

    versions = _content_page_versions(db, seed_page.slug)
    if not versions:
        return _create_missing_initial_version(
            db,
            existing,
            seed_page,
            page_payload,
            seed_schema_hash,
            publisher=publisher,
            dry_run=dry_run,
            note=note,
            context=context,
        )

    current_version = None
    if existing.current_version_id is not None:
        current_version = db.get(ContentPageVersion, existing.current_version_id)
    if current_version is not None and current_version.slug == existing.slug:
        context["current_schema_hash"] = current_version.schema_hash
        if current_version.schema_hash != seed_schema_hash:
            if not upgrade_existing:
                return _initialization_item(
                    slug=seed_page.slug,
                    action="conflict",
                    changed=False,
                    page=existing,
                    version=current_version,
                    ok=False,
                    error="current_schema_differs_from_seed",
                    **context,
                )
            if active_drafts and not allow_stale_drafts:
                return _initialization_item(
                    slug=seed_page.slug,
                    action="stale_drafts_blocked",
                    changed=False,
                    page=existing,
                    version=current_version,
                    ok=False,
                    error="active_drafts_would_become_stale",
                    **context,
                )
            version_conflict = _version_label_conflict(versions, seed_page.version, seed_schema_hash)
            if version_conflict is not None:
                return _initialization_item(
                    slug=seed_page.slug,
                    action="version_conflict",
                    changed=False,
                    page=existing,
                    version=version_conflict,
                    ok=False,
                    error="seed_version_schema_hash_conflict",
                    **context,
                )
            return _upgrade_initialized_page(
                db,
                existing,
                seed_page,
                page_payload,
                seed_schema_hash,
                current_version=current_version,
                publisher=publisher,
                dry_run=dry_run,
                note=note,
                context=context,
            )
        return _initialization_item(
            slug=seed_page.slug,
            action="skipped",
            changed=False,
            page=existing,
            version=current_version,
            schema_hash=existing.schema_hash or seed_schema_hash,
            **context,
        )
    latest_version = versions[0]
    if not dry_run:
        existing.status = latest_version.status
        existing.version = latest_version.version
        existing.schema_json = latest_version.schema_json
        existing.schema_hash = latest_version.schema_hash
        existing.current_version_id = latest_version.id
        existing.published_by_user_id = latest_version.published_by_user_id
        existing.published_at = latest_version.published_at
        record_audit_log(
            db,
            actor=publisher,
            action="content.page.initialize.repair_current",
            resource_type="content_page",
            resource_id=existing.id,
            event_result="success",
            snapshot={"slug": existing.slug, "current_version_id": latest_version.id},
        )
    return _initialization_item(
        slug=seed_page.slug,
        action="repaired_current",
        changed=True,
        page=existing,
        version=latest_version,
        schema_hash=latest_version.schema_hash,
        **context,
    )


def _create_initialized_page(
    db: Session,
    seed_page: ContentPage,
    page_payload: dict[str, Any],
    schema_hash: str,
    *,
    publisher: User,
    dry_run: bool,
    note: str | None,
    context: dict[str, Any],
) -> dict[str, Any]:
    if dry_run:
        return _initialization_item(
            slug=seed_page.slug,
            action="created",
            changed=True,
            page=None,
            version=None,
            schema_hash=schema_hash,
            version_label=seed_page.version,
            **context,
        )
    page = ContentPageRecord(
        slug=seed_page.slug,
        status=seed_page.status,
        version=seed_page.version,
        schema_json=page_payload,
        schema_hash=schema_hash,
    )
    db.add(page)
    db.flush()
    version = _create_content_page_version(
        db,
        page=page,
        schema_json=page_payload,
        schema_hash=schema_hash,
        publisher=publisher,
        note=note,
    )
    _apply_current_version(page, version)
    record_audit_log(
        db,
        actor=publisher,
        action="content.page.initialize.create",
        resource_type="content_page",
        resource_id=page.id,
        event_result="success",
        snapshot={"slug": page.slug, "schema_hash": schema_hash, "version_id": version.id},
    )
    return _initialization_item(
        slug=seed_page.slug,
        action="created",
        changed=True,
        page=page,
        version=version,
        schema_hash=schema_hash,
        **context,
    )


def _create_missing_initial_version(
    db: Session,
    page: ContentPageRecord,
    seed_page: ContentPage,
    seed_payload: dict[str, Any],
    seed_schema_hash: str,
    *,
    publisher: User,
    dry_run: bool,
    note: str | None,
    context: dict[str, Any],
) -> dict[str, Any]:
    try:
        page_schema = ContentPage.model_validate(page.schema_json)
    except Exception as exc:
        return _initialization_item(
            slug=page.slug,
            action="invalid_existing_schema",
            changed=False,
            page=page,
            version=None,
            ok=False,
            error=exc.__class__.__name__,
            **context,
        )
    payload = page_schema.model_dump(mode="json")
    schema_hash = page.schema_hash or _schema_hash(payload)
    if schema_hash != seed_schema_hash:
        context["current_schema_hash"] = schema_hash
        return _initialization_item(
            slug=page.slug,
            action="conflict",
            changed=False,
            page=page,
            version=None,
            ok=False,
            schema_hash=schema_hash,
            error="legacy_schema_differs_from_seed",
            **context,
        )
    if dry_run:
        return _initialization_item(
            slug=page.slug,
            action="version_created",
            changed=True,
            page=page,
            version=None,
            schema_hash=seed_schema_hash,
            version_label=seed_page.version,
            **context,
        )
    page.status = seed_page.status
    page.version = seed_page.version
    page.schema_json = seed_payload
    page.schema_hash = seed_schema_hash
    version = _create_content_page_version(
        db,
        page=page,
        schema_json=seed_payload,
        schema_hash=seed_schema_hash,
        publisher=publisher,
        note=note,
        previous_version_id=None,
    )
    _apply_current_version(page, version)
    record_audit_log(
        db,
        actor=publisher,
        action="content.page.initialize.version",
        resource_type="content_page",
        resource_id=page.id,
        event_result="success",
        snapshot={"slug": page.slug, "schema_hash": schema_hash, "version_id": version.id},
    )
    return _initialization_item(
        slug=page.slug,
        action="version_created",
        changed=True,
        page=page,
        version=version,
        schema_hash=seed_schema_hash,
        **context,
    )


def _upgrade_initialized_page(
    db: Session,
    page: ContentPageRecord,
    seed_page: ContentPage,
    seed_payload: dict[str, Any],
    seed_schema_hash: str,
    *,
    current_version: ContentPageVersion,
    publisher: User,
    dry_run: bool,
    note: str | None,
    context: dict[str, Any],
) -> dict[str, Any]:
    if dry_run:
        return _initialization_item(
            slug=page.slug,
            action="upgraded",
            changed=True,
            page=page,
            version=None,
            schema_hash=seed_schema_hash,
            version_label=seed_page.version,
            previous_version_id=current_version.id,
            **context,
        )
    page.status = seed_page.status
    page.version = seed_page.version
    page.schema_json = seed_payload
    page.schema_hash = seed_schema_hash
    version = _create_content_page_version(
        db,
        page=page,
        schema_json=seed_payload,
        schema_hash=seed_schema_hash,
        publisher=publisher,
        note=note,
        previous_version_id=current_version.id,
    )
    _apply_current_version(page, version)
    record_audit_log(
        db,
        actor=publisher,
        action="content.page.initialize.upgrade",
        resource_type="content_page",
        resource_id=page.id,
        event_result="success",
        snapshot={
            "slug": page.slug,
            "schema_hash": seed_schema_hash,
            "version_id": version.id,
            "previous_version_id": current_version.id,
        },
    )
    return _initialization_item(
        slug=page.slug,
        action="upgraded",
        changed=True,
        page=page,
        version=version,
        schema_hash=seed_schema_hash,
        previous_version_id=current_version.id,
        **context,
    )


def _create_content_page_version(
    db: Session,
    *,
    page: ContentPageRecord,
    schema_json: dict[str, Any],
    schema_hash: str,
    publisher: User,
    note: str | None,
    previous_version_id: int | None = None,
) -> ContentPageVersion:
    version = ContentPageVersion(
        page_id=page.id,
        slug=page.slug,
        status=page.status,
        version=page.version,
        schema_hash=schema_hash,
        schema_json=schema_json,
        source_draft_id=None,
        restored_from_version_id=None,
        previous_version_id=previous_version_id,
        published_by_user_id=publisher.id,
        published_at=utc_now(),
        note=_strip_optional(note),
    )
    db.add(version)
    db.flush()
    return version


def _apply_current_version(page: ContentPageRecord, version: ContentPageVersion) -> None:
    page.status = version.status
    page.version = version.version
    page.schema_json = version.schema_json
    page.schema_hash = version.schema_hash
    page.current_version_id = version.id
    page.published_by_user_id = version.published_by_user_id
    page.published_at = version.published_at


def _content_page_versions(db: Session, slug: str) -> list[ContentPageVersion]:
    return list(
        db.scalars(
            select(ContentPageVersion)
            .where(ContentPageVersion.slug == slug)
            .order_by(ContentPageVersion.published_at.desc(), ContentPageVersion.id.desc())
        ).all()
    )


def _active_content_draft_count(db: Session, slug: str) -> int:
    rows = db.scalars(
        select(ContentDraft.id).where(
            ContentDraft.target_slug == slug,
            ContentDraft.status.in_(_ACTIVE_DRAFT_STATUSES),
        )
    ).all()
    return len(rows)


def _version_label_conflict(
    versions: list[ContentPageVersion],
    version_label: str,
    seed_schema_hash: str,
) -> ContentPageVersion | None:
    for version in versions:
        if version.version == version_label and version.schema_hash != seed_schema_hash:
            return version
    return None


def _initialization_context(
    seed_page: ContentPage,
    seed_schema_hash: str,
    script_policy,
    active_drafts: int,
) -> dict[str, Any]:
    return {
        "seed_version": seed_page.version,
        "seed_schema_hash": seed_schema_hash,
        "active_drafts": active_drafts,
        "script_policy": {
            "policy_version": script_policy.policy_version,
            "status": script_policy.status,
            "risk_level": script_policy.risk_level,
            "finding_count": len(script_policy.findings),
            "sandbox": script_policy.sandbox,
        },
    }


def _initialization_item(
    *,
    slug: str,
    action: str,
    changed: bool,
    page: ContentPageRecord | None,
    version: ContentPageVersion | None,
    ok: bool = True,
    schema_hash: str | None = None,
    version_label: str | None = None,
    previous_version_id: int | None = None,
    seed_version: str | None = None,
    seed_schema_hash: str | None = None,
    current_schema_hash: str | None = None,
    active_drafts: int = 0,
    script_policy: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "ok": ok,
        "slug": slug,
        "action": action,
        "changed": changed,
        "page_id": page.id if page is not None and page.id is not None else None,
        "version_id": version.id if version is not None and version.id is not None else None,
        "version": version.version if version is not None else version_label,
        "previous_version_id": previous_version_id if previous_version_id is not None else (
            version.previous_version_id if version is not None else None
        ),
        "schema_hash": schema_hash or (version.schema_hash if version is not None else None),
        "seed_version": seed_version,
        "seed_schema_hash": seed_schema_hash,
        "current_schema_hash": current_schema_hash,
        "active_drafts": active_drafts,
        "script_policy": script_policy,
    }
    if error is not None:
        item["error"] = error
    return item


def _initialization_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(items),
        "changed": sum(1 for item in items if item.get("changed")),
        "created_pages": sum(1 for item in items if item.get("action") == "created"),
        "created_versions": sum(1 for item in items if item.get("action") in {"created", "version_created"}),
        "repaired_pages": sum(1 for item in items if item.get("action") == "repaired_current"),
        "upgraded": sum(1 for item in items if item.get("action") == "upgraded"),
        "conflicts": sum(1 for item in items if item.get("action") in {"conflict", "version_conflict"}),
        "skipped": sum(1 for item in items if item.get("action") == "skipped"),
        "failed": sum(1 for item in items if not item.get("ok", False)),
    }


def _has_published_versions(db: Session, slug: str) -> bool:
    version_id = db.scalar(select(ContentPageVersion.id).where(ContentPageVersion.slug == slug).limit(1))
    return version_id is not None


def _schema_hash(payload: dict) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None
