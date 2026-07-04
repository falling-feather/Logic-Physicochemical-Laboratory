from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import ClassMembership, LearningEvent, PointLedger, Submission, User
from app.schemas.course import ProgressSummary
from app.services.access_control import get_class, require_class_member, require_school_role


router = APIRouter()


@router.get("/me", response_model=ProgressSummary)
def get_my_progress(
    class_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProgressSummary:
    if class_id is not None:
        require_class_member(db, current_user, class_id)
    return _build_progress_summary(db, current_user.id, class_id)


@router.get("/users/{user_id}", response_model=ProgressSummary)
def get_user_progress(
    user_id: int,
    class_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProgressSummary:
    class_group = get_class(db, class_id)
    require_school_role(db, current_user, class_group.school_id, {"admin", "teacher"})
    target_membership = db.scalar(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.user_id == user_id,
            ClassMembership.status == "active",
        )
    )
    if target_membership is None:
        raise HTTPException(status_code=403, detail="User is outside requested class scope")
    return _build_progress_summary(db, user_id, class_id)


def _build_progress_summary(db: Session, user_id: int, class_id: int | None) -> ProgressSummary:
    submissions = select(Submission).where(Submission.student_id == user_id)
    graded_submissions = select(Submission).where(
        Submission.student_id == user_id,
        Submission.status == "graded",
    )
    events = select(LearningEvent).where(LearningEvent.user_id == user_id)
    completed_events = select(LearningEvent).where(
        LearningEvent.user_id == user_id,
        LearningEvent.event_type == "complete",
    )
    points = select(func.coalesce(func.sum(PointLedger.delta), 0)).where(PointLedger.user_id == user_id)

    if class_id is not None:
        submissions = submissions.where(Submission.class_id == class_id)
        graded_submissions = graded_submissions.where(Submission.class_id == class_id)
        events = events.where(LearningEvent.class_id == class_id)
        completed_events = completed_events.where(LearningEvent.class_id == class_id)
        points = points.where(PointLedger.class_id == class_id)

    submitted_count = _count(db, submissions)
    graded_count = _count(db, graded_submissions)
    event_count = _count(db, events)
    completed_count = _count(db, completed_events)
    completion_percent = round((completed_count / event_count) * 100, 2) if event_count else 0.0
    return ProgressSummary(
        user_id=user_id,
        submitted_assignments=submitted_count,
        graded_assignments=graded_count,
        learning_events=event_count,
        completed_events=completed_count,
        total_points=int(db.scalar(points) or 0),
        completion_percent=completion_percent,
    )


def _count(db: Session, statement) -> int:
    return int(db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
