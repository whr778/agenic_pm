# Code Review

## Backend

### Security

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| Medium | **Session hijacking after username change.** Sessions store `username`, not `user_id`. If an admin renames a user and a new user is created with the old username, the orphaned session resolves to the wrong user. | `db.py` | FIXED -- sessions now store `user_id` with FK to users table; migration drops old sessions |
| Medium | **No CSRF protection.** Cookie-based sessions with `SameSite=lax` do not prevent CSRF on POST/PUT/DELETE from form submissions on other origins. Low-risk for same-origin MVP but needs hardening for production. | `main.py` | Accepted risk for MVP -- same-origin setup with `SameSite=lax` mitigates most vectors |
| Low | **Rate limiter memory leak.** `_login_attempts` is a `defaultdict(list)` that grows unboundedly -- IP keys are never removed after their attempts expire. | `main.py:78-90` | FIXED -- empty IP entries are now pruned |
| Low | **Role field accepts any string.** `CreateUserPayload.role` and `UpdateUserPayload.role` are typed as `str`, not `Literal["user", "admin"]`. Validation happens in `db.create_user()` but garbage roles pass the API layer. | `main.py:493, 499` | FIXED -- now `Literal["user", "admin"]` |

### Bugs

| Severity | Issue | Location |
|----------|-------|----------|
| High | **Chat history returns oldest N messages, not most recent.** `list_chat_messages` orders by `id ASC` with `LIMIT`. For >N messages, the AI receives the oldest 50 messages instead of the most recent 50, losing conversation context. Fix: subquery with `DESC` then re-sort `ASC`. | `db.py:748-757` |
| Low | **`_reorder_card` breaks with 1000+ cards in a column.** The `+1000` offset collides with existing positions. Acknowledged in a code comment but not guarded. | `db.py:587-596` |
| Low | **TOCTOU in `apply_updates_atomically`.** `_get_board` is called outside the transaction; the board could be deleted between the check and the updates. | `db.py:778-779` |

### Code Quality

| Severity | Issue | Location |
|----------|-------|----------|
| Medium | **`main.py` is a 555-line monolith.** All routes, models, helpers, and business logic in one file. Approaching the threshold where splitting into modules (routes, middleware, models) would improve maintainability. | `main.py` |
| Low | **`assert` used for runtime invariants.** If Python runs with `-O`, these are stripped and the code proceeds with `None` values. Use explicit `if/raise`. | `db.py:360, 399, 460, 673` |
| Low | **Inconsistent URL patterns.** `/api/board/{id}` (singular) vs `/api/boards/{id}/...` (plural) for sub-resources. | `main.py:282, 304+` |
| Low | **`_extract_json_object` is brittle.** `find("{")` / `rfind("}")` will fail on responses with multiple JSON objects or `}` in string values. Reasonable for LLM output but fragile. | `main.py:126-141` |
| Low | **No type annotations on several return values.** `_require_user` returns `sqlite3.Row` but only noted in a comment. | `main.py:96` |

### Performance

| Severity | Issue | Location |
|----------|-------|----------|
| Low | **New database connection per operation.** Every function calls `get_connection()`. Fine for low traffic but creates overhead under load. | `db.py:61-67` |
| Low | **`init_db()` runs at import time**, including a bcrypt hash (~100ms), slowing test startup on every `reload(main_module)`. | `main.py:93` |

### Database Design

| Severity | Issue | Location |
|----------|-------|----------|
| Low | **Sessions table has no FK to users.** Orphan sessions remain after user deletion until natural expiry. | `db.py:185-190` |
| Low | **No index on `cards(column_id, position)`.** Would benefit `ORDER BY position ASC` queries. | `db.py:179-183` |
| Low | **No upper bound on chat messages per board.** Table grows without bound; no retention policy. | `db.py` |

### Test Quality

- Tests are thorough with good coverage of happy paths, error paths, auth boundaries, rate limiting, and admin workflows.
- Parametrized tests in `test_ai_schema.py` are well done.
- **Fragile isolation**: both `test_app.py` and `test_db.py` use `importlib.reload()` to reset module-level state -- brittle when reload order matters.
- **Missing tests**: no concurrent database access tests, no integration test verifying admin password reset enables login via HTTP endpoint.

