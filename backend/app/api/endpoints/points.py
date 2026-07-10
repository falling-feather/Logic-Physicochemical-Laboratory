from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import get_current_user
from app.db.session import get_db
from app.models import Assignment, Course, CourseUnit, PointLedger, User
from app.schemas.course import AssignmentPointRuleRead, AssignmentPointRuleUpdate, PointLedgerRead
from app.services.audit import record_audit_log
from app.services.access_control import (
    get_class,
    require_course_collaborator_or_admin,
    require_school_role,
    require_class_teacher_or_admin,
    teacher_class_ids,
)
from app.services.points import DEFAULT_ASSIGNMENT_POINT_RULE, normalize_assignment_point_rule


router = APIRouter()


def _assignment_point_rule_read(assignment: Assignment) -> AssignmentPointRuleRead:
    rule = normalize_assignment_point_rule(assignment.point_rule_json)
    return AssignmentPointRuleRead(
        assignment_id=assignment.id,
        enabled=rule["enabled"],
        points_per_score=rule["points_per_score"],
        max_points=rule["max_points"],
        source="custom" if assignment.point_rule_json is not None else "default",
    )


@router.get("/assignments/{assignment_id}/rule", response_model=AssignmentPointRuleRead)
def read_assignment_point_rule(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssignmentPointRuleRead:
    assignment, _, course = _resolve_assignment(db, assignment_id)
    require_school_role(
        db,
        current_user,
        course.school_id,
        {"admin", "teacher"},
        detail="Assignment point rule requires school teacher scope",
    )
    return _assignment_point_rule_read(assignment)


@router.patch("/assignments/{assignment_id}/rule", response_model=AssignmentPointRuleRead)
def update_assignment_point_rule(
    assignment_id: int,
    payload: AssignmentPointRuleUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssignmentPointRuleRead:
    assignment, _, course = _resolve_assignment(db, assignment_id)
    require_school_role(db, current_user, course.school_id, {"admin", "teacher"})
    require_course_collaborator_or_admin(
        db,
        current_user,
        course,
        {"editor", "assessment_editor"},
        detail="Assignment point rule requires editor or assessment_editor role",
    )
    previous = _assignment_point_rule_read(assignment)
    next_rule = payload.model_dump()
    if next_rule == DEFAULT_ASSIGNMENT_POINT_RULE:
        next_rule_json = None
    else:
        next_rule_json = next_rule
    if assignment.point_rule_json == next_rule_json:
        return previous

    assignment.point_rule_json = next_rule_json
    current = _assignment_point_rule_read(assignment)
    record_audit_log(
        db,
        actor=current_user,
        action="assignment.point_rule.update",
        resource_type="assignment",
        resource_id=assignment.id,
        school_id=course.school_id,
        event_result="success",
        request=request,
        snapshot={
            "before": previous.model_dump(),
            "after": current.model_dump(),
        },
    )
    db.commit()
    db.refresh(assignment)
    return _assignment_point_rule_read(assignment)


def _resolve_assignment(db: Session, assignment_id: int) -> tuple[Assignment, CourseUnit, Course]:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    unit = db.get(CourseUnit, assignment.unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Course unit not found")
    course = db.get(Course, unit.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return assignment, unit, course


@router.get("/ledger", response_model=list[PointLedgerRead])
def list_point_ledger(
    user_id: int | None = Query(default=None),
    class_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PointLedger]:
    statement = select(PointLedger).order_by(PointLedger.id)
    if current_user.role == "student":
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Students can only view their own points")
        statement = statement.where(PointLedger.user_id == current_user.id)
        if class_id is not None:
            statement = statement.where(PointLedger.class_id == class_id)
        return list(db.scalars(statement).all())

    if class_id is not None:
        class_group = get_class(db, class_id)
        require_class_teacher_or_admin(
            db,
            current_user,
            class_group,
            detail="Point ledger requires class teacher scope",
        )
        statement = statement.where(PointLedger.class_id == class_id)
    elif current_user.role != "admin":
        class_ids = teacher_class_ids(db, current_user.id)
        if not class_ids:
            return []
        statement = statement.where(PointLedger.class_id.in_(class_ids))

    if user_id is not None:
        statement = statement.where(PointLedger.user_id == user_id)
    return list(db.scalars(statement).all())
