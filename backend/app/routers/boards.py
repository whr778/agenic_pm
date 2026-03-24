"""Board management routes: list, create, get, update, delete."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_user_id, parse_numeric_id
from app.schemas import CreateBoardPayload, UpdateBoardPayload

router = APIRouter(prefix="/api", tags=["boards"])


@router.get("/boards")
def get_boards(request: Request) -> dict[str, object]:
    user_id = require_user_id(request)
    return {"boards": db.list_boards(user_id)}


@router.post("/boards")
def create_board(request: Request, payload: CreateBoardPayload) -> dict[str, object]:
    user_id = require_user_id(request)
    try:
        return db.create_board(user_id, payload.name)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/boards/{board_id}")
def delete_board_endpoint(request: Request, board_id: str) -> dict[str, str]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    try:
        db.delete_board(user_id, parsed_board_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}


@router.get("/board/{board_id}")
def get_board(request: Request, board_id: str) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    try:
        return db.get_board_payload(user_id, parsed_board_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/board/{board_id}")
def update_board(request: Request, board_id: str, payload: UpdateBoardPayload) -> dict[str, str]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    try:
        return db.update_board_name(user_id, parsed_board_id, payload.name)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
