from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import bcrypt


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "pm.db"

FIXED_COLUMNS: list[tuple[str, str]] = [
    ("backlog", "Backlog"),
    ("todo", "To Do"),
    ("in_progress", "In Progress"),
    ("review", "Review"),
    ("done", "Done"),
]

STARTER_CARDS: list[tuple[str, str, str]] = [
    ("backlog", "Align roadmap themes", "Draft quarterly themes with impact statements and metrics."),
    ("backlog", "Gather customer signals", "Review support tags, sales notes, and churn feedback."),
    ("todo", "Prototype analytics view", "Sketch initial dashboard layout and key drill-downs."),
    ("in_progress", "Refine status language", "Standardize column labels and tone across the board."),
    ("in_progress", "Design card layout", "Add hierarchy and spacing for scanning dense lists."),
    ("review", "QA micro-interactions", "Verify hover, focus, and loading states."),
    ("done", "Ship marketing page", "Final copy approved and asset pack delivered."),
    ("done", "Close onboarding sprint", "Document release notes and share internally."),
]


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


def _normalize_non_empty(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValidationError(f"{label} must not be empty")
    return normalized


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _db_path() -> Path:
    configured = os.getenv("PM_DB_PATH")
    return Path(configured) if configured else DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _migrate_users_add_columns(connection: sqlite3.Connection) -> None:
    """Add role, suspended, and password_hash columns to existing users table."""
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(users)").fetchall()
    }
    if "role" not in columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
        )
    if "suspended" not in columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN suspended INTEGER NOT NULL DEFAULT 0"
        )
    if "password_hash" not in columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT ''"
        )


def _migrate_boards_unique_constraint(connection: sqlite3.Connection) -> None:
    """Migrate boards table from UNIQUE(user_id) to UNIQUE(user_id, name)."""
    table_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='boards'"
    ).fetchone()
    if table_sql is None:
        return
    sql_text = str(table_sql["sql"])
    if "UNIQUE(user_id, name)" in sql_text.replace(" ", ""):
        return
    connection.executescript(
        """
        CREATE TABLE boards_new (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          name TEXT NOT NULL DEFAULT 'Main Board',
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
          UNIQUE(user_id, name)
        );
        INSERT INTO boards_new SELECT * FROM boards;
        DROP TABLE boards;
        ALTER TABLE boards_new RENAME TO boards;
        """
    )


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT NOT NULL UNIQUE,
              role TEXT NOT NULL DEFAULT 'user',
              suspended INTEGER NOT NULL DEFAULT 0,
              password_hash TEXT NOT NULL DEFAULT '',
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

            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY,
              username TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              expires_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
            """
        )

        _migrate_users_add_columns(connection)
        _migrate_boards_unique_constraint(connection)

        default_hash = hash_password("password")
        connection.execute(
            "INSERT OR IGNORE INTO users (username, role, password_hash) VALUES (?, 'admin', ?)",
            ("user", default_hash),
        )
        # Ensure existing default user has a password hash and admin role
        connection.execute(
            "UPDATE users SET role = 'admin', password_hash = ? WHERE username = 'user' AND password_hash = ''",
            (default_hash,),
        )
        user_row = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            ("user",),
        ).fetchone()
        assert user_row is not None
        user_id = int(user_row["id"])

        connection.execute(
            "INSERT OR IGNORE INTO boards (user_id, name) VALUES (?, ?)",
            (user_id, "Main Board"),
        )
        board_row = connection.execute(
            "SELECT id FROM boards WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        assert board_row is not None
        board_id = int(board_row["id"])

        for index, (key, title) in enumerate(FIXED_COLUMNS):
            connection.execute(
                """
                INSERT OR IGNORE INTO board_columns (board_id, key, title, position)
                VALUES (?, ?, ?, ?)
                """,
                (board_id, key, title, index),
            )

        card_count = connection.execute(
            "SELECT COUNT(*) AS count FROM cards WHERE board_id = ?",
            (board_id,),
        ).fetchone()
        assert card_count is not None

        if int(card_count["count"]) == 0:
            column_rows = connection.execute(
                "SELECT id, key FROM board_columns WHERE board_id = ?",
                (board_id,),
            ).fetchall()
            col_id_by_key = {str(row["key"]): int(row["id"]) for row in column_rows}
            next_position_by_column: dict[int, int] = {
                int(row["id"]): 0 for row in column_rows
            }

            for column_key, title, details in STARTER_CARDS:
                column_id = col_id_by_key[column_key]
                position = next_position_by_column[column_id]
                connection.execute(
                    """
                    INSERT INTO cards (board_id, column_id, title, details, position)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (board_id, column_id, title, details, position),
                )
                next_position_by_column[column_id] = position + 1


