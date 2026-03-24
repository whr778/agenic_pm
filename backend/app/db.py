from __future__ import annotations

import json
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


def _migrate_sessions_to_user_id(connection: sqlite3.Connection) -> None:
    """Migrate sessions table from username TEXT to user_id INTEGER FK."""
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
    }
    if "username" in columns and "user_id" not in columns:
        # Drop all old sessions and recreate the table with user_id
        connection.executescript(
            """
            DROP TABLE IF EXISTS sessions;
            CREATE TABLE sessions (
              id TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              expires_at TEXT NOT NULL,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
            """
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


def _migrate_cards_add_columns(connection: sqlite3.Connection) -> None:
    """Add due_date, priority, labels, assignee_id, and archived columns to existing cards table."""
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(cards)").fetchall()
    }
    if "due_date" not in columns:
        connection.execute("ALTER TABLE cards ADD COLUMN due_date TEXT")
    if "priority" not in columns:
        connection.execute("ALTER TABLE cards ADD COLUMN priority TEXT")
    if "labels" not in columns:
        connection.execute("ALTER TABLE cards ADD COLUMN labels TEXT NOT NULL DEFAULT '[]'")
    if "assignee_id" not in columns:
        connection.execute("ALTER TABLE cards ADD COLUMN assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
    if "archived" not in columns:
        connection.execute("ALTER TABLE cards ADD COLUMN archived INTEGER NOT NULL DEFAULT 0")


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
              due_date TEXT,
              priority TEXT,
              labels TEXT NOT NULL DEFAULT '[]',
              assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
              archived INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
              FOREIGN KEY (column_id) REFERENCES board_columns(id) ON DELETE CASCADE,
              UNIQUE(column_id, position)
            );

            CREATE TABLE IF NOT EXISTS activity_log (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              board_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              actor TEXT NOT NULL,
              action TEXT NOT NULL,
              entity_type TEXT NOT NULL,
              entity_id INTEGER,
              detail TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_activity_log_board_id ON activity_log(board_id, created_at);

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
              user_id INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              expires_at TEXT NOT NULL,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

            CREATE TABLE IF NOT EXISTS card_comments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              card_id INTEGER NOT NULL,
              board_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              content TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT (datetime('now')),
              updated_at TEXT NOT NULL DEFAULT (datetime('now')),
              FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE,
              FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
              FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_card_comments_card_id ON card_comments(card_id);
            """
        )

        _migrate_users_add_columns(connection)
        _migrate_boards_unique_constraint(connection)
        _migrate_sessions_to_user_id(connection)
        _migrate_cards_add_columns(connection)

        # Index on assignee_id must come after migration (column added by migration on old DBs)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_cards_assignee_id ON cards(assignee_id)"
        )

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
        if user_row is None:
            raise RuntimeError("Default user missing after insert — database may be corrupt")
        user_id = int(user_row["id"])

        connection.execute(
            "INSERT OR IGNORE INTO boards (user_id, name) VALUES (?, ?)",
            (user_id, "Main Board"),
        )
        board_row = connection.execute(
            "SELECT id FROM boards WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if board_row is None:
            raise RuntimeError("Default board missing after insert — database may be corrupt")
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
        if card_count is None:
            raise RuntimeError("Card count query returned no row — database may be corrupt")

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


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    with get_connection() as connection:
        return connection.execute(
            "SELECT id, username, role, suspended, password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


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
        user_id = int(cursor.lastrowid or 0)
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


def register_user(username: str, password: str) -> dict[str, object]:
    """Create a new user account that starts suspended until an admin activates it."""
    normalized = _normalize_non_empty(username, "Username")
    _normalize_non_empty(password, "Password")
    hashed = hash_password(password)
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ?", (normalized,)
        ).fetchone()
        if existing is not None:
            raise ValidationError("Username already exists")
        cursor = connection.execute(
            "INSERT INTO users (username, role, password_hash, suspended) VALUES (?, 'user', ?, 1)",
            (normalized, hashed),
        )
        user_id = int(cursor.lastrowid or 0)
    return {
        "id": str(user_id),
        "username": normalized,
        "role": "user",
        "suspended": True,
        "message": "Account created. Please wait for an administrator to activate your account.",
    }


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
        board_id = int(cursor.lastrowid or 0)

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
            SELECT c.id, c.column_id, c.title, c.details, c.position,
                   c.due_date, c.priority, c.labels, c.assignee_id,
                   u.username AS assignee_username
            FROM cards c
            LEFT JOIN users u ON c.assignee_id = u.id
            WHERE c.board_id = ? AND c.archived = 0
            ORDER BY c.column_id ASC, c.position ASC
            """,
            (board_id,),
        ).fetchall()

        card_ids_by_column: dict[int, list[str]] = {
            int(row["id"]): [] for row in column_rows
        }
        cards_map: dict[str, dict[str, object]] = {}

        for card in card_rows:
            card_id = str(card["id"])
            column_id = int(card["column_id"])
            card_ids_by_column.setdefault(column_id, []).append(card_id)
            raw_labels = card["labels"]
            try:
                labels = json.loads(raw_labels) if raw_labels else []
            except (json.JSONDecodeError, TypeError):
                labels = []
            cards_map[card_id] = {
                "id": card_id,
                "title": str(card["title"]),
                "details": str(card["details"]),
                "due_date": card["due_date"],
                "priority": card["priority"],
                "labels": labels,
                "assignee_id": str(card["assignee_id"]) if card["assignee_id"] else None,
                "assignee_username": card["assignee_username"],
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
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        normalized = _rename_board_conn(connection, board_id, name)
    return {"boardId": str(board_id), "name": normalized}


def rename_column(user_id: int, board_id: int, column_id: int, title: str) -> dict[str, str]:
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        normalized = _rename_column_conn(connection, board_id, column_id, title)
        _log_activity_conn(connection, board_id, user_id, "rename_column", "column", column_id, normalized)
    return {"id": str(column_id), "title": normalized}


def create_card(
    user_id: int,
    board_id: int,
    column_id: int,
    title: str,
    details: str,
    *,
    due_date: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    assignee_id: int | None = None,
) -> dict[str, object]:
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        card_id, norm_title, norm_details = _create_card_conn(
            connection, board_id, column_id, title, details,
            due_date=due_date, priority=priority, labels=labels, assignee_id=assignee_id,
        )
        _log_activity_conn(connection, board_id, user_id, "create_card", "card", card_id, norm_title)
    return {
        "id": str(card_id),
        "columnId": str(column_id),
        "title": norm_title,
        "details": norm_details,
        "due_date": due_date,
        "priority": priority,
        "labels": labels or [],
        "assignee_id": str(assignee_id) if assignee_id else None,
    }


def update_card(
    user_id: int,
    board_id: int,
    card_id: int,
    title: str,
    details: str,
    *,
    due_date: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    assignee_id: int | None = None,
) -> dict[str, object]:
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        norm_title, norm_details = _update_card_conn(
            connection, board_id, card_id, title, details,
            due_date=due_date, priority=priority, labels=labels, assignee_id=assignee_id,
        )
        _log_activity_conn(connection, board_id, user_id, "update_card", "card", card_id, norm_title)
    return {
        "id": str(card_id),
        "title": norm_title,
        "details": norm_details,
        "due_date": due_date,
        "priority": priority,
        "labels": labels or [],
        "assignee_id": str(assignee_id) if assignee_id else None,
    }


def archive_card(user_id: int, board_id: int, card_id: int) -> None:
    """Soft-delete a card (sets archived=1)."""
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        title = _archive_card_conn(connection, board_id, card_id)
        _log_activity_conn(connection, board_id, user_id, "archive_card", "card", card_id, title)


def restore_card(user_id: int, board_id: int, card_id: int) -> dict[str, object]:
    """Restore an archived card to the bottom of its original column."""
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        archived = connection.execute(
            "SELECT id, column_id, title FROM cards WHERE id = ? AND board_id = ? AND archived = 1",
            (card_id, board_id),
        ).fetchone()
        if archived is None:
            raise NotFoundError("Archived card not found")
        col_id = int(archived["column_id"])
        title = str(archived["title"])
        pos_row = connection.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM cards WHERE column_id = ? AND archived = 0",
            (col_id,),
        ).fetchone()
        next_pos = int(pos_row["next_pos"]) if pos_row else 0
        connection.execute(
            "UPDATE cards SET archived = 0, position = ?, updated_at = datetime('now') WHERE id = ?",
            (next_pos, card_id),
        )
        _log_activity_conn(connection, board_id, user_id, "restore_card", "card", card_id, title)
    return {"id": str(card_id), "columnId": str(col_id), "title": title}