---

## Frontend

### Security

| Severity | Issue | Location | Status |
|----------|-------|----------|--------|
| Medium | **Pre-filled credentials in login form.** `useState("user")` and `useState("password")` ship valid default credentials in production code. Should be empty strings. | `page.tsx:22-23` | FIXED -- now empty strings |
| Low | **No input length limits.** Card titles, card details, board names, and chat messages have no `maxLength` on inputs. | `KanbanCard.tsx`, `NewCardForm.tsx`, `page.tsx`, `KanbanBoard.tsx` | FIXED -- `maxLength` added matching backend limits |

### Code Quality

| Severity | Issue | Location |
|----------|-------|----------|
| Medium | **Duplicated `api` helper.** The same fetch wrapper is copy-pasted across three files. Should be extracted to a shared `lib/api.ts`. | `page.tsx:80-106`, `admin/page.tsx:62-85`, `KanbanBoard.tsx:35-58` |
| Medium | **Duplicated session-checking logic.** Both `page.tsx` and `admin/page.tsx` independently fetch and parse `/api/auth/session`. A shared `useSession` hook would eliminate this. | `page.tsx:45-72`, `admin/page.tsx:100-122` |
| Medium | **`KanbanBoard.tsx` is a 473-line mega-component.** Handles board loading, chat, drag-and-drop, card CRUD, column rename, and board rename. The chat sidebar and board header should be extracted. | `KanbanBoard.tsx` |
| Low | **`initialData` in `kanban.ts` is misleading.** Hardcoded sample data used only as a name fallback. Could be replaced with a simple string default. | `kanban.ts:28-84`, `KanbanBoard.tsx:25` |
| Low | **`ChatMessage` type defined inside component body.** Should be hoisted to module scope or moved to `kanban.ts`. | `KanbanBoard.tsx:22` |
| Low | **Unnecessary `apiRef` pattern.** The `api` function from `useCallback([], ...)` is already stable; the ref wrapper adds complexity without benefit. | `KanbanBoard.tsx:60-61` |

### Type Safety

| Severity | Issue | Location |
|----------|-------|----------|
| Medium | **Unsafe `as` casts on API responses** throughout. No runtime validation of response shapes. If the backend changes, these silently produce wrong data. A lightweight validation layer (Zod) or runtime guards would improve safety. | `page.tsx:35, 49, 92`, `KanbanBoard.tsx:68, 81`, `admin/page.tsx:91` |

### Error Handling

| Severity | Issue | Location |
|----------|-------|----------|
| Medium | **No global 401 handling.** If a session expires mid-use, individual API calls fail with generic error messages rather than redirecting to login. | All `api` helpers |
| Low | **Error state never cleared automatically.** Old errors persist after subsequent successful operations. | `page.tsx:294`, `KanbanBoard.tsx:457-460` |
| Low | **No confirmation before deleting cards or boards.** Cards delete immediately on click; boards delete without confirmation dialog. | `KanbanCard.tsx:143`, `page.tsx:143-161` |
| Low | **Board data race condition.** Rapid sequential operations (drag, edit, etc.) each trigger `loadBoard()`, and responses can interleave. | `KanbanBoard.tsx:148-159` |

### Performance

| Severity | Issue | Location |
|----------|-------|----------|
| Medium | **Full board reload after every mutation.** Every card/column operation triggers a full `loadBoard()` fetch and re-render. | `KanbanBoard.tsx:156, 170, 195, 205, 215, 251` |
| Low | **No `React.memo` on `KanbanColumn` and `KanbanCard`.** Every board state update re-renders all columns and cards. | `KanbanColumn.tsx`, `KanbanCard.tsx` |
| Low | **`cards` array prop recreated every render**, defeating any future memoization. | `KanbanBoard.tsx:395` |

### Accessibility

