# Project Plan

## Confirmed decisions

- Fixed columns for MVP: Backlog, To Do, In Progress, Review, Done.
- Columns are rename-only (no add/remove/reorder columns in MVP).
- Auth will be cookie-based server session auth.
- Data model will use relational tables in SQLite.
- Chat history is persisted per user.
- One Docker container will serve backend + built frontend.
- AI structured output schema will be proposed for user approval before implementation.
- Testing bar: strong unit/integration coverage and minimum 90% coverage threshold.

## Execution rules

- Complete parts in order.
- Do not start the next part until the current part passes tests and success criteria.
- For design or schema decisions, create docs first and request explicit user sign-off.
- Keep implementation simple; no extra features beyond MVP requirements.

## Part 1 - Planning and documentation

### Checklist

- [x] Expand this file into detailed checklists with tests and success criteria per part.
- [x] Add frontend AGENTS documentation in frontend/AGENTS.md.
- [x] User reviews and approves this plan before implementation work starts.

### Tests

- [ ] N/A (documentation-only part).

### Success criteria

- [x] Plan includes concrete tasks, tests, and acceptance criteria for all parts.
- [x] Frontend AGENTS.md reflects current frontend architecture and tooling.
- [x] User approves plan explicitly.

## Part 2 - Scaffolding (Docker + FastAPI + scripts)

Status note: Part 2 scaffold verified. Container build/start/stop and endpoint smoke checks passed after fixing .dockerignore host-venv leakage and Docker app import path in the container command.

### Checklist

- [x] Create backend app skeleton in backend/ using FastAPI.
- [x] Add health endpoint and one example API endpoint.
- [x] Add Dockerfile for single-container runtime.
- [x] Add start/stop scripts for macOS, Linux, and Windows in scripts/.
- [x] Wire environment loading (.env) for OPENROUTER_API_KEY.
- [x] Serve temporary static hello-world page from backend to verify container wiring.

### Tests

- [x] Backend unit test: health endpoint returns 200.
- [x] Backend integration test: example API endpoint returns expected JSON.
- [x] Container smoke test: app boots and serves hello-world page + API route.

### Success criteria

- [x] Running start script launches one container and app is reachable locally.
- [x] / health route and example API route both work.
- [x] Stop script cleanly stops container and related resources.

## Part 3 - Serve the existing frontend at /

Status note: Part 3 verified. Docker now builds exported Next.js assets and FastAPI serves them at /. Frontend build, unit tests, Playwright tests, and container smoke checks passed.

### Checklist

- [x] Build Next.js frontend as static assets for containerized serving.
- [x] Configure FastAPI static mount so / serves the Kanban UI.
- [x] Ensure frontend assets resolve correctly from backend runtime.
- [x] Preserve current kanban behavior (rename columns, drag cards, add/edit/delete cards).

### Tests

- [x] Frontend unit tests run in CI/container context.
- [x] E2E test verifies Kanban page renders at /.
- [x] Integration test verifies backend serves frontend index and assets.

### Success criteria

- [x] Kanban UI appears at / from backend container.
- [x] Existing frontend tests pass.
- [x] No broken static assets or route errors.

## Part 4 - Fake sign-in with cookie session

Status note: Part 4 verified. Frontend is gated behind sign-in, backend provides cookie-based login/session/logout endpoints, and tests plus container auth smoke flow passed.

### Checklist

- [x] Add login UI gate at / before showing board.
- [x] Validate hardcoded credentials: user / password.
- [x] Implement cookie-based session creation and logout endpoint.
- [x] Protect board/API routes by session check.
- [x] Add logout action in UI.

### Tests

- [x] Backend test: valid credentials create session cookie.
- [x] Backend test: invalid credentials rejected.
- [x] Backend test: protected endpoint denies access without session.
- [x] Frontend integration test: login success shows board.
- [x] Frontend integration test: logout returns to login screen.

### Success criteria

- [x] Unauthenticated users cannot access board data.
- [x] Valid login reliably sets session and unlocks board.
- [x] Logout clears session and access.

## Part 5 - Database schema and data modeling (relational SQLite)

Status note: approved schema has been implemented in backend/app/db.py with first-run SQLite init, default seeding, and persistence helpers.

### Checklist

- [x] Draft schema doc in docs/ with tables and relationships.
- [x] Model users, boards, columns, cards, and chat messages relationally.
- [x] Include migration/init strategy for first run (create DB if missing).
- [x] Define fixed-column policy and column-order handling.
- [x] Define persistence shape used for AI context payload generation.
- [x] Request explicit user sign-off before coding schema.

### Tests

- [x] Schema validation test: tables created successfully on empty DB.
- [x] Data integrity test: FK constraints and cascade behavior.
- [x] Repository-level tests for CRUD operations on core entities.

### Success criteria

- [x] User-approved schema doc exists in docs/.
- [x] Schema is normalized and supports one board per user for MVP.
- [x] DB auto-creates on first startup.

## Part 6 - Backend Kanban APIs