def permanent_delete_card(user_id: int, board_id: int, card_id: int) -> None:
    """Hard-delete an archived card."""
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        _permanent_delete_card_conn(connection, board_id, card_id)
        _log_activity_conn(connection, board_id, user_id, "permanent_delete_card", "card", card_id)


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
        "SELECT id FROM cards WHERE column_id = ? AND archived = 0 ORDER BY position ASC",
        (source_column_id,),
    ).fetchall()
    target_rows = connection.execute(
        "SELECT id FROM cards WHERE column_id = ? AND archived = 0 ORDER BY position ASC",
        (target_column_id,),
    ).fetchall()

    source_ids = [int(row["id"]) for row in source_rows]
    target_ids = [int(row["id"]) for row in target_rows]

    if source_column_id == target_column_id:
        reordered = [v for v in source_ids if v != card_id]
        adjusted = min(target_index, len(reordered))
        reordered.insert(adjusted, card_id)

        # Shift all positions by +1000 to avoid UNIQUE(column_id, position) violations
        # while writing final positions. Safe as long as a column has fewer than 1000 cards.
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

    # Shift all positions by +1000 to avoid UNIQUE(column_id, position) violations.
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


def _rename_board_conn(connection: sqlite3.Connection, board_id: int, name: str) -> str:
    board_name = _normalize_non_empty(name, "Board name")
    connection.execute(
        "UPDATE boards SET name = ?, updated_at = datetime('now') WHERE id = ?",
        (board_name, board_id),
    )
    return board_name


