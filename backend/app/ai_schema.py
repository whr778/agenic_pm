from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator


class RenameBoardUpdate(BaseModel):
    type: Literal["rename_board"]
    boardName: str

    @model_validator(mode="after")
    def validate_board_name(self) -> "RenameBoardUpdate":
        if not self.boardName.strip():
            raise ValueError("boardName must not be empty")
        return self


class RenameColumnUpdate(BaseModel):
    type: Literal["rename_column"]
    columnId: str
    title: str

    @model_validator(mode="after")
    def validate_fields(self) -> "RenameColumnUpdate":
        if not self.columnId.isdigit():
            raise ValueError("columnId must be a numeric string")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        return self


_VALID_PRIORITIES = {"low", "medium", "high", "critical"}


class CreateCardUpdate(BaseModel):
    type: Literal["create_card"]
    columnId: str
    title: str
    details: str = ""
    due_date: str | None = None
    priority: str | None = None
    labels: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_fields(self) -> "CreateCardUpdate":
        if not self.columnId.isdigit():
            raise ValueError("columnId must be a numeric string")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if self.priority is not None and self.priority not in _VALID_PRIORITIES:
            raise ValueError("priority must be one of: low, medium, high, critical")
        return self


class UpdateCardUpdate(BaseModel):
    type: Literal["update_card"]
    cardId: str
    title: str
    details: str = ""
    due_date: str | None = None
    priority: str | None = None
    labels: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_fields(self) -> "UpdateCardUpdate":
        if not self.cardId.isdigit():
            raise ValueError("cardId must be a numeric string")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if self.priority is not None and self.priority not in _VALID_PRIORITIES:
            raise ValueError("priority must be one of: low, medium, high, critical")
        return self


class DeleteCardUpdate(BaseModel):
    type: Literal["delete_card"]
    cardId: str

    @model_validator(mode="after")
    def validate_card_id(self) -> "DeleteCardUpdate":
        if not self.cardId.isdigit():
            raise ValueError("cardId must be a numeric string")
        return self


class MoveCardUpdate(BaseModel):
    type: Literal["move_card"]
    cardId: str
    toColumnId: str
    toIndex: int

    @model_validator(mode="after")
    def validate_fields(self) -> "MoveCardUpdate":
        if not self.cardId.isdigit():
            raise ValueError("cardId must be a numeric string")
        if not self.toColumnId.isdigit():
            raise ValueError("toColumnId must be a numeric string")
        if self.toIndex < 0:
            raise ValueError("toIndex must be zero or greater")
        return self


UpdateOperation = Annotated[
    RenameBoardUpdate
    | RenameColumnUpdate
    | CreateCardUpdate
    | UpdateCardUpdate
    | DeleteCardUpdate
    | MoveCardUpdate,
    Field(discriminator="type"),
]


class AIResponseModel(BaseModel):
    assistantMessage: str
    updates: list[UpdateOperation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_message(self) -> "AIResponseModel":
        if not self.assistantMessage.strip():
            raise ValueError("assistantMessage must not be empty")
        return self


def parse_ai_response(payload: dict) -> AIResponseModel:
    return AIResponseModel.model_validate(payload)


def format_validation_error(exc: ValidationError) -> str:
    issues: list[str] = []
    for error in exc.errors():
        path = ".".join(str(part) for part in error.get("loc", []))
        message = str(error.get("msg", "Invalid value"))
        issues.append(f"{path}: {message}" if path else message)
    return "; ".join(issues) if issues else "Invalid AI response"