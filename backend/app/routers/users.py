"""User listing route: non-suspended users available for card assignment."""
from fastapi import APIRouter, Request

from app import db
from app.deps import require_user_id

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/users")
def list_assignable_users(request: Request) -> list[dict[str, str]]:
    require_user_id(request)
    return db.list_assignable_users()