def get_user_by_username(username: str) -> sqlite3.Row | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT id, username, role, suspended, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()


def list_users() -> list[dict[str, object]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, username, role, suspended, created_at FROM users ORDER BY id ASC"
        ).fetchall()
    return [
        {
            "id": str(row["id"]),
            "username": str(row["username"]),
            "role": str(row["role"]),
            "suspended": bool(row["suspended"]),
            "createdAt": str(row["created_at"]),
        }
        for row in rows
    ]


def create_user(username: str, password: str, role: str) -> dict[str, object]:
    normalized = _normalize_non_empty(username, "Username")
    _normalize_non_empty(password, "Password")
    if role not in ("user", "admin"):
        raise ValidationError("Role must be 'user' or 'admin'")
    hashed = hash_password(password)
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ?", (normalized,)
        ).fetchone()
        if existing is not None:
            raise ValidationError("Username already exists")
        cursor = connection.execute(
            "INSERT INTO users (username, role, password_hash) VALUES (?, ?, ?)",
            (normalized, role, hashed),
        )
        user_id = int(cursor.lastrowid)
    return {
        "id": str(user_id),
        "username": normalized,
        "role": role,
        "suspended": False,
    }


def update_user(
    user_id: int,
    *,
    username: str | None = None,
    password: str | None = None,
    role: str | None = None,
    suspended: bool | None = None,
) -> dict[str, object]:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, username, role, suspended FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError("User not found")

        if username is not None:
            normalized = _normalize_non_empty(username, "Username")
            dup = connection.execute(
                "SELECT id FROM users WHERE username = ? AND id != ?",
                (normalized, user_id),
            ).fetchone()
            if dup is not None:
                raise ValidationError("Username already exists")
            connection.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                (normalized, user_id),
            )

        if password is not None:
            _normalize_non_empty(password, "Password")
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(password), user_id),
            )

        if role is not None:
            if role not in ("user", "admin"):
                raise ValidationError("Role must be 'user' or 'admin'")
            if role != "admin" and str(row["role"]) == "admin":
                admin_count = connection.execute(
                    "SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin'"
                ).fetchone()
                assert admin_count is not None
                if int(admin_count["cnt"]) <= 1:
                    raise ValidationError("Cannot remove the last admin")
            connection.execute(
                "UPDATE users SET role = ? WHERE id = ?",
                (role, user_id),
            )

        if suspended is not None:
            connection.execute(
                "UPDATE users SET suspended = ? WHERE id = ?",
                (1 if suspended else 0, user_id),
            )

        updated = connection.execute(
            "SELECT id, username, role, suspended FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        assert updated is not None
    return {
        "id": str(updated["id"]),
        "username": str(updated["username"]),
        "role": str(updated["role"]),
        "suspended": bool(updated["suspended"]),
    }


def delete_user(user_id: int) -> None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError("User not found")
        if str(row["role"]) == "admin":
            admin_count = connection.execute(
                "SELECT COUNT(*) AS cnt FROM users WHERE role = 'admin'"
            ).fetchone()
            assert admin_count is not None
            if int(admin_count["cnt"]) <= 1:
                raise ValidationError("Cannot delete the last admin")
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))


def _get_board(connection: sqlite3.Connection, user_id: int, board_id: int) -> sqlite3.Row:
    board = connection.execute(
        "SELECT id, name FROM boards WHERE id = ? AND user_id = ?",
        (board_id, user_id),
    ).fetchone()
    if board is None:
        raise NotFoundError("Board not found")
    return board


def list_boards(user_id: int) -> list[dict[str, str]]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, created_at, updated_at FROM boards WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    return [
        {"id": str(row["id"]), "name": str(row["name"]),
         "createdAt": str(row["created_at"]), "updatedAt": str(row["updated_at"])}
        for row in rows
    ]


def create_board(user_id: int, name: str) -> dict[str, object]:
    normalized = _normalize_non_empty(name, "Board name")
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM boards WHERE user_id = ? AND name = ?",
            (user_id, normalized),
        ).fetchone()
        if existing is not None:
            raise ValidationError("A board with that name already exists")

        cursor = connection.execute(
            "INSERT INTO boards (user_id, name) VALUES (?, ?)",
            (user_id, normalized),
        )
        board_id = int(cursor.lastrowid)

        for index, (key, title) in enumerate(FIXED_COLUMNS):
            connection.execute(
                "INSERT INTO board_columns (board_id, key, title, position) VALUES (?, ?, ?, ?)",
                (board_id, key, title, index),
            )

    return get_board_payload(user_id, board_id)


