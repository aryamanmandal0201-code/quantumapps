from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import Priority, Role, Status

__all__ = ["Priority", "Role", "Status"]  # re-exported for routers


# ---------- auth ----------
class SignupIn(BaseModel):
    # Note: there is deliberately no "role" field. Extra fields sent by a client are ignored,
    # so nobody can sign up as an admin.
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name can't be empty.")
        return v.strip()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    role: Role
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- tasks ----------
class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    priority: Priority = "medium"


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    priority: Priority | None = None
    status: Status | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    due_date: date | None
    priority: Priority
    status: Status
    assigned_by: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminTaskOut(TaskOut):
    owner_id: int
    owner_name: str
    owner_email: str


class AdminUserOut(UserOut):
    open_tasks: int
    done_tasks: int


class RoleUpdate(BaseModel):
    role: Role


# ---------- chat ----------
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message can't be empty.")
        return v.strip()


class ToolCallOut(BaseModel):
    name: str
    arguments: dict
    ok: bool
    summary: str


class PendingAction(BaseModel):
    type: Literal["delete_task"]
    task_id: int
    title: str


class ChatOut(BaseModel):
    reply: str
    tool_calls: list[ToolCallOut]
    pending_actions: list[PendingAction]
    tasks_changed: bool


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: Literal["user", "assistant"]
    content: str
    tool_calls: list[ToolCallOut] | None = None
    created_at: datetime
