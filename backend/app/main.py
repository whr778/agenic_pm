from pathlib import Path
import json
import os
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import db
from app import ai_schema
from app import openrouter


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
SESSION_COOKIE_NAME = "pm_session"


class LoginPayload(BaseModel):
    username: str
    password: str


class UpdateBoardPayload(BaseModel):
    name: str


class RenameColumnPayload(BaseModel):
    title: str


class CreateCardPayload(BaseModel):
    columnId: str
    title: str
    details: str = ""


class UpdateCardPayload(BaseModel):
    title: str
    details: str = ""


class MoveCardPayload(BaseModel):
    toColumnId: str
    toIndex: int


class ConnectivityPayload(BaseModel):
    prompt: str = "2+2"


class CreateBoardPayload(BaseModel):
    name: str


class AIChatPayload(BaseModel):
    message: str
    boardId: str

app = FastAPI(title="PM MVP Backend", version="0.1.0")
db.init_db()


def _require_user(request: Request) -> str:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    username = db.get_session(session_id) if session_id else None
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.get_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user["suspended"]:
        raise HTTPException(status_code=403, detail="Account suspended")
    return username


def _require_user_id(request: Request) -> int:
    username = _require_user(request)
    user = db.get_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return int(user["id"])


def _require_admin(request: Request) -> int:
    username = _require_user(request)
    user = db.get_user_by_username(username)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if str(user["role"]) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return int(user["id"])


def _parse_numeric_id(value: str, label: str) -> int:
    if not value.isdigit():
        raise HTTPException(status_code=400, detail=f"{label} must be a numeric string")
    return int(value)


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
            },
            {
                "type": "update_card",
                "cardId": "numeric string",
                "title": "string",
                "details": "string",
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
        ],
        "schema": schema_description,
        "board": board,
        "conversationHistory": history,
        "userMessage": message,
    }
    return json.dumps(payload, separators=(",", ":"))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello() -> dict[str, object]:
    return {
        "message": "Hello from FastAPI",
        "openrouterConfigured": bool(os.getenv("OPENROUTER_API_KEY")),
    }


@app.post("/api/auth/login")
def login(payload: LoginPayload, response: Response) -> dict[str, object]:
    user = db.get_user_by_username(payload.username)
    if user is None or not db.verify_password(payload.password, str(user["password_hash"])):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user["suspended"]:
        raise HTTPException(status_code=403, detail="Account suspended")

    session_id = str(uuid4())
    db.create_session(session_id, payload.username)
    db.cleanup_expired_sessions()
    is_production = os.getenv("ENVIRONMENT", "development") != "development"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=is_production,
        path="/",
    )
    return {
        "status": "ok",
        "username": payload.username,
        "role": str(user["role"]),
    }


@app.get("/api/auth/session")
def auth_session(request: Request) -> dict[str, object]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    username = db.get_session(session_id) if session_id else None
    if not username:
        return {"authenticated": False}
    user = db.get_user_by_username(username)
    if user is None or user["suspended"]:
        return {"authenticated": False}
    return {"authenticated": True, "username": username, "role": str(user["role"])}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        db.delete_session(session_id)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}


@app.get("/api/boards")
def get_boards(request: Request) -> dict[str, object]:
    user_id = _require_user_id(request)
    return {"boards": db.list_boards(user_id)}


@app.post("/api/boards")
def create_board(request: Request, payload: CreateBoardPayload) -> dict[str, object]:
    user_id = _require_user_id(request)
    try:
        return db.create_board(user_id, payload.name)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/boards/{board_id}")
