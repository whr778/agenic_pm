"""AI routes: connectivity test and chat with board context."""
import json

from fastapi import APIRouter, HTTPException, Request

from app import db, ai_schema, openrouter
from app.deps import require_user, require_user_id, parse_numeric_id
from app.schemas import ConnectivityPayload, AIChatPayload

router = APIRouter(prefix="/api", tags=["ai"])


def _extract_json_object(content: str) -> dict:
    raw = content.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("AI response did not contain a JSON object")

    return json.loads(raw[start : end + 1])


def _build_structured_prompt(
    message: str,
    board: dict[str, object],
    history: list[dict[str, str]],
) -> str:
    schema_description = {
        "assistantMessage": "string (required, non-empty)",
        "updates": [
            {"type": "rename_board", "boardName": "string"},
            {"type": "rename_column", "columnId": "numeric string", "title": "string"},
            {
                "type": "create_card",
                "columnId": "numeric string",
                "title": "string",
                "details": "string",
                "due_date": "YYYY-MM-DD string or null",
                "priority": "low|medium|high|critical or null",
                "labels": ["string array"],
            },
            {
                "type": "update_card",
                "cardId": "numeric string",
                "title": "string",
                "details": "string",
                "due_date": "YYYY-MM-DD string or null",
                "priority": "low|medium|high|critical or null",
                "labels": ["string array"],
            },
            {"type": "delete_card", "cardId": "numeric string"},
            {
                "type": "move_card",
                "cardId": "numeric string",
                "toColumnId": "numeric string",
                "toIndex": "integer >= 0",
            },
        ],
    }
    payload = {
        "task": "Respond to the user's message. Optionally propose board updates.",
        "rules": [
            "Return JSON only, no markdown.",
            "Use only the schema provided.",
            "Use numeric string IDs from the board snapshot.",
            "Only include updates when necessary.",
            "due_date must be YYYY-MM-DD format or null.",
            "priority must be one of: low, medium, high, critical, or null.",
            "labels must be an array of strings (can be empty).",
        ],
        "schema": schema_description,
        "board": board,
        "conversationHistory": history,
        "userMessage": message,
    }
    return json.dumps(payload, separators=(",", ":"))


@router.post("/ai/connectivity")
def ai_connectivity(request: Request, payload: ConnectivityPayload) -> dict[str, str]:
    require_user(request)
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt cannot be empty")

    try:
        result = openrouter.chat_completion(prompt)
    except openrouter.OpenRouterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return {
        "status": "ok",
        "model": result["model"],
        "response": result["response"],
    }


@router.get("/chat/{board_id}")
def get_chat(request: Request, board_id: str) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    try:
        return {"messages": db.list_chat_messages(user_id, parsed_board_id, limit=200)}
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/ai/chat")
def ai_chat(request: Request, payload: AIChatPayload) -> dict[str, object]:
    user_id = require_user_id(request)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message cannot be empty")
    board_id = parse_numeric_id(payload.boardId, "boardId")

    db.add_chat_message(user_id, board_id, "user", message)

    board_before = db.get_board_payload(user_id, board_id)
    history = db.list_chat_messages(user_id, board_id, limit=50)
    prompt = _build_structured_prompt(message, board_before, history)

    try:
        llm = openrouter.chat_completion(prompt)
    except openrouter.OpenRouterError as exc:
        fallback = "I could not reach the AI provider right now. Please try again shortly."
        db.add_chat_message(user_id, board_id, "assistant", fallback)
        return {
            "assistantMessage": fallback,
            "appliedUpdates": False,
            "updateCount": 0,
            "updatesError": exc.detail,
            "board": db.get_board_payload(user_id, board_id),
        }

    try:
        parsed_raw = _extract_json_object(llm["response"])
        parsed = ai_schema.parse_ai_response(parsed_raw)
    except (ValueError, json.JSONDecodeError) as exc:
        fallback = "I could not format a structured response. Please try again."
        db.add_chat_message(user_id, board_id, "assistant", fallback)
        return {
            "assistantMessage": fallback,
            "appliedUpdates": False,
            "updateCount": 0,
            "updatesError": f"AI returned non-JSON content: {exc}",
            "board": db.get_board_payload(user_id, board_id),
        }
    except ai_schema.ValidationError as exc:
        detail = ai_schema.format_validation_error(exc)
        fallback = "I could not validate the structured response. Please try again."
        db.add_chat_message(user_id, board_id, "assistant", fallback)
        return {
            "assistantMessage": fallback,
            "appliedUpdates": False,
            "updateCount": 0,
            "updatesError": f"AI response failed schema validation: {detail}",
            "board": db.get_board_payload(user_id, board_id),
        }

    updates_payload = [operation.model_dump() for operation in parsed.updates]
    applied_updates = False
    updates_error: str | None = None

    if updates_payload:
        try:
            db.apply_updates_atomically(user_id, board_id, updates_payload)
            applied_updates = True
        except (db.ValidationError, db.NotFoundError, ValueError) as exc:
            updates_error = str(exc)

    db.add_chat_message(user_id, board_id, "assistant", parsed.assistantMessage)

    return {
        "assistantMessage": parsed.assistantMessage,
        "appliedUpdates": applied_updates,
        "updateCount": len(updates_payload) if applied_updates else 0,
        "updatesError": updates_error,
        "board": db.get_board_payload(user_id, board_id),
    }
