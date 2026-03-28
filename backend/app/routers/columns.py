"""Column management routes: rename and WIP limit (fixed 5-column sets)."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_user_id, parse_numeric_id
from app.schemas import RenameColumnPayload, SetWipLimitPayload

router = APIRouter(prefix="/api/boards", tags=["columns"])


@router.patch("/{board_id}/columns/{column_id}")
def rename_column(
    request: Request,
    board_id: str,
    column_id: str,
    payload: RenameColumnPayload,
) -> dict[str, str]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_column_id = parse_numeric_id(column_id, "column_id")
    try:
        return db.rename_column(user_id, parsed_board_id, parsed_column_id, payload.title)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{board_id}/columns/{column_id}/wip-limit")
def set_wip_limit(
    request: Request,
    board_id: str,
    column_id: str,
    payload: SetWipLimitPayload,
) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_column_id = parse_numeric_id(column_id, "column_id")
    try:
        return db.set_column_wip_limit(user_id, parsed_board_id, parsed_column_id, payload.wip_limit)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