def _rename_column_conn(connection: sqlite3.Connection, board_id: int, column_id: int, title: str) -> str:
    normalized = _normalize_non_empty(title, "Column title")
    row = connection.execute(
        "SELECT id FROM board_columns WHERE id = ? AND board_id = ?",
        (column_id, board_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("Column not found")
    connection.execute(
        "UPDATE board_columns SET title = ?, updated_at = datetime('now') WHERE id = ?",
        (normalized, column_id),
    )
    return normalized


def _validate_priority(priority: str | None) -> str | None:
    if priority is not None and priority not in ("low", "medium", "high", "critical"):
        raise ValidationError("priority must be one of: low, medium, high, critical")
    return priority


def _create_card_conn(
    connection: sqlite3.Connection,
    board_id: int,
    column_id: int,
    title: str,
    details: str,
    *,
    due_date: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    assignee_id: int | None = None,
) -> tuple[int, str, str]:
    normalized_title = _normalize_non_empty(title, "Card title")
    normalized_details = details.strip()
    _validate_priority(priority)
    row = connection.execute(
        "SELECT id FROM board_columns WHERE id = ? AND board_id = ?",
        (column_id, board_id),
    ).fetchone()
    if row is None:
        raise NotFoundError("Column not found")
    position_row = connection.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM cards WHERE column_id = ? AND archived = 0",
        (column_id,),
    ).fetchone()
    assert position_row is not None
    position = int(position_row["next_pos"])
    labels_json = json.dumps(labels or [])
    cursor = connection.execute(
        """
        INSERT INTO cards (board_id, column_id, title, details, position, due_date, priority, labels, assignee_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (board_id, column_id, normalized_title, normalized_details, position, due_date, priority, labels_json, assignee_id),
    )
    return int(cursor.lastrowid or 0), normalized_title, normalized_details


def _update_card_conn(
    connection: sqlite3.Connection,
    board_id: int,
    card_id: int,
    title: str,
    details: str,
    *,
    due_date: str | None = None,
    priority: str | None = None,
    labels: list[str] | None = None,
    assignee_id: int | None = None,
) -> tuple[str, str]:
    normalized_title = _normalize_non_empty(title, "Card title")
    normalized_details = details.strip()
    _validate_priority(priority)
    card = connection.execute(
        "SELECT id FROM cards WHERE id = ? AND board_id = ?",
        (card_id, board_id),
    ).fetchone()
    if card is None:
        raise NotFoundError("Card not found")
    labels_json = json.dumps(labels or [])
    connection.execute(
        """
        UPDATE cards
        SET title = ?, details = ?, due_date = ?, priority = ?, labels = ?,
            assignee_id = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (normalized_title, normalized_details, due_date, priority, labels_json, assignee_id, card_id),
    )
    return normalized_title, normalized_details


def _archive_card_conn(connection: sqlite3.Connection, board_id: int, card_id: int) -> str:
    """Soft-delete: set archived=1 and compact the column's positions. Returns card title."""
    card = connection.execute(
        "SELECT id, column_id, position, title FROM cards WHERE id = ? AND board_id = ? AND archived = 0",
        (card_id, board_id),
    ).fetchone()
    if card is None:
        raise NotFoundError("Card not found")
    col_id = int(card["column_id"])
    position = int(card["position"])
    title = str(card["title"])
    # Use -card_id as position for archived cards to avoid UNIQUE(column_id, position) conflicts
    connection.execute(
        "UPDATE cards SET archived = 1, position = ?, updated_at = datetime('now') WHERE id = ?",
        (-card_id, card_id),
    )
    connection.execute(
        "UPDATE cards SET position = position - 1 WHERE column_id = ? AND archived = 0 AND position > ?",
        (col_id, position),
    )
    return title


def _permanent_delete_card_conn(connection: sqlite3.Connection, board_id: int, card_id: int) -> None:
    """Hard-delete an archived card."""
    card = connection.execute(
        "SELECT id FROM cards WHERE id = ? AND board_id = ? AND archived = 1",
        (card_id, board_id),
    ).fetchone()
    if card is None:
        raise NotFoundError("Archived card not found")
    connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))