def delete_board_endpoint(request: Request, board_id: str) -> dict[str, str]:
    user_id = _require_user_id(request)
    parsed_board_id = _parse_numeric_id(board_id, "board_id")
    try:
        db.delete_board(user_id, parsed_board_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


@app.get("/api/board/{board_id}")
def get_board(request: Request, board_id: str) -> dict[str, object]:
    user_id = _require_user_id(request)
    parsed_board_id = _parse_numeric_id(board_id, "board_id")
    try:
        return db.get_board_payload(user_id, parsed_board_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/board/{board_id}")
def update_board(request: Request, board_id: str, payload: UpdateBoardPayload) -> dict[str, str]:
    user_id = _require_user_id(request)
    parsed_board_id = _parse_numeric_id(board_id, "board_id")
    try:
        return db.update_board_name(user_id, parsed_board_id, payload.name)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/api/boards/{board_id}/columns/{column_id}")
def rename_column(
    request: Request,
    board_id: str,
    column_id: str,
    payload: RenameColumnPayload,
) -> dict[str, str]:
    user_id = _require_user_id(request)
    parsed_board_id = _parse_numeric_id(board_id, "board_id")
    parsed_column_id = _parse_numeric_id(column_id, "column_id")
    try:
        return db.rename_column(user_id, parsed_board_id, parsed_column_id, payload.title)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/boards/{board_id}/cards")
def create_card(request: Request, board_id: str, payload: CreateCardPayload) -> dict[str, str]:
    user_id = _require_user_id(request)
    parsed_board_id = _parse_numeric_id(board_id, "board_id")
    parsed_column_id = _parse_numeric_id(payload.columnId, "columnId")
    try:
        return db.create_card(user_id, parsed_board_id, parsed_column_id, payload.title, payload.details)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/boards/{board_id}/cards/{card_id}")
def update_card(
    request: Request,
    board_id: str,
    card_id: str,
    payload: UpdateCardPayload,
) -> dict[str, str]:
    user_id = _require_user_id(request)
    parsed_board_id = _parse_numeric_id(board_id, "board_id")
    parsed_card_id = _parse_numeric_id(card_id, "card_id")
    try:
        return db.update_card(user_id, parsed_board_id, parsed_card_id, payload.title, payload.details)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/boards/{board_id}/cards/{card_id}")
def delete_card(request: Request, board_id: str, card_id: str) -> dict[str, str]:
    user_id = _require_user_id(request)
    parsed_board_id = _parse_numeric_id(board_id, "board_id")
    parsed_card_id = _parse_numeric_id(card_id, "card_id")
    try:
        db.delete_card(user_id, parsed_board_id, parsed_card_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@app.post("/api/boards/{board_id}/cards/{card_id}/move")
def move_card(
    request: Request,
    board_id: str,
    card_id: str,
    payload: MoveCardPayload,
) -> dict[str, str]:
    user_id = _require_user_id(request)
    parsed_board_id = _parse_numeric_id(board_id, "board_id")
    parsed_card_id = _parse_numeric_id(card_id, "card_id")
    parsed_column_id = _parse_numeric_id(payload.toColumnId, "toColumnId")
    try:
        return db.move_card(user_id, parsed_board_id, parsed_card_id, parsed_column_id, payload.toIndex)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/ai/connectivity")
def ai_connectivity(request: Request, payload: ConnectivityPayload) -> dict[str, str]:
    _require_user(request)
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


@app.get("/api/chat/{board_id}")
def get_chat(request: Request, board_id: str) -> dict[str, object]:
    user_id = _require_user_id(request)
    parsed_board_id = _parse_numeric_id(board_id, "board_id")
    try:
        return {"messages": db.list_chat_messages(user_id, parsed_board_id, limit=200)}
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/ai/chat")
def ai_chat(request: Request, payload: AIChatPayload) -> dict[str, object]:
    user_id = _require_user_id(request)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message cannot be empty")
    board_id = _parse_numeric_id(payload.boardId, "boardId")

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


# --- Admin endpoints ---


class CreateUserPayload(BaseModel):
    username: str
    password: str
    role: str = "user"


class UpdateUserPayload(BaseModel):
    username: str | None = None
    password: str | None = None
    role: str | None = None
    suspended: bool | None = None


@app.get("/api/admin/users")
def admin_list_users(request: Request) -> dict[str, object]:
    _require_admin(request)
    return {"users": db.list_users()}


@app.post("/api/admin/users")
def admin_create_user(request: Request, payload: CreateUserPayload) -> dict[str, object]:
    _require_admin(request)
    try:
        return db.create_user(payload.username, payload.password, payload.role)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/admin/users/{user_id}")
def admin_update_user(request: Request, user_id: str, payload: UpdateUserPayload) -> dict[str, object]:
    admin_id = _require_admin(request)
    parsed_user_id = _parse_numeric_id(user_id, "user_id")
    if parsed_user_id == admin_id and payload.suspended:
        raise HTTPException(status_code=400, detail="Cannot suspend yourself")
    if parsed_user_id == admin_id and payload.role and payload.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot remove your own admin role")
    try:
        return db.update_user(
            parsed_user_id,
            username=payload.username,
            password=payload.password,
            role=payload.role,
            suspended=payload.suspended,
        )
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(request: Request, user_id: str) -> dict[str, str]:
    admin_id = _require_admin(request)
    parsed_user_id = _parse_numeric_id(user_id, "user_id")
    if parsed_user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    try:
        db.delete_user(parsed_user_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
