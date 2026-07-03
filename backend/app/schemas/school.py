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


class ClassJoinRequest(BaseModel):
    role: str = "student"


class MembershipRead(BaseModel):
    id: int
    role: str
    status: str