def _log_activity_conn(
    connection: sqlite3.Connection,
    board_id: int,
    user_id: int,
    action: str,
    entity_type: str,
    entity_id: int | None,
    detail: str = "",
) -> None:
    actor_row = connection.execute(
        "SELECT username FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    actor = str(actor_row["username"]) if actor_row else "unknown"
    connection.execute(
        """
        INSERT INTO activity_log (board_id, user_id, actor, action, entity_type, entity_id, detail)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (board_id, user_id, actor, action, entity_type, entity_id, detail),
    )


def _move_card_conn(
    connection: sqlite3.Connection, board_id: int, card_id: int, to_column_id: int, to_index: int
) -> int:
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
    return _reorder_card(connection, card_id, source_column_id, to_column_id, to_index)


def move_card(user_id: int, board_id: int, card_id: int, target_column_id: int, target_index: int) -> dict[str, str]:
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        with connection:
            adjusted = _move_card_conn(connection, board_id, card_id, target_column_id, target_index)
            card_row = connection.execute("SELECT title FROM cards WHERE id = ?", (card_id,)).fetchone()
            detail = str(card_row["title"]) if card_row else ""
            _log_activity_conn(connection, board_id, user_id, "move_card", "card", card_id, detail)
    return {"id": str(card_id), "columnId": str(target_column_id), "position": str(adjusted)}


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
                    _rename_board_conn(connection, board_id, str(update.get("boardName", "")))
                elif update_type == "rename_column":
                    _rename_column_conn(
                        connection, board_id,
                        int(str(update.get("columnId", ""))),
                        str(update.get("title", "")),
                    )
                elif update_type == "create_card":
                    raw_labels = update.get("labels")
                    raw_assignee = update.get("assignee_id")
                    _create_card_conn(
                        connection, board_id,
                        int(str(update.get("columnId", ""))),
                        str(update.get("title", "")),
                        str(update.get("details", "")),
                        due_date=update.get("due_date") or None,  # type: ignore[arg-type]
                        priority=update.get("priority") or None,  # type: ignore[arg-type]
                        labels=raw_labels if isinstance(raw_labels, list) else [],
                        assignee_id=int(str(raw_assignee)) if raw_assignee else None,
                    )
                elif update_type == "update_card":
                    raw_labels = update.get("labels")
                    raw_assignee = update.get("assignee_id")
                    _update_card_conn(
                        connection, board_id,
                        int(str(update.get("cardId", ""))),
                        str(update.get("title", "")),
                        str(update.get("details", "")),
                        due_date=update.get("due_date") or None,  # type: ignore[arg-type]
                        priority=update.get("priority") or None,  # type: ignore[arg-type]
                        labels=raw_labels if isinstance(raw_labels, list) else [],
                        assignee_id=int(str(raw_assignee)) if raw_assignee else None,
                    )
                elif update_type == "delete_card":
                    _archive_card_conn(
                        connection, board_id,
                        int(str(update.get("cardId", ""))),
                    )
                elif update_type == "move_card":
                    _move_card_conn(
                        connection, board_id,
                        int(str(update.get("cardId", ""))),
                        int(str(update.get("toColumnId", ""))),
                        int(str(update.get("toIndex", 0))),
                    )
                else:
                    raise ValidationError(f"Unsupported update type: {update_type}")


def list_assignable_users() -> list[dict[str, str]]:
    """Return non-suspended users available for card assignment."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, username FROM users WHERE suspended = 0 ORDER BY username ASC"
        ).fetchall()
    return [{"id": str(row["id"]), "username": str(row["username"])} for row in rows]


def get_board_stats(user_id: int, board_id: int) -> dict[str, object]:
    """Return aggregate statistics for a board."""
    today = __import__("datetime").date.today().isoformat()
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)

        col_rows = connection.execute(
            """
            SELECT bc.id, bc.title,
                   COUNT(c.id) AS card_count
            FROM board_columns bc
            LEFT JOIN cards c ON c.column_id = bc.id AND c.board_id = ? AND c.archived = 0
            WHERE bc.board_id = ?
            GROUP BY bc.id, bc.title
            ORDER BY bc.position ASC
            """,
            (board_id, board_id),
        ).fetchall()

        overdue_row = connection.execute(
            "SELECT COUNT(*) AS cnt FROM cards WHERE board_id = ? AND archived = 0 AND due_date IS NOT NULL AND due_date < ?",
            (board_id, today),
        ).fetchone()

        priority_rows = connection.execute(
            """
            SELECT COALESCE(priority, 'none') AS priority, COUNT(*) AS cnt
            FROM cards WHERE board_id = ? AND archived = 0
            GROUP BY priority
            """,
            (board_id,),
        ).fetchall()

        total_row = connection.execute(
            "SELECT COUNT(*) AS cnt FROM cards WHERE board_id = ? AND archived = 0",
            (board_id,),
        ).fetchone()

    cards_per_column = [
        {"id": str(row["id"]), "title": str(row["title"]), "count": int(row["card_count"])}
        for row in col_rows
    ]
    by_priority = {str(row["priority"]): int(row["cnt"]) for row in priority_rows}
    return {
        "total_cards": int(total_row["cnt"]) if total_row else 0,
        "overdue_count": int(overdue_row["cnt"]) if overdue_row else 0,
        "cards_per_column": cards_per_column,
        "cards_by_priority": by_priority,
    }


