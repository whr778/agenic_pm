from importlib import reload

import pytest

import app.db as db


@pytest.fixture
def test_db(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "db-test.sqlite"))
    reload(db)
    db.init_db()
    yield db


def _user_id(test_db_module) -> int:
    user = test_db_module.get_user_by_username("user")
    assert user is not None
    return int(user["id"])


def _board_id(test_db_module, user_id: int) -> int:
    boards = test_db_module.list_boards(user_id)
    assert len(boards) >= 1
    return int(boards[0]["id"])


def test_chat_messages_are_saved_and_limited(test_db) -> None:
    user_id = _user_id(test_db)
    board_id = _board_id(test_db, user_id)

    test_db.add_chat_message(user_id, board_id, "user", "first")
    test_db.add_chat_message(user_id, board_id, "assistant", "second")
    test_db.add_chat_message(user_id, board_id, "system", "third")

    messages = test_db.list_chat_messages(user_id, board_id, limit=2)
    assert messages == [
        {"id": "1", "role": "user", "content": "first"},
        {"id": "2", "role": "assistant", "content": "second"},
    ]


def test_add_chat_message_validates_role_and_content(test_db) -> None:
    user_id = _user_id(test_db)
    board_id = _board_id(test_db, user_id)

    with pytest.raises(test_db.ValidationError):
        test_db.add_chat_message(user_id, board_id, "bot", "hello")

    with pytest.raises(test_db.ValidationError):
        test_db.add_chat_message(user_id, board_id, "user", "   ")


def test_create_update_delete_card_errors(test_db) -> None:
    user_id = _user_id(test_db)
    board_id = _board_id(test_db, user_id)

    with pytest.raises(test_db.NotFoundError):
        test_db.create_card(user_id, board_id, 9999, "task", "")

    with pytest.raises(test_db.NotFoundError):
        test_db.update_card(user_id, board_id, 9999, "task", "")

    with pytest.raises(test_db.NotFoundError):
        test_db.delete_card(user_id, board_id, 9999)


def test_move_card_validates_negative_index_and_target_column(test_db) -> None:
    user_id = _user_id(test_db)
    board_id = _board_id(test_db, user_id)
    board = test_db.get_board_payload(user_id, board_id)
    first_column = board["columns"][0]
    card_id = int(first_column["cardIds"][0])

    with pytest.raises(test_db.ValidationError):
        test_db.move_card(user_id, board_id, card_id, int(first_column["id"]), -1)

    with pytest.raises(test_db.NotFoundError):
        test_db.move_card(user_id, board_id, card_id, 9999, 0)


def test_apply_updates_atomically_supports_all_update_types(test_db) -> None:
    user_id = _user_id(test_db)
    board_id = _board_id(test_db, user_id)
    board = test_db.get_board_payload(user_id, board_id)

    backlog_id = board["columns"][0]["id"]
    todo_id = board["columns"][1]["id"]
    first_card_id = board["columns"][0]["cardIds"][0]

    updates = [
        {"type": "rename_board", "boardName": "Quarterly Plan"},
        {"type": "rename_column", "columnId": backlog_id, "title": "Ideas"},
        {"type": "create_card", "columnId": backlog_id, "title": "Draft launch", "details": "sync"},
        {"type": "update_card", "cardId": first_card_id, "title": "Updated seed", "details": "edited"},
        {"type": "move_card", "cardId": first_card_id, "toColumnId": todo_id, "toIndex": 0},
    ]
    test_db.apply_updates_atomically(user_id, board_id, updates)

    refreshed = test_db.get_board_payload(user_id, board_id)
    assert refreshed["name"] == "Quarterly Plan"
    assert refreshed["columns"][0]["title"] == "Ideas"
    assert refreshed["cards"][first_card_id]["title"] == "Updated seed"
    assert refreshed["columns"][1]["cardIds"][0] == first_card_id

    created_id = next(
        card_id
        for card_id, card in refreshed["cards"].items()
        if card["title"] == "Draft launch"
    )

    test_db.apply_updates_atomically(
        user_id,
        board_id,
        [{"type": "delete_card", "cardId": created_id}],
    )

    after_delete = test_db.get_board_payload(user_id, board_id)
    assert created_id not in after_delete["cards"]


def test_apply_updates_atomically_rolls_back_on_error(test_db) -> None:
    user_id = _user_id(test_db)
    board_id = _board_id(test_db, user_id)
    board_before = test_db.get_board_payload(user_id, board_id)

    with pytest.raises(test_db.NotFoundError):
        test_db.apply_updates_atomically(
            user_id,
            board_id,
            [
                {"type": "rename_board", "boardName": "Should Rollback"},
                {"type": "rename_column", "columnId": "9999", "title": "Missing"},
            ],
        )

    board_after = test_db.get_board_payload(user_id, board_id)
    assert board_after["name"] == board_before["name"]


