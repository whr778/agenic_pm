"""Notification routes: list, mark-read, mark-all-read."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_user_id, parse_numeric_id

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(request: Request) -> dict[str, object]:
    user_id = require_user_id(request)
    return db.list_notifications(user_id)


@router.post("/{notification_id}/read")
def mark_read(request: Request, notification_id: str) -> dict[str, str]:
    user_id = require_user_id(request)
    parsed_id = parse_numeric_id(notification_id, "notification_id")
    try:
        db.mark_notification_read(parsed_id, user_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "read"}


@router.post("/read-all")
def mark_all_read(request: Request) -> dict[str, str]:
    user_id = require_user_id(request)
    db.mark_all_notifications_read(user_id)
    return {"status": "ok"}
