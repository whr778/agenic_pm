"""Time tracking routes: log time on cards, list/delete entries, board time report."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_user_id, parse_numeric_id
from app.schemas import LogTimePayload

router = APIRouter(prefix="/api/boards", tags=["time_logs"])


@router.get("/{board_id}/cards/{card_id}/time-logs")
def list_time_logs(request: Request, board_id: str, card_id: str) -> list[dict[str, object]]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    try:
        return db.list_time_logs(user_id, parsed_board_id, parsed_card_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{board_id}/cards/{card_id}/time-logs")
def log_time(
    request: Request,
    board_id: str,
    card_id: str,
    payload: LogTimePayload,
) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    try:
        return db.log_time(user_id, parsed_board_id, parsed_card_id, payload.minutes, payload.note)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{board_id}/cards/{card_id}/time-logs/{log_id}")
def delete_time_log(
    request: Request,
    board_id: str,
    card_id: str,
    log_id: str,
) -> dict[str, str]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_card_id = parse_numeric_id(card_id, "card_id")
    parsed_log_id = parse_numeric_id(log_id, "log_id")
    try:
        db.delete_time_log(user_id, parsed_board_id, parsed_card_id, parsed_log_id)
    except db.ValidationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.get("/{board_id}/time-report")
def time_report(request: Request, board_id: str) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    try:
        return db.get_time_report(user_id, parsed_board_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