| Severity | Issue | Location |
|----------|-------|----------|
| Medium | **Chat messages container has no `aria-live` region.** Screen readers won't announce new messages. | `KanbanBoard.tsx:416` |
| Low | **Delete board button uses "x" text.** Has `aria-label` but the visual affordance is minimal. | `page.tsx:269` |
| Low | **Column title `aria-label` is generic** ("Column title") -- doesn't distinguish between columns. | `KanbanColumn.tsx:90` |
| Low | **No `role="alert"` on success messages** in admin panel (error messages have it). | `admin/page.tsx:265` |
| Low | **No focus management** after login, card creation, or edit mode transitions. | Multiple components |
| Low | **New board name input has no label or `aria-label`.** | `page.tsx:276` |

---

## Infrastructure

### Docker

| Severity | Issue | Location |
|----------|-------|----------|
| High | **`uv.lock` not copied into Docker build.** Only `pyproject.toml` is copied, so `uv sync` resolves dependencies fresh each build. Builds are non-reproducible. Fix: `COPY backend/uv.lock /app/backend/uv.lock` before `uv sync`. | `Dockerfile:21-22` |
| Medium | **`uv` installed via pip instead of multi-stage binary copy.** `pip install uv` adds unnecessary weight. Use `COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /usr/local/bin/uv` instead. | `Dockerfile:19` |
| Medium | **Volume mount UID mismatch risk.** `appuser` is UID 1000; if the host user has a different UID, the container may not have write access to the SQLite data directory. | `Dockerfile:28`, `scripts/start-mac.sh:50` |
| Low | **No `HEALTHCHECK` instruction.** Prevents Docker from monitoring container health. | `Dockerfile` |

### Scripts

| Severity | Issue | Location |
|----------|-------|----------|
| Medium | **No `.env` file existence check.** `docker run --env-file .env` fails with a confusing error if `.env` is missing. | `scripts/start-mac.sh:51` | FIXED -- guard added before docker run |
| Low | **BuildKit disabled in fallback path.** The retry logic disables BuildKit unnecessarily; `--pull=false` alone would suffice. | `scripts/start-mac.sh:35` |
| Low | **No wait-for-healthy check after `docker run`.** Script reports "running" immediately, but the container may take seconds to start. | `scripts/start-mac.sh:47-52` |

### `.dockerignore`

| Severity | Issue | Location |
|----------|-------|----------|
| Low | **Missing exclusions** for `docs/`, `scripts/`, `*.md`, `backend/tests/`, `frontend/tests/`, and test configs. These are sent to the Docker daemon unnecessarily. | `.dockerignore` |

### Configuration

| Severity | Issue | Location |
|----------|-------|----------|
| Low | **`requires-python >= 3.11`** is looser than the Docker image (3.12.9). Could cause local/Docker divergence. | `backend/pyproject.toml:5` |
| Low | **Coverage threshold in `pytest addopts`** runs on every test invocation, even quick single-test iterations. Consider CI-only enforcement. | `backend/pyproject.toml:22` |
| Low | **No `engines` field** in `package.json` to enforce Node version for local dev (Docker uses Node 22.14). | `frontend/package.json` |
| Low | **E2E tests target `localhost:3000`** (Next.js dev server), not the production Docker build at port 8000. | `frontend/playwright.config.ts:10` |

---

## Top Priority Fixes

1. ~~**Session stores username, not user_id** -- session hijacking vector after user rename~~ FIXED
2. ~~**Pre-filled credentials in login form** -- ships valid defaults in production code~~ FIXED
3. ~~**Rate limiter memory leak** -- IP keys never pruned~~ FIXED
4. ~~**Role field accepts any string** -- Pydantic models not constrained~~ FIXED
5. ~~**No input length limits** -- frontend inputs unbounded~~ FIXED
6. ~~**No `.env` existence check in start script** -- confusing failure mode~~ FIXED
7. **Chat history returns oldest messages instead of most recent** -- the AI loses context of recent conversation (`db.py`)
8. **`uv.lock` not copied into Docker build** -- non-reproducible Python dependencies (`Dockerfile:21-22`)
9. **Duplicated `api` helper across three files** -- maintenance risk for any behavior change (`page.tsx`, `admin/page.tsx`, `KanbanBoard.tsx`)
10. **No global 401 handling** -- expired sessions cause confusing per-operation errors instead of login redirect
11. **Full board reload after every mutation** -- performance degrades with larger boards (`KanbanBoard.tsx`)
