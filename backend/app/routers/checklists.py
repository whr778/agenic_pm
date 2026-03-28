"""Checklist item management routes for cards."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_user_id, parse_numeric_id
from app.schemas import AddChecklistItemPayload, UpdateChecklistItemPayload

router = APIRouter(prefix="/api/boards", tags=["checklists"])


@router.get("/{board_id}/cards/{card_id}/checklist")
def list_checklist(request: Request, board_id: str, card_id: str) -> list[dict[str, object]]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    try:
        return db.list_card_checklist(user_id, parsed_board_id, parsed_card_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{board_id}/cards/{card_id}/checklist")
def add_checklist_item(
    request: Request,
    board_id: str,
    card_id: str,
    payload: AddChecklistItemPayload,
) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    try:
        return db.add_checklist_item(user_id, parsed_board_id, parsed_card_id, payload.text)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{board_id}/cards/{card_id}/checklist/{item_id}")
def update_checklist_item(
    request: Request,
    board_id: str,
    card_id: str,
    item_id: str,
    payload: UpdateChecklistItemPayload,
) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    parsed_item_id = parse_numeric_id(item_id, "item_id")
    try:
        return db.update_checklist_item(
            user_id, parsed_board_id, parsed_card_id, parsed_item_id,
            text=payload.text,
            checked=payload.checked,
        )
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{board_id}/cards/{card_id}/checklist/{item_id}")
def delete_checklist_item(
    request: Request,
    board_id: str,
    card_id: str,
    item_id: str,
) -> dict[str, str]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    parsed_item_id = parse_numeric_id(item_id, "item_id")
    try:
        db.delete_checklist_item(user_id, parsed_board_id, parsed_card_id, parsed_item_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}
