import os
from typing import Any

import httpx


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"


class OpenRouterError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def build_chat_payload(prompt: str, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }


def _extract_message_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterError(502, "OpenRouter response did not include choices")

    first = choices[0]
    if not isinstance(first, dict):
        raise OpenRouterError(502, "OpenRouter response choice was malformed")

    message = first.get("message")
    if not isinstance(message, dict):
        raise OpenRouterError(502, "OpenRouter response message was malformed")

    content = message.get("content")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text")
                if isinstance(value, str):
                    text_parts.append(value)
        if text_parts:
            return "\n".join(text_parts)

    raise OpenRouterError(502, "OpenRouter response did not include message content")


def chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterError(503, "OPENROUTER_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = build_chat_payload(prompt)

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(OPENROUTER_URL, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise OpenRouterError(504, "OpenRouter request timed out") from exc
    except httpx.RequestError as exc:
        raise OpenRouterError(502, "Unable to reach OpenRouter") from exc

    if response.status_code >= 400:
        detail = "OpenRouter returned an error"
        try:
            error_payload = response.json()
            if isinstance(error_payload, dict):
                error = error_payload.get("error")
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    detail = str(error["message"])
        except ValueError:
            pass
        raise OpenRouterError(502, f"OpenRouter error {response.status_code}: {detail}")

    try:
        data = response.json()
    except ValueError as exc:
        raise OpenRouterError(502, "OpenRouter returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise OpenRouterError(502, "OpenRouter response body was malformed")

    return {
        "model": str(data.get("model") or DEFAULT_MODEL),
        "response": _extract_message_text(data),
    }