def list_card_comments(user_id: int, board_id: int, card_id: int) -> list[dict[str, object]]:
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        card = connection.execute(
            "SELECT id FROM cards WHERE id = ? AND board_id = ?",
            (card_id, board_id),
        ).fetchone()
        if card is None:
            raise NotFoundError("Card not found")
        rows = connection.execute(
            """
            SELECT cc.id, cc.content, cc.created_at, u.username AS author
            FROM card_comments cc
            JOIN users u ON cc.user_id = u.id
            WHERE cc.card_id = ? AND cc.board_id = ?
            ORDER BY cc.created_at ASC
            """,
            (card_id, board_id),
        ).fetchall()
    return [
        {
            "id": str(row["id"]),
            "content": str(row["content"]),
            "author": str(row["author"]),
            "createdAt": str(row["created_at"]),
        }
        for row in rows
    ]


def add_card_comment(user_id: int, board_id: int, card_id: int, content: str) -> dict[str, object]:
    normalized = _normalize_non_empty(content, "Comment content")
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        card = connection.execute(
            "SELECT id FROM cards WHERE id = ? AND board_id = ?",
            (card_id, board_id),
        ).fetchone()
        if card is None:
            raise NotFoundError("Card not found")
        cursor = connection.execute(
            "INSERT INTO card_comments (card_id, board_id, user_id, content) VALUES (?, ?, ?, ?)",
            (card_id, board_id, user_id, normalized),
        )
        comment_id = int(cursor.lastrowid or 0)
        author_row = connection.execute(
            "SELECT username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return {
        "id": str(comment_id),
        "content": normalized,
        "author": str(author_row["username"]) if author_row else "",
        "createdAt": __import__("datetime").datetime.utcnow().isoformat(),
    }


