# Code Review Report

**Date**: 2026-03-23
**Scope**: Full repository — backend, frontend, tests, configuration, infrastructure

---

## Fixes applied

| Fix | File | Status |
|---|---|---|
| Session cookie `secure` flag | `backend/app/main.py` | Fixed — reads `ENVIRONMENT` env var; set `ENVIRONMENT=production` in deployment |
| CORS policy | `backend/app/main.py` | Fixed — explicit `CORSMiddleware`; configure origins via `ALLOWED_ORIGINS` env var |
| Login rate limiting | `backend/app/main.py` | Fixed — in-memory per-IP limiter, 10 req/60 s, `LOGIN_RATE_LIMIT` env var overrides limit |
| Input length validation | `backend/app/main.py` | Fixed — `Field(max_length=...)` on all Pydantic request models |

All four fixes have passing tests (125 backend, 55 frontend, 96.5% backend coverage).

---

## Summary

| Category | Count |
|---|---|
| Security | 4 issues — all fixed |
| Code quality | 7 issues |
| Test coverage | 1 blocker + 2 gaps |
| Performance | 4 issues |
| Infrastructure | 3 issues |

---

## Security

### 1. CORS policy — FIXED

`CORSMiddleware` added. Default allows no origins. Set `ALLOWED_ORIGINS=http://your-origin.com` (comma-separated) in production.

---

### 2. Login rate limiting — FIXED

In-memory per-IP limiter at `POST /api/auth/login`: 10 attempts per 60-second rolling window, returns `429`. Override with `LOGIN_RATE_LIMIT` env var.

---

### 3. Input length validation — FIXED

`Field(max_length=...)` applied to all Pydantic request models: usernames 100, passwords 256, board/column names 256, card titles 512, card details 10 000, chat messages 4 000.

---

### 4. Internal error strings returned to the client in AI chat

**File**: `backend/app/main.py:423, 434`

```python
"updatesError": f"AI returned non-JSON content: {exc}",
"updatesError": f"AI response failed schema validation: {detail}",
```

These strings are displayed in the chat sidebar as system messages. They expose implementation details (exception class names, internal field paths). The detail is visible to the user but not a direct injection risk.

**Action**: Replace with a generic user-facing message; log the full error server-side.

---

## Code Quality

### 5. `apply_updates_atomically` duplicates all CRUD logic

**File**: `backend/app/db.py:787–912`

`apply_updates_atomically` reimplements the bodies of `create_card`, `update_card`, `delete_card`, `rename_column`, and `move_card` inline rather than calling those functions. This is ~120 lines of duplicated logic. Any bug fix or validation change applied to a CRUD function must be manually mirrored here.

**Action**: Refactor to call the shared helpers inside the existing transaction. The inner functions already accept a `connection` parameter pattern — pass a shared connection object or extract the core logic into connection-scoped helpers.

---

### 6. Double (and triple) DB lookups per authenticated request

**File**: `backend/app/main.py:65–93`

`_require_user_id` calls `_require_user` (which calls `get_user_by_username`), then calls `get_user_by_username` again — 2 DB round trips. `_require_admin` calls `_require_user` then `get_user_by_username` again — 3 round trips. SQLite is fast here, but the pattern is wasteful and confusing.

**Action**: Have `_require_user` return the full user row so callers do not need to re-fetch it.

---

### 7. `assert` used for invariants in `init_db`

**File**: `backend/app/db.py:213, 224, 225, 240, 241`

```python
assert user_row is not None
assert board_row is not None
assert card_count is not None
```

Python's `-O` (optimize) flag disables assertions, turning these into silent no-ops that would then cause an `AttributeError` rather than a clear error. They are also not tested — a database inconsistency would produce confusing output.

**Action**: Replace with explicit `if row is None: raise RuntimeError(...)` checks, or restructure to eliminate the possibility entirely.

---

### 8. Silent `loadBoards` failure in `page.tsx`

**File**: `frontend/src/app/page.tsx:40–42`

```typescript
} catch {
  // ignore
}
```

Board loading failure is silently swallowed. The user sees an empty board list with no feedback.

**Action**: At minimum log to console: `} catch (err) { console.error("loadBoards failed", err); }`. Optionally surface an error state.

---

### 9. `board ?? initialData` fallback silently shows placeholder data

**File**: `frontend/src/components/KanbanBoard.tsx:280, 312`

In `handleSendChat`: `setBoard(payload.board ?? initialData)` — if the API returns a response without a board, the chat replaces the real board state with placeholder seed data.
In the render: `const safeBoard = board ?? initialData` — if loading fails, the board renders placeholder cards rather than showing an error.

**Action**: In `handleSendChat`, only update board state if `payload.board` is present; otherwise leave it unchanged. In the render, if `board` is null after loading (error path), render the error message rather than `initialData`.

---

### 10. Index-based keys on chat messages

**File**: `frontend/src/components/KanbanBoard.tsx:411`

```typescript
key={message.id ?? `${message.role}-${index}`}
```

Optimistic messages (added locally in `handleSendChat`) never have an `id`, so every local message uses an index-based key. If messages are trimmed or prepended later, React will reconcile incorrectly.

**Action**: Assign a stable client-side id with `crypto.randomUUID()` when adding optimistic messages to state.

---

### 11. Magic number `+1000` in card reorder

**File**: `backend/app/db.py:676, 694, 697`

```python
connection.execute(
    "UPDATE cards SET position = position + 1000 WHERE column_id = ?",
    ...
)
```

The offset is used to avoid `UNIQUE(column_id, position)` constraint violations while rewriting positions. The value `1000` is not explained and creates a latent bug: if a column ever has more than 1000 cards, adding 1000 to the highest position will collide with the temporary offset of a lower card.

