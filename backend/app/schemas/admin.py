from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AdminUserRole = Literal["admin", "teacher", "student"]
AdminUserStatus = Literal["active", "disabled"]
BugSeverity = Literal["P0", "P1", "P2", "P3"]
BugStatus = Literal["open", "triaged", "in_progress", "closed"]


class AdminBootstrapRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    bootstrap_token: str | None = Field(default=None, max_length=240)


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class AdminUserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: AdminUserRole | None = None
    status: AdminUserStatus | None = None


class AdminContentPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    galaxy: str
    subject: str
    layout: str
    status: str
    version: str
    updated_at: datetime


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    users_by_role: dict[str, int]
    total_schools: int
    total_classes: int
    total_content_pages: int
    total_courses: int
    total_assignments: int
    total_learning_events: int
    total_submissions: int
    total_point_ledger_entries: int
    total_bug_records: int
    open_bug_records: int
    total_audit_logs: int


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None = None
    actor_role: str | None = None
    action: str
    resource: str
    resource_type: str
    resource_id: str | None = None
    school_id: int | None = None
    class_id: int | None = None
    snapshot_json: dict
    created_at: datetime


class BugRecordCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    category: str = Field(default="general", min_length=1, max_length=80)
    severity: BugSeverity = "P2"
    status: BugStatus = "open"
    source: str | None = Field(default=None, max_length=240)
    evidence: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)


class BugRecordUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    severity: BugSeverity | None = None
    status: BugStatus | None = None
    source: str | None = Field(default=None, max_length=240)
    evidence: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)


class BugRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    severity: str
    status: str
    source: str | None = None
    evidence: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