def delete_board(user_id: int, board_id: int) -> None:
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        count_row = connection.execute(
            "SELECT COUNT(*) AS cnt FROM boards WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        assert count_row is not None
        if int(count_row["cnt"]) <= 1:
            raise ValidationError("Cannot delete the last board")
        connection.execute("DELETE FROM boards WHERE id = ?", (board_id,))


def get_board_payload(user_id: int, board_id: int) -> dict[str, object]:
    with get_connection() as connection:
        board = _get_board(connection, user_id, board_id)
        board_id = int(board["id"])

        column_rows = connection.execute(
            """
            SELECT id, key, title, position
            FROM board_columns
            WHERE board_id = ?
            ORDER BY position ASC
            """,
            (board_id,),
        ).fetchall()

        card_rows = connection.execute(
            """
            SELECT id, column_id, title, details, position
            FROM cards
            WHERE board_id = ?
            ORDER BY column_id ASC, position ASC
            """,
            (board_id,),
        ).fetchall()

        card_ids_by_column: dict[int, list[str]] = {
            int(row["id"]): [] for row in column_rows
        }
        cards_map: dict[str, dict[str, str]] = {}

        for card in card_rows:
            card_id = str(card["id"])
            column_id = int(card["column_id"])
            card_ids_by_column.setdefault(column_id, []).append(card_id)
            cards_map[card_id] = {
                "id": card_id,
                "title": str(card["title"]),
                "details": str(card["details"]),
            }

        columns_payload = [
            {
                "id": str(row["id"]),
                "key": str(row["key"]),
                "title": str(row["title"]),
                "cardIds": card_ids_by_column.get(int(row["id"]), []),
            }
            for row in column_rows
        ]

        return {
            "boardId": str(board_id),
            "name": str(board["name"]),
            "columns": columns_payload,
            "cards": cards_map,
        }


def update_board_name(user_id: int, board_id: int, name: str) -> dict[str, str]:
    normalized = _normalize_non_empty(name, "Board name")

    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        connection.execute(
            """
            UPDATE boards
            SET name = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (normalized, board_id),
        )
    return {"boardId": str(board_id), "name": normalized}


def rename_column(user_id: int, board_id: int, column_id: int, title: str) -> dict[str, str]:
    normalized = _normalize_non_empty(title, "Column title")

    with get_connection() as connection:
        _get_board(connection, user_id, board_id)

        row = connection.execute(
            "SELECT id FROM board_columns WHERE id = ? AND board_id = ?",
            (column_id, board_id),
        ).fetchone()
        if row is None:
            raise NotFoundError("Column not found")

        connection.execute(
            """
            UPDATE board_columns
            SET title = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (normalized, column_id),
        )

    return {"id": str(column_id), "title": normalized}


def create_card(user_id: int, board_id: int, column_id: int, title: str, details: str) -> dict[str, str]:
    normalized_title = _normalize_non_empty(title, "Card title")
    normalized_details = details.strip()

    with get_connection() as connection:
        _get_board(connection, user_id, board_id)

        row = connection.execute(
            "SELECT id FROM board_columns WHERE id = ? AND board_id = ?",
            (column_id, board_id),
        ).fetchone()
        if row is None:
            raise NotFoundError("Column not found")

        position_row = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM cards WHERE column_id = ?",
            (column_id,),
        ).fetchone()
        assert position_row is not None
        position = int(position_row["next_pos"])

        cursor = connection.execute(
            """
            INSERT INTO cards (board_id, column_id, title, details, position)
            VALUES (?, ?, ?, ?, ?)
            """,
            (board_id, column_id, normalized_title, normalized_details, position),
        )
        card_id = int(cursor.lastrowid)

    return {
        "id": str(card_id),
        "columnId": str(column_id),
        "title": normalized_title,
        "details": normalized_details,
    }


