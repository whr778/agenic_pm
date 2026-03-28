"""Sprint management routes: CRUD, lifecycle transitions, and stats."""
from fastapi import APIRouter, HTTPException, Request

from app import db
from app.deps import require_user_id, parse_numeric_id
from app.schemas import CreateSprintPayload, UpdateSprintPayload

router = APIRouter(prefix="/api/boards", tags=["sprints"])


@router.get("/{board_id}/sprints")
def list_sprints(request: Request, board_id: str) -> list[dict[str, object]]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    try:
        return db.list_sprints(user_id, parsed_board_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{board_id}/sprints")
def create_sprint(request: Request, board_id: str, payload: CreateSprintPayload) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    try:
        return db.create_sprint(
            user_id, parsed_board_id,
            payload.name,
            goal=payload.goal,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{board_id}/sprints/{sprint_id}")
def update_sprint(
    request: Request,
    board_id: str,
    sprint_id: str,
    payload: UpdateSprintPayload,
) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_sprint_id = parse_numeric_id(sprint_id, "sprint_id")
    try:
        return db.update_sprint(
            user_id, parsed_board_id, parsed_sprint_id,
            name=payload.name,
            goal=payload.goal,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{board_id}/sprints/{sprint_id}")
def delete_sprint(request: Request, board_id: str, sprint_id: str) -> dict[str, str]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_sprint_id = parse_numeric_id(sprint_id, "sprint_id")
    try:
        db.delete_sprint(user_id, parsed_board_id, parsed_sprint_id)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}


@router.post("/{board_id}/sprints/{sprint_id}/start")
def start_sprint(request: Request, board_id: str, sprint_id: str) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_sprint_id = parse_numeric_id(sprint_id, "sprint_id")
    try:
        return db.start_sprint(user_id, parsed_board_id, parsed_sprint_id)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{board_id}/sprints/{sprint_id}/complete")
def complete_sprint(request: Request, board_id: str, sprint_id: str) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_sprint_id = parse_numeric_id(sprint_id, "sprint_id")
    try:
        return db.complete_sprint(user_id, parsed_board_id, parsed_sprint_id)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{board_id}/sprints/{sprint_id}/stats")
def get_sprint_stats(request: Request, board_id: str, sprint_id: str) -> dict[str, object]:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    parsed_sprint_id = parse_numeric_id(sprint_id, "sprint_id")
    try:
        return db.get_sprint_stats(user_id, parsed_board_id, parsed_sprint_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
