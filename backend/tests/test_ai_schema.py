import pytest
from pydantic import ValidationError

from app.ai_schema import format_validation_error, parse_ai_response


def test_parse_ai_response_message_only() -> None:
    parsed = parse_ai_response({"assistantMessage": "All good", "updates": []})
    assert parsed.assistantMessage == "All good"
    assert parsed.updates == []


def test_parse_ai_response_with_move_update() -> None:
    parsed = parse_ai_response(
        {
            "assistantMessage": "Moved card",
            "updates": [
                {
                    "type": "move_card",
                    "cardId": "1",
                    "toColumnId": "2",
                    "toIndex": 0,
                }
            ],
        }
    )
    assert len(parsed.updates) == 1


def test_parse_ai_response_rejects_invalid_shape() -> None:
    with pytest.raises(ValidationError):
        parse_ai_response({"assistantMessage": "", "updates": [{"type": "delete_card"}]})


@pytest.mark.parametrize(
    "update",
    [
        {"type": "rename_board", "boardName": "Sprint Board"},
        {"type": "rename_column", "columnId": "1", "title": "Ideas"},
        {"type": "create_card", "columnId": "1", "title": "T", "details": "D"},
        {"type": "update_card", "cardId": "2", "title": "New", "details": ""},
        {"type": "delete_card", "cardId": "3"},
        {"type": "move_card", "cardId": "3", "toColumnId": "4", "toIndex": 0},
    ],
)
def test_parse_ai_response_accepts_all_update_types(update: dict[str, object]) -> None:
    parsed = parse_ai_response({"assistantMessage": "ok", "updates": [update]})
    assert len(parsed.updates) == 1


@pytest.mark.parametrize(
    "update, expected_fragment",
    [
        ({"type": "rename_board", "boardName": "   "}, "boardName must not be empty"),
        ({"type": "rename_column", "columnId": "x", "title": "Ideas"}, "columnId must be a numeric string"),
        ({"type": "rename_column", "columnId": "1", "title": "   "}, "title must not be empty"),
        ({"type": "create_card", "columnId": "x", "title": "Task"}, "columnId must be a numeric string"),
        ({"type": "create_card", "columnId": "1", "title": "   "}, "title must not be empty"),
        ({"type": "update_card", "cardId": "abc", "title": "Task"}, "cardId must be a numeric string"),
        ({"type": "update_card", "cardId": "1", "title": "   "}, "title must not be empty"),
        ({"type": "delete_card", "cardId": "abc"}, "cardId must be a numeric string"),
        ({"type": "move_card", "cardId": "1", "toColumnId": "2", "toIndex": -1}, "toIndex must be zero or greater"),
    ],
)
def test_parse_ai_response_rejects_invalid_update_values(
    update: dict[str, object], expected_fragment: str
) -> None:
    with pytest.raises(ValidationError) as exc:
        parse_ai_response({"assistantMessage": "ok", "updates": [update]})
    assert expected_fragment in format_validation_error(exc.value)


def test_format_validation_error_fallback_when_errors_empty() -> None:
    exc = ValidationError.from_exception_data("AIResponseModel", [])
    assert format_validation_error(exc) == "Invalid AI response"
