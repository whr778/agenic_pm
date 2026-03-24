"""Admin routes: user management (list, create, update, delete)."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_admin, parse_numeric_id
from app.schemas import CreateUserPayload, UpdateUserPayload

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
def admin_list_users(request: Request) -> dict[str, object]:
    require_admin(request)
    return {"users": db.list_users()}


@router.post("/users")
def admin_create_user(request: Request, payload: CreateUserPayload) -> dict[str, object]:
    require_admin(request)
    try:
        return db.create_user(payload.username, payload.password, payload.role)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/users/{user_id}")
def admin_update_user(request: Request, user_id: str, payload: UpdateUserPayload) -> dict[str, object]:
    admin_id = require_admin(request)
    parsed_user_id = parse_numeric_id(user_id, "user_id")
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


@router.delete("/users/{user_id}")
def admin_delete_user(request: Request, user_id: str) -> dict[str, str]:
    admin_id = require_admin(request)
    parsed_user_id = parse_numeric_id(user_id, "user_id")
    if parsed_user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    try:
        db.delete_user(parsed_user_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}
