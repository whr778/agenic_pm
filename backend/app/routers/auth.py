"""Authentication routes: login, session check, logout."""
import os
from collections import defaultdict
from uuid import uuid4
import time

from fastapi import APIRouter, HTTPException, Request, Response

from app import db
from app.deps import SESSION_COOKIE_NAME
from app.schemas import LoginPayload

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory login rate limiter: max attempts per IP per rolling window.
# State is module-level so it resets on reload (useful in tests).
_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_RATE_LIMIT_MAX = int(os.getenv("LOGIN_RATE_LIMIT", "10"))
_LOGIN_RATE_LIMIT_WINDOW = 60  # seconds


def _check_login_rate_limit(ip: str) -> None:
    now = time.time()
    cutoff = now - _LOGIN_RATE_LIMIT_WINDOW
    recent = [t for t in _login_attempts[ip] if t > cutoff]
    recent.append(now)
    if len(recent) > _LOGIN_RATE_LIMIT_MAX:
        _login_attempts[ip] = recent
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")
    if recent:
        _login_attempts[ip] = recent
    else:
        _login_attempts.pop(ip, None)


@router.post("/login")
def login(payload: LoginPayload, request: Request, response: Response) -> dict[str, object]:
    ip = request.client.host if request.client else "unknown"
    _check_login_rate_limit(ip)
    user = db.get_user_by_username(payload.username)
    if user is None or not db.verify_password(payload.password, str(user["password_hash"])):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user["suspended"]:
        raise HTTPException(status_code=403, detail="Account suspended")

    session_id = str(uuid4())
    db.create_session(session_id, int(user["id"]))
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


@router.get("/session")
def auth_session(request: Request) -> dict[str, object]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    user_id = db.get_session(session_id) if session_id else None
    if user_id is None:
        return {"authenticated": False}
    user = db.get_user_by_id(user_id)
    if user is None or user["suspended"]:
        return {"authenticated": False}
    return {"authenticated": True, "username": str(user["username"]), "role": str(user["role"])}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        db.delete_session(session_id)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}
