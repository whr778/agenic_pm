"""Card comments routes: list and add comments on a card."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_user_id, parse_numeric_id
from app.schemas import AddCommentPayload

router = APIRouter(prefix="/api/boards", tags=["comments"])


@router.get("/{board_id}/cards/{card_id}/comments")
def list_comments(
    request: Request, board_id: str, card_id: str
) -> list[dict[str, object]]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    try:
        return db.list_card_comments(user_id, parsed_board_id, parsed_card_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{board_id}/cards/{card_id}/comments")
def add_comment(
    request: Request,
    board_id: str,
    card_id: str,
    payload: AddCommentPayload,
) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    try:
        return db.add_card_comment(user_id, parsed_board_id, parsed_card_id, payload.content)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
