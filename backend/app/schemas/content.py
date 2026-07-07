from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SectionType = Literal[
    "hero",
    "learning-task",
    "experiment",
    "assessment",
    "source-list",
]


class ContentSection(BaseModel):
    sectionId: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
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
    sourceId: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
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

    @model_validator(mode="after")
    def validate_stable_identity_uniqueness(self) -> "ContentPage":
        _reject_duplicate_stable_ids(
            "sectionId",
            [section.sectionId for section in self.sections],
        )
        _reject_duplicate_stable_ids(
            "sourceId",
            [source.sourceId for source in self.sources],
        )
        return self


def _reject_duplicate_stable_ids(field_name: str, values: list[str | None]) -> None:
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        normalized = value.strip().lower()
        if normalized in seen:
            raise ValueError(f"Duplicate content {field_name}: {value}")
        seen.add(normalized)


class ContentDraftCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    target_slug: str = Field(min_length=1, max_length=180)
    page_schema: ContentPage = Field(alias="schema")
    allow_script: bool = False


class ContentDraftUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    page_schema: ContentPage = Field(alias="schema")
    allow_script: bool | None = None
    note: str | None = Field(default=None, max_length=1000)


class ContentDraftScriptReview(BaseModel):
    status: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class ContentDraftSubmit(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ContentDraftWithdraw(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ContentDraftRequestChanges(BaseModel):
    note: str = Field(min_length=1, max_length=1000)


class ContentDraftPublish(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ContentPageRollback(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ScriptAnalysisFindingRead(BaseModel):
    code: str
    severity: str
    path: str
    message: str
    key: str | None = None
    value_type: str | None = None
    value_preview: str | None = None
    value_sha256: str | None = None
    metadata: dict[str, Any] | None = None


class ScriptAnalysisRead(BaseModel):
    policy_version: str
    policy_context_hash: str | None = None
    schema_hash: str | None = None
    status: str
    risk_level: str
    finding_count: int
    sandbox: dict[str, Any] | None = None
    findings: list[ScriptAnalysisFindingRead] = Field(default_factory=list)


class ContentDraftRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    author_user_id: int
    target_slug: str
    title: str
    status: str
    allow_script: bool
    schema_hash: str | None = None
    base_version_id: int | None = None
    base_schema_hash: str | None = None
    script_risk_level: str | None = None
    script_analysis: ScriptAnalysisRead | None = None
    script_review_status: str
    script_reviewed_by_user_id: int | None = None
    script_reviewed_at: datetime | None = None
    script_review_note: str | None = None
    submitted_at: datetime | None = None
    withdrawn_at: datetime | None = None
    change_requested_by_user_id: int | None = None
    change_requested_at: datetime | None = None
    change_request_note: str | None = None
    published_page_id: int | None = None
    published_version_id: int | None = None
    published_by_user_id: int | None = None
    published_at: datetime | None = None
    page_schema: ContentPage = Field(alias="schema")
    created_at: datetime
    updated_at: datetime


class ContentPublicationRead(BaseModel):
    id: int
    slug: str
    title: str
    status: str
    version: str
    schema_hash: str
    version_id: int
    previous_version_id: int | None = None
    source_draft_id: int | None = None
    restored_from_version_id: int | None = None
    updated_at: datetime

