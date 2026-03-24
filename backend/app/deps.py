"""Shared FastAPI dependencies for authentication and request parsing."""
from fastapi import HTTPException, Request

from app import db

SESSION_COOKIE_NAME = "pm_session"


def require_user(request: Request):  # returns sqlite3.Row
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    user_id = db.get_session(session_id) if session_id else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if user["suspended"]:
        raise HTTPException(status_code=403, detail="Account suspended")
    return user


def require_user_id(request: Request) -> int:
    return int(require_user(request)["id"])


def require_admin(request: Request) -> int:
    user = require_user(request)
    if str(user["role"]) != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return int(user["id"])


def parse_numeric_id(value: str, label: str) -> int:
    if not value.isdigit():
        raise HTTPException(status_code=400, detail=f"{label} must be a numeric string")
    return int(value)
