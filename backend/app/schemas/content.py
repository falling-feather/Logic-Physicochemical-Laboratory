from typing import Any, Literal

from pydantic import BaseModel, Field


SectionType = Literal[
    "hero",
    "learning-task",
    "experiment",
    "assessment",
    "source-list",
]


class ContentSection(BaseModel):
    type: SectionType
    title: str | None = None
    summary: str | None = None
    experimentId: str | None = None
    questionSetId: str | None = None
    props: dict[str, Any] = Field(default_factory=dict)


class CourseUnitRef(BaseModel):
    courseId: str
    unitId: str
    order: int
    title: str


class SourceRef(BaseModel):
    label: str
    url: str


class ContentPage(BaseModel):
    slug: str
    galaxy: str
    subject: str
    title: str
    layout: str
    status: Literal["draft", "published", "archived"] = "draft"
    version: str
    summary: str
    sections: list[ContentSection]
    courseUnit: CourseUnitRef | None = None
    sources: list[SourceRef] = Field(default_factory=list)

