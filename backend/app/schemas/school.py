from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SchoolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    region: str | None = Field(default=None, max_length=160)


class SchoolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    region: str | None = None
    status: str


class ClassCreate(BaseModel):
    school_id: int
    name: str = Field(min_length=1, max_length=160)
    grade: str | None = Field(default=None, max_length=64)
    term: str | None = Field(default=None, max_length=64)


class ClassRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    name: str
    grade: str | None = None
    term: str | None = None
    status: str


class ClassJoinPayload(BaseModel):
    role: str = "student"


class ClassJoinRequestCreate(BaseModel):
    role: str = "student"
    message: str | None = Field(default=None, max_length=500)


class ClassJoinRequestReview(BaseModel):
    status: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=500)


class ClassMemberStatusUpdate(BaseModel):
    status: Literal["active", "inactive"]
    note: str | None = Field(default=None, max_length=500)


class ClassJoinRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    class_id: int
    user_id: int
    role: str
    status: str
    message: str | None = None
    requested_by_user_id: int
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    status: str


class ClassMemberRead(BaseModel):
    id: int
    class_id: int
    user_id: int
    username: str
    display_name: str
    user_status: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime
