"""Board export endpoint: CSV or JSON download."""
import csv
import io

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from app import db
from app.deps import require_user_id, parse_numeric_id

router = APIRouter(prefix="/api/boards", tags=["export"])


@router.get("/{board_id}/export", response_model=None)
def export_board(
    request: Request,
    board_id: str,
    format: str = Query(default="json", pattern="^(json|csv)$"),
) -> PlainTextResponse | JSONResponse:
    user_id = require_user_id(request)
    parsed_board_id = parse_numeric_id(board_id, "board_id")
    try:
        data = db.export_board_data(user_id, parsed_board_id)
    except db.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    board_name = str(data.get("board", "board")).replace(" ", "_")

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["column", "title", "details", "priority", "due_date", "labels", "assignee"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for card in data.get("cards", []):  # type: ignore[union-attr]
            card_dict = dict(card)  # type: ignore[arg-type]
            labels_val = card_dict.get("labels", [])
            card_dict["labels"] = ", ".join(labels_val) if isinstance(labels_val, list) else str(labels_val)
            writer.writerow(card_dict)
        csv_content = output.getvalue()
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{board_name}.csv"'},
        )

    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{board_name}.json"'},
    )
