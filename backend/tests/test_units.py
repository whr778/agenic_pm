"""Unit tests for ai_schema and openrouter modules (no FastAPI client needed)."""
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError as PydanticValidationError

from app import ai_schema, openrouter


# ---------------------------------------------------------------------------
# ai_schema validators
# ---------------------------------------------------------------------------


def test_rename_board_valid() -> None:
    u = ai_schema.parse_ai_response({
        "assistantMessage": "OK",
        "updates": [{"type": "rename_board", "boardName": "New Name"}],
    })
    assert u.updates[0].boardName == "New Name"  # type: ignore[union-attr]


def test_rename_board_empty_name_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "rename_board", "boardName": "   "}],
        })


def test_rename_column_non_numeric_id_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "rename_column", "columnId": "col-1", "title": "Ideas"}],
        })


def test_rename_column_empty_title_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "rename_column", "columnId": "1", "title": "   "}],
        })


def test_create_card_non_numeric_column_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "create_card", "columnId": "col-1", "title": "Card"}],
        })


def test_create_card_empty_title_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "create_card", "columnId": "1", "title": "   "}],
        })


def test_create_card_invalid_priority_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "create_card", "columnId": "1", "title": "Card", "priority": "urgent"}],
        })


def test_create_card_valid_priority_accepted() -> None:
    result = ai_schema.parse_ai_response({
        "assistantMessage": "OK",
        "updates": [{"type": "create_card", "columnId": "1", "title": "Card", "priority": "high"}],
    })
    assert len(result.updates) == 1


def test_update_card_non_numeric_id_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "update_card", "cardId": "card-1", "title": "Card"}],
        })


def test_update_card_empty_title_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "update_card", "cardId": "1", "title": "  "}],
        })


def test_update_card_invalid_priority_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "update_card", "cardId": "1", "title": "Card", "priority": "extreme"}],
        })


def test_delete_card_non_numeric_id_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "delete_card", "cardId": "card-1"}],
        })


def test_move_card_non_numeric_card_id_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "move_card", "cardId": "card-1", "toColumnId": "1", "toIndex": 0}],
        })


def test_move_card_non_numeric_column_id_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "move_card", "cardId": "1", "toColumnId": "col-1", "toIndex": 0}],
        })


def test_move_card_negative_index_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "move_card", "cardId": "1", "toColumnId": "1", "toIndex": -1}],
        })


def test_format_validation_error_returns_string() -> None:
    try:
        ai_schema.parse_ai_response({"assistantMessage": "", "updates": []})
    except PydanticValidationError as exc:
        result = ai_schema.format_validation_error(exc)
        assert isinstance(result, str)
        assert len(result) > 0


def test_format_validation_error_with_path() -> None:
    try:
        ai_schema.parse_ai_response({
            "assistantMessage": "OK",
            "updates": [{"type": "rename_board", "boardName": "  "}],
        })
    except PydanticValidationError as exc:
        result = ai_schema.format_validation_error(exc)
        assert "boardName" in result or "must not be empty" in result


# ---------------------------------------------------------------------------
# openrouter unit tests
# ---------------------------------------------------------------------------


def test_build_chat_payload_structure() -> None:
    payload = openrouter.build_chat_payload("hello")
    assert payload["model"] == openrouter.DEFAULT_MODEL
    assert payload["messages"] == [{"role": "user", "content": "hello"}]


def test_build_chat_payload_custom_model() -> None:
    payload = openrouter.build_chat_payload("hi", model="gpt-4o")
    assert payload["model"] == "gpt-4o"


def test_extract_message_text_string_content() -> None:
    data = {
        "choices": [{"message": {"content": "Hello!"}}]
    }
    assert openrouter._extract_message_text(data) == "Hello!"


def test_extract_message_text_list_content() -> None:
    data = {
        "choices": [{"message": {"content": [{"type": "text", "text": "Part 1"}, {"type": "text", "text": "Part 2"}]}}]
    }
    result = openrouter._extract_message_text(data)
    assert "Part 1" in result
    assert "Part 2" in result


def test_extract_message_text_no_choices_raises() -> None:
    with pytest.raises(openrouter.OpenRouterError) as exc_info:
        openrouter._extract_message_text({"choices": []})
    assert exc_info.value.status_code == 502


def test_extract_message_text_missing_choices_raises() -> None:
    with pytest.raises(openrouter.OpenRouterError):
        openrouter._extract_message_text({})


def test_extract_message_text_malformed_choice_raises() -> None:
    with pytest.raises(openrouter.OpenRouterError):
        openrouter._extract_message_text({"choices": ["not-a-dict"]})


def test_extract_message_text_missing_message_raises() -> None:
    with pytest.raises(openrouter.OpenRouterError):
        openrouter._extract_message_text({"choices": [{"no_message": True}]})


def test_extract_message_text_null_content_raises() -> None:
    with pytest.raises(openrouter.OpenRouterError):
        openrouter._extract_message_text({"choices": [{"message": {"content": None}}]})


def test_chat_completion_no_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(openrouter.OpenRouterError) as exc_info:
        openrouter.chat_completion("test")
    assert exc_info.value.status_code == 503


def test_chat_completion_timeout_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.side_effect = httpx.TimeoutException("timed out")

    with patch("httpx.Client", return_value=mock_client):
        with pytest.raises(openrouter.OpenRouterError) as exc_info:
            openrouter.chat_completion("test")
    assert exc_info.value.status_code == 504


def test_chat_completion_request_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.side_effect = httpx.RequestError("connection refused")

    with patch("httpx.Client", return_value=mock_client):
        with pytest.raises(openrouter.OpenRouterError) as exc_info:
            openrouter.chat_completion("test")
    assert exc_info.value.status_code == 502


def test_chat_completion_http_error_response(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": {"message": "Unauthorized"}}

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client):
        with pytest.raises(openrouter.OpenRouterError) as exc_info:
            openrouter.chat_completion("test")
    assert "Unauthorized" in str(exc_info.value) or exc_info.value.status_code == 502


def test_chat_completion_invalid_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("not json")

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client):
        with pytest.raises(openrouter.OpenRouterError) as exc_info:
            openrouter.chat_completion("test")
    assert exc_info.value.status_code == 502


def test_chat_completion_non_dict_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = ["not", "a", "dict"]

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client):
        with pytest.raises(openrouter.OpenRouterError) as exc_info:
            openrouter.chat_completion("test")
    assert exc_info.value.status_code == 502


def test_chat_completion_success(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "openai/gpt-oss-120b",
        "choices": [{"message": {"content": "The answer is 4"}}],
    }

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client):
        result = openrouter.chat_completion("2+2")

    assert result["response"] == "The answer is 4"
    assert result["model"] == "openai/gpt-oss-120b"


def test_chat_completion_http_error_non_json(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.json.side_effect = ValueError("no json")

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client):
        with pytest.raises(openrouter.OpenRouterError):
            openrouter.chat_completion("test")
