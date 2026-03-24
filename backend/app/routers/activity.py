"""Board activity log endpoint."""
from fastapi import APIRouter, HTTPException, Query, Request

from app import db
from app.deps import require_user_id, parse_numeric_id

router = APIRouter(prefix="/api/boards", tags=["activity"])


@router.get("/{board_id}/activity")
def board_activity(
    request: Request,
    board_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, object]]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    try:
        return db.list_board_activity(user_id, parsed_board_id, limit)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
