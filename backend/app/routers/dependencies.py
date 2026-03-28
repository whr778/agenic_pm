"""Card dependency routes: add and remove block/blocked-by relationships."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_user_id, parse_numeric_id
from app.schemas import AddDependencyPayload

router = APIRouter(prefix="/api/boards", tags=["dependencies"])


@router.get("/{board_id}/cards/{card_id}/dependencies")
def get_dependencies(request: Request, board_id: str, card_id: str) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    try:
        return db.get_card_dependencies(user_id, parsed_board_id, parsed_card_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{board_id}/dependencies")
def add_dependency(
    request: Request,
    board_id: str,
    payload: AddDependencyPayload,
) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    blocker_id = parse_numeric_id(payload.blocker_id, "blocker_id")
    blocked_id = parse_numeric_id(payload.blocked_id, "blocked_id")
    try:
        return db.add_card_dependency(user_id, parsed_board_id, blocker_id, blocked_id)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{board_id}/dependencies/{dep_id}")
def remove_dependency(
    request: Request,
    board_id: str,
    dep_id: str,
) -> dict[str, str]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_dep_id = parse_numeric_id(dep_id, "dep_id")
    try:
        db.remove_card_dependency(user_id, parsed_board_id, parsed_dep_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}