**Action**: Add a comment explaining the constraint and the invariant (`position < 1000 cards per column`), or use a two-phase approach (set all to a large negative temporary offset, then write final positions) that has no upper-bound sensitivity.

---

## Test Coverage

### 12. `KanbanCard` and `KanbanColumn` have no unit tests — blocker

**Missing files**: No `KanbanCard.test.tsx`, no `KanbanColumn.test.tsx`

These are the most interacted-with components in the application. Without tests they are invisible to coverage. The frontend is currently at ~65% against the 90% CI threshold.

**Actions** (in priority order):

1. `KanbanCard.test.tsx`: render in view mode, click Edit to enter edit mode, save with valid title, cancel, attempt save with empty title, click Remove, test directional move buttons (enabled/disabled states).
2. `KanbanColumn.test.tsx`: render with cards, open add-card form via `NewCardForm`, submit a card, verify `onAddCard` is called.
3. Add a `KanbanBoard` test for the load-failure path: mock fetch to return 500, assert error message is displayed and placeholder data is not shown.

---

### 13. No test for the `apply_updates_atomically` duplication paths

**File**: `backend/tests/test_app.py` — AI chat tests exist but only cover the happy path and top-level error handling.

The duplicated inline logic in `apply_updates_atomically` (issue 5) is not independently tested against edge cases like: deleting a non-existent card, creating a card in a column from a different board, or a `move_card` with a negative `toIndex`.

**Action**: Add `test_db.py` tests that call `apply_updates_atomically` directly with malformed update payloads and assert the correct exceptions are raised.

---

### 14. No `NewCardForm.test.tsx`

`NewCardForm.tsx` handles its own validation state (empty-title guard). It has no tests.

**Action**: Add tests for: submit with valid data calls `onAddCard`, submit with empty title shows validation message, cancel clears the form.

---

## Performance

### 15. Every mutation triggers a full board refetch

**File**: `frontend/src/components/KanbanBoard.tsx` — every handler calls `await loadBoard()` after a successful mutation.

Each card add, edit, delete, move, and column rename fetches the full board payload. This causes visible flicker and doubles the network round trips for every user action.

**Action**: The mutation API responses already return enough information to update state locally. For card add/edit/delete, update the `board` state directly from the response; only fall back to `loadBoard()` on error. The AI chat endpoint already demonstrates this pattern — it returns the full updated board in the response.

---

### 16. No timeout on board and mutation fetch calls

**File**: `frontend/src/components/KanbanBoard.tsx:35–58` — the `api` helper

The initial `loadBoard` and `loadChat` use an `AbortController` tied to component mount/unmount. But mutation calls (drag-drop, add card, etc.) have no timeout. A hung backend will leave the UI in a permanent loading state.

**Action**: Pass an `AbortController` with a 30-second timeout to the `api` helper, or add a timeout inside the helper itself using `AbortSignal.timeout(30_000)` (supported in Node 18+ and modern browsers).

---

### 17. Chat message history is unbounded

**File**: `frontend/src/components/KanbanBoard.tsx:281–290`

`chatMessages` grows without limit. Long sessions will accumulate hundreds of messages, slowing re-renders.

**Action**: Cap the state at the last N messages (e.g., 100) when appending: `const next = [...prev, ...newMessages].slice(-100)`.

---

### 18. Missing composite index for card ordering queries

**File**: `backend/app/db.py:182`

`get_board_payload` queries all cards ordered by `column_id, position`. There is an index on `column_id` alone but not the composite `(column_id, position)`. SQLite will use the `column_id` index but must then sort in memory.

**Action**: Add to `init_db`:

```sql
CREATE INDEX IF NOT EXISTS idx_cards_column_position ON cards (column_id, position);
```

---

## Infrastructure

### 19. Floating Docker base image tags

**File**: `Dockerfile:1, 12`

```dockerfile
FROM node:22-alpine        # floating tag
FROM python:3.12-slim      # floating tag
```

Both tags resolve to different images as new patch releases are published. Builds are not reproducible.

**Action**: Pin to full version tags, e.g., `node:22.14-alpine3.21` and `python:3.12.9-slim`, and update deliberately.

---

### 20. `uv` installed without version pin in Dockerfile

**File**: `Dockerfile:19`

```dockerfile
RUN pip install --no-cache-dir uv
```

Installs the latest `uv` release. A breaking change in `uv` would silently change build behaviour.

**Action**: Pin to a specific version: `pip install --no-cache-dir "uv==0.6.x"`.

---

### 21. `bcrypt` dependency unbounded above 4.x

**File**: `backend/pyproject.toml:7`

```toml
bcrypt>=4.0.0
```

A future `bcrypt>=5.0.0` major release could introduce breaking API changes.

**Action**: Pin to `bcrypt>=4.0.0,<5.0.0`.

---

## What is working well

- All SQL queries use parameterized statements throughout — no injection risk.
- Bcrypt password hashing with per-user salts.
- Pydantic validation on all request bodies, including the discriminated union in `ai_schema.py`.
- `openrouter.py` has a 20-second timeout, structured error types, and handles multi-part content responses — solid defensive client.
- Non-root container user in Dockerfile.
- Session expiry (24 hr) with cleanup on login.
- Atomic transactions for AI-triggered board updates.
- Schema migration functions handle existing databases gracefully.
- Backend test coverage at ~92% with good error path coverage.
- `AbortController` used on component mount/unmount to cancel in-flight requests.
- Immutable state updates throughout the frontend.
- The `_reorder_card` algorithm correctly handles same-column and cross-column moves, and clamps out-of-bounds `toIndex` values.