def list_archived_cards(user_id: int, board_id: int) -> list[dict[str, object]]:
    """Return all archived cards for a board."""
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        rows = connection.execute(
            """
            SELECT c.id, c.column_id, c.title, c.details, c.due_date, c.priority, c.labels,
                   bc.title AS column_title
            FROM cards c
            JOIN board_columns bc ON c.column_id = bc.id
            WHERE c.board_id = ? AND c.archived = 1
            ORDER BY c.updated_at DESC
            """,
            (board_id,),
        ).fetchall()

    result = []
    for row in rows:
        raw_labels = row["labels"]
        try:
            labels = json.loads(raw_labels) if raw_labels else []
        except (json.JSONDecodeError, TypeError):
            labels = []
        result.append({
            "id": str(row["id"]),
            "columnId": str(row["column_id"]),
            "columnTitle": str(row["column_title"]),
            "title": str(row["title"]),
            "details": str(row["details"]),
            "due_date": row["due_date"],
            "priority": row["priority"],
            "labels": labels,
        })
    return result


def list_board_activity(user_id: int, board_id: int, limit: int = 50) -> list[dict[str, object]]:
    """Return recent activity log entries for a board (newest first)."""
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        rows = connection.execute(
            """
            SELECT id, actor, action, entity_type, entity_id, detail, created_at
            FROM activity_log
            WHERE board_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (board_id, limit),
        ).fetchall()
    return [
        {
            "id": str(row["id"]),
            "actor": str(row["actor"]),
            "action": str(row["action"]),
            "entity_type": str(row["entity_type"]),
            "entity_id": row["entity_id"],
            "detail": str(row["detail"]),
            "createdAt": str(row["created_at"]),
        }
        for row in rows
    ]


def export_board_data(user_id: int, board_id: int) -> dict[str, object]:
    """Return full board snapshot for export (includes columns, cards, column titles)."""
    with get_connection() as connection:
        _get_board(connection, user_id, board_id)
        board_row = connection.execute(
            "SELECT name FROM boards WHERE id = ?", (board_id,)
        ).fetchone()

        column_rows = connection.execute(
            "SELECT id, key, title, position FROM board_columns WHERE board_id = ? ORDER BY position ASC",
            (board_id,),
        ).fetchall()

        card_rows = connection.execute(
            """
            SELECT c.id, c.column_id, c.title, c.details, c.position,
                   c.due_date, c.priority, c.labels, c.assignee_id,
                   u.username AS assignee_username,
                   bc.title AS column_title
            FROM cards c
            LEFT JOIN users u ON c.assignee_id = u.id
            JOIN board_columns bc ON c.column_id = bc.id
            WHERE c.board_id = ? AND c.archived = 0
            ORDER BY bc.position ASC, c.position ASC
            """,
            (board_id,),
        ).fetchall()

    columns = [
        {"id": str(r["id"]), "key": str(r["key"]), "title": str(r["title"])}
        for r in column_rows
    ]
    cards = []
    for r in card_rows:
        try:
            labels = json.loads(r["labels"]) if r["labels"] else []
        except (json.JSONDecodeError, TypeError):
            labels = []
        cards.append({
            "id": str(r["id"]),
            "column": str(r["column_title"]),
            "title": str(r["title"]),
            "details": str(r["details"]),
            "priority": r["priority"],
            "due_date": r["due_date"],
            "labels": labels,
            "assignee": r["assignee_username"],
        })
    return {
        "board": str(board_row["name"]) if board_row else "",
        "exportedAt": __import__("datetime").datetime.utcnow().isoformat(),
        "columns": columns,
        "cards": cards,
    }


SESSION_LIFETIME_SECONDS = 24 * 60 * 60  # 24 hours


def create_session(session_id: str, user_id: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO sessions (id, user_id, expires_at)
            VALUES (?, ?, datetime('now', '+' || ? || ' seconds'))
            """,
            (session_id, user_id, SESSION_LIFETIME_SECONDS),
        )


def get_session(session_id: str) -> int | None:
    """Return the user_id for a valid (non-expired) session, or None."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT user_id FROM sessions WHERE id = ? AND expires_at > datetime('now')",
            (session_id,),
        ).fetchone()
    return int(row["user_id"]) if row else None


def delete_session(session_id: str) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def cleanup_expired_sessions() -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE expires_at <= datetime('now')")