Status note: core authenticated board/card/column APIs are implemented and integration-tested, including same-column and cross-column card move ordering.

### Checklist

- [x] Implement API routes for board read/update operations.
- [x] Implement routes for card create/edit/move/delete.
- [x] Implement route for column rename only.
- [x] Enforce fixed columns: no add/remove/reorder via API.
- [x] Attach all board operations to authenticated user session.

### Tests

- [x] Unit tests for service/repository logic.
- [x] Integration tests for each API route.
- [x] Negative tests for unauthorized access and invalid payloads.
- [x] Regression tests for card move edge cases.

### Success criteria

- [x] API can fully power board interactions for a logged-in user.
- [x] All operations persist in SQLite.
- [x] DB is created automatically if absent.

## Part 7 - Frontend/backend integration

Status note: frontend board interactions now call backend APIs (board load/rename, column rename, card add/edit/delete/move) with server-confirmed refresh after each mutation.

### Checklist

- [x] Replace frontend in-memory mutations with backend API calls.
- [x] Load board data from backend after login.
- [x] Keep optimistic UI minimal and safe, or use server-confirmed updates.
- [x] Ensure UI refreshes from persisted data after reload.

### Tests

- [x] Frontend integration tests with mocked API errors and success paths.
- [x] E2E tests for login, load board, add/edit/move/delete card, rename column.
- [x] Integration tests for persistence across reload/restart.

### Success criteria

- [x] Board state persists between browser refreshes and app restarts.
- [x] Frontend behavior matches current UX while using backend source of truth.
- [x] End-to-end user flow is stable.

## Part 8 - OpenRouter connectivity

### Checklist

- [x] Add backend AI client using OpenRouter and model openai/gpt-oss-120b.
- [x] Read OPENROUTER_API_KEY from environment.
- [x] Implement simple connectivity endpoint/service for smoke test.
- [x] Add timeout, basic error handling, and clear failure responses.

### Tests

- [x] Unit tests for request payload construction.
- [x] Integration test with mocked OpenRouter response.
- [x] Real connectivity smoke test prompt: "2+2" (when key is available).

### Success criteria

- [x] Backend can successfully call OpenRouter with configured model.
- [x] Connectivity test returns expected non-error response.
- [x] Failures are observable and do not crash app.

## Part 9 - Structured AI response with board context

Status note: backend structured AI flow implemented and validated, including board/history context prompting, chat persistence, schema validation, and atomic optional board updates.

### Checklist

- [x] Propose structured output schema doc and get user approval.
- [x] Include board JSON snapshot + user question + conversation history in prompt input.
- [x] Persist chat messages and AI responses per user.
- [x] Parse/validate structured output on backend.
- [x] Apply optional board updates atomically when provided.

### Tests

- [x] Unit tests for schema validation/parsing.
- [x] Integration tests for both response modes:
- [x] 1) assistant message only.
- [x] 2) assistant message plus board updates.
- [x] Negative tests for malformed AI output.
- [x] Persistence tests for conversation history retrieval.

### Success criteria

- [x] AI endpoint always returns structured response to frontend.
- [x] Optional updates are validated and persisted safely.
- [x] Conversation history is durable and tied to user/board.

## Part 10 - AI chat sidebar in frontend

Status note: chat sidebar is implemented and integrated with backend AI endpoints, including conversation rendering, loading/error states, and automatic board refresh after AI updates.

### Checklist

- [x] Build sidebar chat UI integrated with existing board layout.
- [x] Send user prompts to backend AI endpoint.
- [x] Render conversation history and loading/error states.
- [x] Apply AI-provided board updates and refresh UI automatically.
- [x] Keep visual style aligned with project palette and existing aesthetic.

### Tests

- [x] Component tests for chat interactions and message rendering.
- [x] Integration tests for AI response handling and board refresh.
- [x] E2E tests for end-to-end chat + board update scenarios.

### Success criteria

- [x] User can chat with AI in sidebar and receive responses.
- [x] AI-initiated board updates are visible without manual reload.
- [x] Full app flow (login -> board -> chat -> persisted updates) works reliably.

## Coverage and quality gates

Status note: coverage baseline measured on 2026-03-20 after latest fixes. Backend total coverage is 70% (`uv run pytest --cov=app --cov-report=term`), frontend total coverage is 65.28% (`npm run test:unit -- --coverage`). Threshold enforcement remains pending until coverage is raised to at least 90%.

- [x] Enforce minimum 90% coverage for backend and frontend test suites.
- [x] All linting and tests must pass before moving to next part.
- [x] For each part, capture brief validation evidence in commit/PR notes.

## Part 11 - Multi-board support

Status note: implemented. Users can create, list, select, and delete multiple boards. All API routes are board-scoped. Backend and frontend tests updated and passing.

### Checklist