def test_apply_updates_atomically_rejects_invalid_and_unsupported_operations(test_db) -> None:
    user_id = _user_id(test_db)
    board_id = _board_id(test_db, user_id)
    board = test_db.get_board_payload(user_id, board_id)
    first_card_id = board["columns"][0]["cardIds"][0]
    first_column_id = board["columns"][0]["id"]

    with pytest.raises(test_db.ValidationError):
        test_db.apply_updates_atomically(
            user_id,
            board_id,
            [{"type": "move_card", "cardId": first_card_id, "toColumnId": first_column_id, "toIndex": -1}],
        )

    with pytest.raises(test_db.ValidationError):
        test_db.apply_updates_atomically(user_id, board_id, [{"type": "unknown_op"}])


def test_list_boards_returns_all_user_boards(test_db) -> None:
    user_id = _user_id(test_db)
    boards = test_db.list_boards(user_id)
    assert len(boards) == 1
    assert boards[0]["name"] == "Main Board"


def test_create_board_adds_board_with_columns(test_db) -> None:
    user_id = _user_id(test_db)
    new_board = test_db.create_board(user_id, "Sprint Board")
    assert new_board["name"] == "Sprint Board"
    assert len(new_board["columns"]) == 5
    assert new_board["cards"] == {}

    boards = test_db.list_boards(user_id)
    assert len(boards) == 2


def test_create_board_rejects_duplicate_name(test_db) -> None:
    user_id = _user_id(test_db)
    with pytest.raises(test_db.ValidationError, match="already exists"):
        test_db.create_board(user_id, "Main Board")


def test_delete_board_removes_board_and_data(test_db) -> None:
    user_id = _user_id(test_db)
    new_board = test_db.create_board(user_id, "Temp Board")
    new_board_id = int(new_board["boardId"])

    test_db.create_card(user_id, new_board_id, int(new_board["columns"][0]["id"]), "temp card", "")
    test_db.delete_board(user_id, new_board_id)

    boards = test_db.list_boards(user_id)
    assert len(boards) == 1
    assert boards[0]["name"] == "Main Board"


def test_delete_last_board_raises_error(test_db) -> None:
    user_id = _user_id(test_db)
    board_id = _board_id(test_db, user_id)
    with pytest.raises(test_db.ValidationError, match="Cannot delete the last board"):
        test_db.delete_board(user_id, board_id)


def test_board_ownership_validation(test_db) -> None:
    user_id = _user_id(test_db)
    board_id = _board_id(test_db, user_id)
    with pytest.raises(test_db.NotFoundError):
        test_db.get_board_payload(9999, board_id)


# --- Admin user management tests ---


def test_list_users(test_db) -> None:
    users = test_db.list_users()
    assert len(users) >= 1
    default = users[0]
    assert default["username"] == "user"
    assert default["role"] == "admin"
    assert default["suspended"] is False


def test_create_user(test_db) -> None:
    result = test_db.create_user("alice", "secret123", "user")
    assert result["username"] == "alice"
    assert result["role"] == "user"
    assert result["suspended"] is False

    user = test_db.get_user_by_username("alice")
    assert user is not None
    assert test_db.verify_password("secret123", str(user["password_hash"]))
    assert not test_db.verify_password("wrongpass", str(user["password_hash"]))


def test_create_user_duplicate_username(test_db) -> None:
    with pytest.raises(test_db.ValidationError, match="already exists"):
        test_db.create_user("user", "pass", "user")


def test_update_user_role(test_db) -> None:
    test_db.create_user("bob", "pass", "user")
    bob = test_db.get_user_by_username("bob")
    assert bob is not None
    result = test_db.update_user(int(bob["id"]), role="admin")
    assert result["role"] == "admin"


def test_update_user_suspend(test_db) -> None:
    test_db.create_user("carol", "pass", "user")
    carol = test_db.get_user_by_username("carol")
    assert carol is not None
    uid = int(carol["id"])

    result = test_db.update_user(uid, suspended=True)
    assert result["suspended"] is True

    result = test_db.update_user(uid, suspended=False)
    assert result["suspended"] is False


def test_update_user_password(test_db) -> None:
    test_db.create_user("dave", "oldpass", "user")
    dave = test_db.get_user_by_username("dave")
    assert dave is not None
    uid = int(dave["id"])

    test_db.update_user(uid, password="newpass")
    dave = test_db.get_user_by_username("dave")
    assert dave is not None
    assert test_db.verify_password("newpass", str(dave["password_hash"]))
    assert not test_db.verify_password("oldpass", str(dave["password_hash"]))


def test_delete_user_cascades(test_db) -> None:
    result = test_db.create_user("ephemeral", "pass", "user")
    uid = int(result["id"])
    test_db.delete_user(uid)
    assert test_db.get_user_by_username("ephemeral") is None


def test_cannot_remove_last_admin_via_role_change(test_db) -> None:
    admin = test_db.get_user_by_username("user")
    assert admin is not None
    with pytest.raises(test_db.ValidationError, match="last admin"):
        test_db.update_user(int(admin["id"]), role="user")


def test_cannot_delete_last_admin(test_db) -> None:
    admin = test_db.get_user_by_username("user")
    assert admin is not None
    with pytest.raises(test_db.ValidationError, match="last admin"):
        test_db.delete_user(int(admin["id"]))


def test_hash_and_verify_password(test_db) -> None:
    hashed = test_db.hash_password("testpass")
    assert hashed != "testpass"
    assert test_db.verify_password("testpass", hashed)
    assert not test_db.verify_password("wrong", hashed)
