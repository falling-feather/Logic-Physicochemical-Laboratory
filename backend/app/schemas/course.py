from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


CourseStatus = Literal["draft", "published", "archived"]
UnitStatus = Literal["draft", "published", "archived"]
AssignmentStatus = Literal["active", "closed", "archived"]
SubmissionStatus = Literal["submitted", "graded", "returned"]
SubmissionGradeStatus = Literal["graded", "returned"]
LearningEventType = Literal["visit", "start", "submit", "complete"]
AssignmentPointRuleSource = Literal["default", "custom"]
CourseCollaboratorRole = Literal["editor"]
CourseCollaboratorStatus = Literal["active", "inactive"]


class CourseCreate(BaseModel):
    school_id: int
    title: str = Field(min_length=1, max_length=180)
    summary: str | None = Field(default=None, max_length=2000)
    status: CourseStatus = "draft"


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    creator_user_id: int
    title: str
    summary: str | None = None
    status: str


class CourseClassAttach(BaseModel):
    class_id: int


class CourseClassRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    class_id: int
    status: str


class CourseCollaboratorCreate(BaseModel):
    user_id: int
    role: CourseCollaboratorRole = "editor"


class CourseCollaboratorUpdate(BaseModel):
    status: CourseCollaboratorStatus


class CourseCollaboratorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    user_id: int
    role: str
    status: str


class CourseOwnerTransfer(BaseModel):
    target_user_id: int


class CourseUnitCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    position: int = Field(ge=1)
    content_slug: str | None = Field(default=None, max_length=180)
    status: UnitStatus = "published"


class CourseUnitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    position: int
    content_slug: str | None = None
    status: str


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None
    max_score: int = Field(default=100, ge=0, le=1000)
    status: AssignmentStatus = "active"


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: int
    title: str
    description: str | None = None
    due_at: datetime | None = None
    max_score: int
    status: str


class LearningEventCreate(BaseModel):
    event_type: LearningEventType
    class_id: int | None = None
    course_id: int | None = None
    unit_id: int | None = None
    assignment_id: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class LearningEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    school_id: int | None = None
    class_id: int | None = None
    course_id: int | None = None
    unit_id: int | None = None
    assignment_id: int | None = None
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime


class SubmissionCreate(BaseModel):
    class_id: int
    content: dict[str, Any] = Field(default_factory=dict)


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    student_id: int
    class_id: int | None = None
    content: dict[str, Any]
    status: str
    score: int | None = None
    feedback: str | None = None
    graded_by_user_id: int | None = None
    submitted_at: datetime
    graded_at: datetime | None = None


class AssignmentReviewRead(BaseModel):
    course_id: int
    unit_id: int
    assignment: AssignmentRead
    submission: SubmissionRead | None = None
    can_submit: bool
    read_only: bool
    submit_block_reason: str | None = None


class SubmissionGrade(BaseModel):
    score: int = Field(ge=0, le=1000)
    feedback: str | None = Field(default=None, max_length=4000)
    status: SubmissionGradeStatus = "graded"


class PointLedgerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    school_id: int | None = None
    class_id: int | None = None
    assignment_id: int | None = None
    submission_id: int | None = None
    delta: int
    reason: str
    note: str | None = None
    created_by_user_id: int | None = None


class AssignmentPointRuleUpdate(BaseModel):
    enabled: bool = True
    points_per_score: int = Field(default=1, ge=0, le=1000)
    max_points: int | None = Field(default=None, ge=0, le=100000)


class AssignmentPointRuleRead(BaseModel):
    assignment_id: int
    enabled: bool
    points_per_score: int
    max_points: int | None = None
    source: AssignmentPointRuleSource


class ProgressSummary(BaseModel):
    user_id: int
    submitted_assignments: int
    graded_assignments: int
    learning_events: int
    completed_events: int
    total_points: int
    completion_percent: float
