"""Pydantic request/response models shared across routers."""
from typing import Literal

from pydantic import BaseModel, Field

PRIORITY_VALUES = Literal["low", "medium", "high", "critical"]


class LoginPayload(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)


class UpdateBoardPayload(BaseModel):
    name: str = Field(max_length=256)


class RenameColumnPayload(BaseModel):
    title: str = Field(max_length=256)


class CreateCardPayload(BaseModel):
    columnId: str = Field(max_length=20)
    title: str = Field(max_length=512)
    details: str = Field(default="", max_length=10000)
    due_date: str | None = Field(default=None, max_length=10)  # YYYY-MM-DD
    priority: PRIORITY_VALUES | None = None
    labels: list[str] = Field(default_factory=list)


class UpdateCardPayload(BaseModel):
    title: str = Field(max_length=512)
    details: str = Field(default="", max_length=10000)
    due_date: str | None = Field(default=None, max_length=10)  # YYYY-MM-DD or None to clear
    priority: PRIORITY_VALUES | None = None
    labels: list[str] = Field(default_factory=list)


class MoveCardPayload(BaseModel):
    toColumnId: str = Field(max_length=20)
    toIndex: int


class ConnectivityPayload(BaseModel):
    prompt: str = Field(default="2+2", max_length=1000)


class CreateBoardPayload(BaseModel):
    name: str = Field(max_length=256)


class AIChatPayload(BaseModel):
    message: str = Field(max_length=4000)
    boardId: str = Field(max_length=20)


class CreateUserPayload(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)
    role: Literal["user", "admin"] = "user"


class UpdateUserPayload(BaseModel):
    username: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, max_length=256)
    role: Literal["user", "admin"] | None = None
    suspended: bool | None = None


class RegisterPayload(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)
