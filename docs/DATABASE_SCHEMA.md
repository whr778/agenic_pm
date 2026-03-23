# Database Schema Proposal (Part 5)

## Goals

- Use relational SQLite tables for MVP persistence.
- Support multiple boards per user.
- Enforce fixed columns policy: Backlog, To Do, In Progress, Review, Done.
- Persist chat history per board.
- Keep read/write queries simple for FastAPI endpoints.

## Summary of entities

- users: authenticated users.
- boards: logical board container.
- board_columns: fixed columns on a board (rename allowed, no add/remove/reorder in MVP API).
- cards: individual cards belonging to a board and column.
- chat_messages: stored user/assistant messages.

## Proposed schema (SQLite)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS boards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL DEFAULT 'Main Board',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS board_columns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id INTEGER NOT NULL,
  key TEXT NOT NULL,
  title TEXT NOT NULL,
  position INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
  UNIQUE(board_id, key),
  UNIQUE(board_id, position)
);

CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id INTEGER NOT NULL,
  column_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  details TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
  FOREIGN KEY (column_id) REFERENCES board_columns(id) ON DELETE CASCADE,
  UNIQUE(column_id, position)
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  board_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id);
CREATE INDEX IF NOT EXISTS idx_board_columns_board_id ON board_columns(board_id);
CREATE INDEX IF NOT EXISTS idx_cards_board_id ON cards(board_id);
CREATE INDEX IF NOT EXISTS idx_cards_column_id ON cards(column_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_board_id_created_at ON chat_messages(board_id, created_at);
```

## MVP fixed columns policy

- Column keys are immutable identifiers in DB/API logic.
- Allowed keys:
  - backlog
  - todo
  - in_progress
  - review
  - done
- Titles are user-editable labels.
- API rejects add/remove/reorder column operations.
- Initial seed inserts exactly 5 rows in board_columns with positions 0..4.

## How board data maps to frontend model

Frontend currently expects:

- columns[] with id/title/cardIds[]
- cards map keyed by card id

Backend response adapter should return:

- columns ordered by board_columns.position
- cards ordered by cards.position within each column
- ids serialized as stable strings (example: "card-<id>", "col-<id>") or raw numeric strings consistently

## Suggested initialization flow (first run)

1. Open SQLite DB file (create if missing).
2. Run schema DDL in a transaction.
3. Ensure default user row exists for username "user".
4. Ensure one default board exists for that user (additional boards can be created via API).
5. Ensure fixed 5 columns exist for each board with default titles:
   - Backlog
   - To Do
   - In Progress
   - Review
   - Done
6. Seed starter cards only if board has zero cards.

## Multi-board support

- Users can create, list, and delete boards via `/api/boards` endpoints.
- Each board has its own columns, cards, and chat history.
- Board names must be unique per user (enforced by `UNIQUE(user_id, name)`).
- Deleting a board cascades to all its columns, cards, and chat messages.
- The last remaining board for a user cannot be deleted.

## API-operation notes for Part 6/7

- Rename column:
  - update board_columns.title where board_id + key match
- Add card:
  - insert into cards with position = max(position)+1 for target column
- Move card:
  - update cards.column_id and recompute positions in source and destination columns in one transaction
- Delete card:
  - delete row, then compact positions in that column
- Edit card:
  - update title/details and updated_at

## Chat persistence notes for Part 9/10

- Persist each message as one row in chat_messages.
- Query history ordered by created_at, id for deterministic replay.
- Keep role field aligned with LLM input structure.

## Why relational over JSON blob

- Card moves and ordering updates are simpler and safer in transactions.
- Constraints guarantee referential integrity.
- Querying subsets (cards by column, recent messages) is efficient.
- Supports future reporting and multi-board expansion.

## Signed-off decisions

- API IDs in payloads use numeric strings.
- Board name is editable in MVP.
- Chat history retention is full history in MVP.
