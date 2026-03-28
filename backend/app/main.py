"""FastAPI application entry point: app setup, middleware, and router registration."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import db, openrouter  # noqa: F401 — openrouter re-exported for test patching
from app.routers import auth, registration, boards, columns, cards, ai, admin, users, stats, comments, export, activity, checklists

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="PM Backend", version="0.2.0")

_origins_raw = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()

app.include_router(auth.router)
app.include_router(registration.router)
app.include_router(boards.router)
app.include_router(columns.router)
app.include_router(cards.router)
app.include_router(ai.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(stats.router)
app.include_router(comments.router)
app.include_router(export.router)
app.include_router(activity.router)
app.include_router(checklists.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello() -> dict[str, object]:
    return {
        "message": "Hello from FastAPI",
        "openrouterConfigured": bool(os.getenv("OPENROUTER_API_KEY")),
    }


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
