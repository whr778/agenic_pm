# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Project Management MVP with a Kanban board, AI chat sidebar, and admin panel. Runs as a single Docker container serving a Next.js frontend (built as static assets) via a FastAPI backend. Multi-board support and user management are implemented beyond the original MVP spec.

## Commands

### Frontend (`cd frontend`)
```bash
npm run dev              # Next.js dev server
npm run build            # Production build
npm run lint             # ESLint
npm run test:unit        # Vitest (run once)
npm run test:unit:watch  # Vitest watch mode
npm run test:e2e         # Playwright E2E tests
npm run test:all         # Unit + E2E
```

### Backend (`cd backend`)
```bash
uv sync                                              # Install dependencies
uv run pytest                                        # All tests
uv run pytest tests/test_app.py::test_name           # Single test
uv run pytest --cov=app --cov-report=term-missing    # With coverage
uv run python -m uvicorn app.main:app --reload       # Dev server on :8000
```

### Docker
```bash
./scripts/start-mac.sh   # Build and run container (port 8000)
./scripts/stop-mac.sh    # Stop container
```

## Architecture

### Request Flow
Browser → FastAPI (port 8000) → serves Next.js static assets at `/`, handles `/api/*` routes → SQLite (`backend/data/pm.db`) or OpenRouter API for AI chat.

### Backend (`backend/app/`)
- `main.py` — All FastAPI routes: auth (`/api/auth/*`), boards, cards, AI chat (`/api/ai/chat`), admin user management
- `db.py` — SQLite layer: schema init, CRUD functions, session management (24hr expiry), default user seed (`user`/`password`)
- `ai_schema.py` — Pydantic models for AI response validation; discriminated union of 6 update types (rename_board, rename_column, create_card, update_card, delete_card, move_card)
- `openrouter.py` — OpenRouter API client using model `openai/gpt-oss-120b`

### Frontend (`frontend/src/`)
- `app/page.tsx` — Entry: login form, board selector, board creation/deletion
- `app/admin/page.tsx` — Admin panel: user CRUD, roles, suspension
- `components/KanbanBoard.tsx` — Main board: drag/drop orchestration, API integration, chat sidebar
- `lib/kanban.ts` — Shared types: `Card`, `Column`, `BoardData`, `BoardSummary`

### Database Schema (SQLite)
6 tables: `users`, `boards`, `board_columns`, `cards`, `chat_messages`, `sessions`. Columns are fixed (Backlog, To Do, In Progress, Review, Done) — immutable keys, rename-only via API.

### AI Chat Flow
`/api/ai/chat` → builds prompt with full board state → OpenRouter → parses structured JSON response → applies board updates atomically → returns assistant message + updated board state.

## Key Constraints

- **No add/remove/reorder columns** — columns are fixed 5-column sets per board, rename only
- **Last board cannot be deleted**; board names unique per user
- Authentication uses cookie-based sessions; admin role required for admin endpoints
- Coverage thresholds enforced: backend 90% (currently ~92%), frontend 90% (currently ~65%)

## Coding Standards

- No emojis anywhere in code or output
- No over-engineering — keep it simple, no unnecessary defensive programming
- Keep frontend logic thin; business rules belong in the backend
- Prefer immutable state updates on the frontend
- Always identify root cause before fixing; prove with evidence
- Use latest idiomatic library patterns

## Color Palette

Defined as CSS variables in `frontend/src/app/globals.css`:
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991`
- Dark Navy: `#032147`
- Gray Text: `#888888`

## Planning Docs

- `docs/PLAN.md` — 12 completed implementation parts with checklists; review before major work
- `docs/DATABASE_SCHEMA.md` — Full schema with constraints and design rationale
- `docs/AI_OUTPUT_SCHEMA.md` — AI response format specification
