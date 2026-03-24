"""Board statistics route."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_user_id, parse_numeric_id

router = APIRouter(prefix="/api/boards", tags=["stats"])


@router.get("/{board_id}/stats")
def board_stats(request: Request, board_id: str) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    try:
        return db.get_board_stats(user_id, parsed_board_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
