# Frontend Agent Guide

## Purpose

This directory contains the current frontend-only MVP demo for the Project Management app.
It is a Next.js app that renders a single Kanban board page with local in-memory state.

## Current architecture

- Framework: Next.js 16 (App Router).
- UI: custom React components, Tailwind CSS v4, project color variables in globals.css.
- Drag and drop: @dnd-kit.
- Data state: local component state in KanbanBoard using a normalized board model from src/lib/kanban.ts.
- Tests: Vitest + React Testing Library for unit/integration style tests, Playwright for E2E.

## Key files

- src/app/page.tsx: entry page that renders the board.
- src/app/layout.tsx: root layout, metadata, and font setup.
- src/app/globals.css: global styles and palette variables.
- src/components/KanbanBoard.tsx: top-level board state and drag/drop orchestration.
- src/components/KanbanColumn.tsx: column UI, rename handling, add-card form integration.
- src/components/KanbanCard.tsx: draggable card item.
- src/components/KanbanCardPreview.tsx: drag overlay preview.
- src/components/NewCardForm.tsx: add-card form.
- src/lib/kanban.ts: shared types, initial fixture board, and moveCard logic.
- src/components/KanbanBoard.test.tsx: component behavior tests.
- src/lib/kanban.test.ts: logic tests for board utilities.
- tests/kanban.spec.ts: Playwright end-to-end tests.

## Board behavior today

- Board starts from fixture data in src/lib/kanban.ts.
- Columns are rendered from board.columns.
- Cards are looked up from board.cards by id.
- Users can rename columns, add cards, delete cards, and drag cards between columns.
- Data is not persisted; page reload resets to fixture state.

## Constraints for upcoming MVP work

- Product decision for MVP columns is: Backlog, To Do, In Progress, Review, Done.
- Columns are fixed and rename-only for MVP (no add/remove/reorder columns).
- Authentication, backend persistence, and AI chat are not implemented in this frontend yet.

## Development commands

- npm run dev: start local Next dev server.
- npm run build: production build.
- npm run start: run production server.
- npm run lint: run ESLint.
- npm run test: run unit tests once.
- npm run test:unit:watch: run unit tests in watch mode.
- npm run test:e2e: run Playwright tests.
- npm run test:all: run both unit and E2E tests.

## Agent guidance

- Keep implementations simple; no extra features beyond approved plan.
- Preserve existing styling direction unless explicitly asked to redesign.
- Prefer immutable updates for all board state changes.
- When adding API integration, keep frontend logic thin and move business rules to backend.
- Update tests alongside behavior changes.

## Definition of done for frontend changes

- Relevant unit tests and E2E tests are updated and passing.
- Lint passes.
- UI behavior matches approved requirements.
- No regression in drag/drop, add/delete, or column rename flows.