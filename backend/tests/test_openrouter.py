from typing import Any

import httpx
import pytest

from app import openrouter


def test_build_chat_payload_uses_model_and_prompt() -> None:
    payload = openrouter.build_chat_payload("2+2")

    assert payload == {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": "2+2"}],
    }


def test_build_chat_payload_allows_custom_model() -> None:
    payload = openrouter.build_chat_payload("hello", model="test/model")

    assert payload["model"] == "test/model"


class _FakeResponse:
    def __init__(self, status_code: int, payload: Any = None, *, json_error: bool = False) -> None:
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self) -> Any:
        if self._json_error:
            raise ValueError("bad json")
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse | Exception) -> None:
        self._response = response

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_extract_message_text_accepts_string_content() -> None:
    result = openrouter._extract_message_text(
        {"choices": [{"message": {"content": "Hello"}}]}
    )
    assert result == "Hello"


def test_extract_message_text_accepts_list_content() -> None:
    result = openrouter._extract_message_text(
        {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "Part one"},
                            {"type": "text", "text": "Part two"},
                        ]
                    }
                }
            ]
        }
    )
    assert result == "Part one\nPart two"


@pytest.mark.parametrize(
    "payload, expected_detail",
    [
        ({}, "OpenRouter response did not include choices"),
        ({"choices": ["bad"]}, "OpenRouter response choice was malformed"),
        ({"choices": [{}]}, "OpenRouter response message was malformed"),
        ({"choices": [{"message": {"content": []}}]}, "OpenRouter response did not include message content"),
    ],
)
def test_extract_message_text_rejects_malformed_shapes(payload: dict[str, Any], expected_detail: str) -> None:
    with pytest.raises(openrouter.OpenRouterError) as exc:
        openrouter._extract_message_text(payload)
    assert exc.value.status_code == 502
    assert exc.value.detail == expected_detail


def test_chat_completion_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(openrouter.OpenRouterError) as exc:
        openrouter.chat_completion("hello")
    assert exc.value.status_code == 503


def test_chat_completion_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "token")
    timeout_exc = httpx.TimeoutException("slow")
    monkeypatch.setattr(openrouter.httpx, "Client", lambda timeout: _FakeClient(timeout_exc))

    with pytest.raises(openrouter.OpenRouterError) as exc:
        openrouter.chat_completion("hello")
    assert exc.value.status_code == 504
    assert exc.value.detail == "OpenRouter request timed out"


def test_chat_completion_handles_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "token")
    req = httpx.Request("POST", openrouter.OPENROUTER_URL)
    request_exc = httpx.RequestError("network", request=req)
    monkeypatch.setattr(openrouter.httpx, "Client", lambda timeout: _FakeClient(request_exc))

    with pytest.raises(openrouter.OpenRouterError) as exc:
        openrouter.chat_completion("hello")
    assert exc.value.status_code == 502
    assert exc.value.detail == "Unable to reach OpenRouter"


def test_chat_completion_surfaces_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "token")
    response = _FakeResponse(429, {"error": {"message": "rate limited"}})
    monkeypatch.setattr(openrouter.httpx, "Client", lambda timeout: _FakeClient(response))

    with pytest.raises(openrouter.OpenRouterError) as exc:
        openrouter.chat_completion("hello")
    assert exc.value.status_code == 502
    assert "OpenRouter error 429: rate limited" == exc.value.detail


def test_chat_completion_uses_generic_error_when_error_payload_is_not_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "token")
    response = _FakeResponse(500, json_error=True)
    monkeypatch.setattr(openrouter.httpx, "Client", lambda timeout: _FakeClient(response))

    with pytest.raises(openrouter.OpenRouterError) as exc:
        openrouter.chat_completion("hello")
    assert exc.value.detail == "OpenRouter error 500: OpenRouter returned an error"


def test_chat_completion_rejects_invalid_json_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "token")
    response = _FakeResponse(200, json_error=True)
    monkeypatch.setattr(openrouter.httpx, "Client", lambda timeout: _FakeClient(response))

    with pytest.raises(openrouter.OpenRouterError) as exc:
        openrouter.chat_completion("hello")
    assert exc.value.detail == "OpenRouter returned invalid JSON"


def test_chat_completion_rejects_non_dict_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "token")
    response = _FakeResponse(200, payload=[{"choices": []}])
    monkeypatch.setattr(openrouter.httpx, "Client", lambda timeout: _FakeClient(response))

    with pytest.raises(openrouter.OpenRouterError) as exc:
        openrouter.chat_completion("hello")
    assert exc.value.detail == "OpenRouter response body was malformed"


def test_chat_completion_returns_model_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "token")
    response = _FakeResponse(
        200,
        payload={
            "model": "openai/gpt-oss-120b",
            "choices": [{"message": {"content": "4"}}],
        },
    )
    monkeypatch.setattr(openrouter.httpx, "Client", lambda timeout: _FakeClient(response))

    result = openrouter.chat_completion("2+2")
    assert result == {"model": "openai/gpt-oss-120b", "response": "4"}