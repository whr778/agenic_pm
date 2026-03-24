"""Card management routes: create, update, delete, move."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_user_id, parse_numeric_id
from app.schemas import CreateCardPayload, UpdateCardPayload, MoveCardPayload

router = APIRouter(prefix="/api/boards", tags=["cards"])


@router.post("/{board_id}/cards")
def create_card(request: Request, board_id: str, payload: CreateCardPayload) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_column_id = parse_numeric_id(payload.columnId, "columnId")
    try:
        return db.create_card(
            user_id, parsed_board_id, parsed_column_id,
            payload.title, payload.details,
            due_date=payload.due_date,
            priority=payload.priority,
            labels=payload.labels,
        )
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{board_id}/cards/{card_id}")
def update_card(
    request: Request,
    board_id: str,
    card_id: str,
    payload: UpdateCardPayload,
) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    try:
        return db.update_card(
            user_id, parsed_board_id, parsed_card_id,
            payload.title, payload.details,
            due_date=payload.due_date,
            priority=payload.priority,
            labels=payload.labels,
        )
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{board_id}/cards/{card_id}")
def delete_card(request: Request, board_id: str, card_id: str) -> dict[str, str]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    try:
        db.delete_card(user_id, parsed_board_id, parsed_card_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@router.post("/{board_id}/cards/{card_id}/move")
def move_card(
    request: Request,
    board_id: str,
    card_id: str,
    payload: MoveCardPayload,
) -> dict[str, str]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    parsed_column_id = parse_numeric_id(payload.toColumnId, "toColumnId")
    try:
        return db.move_card(user_id, parsed_board_id, parsed_card_id, parsed_column_id, payload.toIndex)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