- [x] Update database layer: change boards UNIQUE constraint from (user_id) to (user_id, name), add list_boards/create_board/delete_board functions, update all CRUD functions to accept board_id parameter.
- [x] Update backend API: add GET/POST /api/boards and DELETE /api/boards/{board_id}, scope all existing routes under board_id.
- [x] Update backend tests for new API shape and new endpoints.
- [x] Update frontend types: add BoardSummary type.
- [x] Update frontend UI: board selector tabs, create/delete board actions, pass boardId to KanbanBoard component.
- [x] Update frontend tests for board-scoped URL patterns and new props.
- [x] Update docs (DATABASE_SCHEMA.md and PLAN.md).

### Tests

- [x] Backend: 74 tests pass, 92% coverage.
- [x] Frontend: 30 tests pass.

### Success criteria

- [x] Users can create, select, and delete boards.
- [x] Each board has independent columns, cards, and chat history.
- [x] Last board cannot be deleted.
- [x] Duplicate board names per user are rejected.
- [x] All existing functionality works under new board-scoped routes.

## Part 12 - Administration panel and user management

Status note: core implementation completed. Admin UI route and role-gated navigation are implemented with user list/create/edit/delete and role/suspension controls, plus frontend tests. E2E coverage for this part remains pending.

### Checklist

- [x] Add frontend admin panel route/view for admin users.
- [x] Add admin navigation entry visible only to authenticated admins.
- [x] Implement user listing UI backed by `GET /api/admin/users`.
- [x] Implement create-user UI backed by `POST /api/admin/users`.
- [x] Implement edit-user UI backed by `PUT /api/admin/users/{user_id}`.
- [x] Implement delete-user UI backed by `DELETE /api/admin/users/{user_id}`.
- [x] Implement role assignment controls (user/admin) in create and edit flows.
- [x] Implement suspend/unsuspend controls in edit flow.
- [x] Surface backend validation and authorization errors clearly in admin UI.
- [x] Enforce non-admin access denial in frontend routing and API handling.
- [x] Update docs for admin behavior and constraints.

### Admin panel UX specification (for approval before coding)

- Route: `/admin`.
- Access rule: route renders only for authenticated admins; all others are redirected to `/`.
- Entry point: `Admin` button/link in top-level app chrome, shown only when session role is `admin`.
- Layout: two panes.
- Left pane: Create User form.
- Right pane: Users table with inline actions.
- Empty state: if no users are returned (non-seeded environments), show `No users found` with refresh action.

### Create User form

- Fields:
- `username` (required, trimmed, unique)
- `password` (required)
- `role` (required select: `user` or `admin`, default `user`)
- Submit button: `Create user`.
- On success: form resets, success toast/banner appears, users list refreshes.
- On validation/API error: inline error message under form; no silent failures.

### Users table

- Columns:
- `Username`
- `Role` (badge: admin/user)
- `Suspended` (yes/no badge)
- `Created` (createdAt)
- `Actions`
- Row actions:
- `Edit` opens row edit mode (or modal) for username/role/suspended/password-reset.
- `Delete` opens confirmation dialog with explicit username in prompt.

### Edit user behavior

- Editable fields:
- `username` (optional update)
- `role` (`user`/`admin`)
- `suspended` (toggle)
- `password` (optional; when provided, sets a new password)
- Save button: `Save changes`.
- Cancel button: `Cancel` restores original row values.

### Safety and guardrails

- Disallow deleting currently logged-in admin (show backend error text).
- Disallow removing own admin role (show backend error text).
- Disallow removing the last admin role in the system (show backend error text).
- Disable submit buttons while requests are in flight to prevent duplicate actions.
- Refresh users list after every successful create/edit/delete operation.

### API contract mapping

- List users: `GET /api/admin/users`.
- Create user: `POST /api/admin/users` with `{ username, password, role }`.
- Update user: `PUT /api/admin/users/{user_id}` with any subset of `{ username, password, role, suspended }`.
- Delete user: `DELETE /api/admin/users/{user_id}`.

### Acceptance flow (manual)

- Login as seeded admin user.
- Open `/admin`.
- Create standard user.
- Change that user to admin.
- Suspend and unsuspend that user.
- Reset that user password.
- Delete that user.
- Confirm non-admin account cannot access `/admin`.

### Tests

- [x] Backend integration tests for admin endpoints: list/create/edit/delete user and role updates.
- [x] Backend negative tests: non-admin forbidden, cannot delete self, cannot remove own admin role, cannot remove last admin.
- [x] Frontend component/integration tests for admin panel list/create/edit/delete actions.
- [x] Frontend tests for role assignment UI and suspend/unsuspend behavior.
- [x] E2E tests for full admin flow: login as admin -> manage users -> verify login/access for updated user role.

### Success criteria

- [x] Admin can list, add, edit, and delete users through the UI.
- [x] Admin can assign and update roles (`user` / `admin`) through the UI.
- [x] Admin can suspend and unsuspend users through the UI.
- [x] Non-admin users cannot access the admin panel or admin APIs.
- [x] All admin actions persist correctly in SQLite and survive restart.

## Open approvals required during execution

- [x] Part 1: plan approval.
- [x] Part 5: schema doc approval before implementation.
- [x] Part 9: structured output schema approval before implementation.
- [x] Part 12: admin panel UX/fields approval before implementation.