def update_card(user_id: int, board_id: int, card_id: int, title: str, details: str) -> dict[str, str]:
    normalized_title = _normalize_non_empty(title, "Card title")
    normalized_details = details.strip()

    with get_connection() as connection:
        _get_board(connection, user_id, board_id)

        card = connection.execute(
            "SELECT id FROM cards WHERE id = ? AND board_id = ?",
            (card_id, board_id),
        ).fetchone()
        if card is None:
            raise NotFoundError("Card not found")

        connection.execute(
            """
            UPDATE cards
            SET title = ?, details = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (normalized_title, normalized_details, card_id),
        )

    return {"id": str(card_id), "title": normalized_title, "details": normalized_details}


def delete_card(user_id: int, board_id: int, card_id: int) -> None:
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)

        card = connection.execute(
            "SELECT id, column_id, position FROM cards WHERE id = ? AND board_id = ?",
            (card_id, board_id),
        ).fetchone()
        if card is None:
            raise NotFoundError("Card not found")

        column_id = int(card["column_id"])
        position = int(card["position"])

        connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        connection.execute(
            "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
            (column_id, position),
        )


def _reorder_card(
    connection: sqlite3.Connection,
    card_id: int,
    source_column_id: int,
    target_column_id: int,
    target_index: int,
) -> int:
    """Move a card within or across columns, returning the adjusted index.

    Caller must already be inside a transaction.
    """
    source_rows = connection.execute(
        "SELECT id FROM cards WHERE column_id = ? ORDER BY position ASC",
        (source_column_id,),
    ).fetchall()
    target_rows = connection.execute(
        "SELECT id FROM cards WHERE column_id = ? ORDER BY position ASC",
        (target_column_id,),
    ).fetchall()

    source_ids = [int(row["id"]) for row in source_rows]
    target_ids = [int(row["id"]) for row in target_rows]

    if source_column_id == target_column_id:
        reordered = [v for v in source_ids if v != card_id]
        adjusted = min(target_index, len(reordered))
        reordered.insert(adjusted, card_id)

        connection.execute(
            "UPDATE cards SET position = position + 1000 WHERE column_id = ?",
            (source_column_id,),
        )
        for position, cid in enumerate(reordered):
            connection.execute(
                "UPDATE cards SET position = ?, updated_at = datetime('now') WHERE id = ?",
                (position, cid),
            )
        return adjusted

    source_reordered = [v for v in source_ids if v != card_id]
    target_without = [v for v in target_ids if v != card_id]
    adjusted = min(target_index, len(target_without))
    target_without.insert(adjusted, card_id)

    connection.execute(
        "UPDATE cards SET position = position + 1000 WHERE column_id = ?",
        (source_column_id,),
    )
    connection.execute(
        "UPDATE cards SET position = position + 1000 WHERE column_id = ?",
        (target_column_id,),
    )

    for position, cid in enumerate(source_reordered):
        connection.execute(
            "UPDATE cards SET position = ?, updated_at = datetime('now') WHERE id = ?",
            (position, cid),
        )

    for position, cid in enumerate(target_without):
        if cid == card_id:
            connection.execute(
                "UPDATE cards SET column_id = ?, position = ?, updated_at = datetime('now') WHERE id = ?",
                (target_column_id, position, cid),
            )
        else:
            connection.execute(
                "UPDATE cards SET position = ?, updated_at = datetime('now') WHERE id = ?",
                (position, cid),
            )
    return adjusted


def move_card(user_id: int, board_id: int, card_id: int, target_column_id: int, target_index: int) -> dict[str, str]:
    if target_index < 0:
        raise ValidationError("Target index must be zero or greater")

    with get_connection() as connection:
        _get_board(connection, user_id, board_id)

        target_column = connection.execute(
            "SELECT id FROM board_columns WHERE id = ? AND board_id = ?",
            (target_column_id, board_id),
        ).fetchone()
        if target_column is None:
            raise NotFoundError("Target column not found")

        card = connection.execute(
            "SELECT id, column_id, position FROM cards WHERE id = ? AND board_id = ?",
            (card_id, board_id),
        ).fetchone()
        if card is None:
            raise NotFoundError("Card not found")

        source_column_id = int(card["column_id"])

        with connection:
            adjusted = _reorder_card(
                connection, card_id, source_column_id, target_column_id, target_index
            )

    return {
        "id": str(card_id),
        "columnId": str(target_column_id),
        "position": str(adjusted),
    }


def list_chat_messages(user_id: int, board_id: int, limit: int = 20) -> list[dict[str, str]]:
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        rows = connection.execute(
            """
            SELECT id, role, content
            FROM chat_messages
            WHERE board_id = ? AND user_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (board_id, user_id, limit),
        ).fetchall()
    return [{"id": str(row["id"]), "role": str(row["role"]), "content": str(row["content"])} for row in rows]


def add_chat_message(user_id: int, board_id: int, role: str, content: str) -> None:
    if role not in {"user", "assistant", "system"}:
        raise ValidationError("role must be one of user, assistant, or system")
    normalized_content = _normalize_non_empty(content, "content")

    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        connection.execute(
            """
            INSERT INTO chat_messages (board_id, user_id, role, content)
            VALUES (?, ?, ?, ?)
            """,
            (board_id, user_id, role, normalized_content),
        )


