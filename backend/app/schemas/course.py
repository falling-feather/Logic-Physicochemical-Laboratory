from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


CourseStatus = Literal["draft", "published", "archived"]
UnitStatus = Literal["draft", "published", "archived"]
AssignmentStatus = Literal["active", "closed", "archived"]
LearningEventType = Literal["visit", "start", "submit", "complete"]


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
