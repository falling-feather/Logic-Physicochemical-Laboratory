from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import ContentDraft, User
from app.models.base import utc_now
from app.schemas.content import ContentDraftCreate, ContentDraftRead, ContentDraftScriptReview, ContentPage
from app.services.audit import record_audit_log
from app.services.content_catalog import get_page_schema, list_page_summaries


router = APIRouter()
SCRIPT_REVIEW_NOT_REQUIRED = "not_required"
SCRIPT_REVIEW_PENDING = "pending"


@router.post("/drafts", response_model=ContentDraftRead, status_code=status.HTTP_201_CREATED)
def create_content_draft(
    payload: ContentDraftCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContentDraftRead:
    _require_content_author(current_user)
    target_slug = payload.target_slug.strip()
    _validate_content_slug(target_slug)
    page_schema = payload.page_schema
    if target_slug != page_schema.slug.strip():
        raise HTTPException(status_code=422, detail="target_slug must match schema.slug")
    existing = db.scalar(
        select(ContentDraft).where(
            ContentDraft.author_user_id == current_user.id,
            ContentDraft.target_slug == target_slug,
            ContentDraft.status == "draft",
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Active content draft already exists for this target")

    draft = ContentDraft(
        author_user_id=current_user.id,
        target_slug=target_slug,
        title=page_schema.title.strip(),
        status="draft",
        schema_json=page_schema.model_dump(mode="json"),
        allow_script=payload.allow_script,
        script_review_status=SCRIPT_REVIEW_PENDING if payload.allow_script else SCRIPT_REVIEW_NOT_REQUIRED,
    )
    db.add(draft)
    db.flush()
    record_audit_log(
        db,
        actor=current_user,
        action="content.draft.create",
        resource_type="content_draft",
        resource_id=draft.id,
        event_result="success",
        request=request,
        snapshot={"after": _content_draft_snapshot(draft)},
    )
    db.commit()
    db.refresh(draft)
    return _content_draft_read(draft)


@router.get("/drafts/{draft_id}", response_model=ContentDraftRead)
def read_content_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContentDraftRead:
    draft = db.get(ContentDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Content draft not found")
    if current_user.role != "admin" and draft.author_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Content draft is outside your scope")
    return _content_draft_read(draft)


@router.patch("/drafts/{draft_id}/script-review", response_model=ContentDraftRead)
def review_content_draft_script(
    draft_id: int,
    payload: ContentDraftScriptReview,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContentDraftRead:
    _require_admin(current_user)
    draft = db.get(ContentDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Content draft not found")
    if not draft.allow_script:
        raise HTTPException(status_code=409, detail="Content draft does not allow scripts")
    if draft.author_user_id == current_user.id:
        raise HTTPException(status_code=403, detail="Content draft authors cannot review their own scripts")

    before = _content_draft_snapshot(draft)
    draft.script_review_status = payload.status
    draft.script_reviewed_by_user_id = current_user.id
    draft.script_reviewed_at = utc_now()
    draft.script_review_note = _strip_optional(payload.note)
    after = _content_draft_snapshot(draft)
    record_audit_log(
        db,
        actor=current_user,
        action=f"content.draft.script_review.{payload.status}",
        resource_type="content_draft",
        resource_id=draft.id,
        event_result="success",
        request=request,
        snapshot=_change_snapshot(before, after),
    )
    db.commit()
    db.refresh(draft)
    return _content_draft_read(draft)


@router.get("/pages", response_model=list[dict])
def list_content_pages(db: Session = Depends(get_db)) -> list[dict]:
    return list_page_summaries(db)


@router.get("/pages/{slug:path}", response_model=ContentPage)
def read_content_page(slug: str, db: Session = Depends(get_db)) -> ContentPage:
    page = get_page_schema(db, slug)
    if page is None:
        raise HTTPException(status_code=404, detail="Content page not found")
    return page


def _require_content_author(user: User) -> None:
    if user.role not in {"admin", "teacher"}:
        raise HTTPException(status_code=403, detail="Teacher or admin role required")


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")


def _validate_content_slug(slug: str) -> None:
    if (
        not slug
        or slug.startswith("/")
        or slug.endswith("/")
        or "\\" in slug
        or "//" in slug
        or any(part in {"", ".", ".."} for part in slug.split("/"))
    ):
        raise HTTPException(status_code=422, detail="Invalid content slug")


def _content_draft_read(draft: ContentDraft) -> ContentDraftRead:
    return ContentDraftRead(
        id=draft.id,
        author_user_id=draft.author_user_id,
        target_slug=draft.target_slug,
        title=draft.title,
        status=draft.status,
        allow_script=draft.allow_script,
        script_review_status=draft.script_review_status,
        script_reviewed_by_user_id=draft.script_reviewed_by_user_id,
        script_reviewed_at=draft.script_reviewed_at,
        script_review_note=draft.script_review_note,
        page_schema=ContentPage.model_validate(draft.schema_json),
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _content_draft_snapshot(draft: ContentDraft) -> dict:
    return {
        "author_user_id": draft.author_user_id,
        "target_slug": draft.target_slug,
        "title": draft.title,
        "status": draft.status,
        "allow_script": draft.allow_script,
        "script_review_status": draft.script_review_status,
        "script_reviewed_by_user_id": draft.script_reviewed_by_user_id,
        "script_review_note": draft.script_review_note,
    }


def _change_snapshot(before: dict, after: dict) -> dict:
    changes = {
        key: {"from": before.get(key), "to": after.get(key)}
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    }
    return {"before": before, "after": after, "changes": changes}


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None
