from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    status: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    role: str = "student"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    user: UserPublic
    access_token: str = Field(
        description=(
            "Compatibility credential for explicit non-browser API clients. "
            "Browser clients must ignore it and must never store or resend it."
        )
    )
    token_type: str = Field(default="bearer", description="Compatibility credential scheme.")


class PasswordResetRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)


class PasswordResetRequestResponse(BaseModel):
    status: str = "ok"
    expires_in_seconds: int
    reset_token: str | None = None


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class PasswordResetConfirmResponse(BaseModel):
    status: str = "ok"
    revoked_sessions: int
    cleared_login_attempt: bool


class AuthSessionPublic(BaseModel):
    id: int
    device_label: str | None = None
    user_agent: str | None = None
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None
    is_current: bool


class AuthSessionRevokeResponse(BaseModel):
    status: str = "ok"
    revoked_session_id: int
    is_current: bool