def apply_updates_atomically(user_id: int, board_id: int, updates: list[dict[str, object]]) -> None:
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        with connection:
            for update in updates:
                update_type = str(update.get("type", ""))

                if update_type == "rename_board":
                    board_name = _normalize_non_empty(str(update.get("boardName", "")), "Board name")
                    connection.execute(
                        """
                        UPDATE boards
                        SET name = ?, updated_at = datetime('now')
                        WHERE id = ?
                        """,
                        (board_name, board_id),
                    )
                    continue

                if update_type == "rename_column":
                    column_id = int(str(update.get("columnId", "")))
                    title = _normalize_non_empty(str(update.get("title", "")), "Column title")
                    row = connection.execute(
                        "SELECT id FROM board_columns WHERE id = ? AND board_id = ?",
                        (column_id, board_id),
                    ).fetchone()
                    if row is None:
                        raise NotFoundError("Column not found")
                    connection.execute(
                        """
                        UPDATE board_columns
                        SET title = ?, updated_at = datetime('now')
                        WHERE id = ?
                        """,
                        (title, column_id),
                    )
                    continue

                if update_type == "create_card":
                    column_id = int(str(update.get("columnId", "")))
                    title = _normalize_non_empty(str(update.get("title", "")), "Card title")
                    details = str(update.get("details", "")).strip()
                    row = connection.execute(
                        "SELECT id FROM board_columns WHERE id = ? AND board_id = ?",
                        (column_id, board_id),
                    ).fetchone()
                    if row is None:
                        raise NotFoundError("Column not found")
                    position_row = connection.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM cards WHERE column_id = ?",
                        (column_id,),
                    ).fetchone()
                    assert position_row is not None
                    position = int(position_row["next_pos"])
                    connection.execute(
                        """
                        INSERT INTO cards (board_id, column_id, title, details, position)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (board_id, column_id, title, details, position),
                    )
                    continue

                if update_type == "update_card":
                    card_id = int(str(update.get("cardId", "")))
                    title = _normalize_non_empty(str(update.get("title", "")), "Card title")
                    details = str(update.get("details", "")).strip()
                    card = connection.execute(
                        "SELECT id FROM cards WHERE id = ? AND board_id = ?",
                        (card_id, board_id),
                    ).fetchone()
                    if card is None:
                        raise NotFoundError("Card not found")
                    connection.execute(
                        """
                        UPDATE cards
                        SET title = ?, details = ?, updated_at = datetime('now')
                        WHERE id = ?
                        """,
                        (title, details, card_id),
                    )
                    continue

                if update_type == "delete_card":
                    card_id = int(str(update.get("cardId", "")))
                    card = connection.execute(
                        "SELECT id, column_id, position FROM cards WHERE id = ? AND board_id = ?",
                        (card_id, board_id),
                    ).fetchone()
                    if card is None:
                        raise NotFoundError("Card not found")
                    column_id = int(card["column_id"])
                    position = int(card["position"])
                    connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
                    connection.execute(
                        "UPDATE cards SET position = position - 1 WHERE column_id = ? AND position > ?",
                        (column_id, position),
                    )
                    continue

                if update_type == "move_card":
                    card_id = int(str(update.get("cardId", "")))
                    to_column_id = int(str(update.get("toColumnId", "")))
                    to_index = int(update.get("toIndex", 0))
                    if to_index < 0:
                        raise ValidationError("Target index must be zero or greater")

                    target_column = connection.execute(
                        "SELECT id FROM board_columns WHERE id = ? AND board_id = ?",
                        (to_column_id, board_id),
                    ).fetchone()
                    if target_column is None:
                        raise NotFoundError("Target column not found")

                    card = connection.execute(
                        "SELECT id, column_id FROM cards WHERE id = ? AND board_id = ?",
                        (card_id, board_id),
                    ).fetchone()
                    if card is None:
                        raise NotFoundError("Card not found")

                    source_column_id = int(card["column_id"])
                    _reorder_card(connection, card_id, source_column_id, to_column_id, to_index)
                    continue

                raise ValidationError(f"Unsupported update type: {update_type}")


SESSION_LIFETIME_SECONDS = 24 * 60 * 60  # 24 hours


def create_session(session_id: str, username: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO sessions (id, username, expires_at)
            VALUES (?, ?, datetime('now', '+' || ? || ' seconds'))
            """,
            (session_id, username, SESSION_LIFETIME_SECONDS),
        )


def get_session(session_id: str) -> str | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT username FROM sessions WHERE id = ? AND expires_at > datetime('now')",
            (session_id,),
        ).fetchone()
    return str(row["username"]) if row else None


def delete_session(session_id: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def cleanup_expired_sessions() -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
