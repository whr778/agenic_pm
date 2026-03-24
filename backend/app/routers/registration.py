"""Self-registration route: anyone can create an account, starts suspended."""
from fastapi import APIRouter, HTTPException

from app import db
from app.schemas import RegisterPayload

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
def register(payload: RegisterPayload) -> dict[str, object]:
    """Create a new user account. Accounts start suspended until an admin activates them."""
    try:
        return db.register_user(payload.username, payload.password)
    except db.ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
