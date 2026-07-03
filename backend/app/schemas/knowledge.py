from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

KnowledgeSnapshotGranularity = Literal["day", "week", "custom"]


class KnowledgeStatRead(BaseModel):
    rule_code: str
    user_id: int | None = None
    class_id: int | None = None
    course_id: int | None = None
    unit_id: int | None = None
    frequency: int
    sample_size: int
    percent: float
    evidence: dict[str, Any] = Field(default_factory=dict)


class UserKnowledgeRead(BaseModel):
    user_id: int
    class_id: int | None = None
    course_id: int | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    assignment_count: int
    submitted_assignments: int
    graded_assignments: int
    total_events: int
    visit_events: int
    start_events: int
    submit_events: int
    complete_events: int
    score_total: int
    max_score_total: int
    accuracy_percent: float
    completion_percent: float
    total_points: int
    knowledge_stats: list[KnowledgeStatRead]


class ClassKnowledgeRead(BaseModel):
    class_id: int
    school_id: int
    course_id: int | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    students_total: int
    students_active: int
    assignment_count: int
    expected_submissions: int
    submitted_assignments: int
    graded_assignments: int
    total_events: int
    complete_events: int
    score_total: int
    max_score_total: int
    average_score_percent: float
    completion_percent: float
    total_points: int
    average_points_per_student: float
    knowledge_stats: list[KnowledgeStatRead]


class ClassKnowledgeSnapshotRead(BaseModel):
    id: int
    school_id: int
    class_id: int
    course_id: int | None = None
    granularity: KnowledgeSnapshotGranularity
    period_start: datetime
    period_end: datetime
    rule_version: str
    created_by_user_id: int
    calculated_at: datetime
    created_at: datetime
    updated_at: datetime
    students_total: int
    students_active: int
    assignment_count: int
    expected_submissions: int
    submitted_assignments: int
    graded_assignments: int
    total_events: int
    complete_events: int
    score_total: int
    max_score_total: int
    average_score_percent: float
    completion_percent: float
    total_points: int
    average_points_per_student: float
    knowledge_stats: list[KnowledgeStatRead]


class ClassKnowledgeSnapshotPage(BaseModel):
    items: list[ClassKnowledgeSnapshotRead]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None
