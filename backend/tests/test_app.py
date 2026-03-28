from importlib import reload
import os
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "pm-test.db"
    monkeypatch.setenv("PM_DB_PATH", str(db_path))

    # Reload the auth router first so the in-memory rate-limit state is reset,
    # then reload main so it re-registers all routers on the fresh app instance.
    import app.routers.auth as auth_module
    import app.main as main_module

    reload(auth_module)
    reload(main_module)
    return TestClient(main_module.app)


def login(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert response.status_code == 200


def get_board_id(client: TestClient) -> str:
    response = client.get("/api/boards")
    assert response.status_code == 200
    boards = response.json()["boards"]
    assert len(boards) >= 1
    return boards[0]["id"]


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_hello_returns_message_and_env_flag(client: TestClient) -> None:
    response = client.get("/api/hello")

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Hello from FastAPI"
    assert isinstance(payload["openrouterConfigured"], bool)


def test_root_serves_static_html(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<!doctype html>" in response.text.lower()


def test_login_rejects_invalid_credentials(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "wrong"},
    )

    assert response.status_code == 401


def test_login_session_and_logout_flow(client: TestClient) -> None:
    login(client)

    session = client.get("/api/auth/session")
    assert session.status_code == 200
    assert session.json() == {"authenticated": True, "username": "user", "role": "admin"}

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    after_logout = client.get("/api/auth/session")
    assert after_logout.status_code == 200
    assert after_logout.json() == {"authenticated": False}


def test_board_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/boards")
    assert response.status_code == 401


def test_get_board_returns_seeded_numeric_string_ids(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.get(f"/api/board/{board_id}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["boardId"].isdigit()
    assert payload["name"] == "Main Board"
    assert len(payload["columns"]) == 5
    assert all(column["id"].isdigit() for column in payload["columns"])
    assert all(card_id.isdigit() for column in payload["columns"] for card_id in column["cardIds"])
    assert all(card["id"].isdigit() for card in payload["cards"].values())


def test_update_board_name(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.put(f"/api/board/{board_id}", json={"name": "Roadmap Q2"})
    assert response.status_code == 200
    assert response.json()["name"] == "Roadmap Q2"

    board = client.get(f"/api/board/{board_id}").json()
    assert board["name"] == "Roadmap Q2"


def test_rename_column(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    first_column_id = board["columns"][0]["id"]

    response = client.patch(
        f"/api/boards/{board_id}/columns/{first_column_id}",
        json={"title": "Ideas"},
    )
    assert response.status_code == 200
    assert response.json() == {"id": first_column_id, "title": "Ideas"}

    refreshed = client.get(f"/api/board/{board_id}").json()
    assert refreshed["columns"][0]["title"] == "Ideas"


def test_create_update_move_and_delete_card(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    source_column_id = board["columns"][0]["id"]
    target_column_id = board["columns"][1]["id"]

    create = client.post(
        f"/api/boards/{board_id}/cards",
        json={
            "columnId": source_column_id,
            "title": "New card",
            "details": "Needs review",
        },
    )
    assert create.status_code == 200
    card_id = create.json()["id"]

    update = client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "Updated card", "details": "Updated details"},
    )
    assert update.status_code == 200
    assert update.json()["title"] == "Updated card"

    move = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/move",
        json={"toColumnId": target_column_id, "toIndex": 0},
    )
    assert move.status_code == 200
    assert move.json()["columnId"] == target_column_id

    after_move = client.get(f"/api/board/{board_id}").json()
    assert after_move["columns"][1]["cardIds"][0] == card_id
    assert after_move["cards"][card_id]["title"] == "Updated card"

    delete = client.delete(f"/api/boards/{board_id}/cards/{card_id}")
    assert delete.status_code == 200

    after_delete = client.get(f"/api/board/{board_id}").json()
    assert card_id not in after_delete["cards"]
    assert card_id not in after_delete["columns"][1]["cardIds"]


def test_move_card_within_same_column_reorders(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    first_column = board["columns"][0]
    assert len(first_column["cardIds"]) >= 2
    first_card = first_column["cardIds"][0]
    second_card = first_column["cardIds"][1]

    move = client.post(
        f"/api/boards/{board_id}/cards/{first_card}/move",
        json={"toColumnId": first_column["id"], "toIndex": 1},
    )
    assert move.status_code == 200

    refreshed = client.get(f"/api/board/{board_id}").json()
    ids = refreshed["columns"][0]["cardIds"]
    assert ids[0] == second_card
    assert ids[1] == first_card


def test_non_numeric_ids_are_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.patch(f"/api/boards/{board_id}/columns/col-backlog", json={"title": "Ideas"})
    assert response.status_code == 400


def test_ai_connectivity_requires_auth(client: TestClient) -> None:
    response = client.post("/api/ai/connectivity", json={"prompt": "2+2"})
    assert response.status_code == 401


def test_ai_connectivity_returns_mocked_openrouter_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)

    import app.main as main_module

    def fake_chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
        assert prompt == "2+2"
        assert timeout_seconds == 20.0
        return {
            "model": "openai/gpt-oss-120b",
            "response": "4",
        }

    monkeypatch.setattr(main_module.openrouter, "chat_completion", fake_chat_completion)

    response = client.post("/api/ai/connectivity", json={"prompt": "2+2"})
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model": "openai/gpt-oss-120b",
        "response": "4",
    }


def test_ai_connectivity_surfaces_openrouter_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)

    import app.main as main_module

    def fake_chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
        raise main_module.openrouter.OpenRouterError(504, "OpenRouter request timed out")

    monkeypatch.setattr(main_module.openrouter, "chat_completion", fake_chat_completion)

    response = client.post("/api/ai/connectivity", json={"prompt": "2+2"})
    assert response.status_code == 504
    assert response.json()["detail"] == "OpenRouter request timed out"


def test_ai_connectivity_rejects_empty_prompt(client: TestClient) -> None:
    login(client)
    response = client.post("/api/ai/connectivity", json={"prompt": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "prompt cannot be empty"


def test_ai_chat_requires_auth(client: TestClient) -> None:
    response = client.post("/api/ai/chat", json={"message": "help", "boardId": "1"})
    assert response.status_code == 401


def test_ai_chat_returns_message_without_updates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    board_id = get_board_id(client)

    import app.main as main_module

    def fake_chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
        assert '"board"' in prompt
        assert '"conversationHistory"' in prompt
        return {
            "model": "openai/gpt-oss-120b",
            "response": '{"assistantMessage":"No board changes needed","updates":[]}',
        }

    monkeypatch.setattr(main_module.openrouter, "chat_completion", fake_chat_completion)

    response = client.post("/api/ai/chat", json={"message": "what should I do next?", "boardId": board_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["assistantMessage"] == "No board changes needed"
    assert payload["appliedUpdates"] is False
    assert payload["updateCount"] == 0
    assert payload["updatesError"] is None


def test_ai_chat_handles_openrouter_error_as_structured_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    board_id = get_board_id(client)

    import app.main as main_module

    def fake_chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
        raise main_module.openrouter.OpenRouterError(502, "Unable to reach OpenRouter")

    monkeypatch.setattr(main_module.openrouter, "chat_completion", fake_chat_completion)

    response = client.post("/api/ai/chat", json={"message": "help", "boardId": board_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["appliedUpdates"] is False
    assert payload["updateCount"] == 0
    assert payload["assistantMessage"].startswith("I could not reach the AI provider")
    assert payload["updatesError"] == "Unable to reach OpenRouter"


def test_list_boards(client: TestClient) -> None:
    login(client)
    response = client.get("/api/boards")
    assert response.status_code == 200
    boards = response.json()["boards"]
    assert len(boards) == 1
    assert boards[0]["name"] == "Main Board"


def test_create_and_delete_board(client: TestClient) -> None:
    login(client)
    create = client.post("/api/boards", json={"name": "Sprint Board"})
    assert create.status_code == 200
    new_board = create.json()
    assert new_board["name"] == "Sprint Board"
    assert len(new_board["columns"]) == 5

    boards = client.get("/api/boards").json()["boards"]
    assert len(boards) == 2

    delete = client.delete(f"/api/boards/{new_board['boardId']}")
    assert delete.status_code == 200

    boards_after = client.get("/api/boards").json()["boards"]
    assert len(boards_after) == 1


def test_cannot_delete_last_board(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.delete(f"/api/boards/{board_id}")
    assert response.status_code == 400
    assert "Cannot delete the last board" in response.json()["detail"]


def test_create_board_rejects_duplicate_name(client: TestClient) -> None:
    login(client)
    response = client.post("/api/boards", json={"name": "Main Board"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_ai_chat_applies_updates_atomically(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    first_column_id = board["columns"][0]["id"]
    first_card_id = board["columns"][0]["cardIds"][0]

    import app.main as main_module

    def fake_chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
        return {
            "model": "openai/gpt-oss-120b",
            "response": (
                "{"
                '"assistantMessage":"Applied updates",'
                '"updates":['
                '{"type":"rename_column","columnId":"' + first_column_id + '","title":"Ideas"},'
                '{"type":"update_card","cardId":"' + first_card_id + '","title":"Card retitled","details":"Updated by AI"}'
                "]"
                "}"
            ),
        }

    monkeypatch.setattr(main_module.openrouter, "chat_completion", fake_chat_completion)

    response = client.post("/api/ai/chat", json={"message": "please tidy this board", "boardId": board_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["assistantMessage"] == "Applied updates"
    assert payload["appliedUpdates"] is True
    assert payload["updateCount"] == 2
    assert payload["updatesError"] is None

    refreshed = client.get(f"/api/board/{board_id}").json()
    assert refreshed["columns"][0]["title"] == "Ideas"
    assert refreshed["cards"][first_card_id]["title"] == "Card retitled"


def test_ai_chat_rejects_malformed_ai_output(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    board_id = get_board_id(client)

    import app.main as main_module

    def fake_chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
        return {
            "model": "openai/gpt-oss-120b",
            "response": "not json",
        }

    monkeypatch.setattr(main_module.openrouter, "chat_completion", fake_chat_completion)

    response = client.post("/api/ai/chat", json={"message": "do something", "boardId": board_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["appliedUpdates"] is False
    assert payload["updateCount"] == 0
    assert "non-JSON" in payload["updatesError"]


def test_chat_history_endpoint_returns_persisted_messages(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    board_id = get_board_id(client)

    import app.main as main_module

    def fake_chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
        return {
            "model": "openai/gpt-oss-120b",
            "response": '{"assistantMessage":"Acknowledged","updates":[]}',
        }

    monkeypatch.setattr(main_module.openrouter, "chat_completion", fake_chat_completion)

    first = client.post("/api/ai/chat", json={"message": "first question", "boardId": board_id})
    assert first.status_code == 200

    history = client.get(f"/api/chat/{board_id}")
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert any(item["role"] == "user" and item["content"] == "first question" for item in messages)
    assert any(item["role"] == "assistant" and item["content"] == "Acknowledged" for item in messages)


# --- Admin endpoint tests ---


def test_admin_list_users(client: TestClient) -> None:
    login(client)
    response = client.get("/api/admin/users")
    assert response.status_code == 200
    users = response.json()["users"]
    assert len(users) >= 1
    assert any(u["username"] == "user" for u in users)


def test_admin_create_user(client: TestClient) -> None:
    login(client)
    response = client.post(
        "/api/admin/users",
        json={"username": "newuser", "password": "newpass", "role": "user"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "newuser"
    assert payload["role"] == "user"
    assert payload["suspended"] is False


def test_admin_create_user_duplicate_rejected(client: TestClient) -> None:
    login(client)
    response = client.post(
        "/api/admin/users",
        json={"username": "user", "password": "pass", "role": "user"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_admin_update_user(client: TestClient) -> None:
    login(client)
    # Create a user to update
    create = client.post(
        "/api/admin/users",
        json={"username": "toupdate", "password": "pass", "role": "user"},
    )
    user_id = create.json()["id"]

    response = client.put(
        f"/api/admin/users/{user_id}",
        json={"username": "updated_name"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "updated_name"


def test_admin_update_user_not_found(client: TestClient) -> None:
    login(client)
    response = client.put(
        "/api/admin/users/99999",
        json={"username": "nobody"},
    )
    assert response.status_code == 404


def test_admin_cannot_suspend_self(client: TestClient) -> None:
    login(client)
    # Get admin's user id
    users = client.get("/api/admin/users").json()["users"]
    admin_user = next(u for u in users if u["username"] == "user")

    response = client.put(
        f"/api/admin/users/{admin_user['id']}",
        json={"suspended": True},
    )
    assert response.status_code == 400
    assert "Cannot suspend yourself" in response.json()["detail"]


def test_admin_cannot_remove_own_admin_role(client: TestClient) -> None:
    login(client)
    users = client.get("/api/admin/users").json()["users"]
    admin_user = next(u for u in users if u["username"] == "user")

    response = client.put(
        f"/api/admin/users/{admin_user['id']}",
        json={"role": "user"},
    )
    assert response.status_code == 400
    assert "Cannot remove your own admin role" in response.json()["detail"]


def test_admin_delete_user(client: TestClient) -> None:
    login(client)
    create = client.post(
        "/api/admin/users",
        json={"username": "todelete", "password": "pass", "role": "user"},
    )
    user_id = create.json()["id"]

    response = client.delete(f"/api/admin/users/{user_id}")
    assert response.status_code == 200

    users = client.get("/api/admin/users").json()["users"]
    assert not any(u["id"] == user_id for u in users)


def test_admin_cannot_delete_self(client: TestClient) -> None:
    login(client)
    users = client.get("/api/admin/users").json()["users"]
    admin_user = next(u for u in users if u["username"] == "user")

    response = client.delete(f"/api/admin/users/{admin_user['id']}")
    assert response.status_code == 400
    assert "Cannot delete yourself" in response.json()["detail"]


def test_admin_delete_user_not_found(client: TestClient) -> None:
    login(client)
    response = client.delete("/api/admin/users/99999")
    assert response.status_code == 404


def test_admin_endpoints_require_admin_role(client: TestClient) -> None:
    login(client)
    # Create a non-admin user
    client.post(
        "/api/admin/users",
        json={"username": "regular", "password": "pass", "role": "user"},
    )
    # Login as that user
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/login",
        json={"username": "regular", "password": "pass"},
    )

    assert client.get("/api/admin/users").status_code == 403
    assert client.post("/api/admin/users", json={"username": "x", "password": "p"}).status_code == 403
    assert client.put("/api/admin/users/1", json={"username": "x"}).status_code == 403
    assert client.delete("/api/admin/users/1").status_code == 403


# --- Suspended user tests ---


def test_suspended_user_cannot_login(client: TestClient) -> None:
    login(client)
    create = client.post(
        "/api/admin/users",
        json={"username": "suspended_user", "password": "pass", "role": "user"},
    )
    user_id = create.json()["id"]

    # Suspend the user
    client.put(f"/api/admin/users/{user_id}", json={"suspended": True})

    # Logout and try to login as suspended user
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/login",
        json={"username": "suspended_user", "password": "pass"},
    )
    assert response.status_code == 403
    assert "suspended" in response.json()["detail"].lower()


def test_suspended_user_session_check_returns_unauthenticated(client: TestClient) -> None:
    login(client)
    create = client.post(
        "/api/admin/users",
        json={"username": "willsuspend", "password": "pass", "role": "user"},
    )
    user_id = create.json()["id"]
    client.post("/api/auth/logout")

    # Login as the user first
    client.post(
        "/api/auth/login",
        json={"username": "willsuspend", "password": "pass"},
    )
    session = client.get("/api/auth/session")
    assert session.json()["authenticated"] is True

    # Now suspend via admin (login as admin)
    client.post("/api/auth/logout")
    login(client)
    client.put(f"/api/admin/users/{user_id}", json={"suspended": True})
    client.post("/api/auth/logout")

    # Login as suspended user should fail
    response = client.post(
        "/api/auth/login",
        json={"username": "willsuspend", "password": "pass"},
    )
    assert response.status_code == 403


# --- Validation/error path tests ---


def test_update_board_not_found(client: TestClient) -> None:
    login(client)
    response = client.put("/api/board/99999", json={"name": "New Name"})
    assert response.status_code == 404


def test_update_board_empty_name(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.put(f"/api/board/{board_id}", json={"name": "   "})
    assert response.status_code == 400


def test_rename_column_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.patch(
        f"/api/boards/{board_id}/columns/99999",
        json={"title": "New Title"},
    )
    assert response.status_code == 404


def test_rename_column_empty_title(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    col_id = board["columns"][0]["id"]
    response = client.patch(
        f"/api/boards/{board_id}/columns/{col_id}",
        json={"title": "   "},
    )
    assert response.status_code == 400


def test_create_card_column_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": "99999", "title": "Card"},
    )
    assert response.status_code == 404


def test_create_card_empty_title(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    col_id = board["columns"][0]["id"]
    response = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "   "},
    )
    assert response.status_code == 400


def test_update_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.put(
        f"/api/boards/{board_id}/cards/99999",
        json={"title": "Updated"},
    )
    assert response.status_code == 404


def test_update_card_empty_title(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]
    response = client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "   "},
    )
    assert response.status_code == 400


def test_delete_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.delete(f"/api/boards/{board_id}/cards/99999")
    assert response.status_code == 404


def test_move_card_validation_error(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]
    response = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/move",
        json={"toColumnId": "99999", "toIndex": 0},
    )
    assert response.status_code == 404


def test_move_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    col_id = board["columns"][0]["id"]
    response = client.post(
        f"/api/boards/{board_id}/cards/99999/move",
        json={"toColumnId": col_id, "toIndex": 0},
    )
    assert response.status_code == 404


def test_get_board_not_found(client: TestClient) -> None:
    login(client)
    response = client.get("/api/board/99999")
    assert response.status_code == 404


def test_delete_board_not_found(client: TestClient) -> None:
    login(client)
    response = client.delete("/api/boards/99999")
    assert response.status_code == 404


def test_ai_chat_empty_message(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.post("/api/ai/chat", json={"message": "   ", "boardId": board_id})
    assert response.status_code == 400
    assert "message cannot be empty" in response.json()["detail"]


def test_ai_chat_schema_validation_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    board_id = get_board_id(client)

    import app.main as main_module

    def fake_chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
        return {
            "model": "openai/gpt-oss-120b",
            "response": '{"assistantMessage":"","updates":[]}',
        }

    monkeypatch.setattr(main_module.openrouter, "chat_completion", fake_chat_completion)

    response = client.post("/api/ai/chat", json={"message": "test", "boardId": board_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["appliedUpdates"] is False
    assert payload["updatesError"] is not None
    assert "assistantMessage" in payload["updatesError"]


def test_ai_chat_code_fenced_json_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    board_id = get_board_id(client)

    import app.main as main_module

    def fake_chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
        return {
            "model": "openai/gpt-oss-120b",
            "response": '```json\n{"assistantMessage":"Wrapped in code fence","updates":[]}\n```',
        }

    monkeypatch.setattr(main_module.openrouter, "chat_completion", fake_chat_completion)

    response = client.post("/api/ai/chat", json={"message": "help", "boardId": board_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["assistantMessage"] == "Wrapped in code fence"


def test_ai_chat_update_apply_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    login(client)
    board_id = get_board_id(client)

    import app.main as main_module

    def fake_chat_completion(prompt: str, timeout_seconds: float = 20.0) -> dict[str, str]:
        return {
            "model": "openai/gpt-oss-120b",
            "response": '{"assistantMessage":"Will try updates","updates":[{"type":"delete_card","cardId":"99999"}]}',
        }

    monkeypatch.setattr(main_module.openrouter, "chat_completion", fake_chat_completion)

    response = client.post("/api/ai/chat", json={"message": "delete a card", "boardId": board_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["appliedUpdates"] is False
    assert payload["updateCount"] == 0
    assert payload["updatesError"] is not None


def test_get_chat_board_not_found(client: TestClient) -> None:
    login(client)
    response = client.get("/api/chat/99999")
    assert response.status_code == 404


# --- Rate limiting ---


def test_login_rate_limit_blocks_excess_attempts(client: TestClient) -> None:
    import app.routers.auth as auth_module

    auth_module._LOGIN_RATE_LIMIT_MAX = 3

    for _ in range(3):
        client.post("/api/auth/login", json={"username": "user", "password": "wrong"})

    response = client.post("/api/auth/login", json={"username": "user", "password": "password"})
    assert response.status_code == 429
    assert "Too many login attempts" in response.json()["detail"]


def test_login_rate_limit_resets_after_window(client: TestClient) -> None:
    import app.routers.auth as auth_module

    auth_module._LOGIN_RATE_LIMIT_MAX = 2
    auth_module._LOGIN_RATE_LIMIT_WINDOW = 0  # zero-second window: all old attempts expire immediately

    for _ in range(2):
        client.post("/api/auth/login", json={"username": "user", "password": "wrong"})

    # Window has expired, so this should succeed
    response = client.post("/api/auth/login", json={"username": "user", "password": "password"})
    assert response.status_code == 200


# --- CORS ---


def test_cors_no_header_when_origins_not_configured(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_header_present_when_origin_configured(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PM_DB_PATH", str(tmp_path / "db-cors.sqlite"))
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")
    import app.main as main_module
    reload(main_module)
    cors_client = TestClient(main_module.app)
    response = cors_client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


# --- Input length validation ---


def test_login_rejects_oversized_username(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "x" * 101, "password": "pw"})
    assert response.status_code == 422


def test_create_board_rejects_oversized_name(client: TestClient) -> None:
    login(client)
    response = client.post("/api/boards", json={"name": "x" * 257})
    assert response.status_code == 422


def test_create_card_rejects_oversized_title(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]
    response = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "x" * 513},
    )
    assert response.status_code == 422


def test_create_card_rejects_oversized_details(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]
    response = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "ok", "details": "x" * 10001},
    )
    assert response.status_code == 422


def test_ai_chat_rejects_oversized_message(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.post("/api/ai/chat", json={"message": "x" * 4001, "boardId": board_id})
    assert response.status_code == 422


def test_admin_create_user_rejects_oversized_username(client: TestClient) -> None:
    login(client)
    response = client.post(
        "/api/admin/users",
        json={"username": "x" * 101, "password": "pw", "role": "user"},
    )
    assert response.status_code == 422


# --- Self-registration ---


def test_register_creates_suspended_account(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "mypassword"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "newuser"
    assert body["role"] == "user"
    assert body["suspended"] is True
    assert "administrator" in body["message"].lower()


def test_register_suspended_user_cannot_login(client: TestClient) -> None:
    client.post("/api/auth/register", json={"username": "pending", "password": "pass"})
    response = client.post("/api/auth/login", json={"username": "pending", "password": "pass"})
    assert response.status_code == 403
    assert "suspended" in response.json()["detail"].lower()


def test_register_duplicate_username_rejected(client: TestClient) -> None:
    client.post("/api/auth/register", json={"username": "dupuser", "password": "pass"})
    response = client.post("/api/auth/register", json={"username": "dupuser", "password": "pass2"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_register_empty_username_rejected(client: TestClient) -> None:
    response = client.post("/api/auth/register", json={"username": "  ", "password": "pass"})
    assert response.status_code == 400


def test_register_admin_can_activate_registered_user(client: TestClient) -> None:
    client.post("/api/auth/register", json={"username": "activateme", "password": "pass"})

    # Admin activates the user by unsuspending
    login(client)
    users = client.get("/api/admin/users").json()["users"]
    new_user = next(u for u in users if u["username"] == "activateme")
    assert new_user["suspended"] is True

    client.put(f"/api/admin/users/{new_user['id']}", json={"suspended": False})
    client.post("/api/auth/logout")

    # Now the user can log in
    response = client.post("/api/auth/login", json={"username": "activateme", "password": "pass"})
    assert response.status_code == 200


# --- Card metadata: due_date, priority, labels ---


def test_create_card_with_metadata(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    cols = client.get(f"/api/board/{board_id}").json()["columns"]
    col_id = cols[0]["id"]

    response = client.post(
        f"/api/boards/{board_id}/cards",
        json={
            "columnId": col_id,
            "title": "Metadata card",
            "details": "Some details",
            "due_date": "2026-06-30",
            "priority": "high",
            "labels": ["frontend", "bug"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["due_date"] == "2026-06-30"
    assert body["priority"] == "high"
    assert body["labels"] == ["frontend", "bug"]


def test_update_card_clears_metadata(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    col_id = board["columns"][0]["id"]
    card_id = board["columns"][0]["cardIds"][0]

    # Set metadata
    client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "Card", "details": "", "due_date": "2026-06-30", "priority": "low", "labels": ["x"]},
    )

    # Clear metadata
    response = client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "Card", "details": "", "due_date": None, "priority": None, "labels": []},
    )
    assert response.status_code == 200
    assert response.json()["due_date"] is None
    assert response.json()["priority"] is None
    assert response.json()["labels"] == []


def test_board_payload_includes_card_metadata(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    cols = client.get(f"/api/board/{board_id}").json()["columns"]
    col_id = cols[0]["id"]

    client.post(
        f"/api/boards/{board_id}/cards",
        json={
            "columnId": col_id,
            "title": "Tagged",
            "details": "",
            "due_date": "2026-12-31",
            "priority": "critical",
            "labels": ["release"],
        },
    )

    board = client.get(f"/api/board/{board_id}").json()
    cards = board["cards"]
    tagged = next(c for c in cards.values() if c["title"] == "Tagged")
    assert tagged["due_date"] == "2026-12-31"
    assert tagged["priority"] == "critical"
    assert tagged["labels"] == ["release"]


def test_create_card_invalid_priority_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]
    response = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Bad", "details": "", "priority": "urgent"},
    )
    assert response.status_code == 422


@pytest.mark.skipif(
    os.getenv("PM_RUN_OPENROUTER_SMOKE") != "1" or not os.getenv("OPENROUTER_API_KEY"),
    reason="Set PM_RUN_OPENROUTER_SMOKE=1 and OPENROUTER_API_KEY to run real connectivity smoke test",
)
def test_ai_connectivity_real_smoke(client: TestClient) -> None:
    login(client)
    response = None
    for _ in range(3):
        response = client.post("/api/ai/connectivity", json={"prompt": "2+2"})
        if response.status_code == 200:
            break
        if response.status_code in (502, 504):
            time.sleep(1)
            continue
        break

    assert response is not None
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert isinstance(payload["response"], str)
    assert payload["response"].strip() != ""


# --- Card assignment ---


def test_list_assignable_users_requires_auth(client: TestClient) -> None:
    response = client.get("/api/users")
    assert response.status_code == 401


def test_list_assignable_users(client: TestClient) -> None:
    login(client)
    response = client.get("/api/users")
    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)
    # seeded admin user is unsuspended
    assert any(u["username"] == "user" for u in users)
    assert all("id" in u and "username" in u for u in users)


def test_suspended_user_excluded_from_assignable(client: TestClient) -> None:
    login(client)
    create = client.post(
        "/api/admin/users",
        json={"username": "susp_assign", "password": "pass", "role": "user"},
    )
    uid = create.json()["id"]
    client.put(f"/api/admin/users/{uid}", json={"suspended": True})

    users = client.get("/api/users").json()
    assert not any(u["username"] == "susp_assign" for u in users)


def test_create_card_with_assignee(client: TestClient) -> None:
    login(client)
    # create a second user to assign
    client.post("/api/admin/users", json={"username": "assignee", "password": "pass", "role": "user"})
    users = client.get("/api/users").json()
    assignee = next(u for u in users if u["username"] == "assignee")

    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    response = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Assigned card", "details": "", "assignee_id": assignee["id"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assignee_id"] == assignee["id"]


def test_board_payload_includes_assignee_username(client: TestClient) -> None:
    login(client)
    client.post("/api/admin/users", json={"username": "assignee2", "password": "pass", "role": "user"})
    users = client.get("/api/users").json()
    assignee = next(u for u in users if u["username"] == "assignee2")

    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Assigned", "details": "", "assignee_id": assignee["id"]},
    )

    board = client.get(f"/api/board/{board_id}").json()
    assigned_card = next(c for c in board["cards"].values() if c["title"] == "Assigned")
    assert assigned_card["assignee_id"] == assignee["id"]
    assert assigned_card["assignee_username"] == "assignee2"


def test_assignee_clears_when_user_deleted(client: TestClient) -> None:
    login(client)
    create = client.post(
        "/api/admin/users",
        json={"username": "temp_assignee", "password": "pass", "role": "user"},
    )
    uid = create.json()["id"]
    users = client.get("/api/users").json()
    assignee = next(u for u in users if u["id"] == uid)

    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]
    card_resp = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Will lose assignee", "details": "", "assignee_id": assignee["id"]},
    )
    card_id = card_resp.json()["id"]

    # Delete the user
    client.delete(f"/api/admin/users/{uid}")

    board = client.get(f"/api/board/{board_id}").json()
    assert board["cards"][card_id]["assignee_id"] is None
    assert board["cards"][card_id]["assignee_username"] is None


# --- Board statistics ---


def test_board_stats_requires_auth(client: TestClient) -> None:
    response = client.get("/api/boards/1/stats")
    assert response.status_code == 401


def test_board_stats_not_found(client: TestClient) -> None:
    login(client)
    response = client.get("/api/boards/99999/stats")
    assert response.status_code == 404


def test_board_stats_returns_correct_counts(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)

    response = client.get(f"/api/boards/{board_id}/stats")
    assert response.status_code == 200
    stats = response.json()

    assert "total_cards" in stats
    assert "overdue_count" in stats
    assert "cards_per_column" in stats
    assert "cards_by_priority" in stats
    assert isinstance(stats["total_cards"], int)
    assert stats["total_cards"] >= 8  # seeded cards
    assert isinstance(stats["overdue_count"], int)
    assert isinstance(stats["cards_per_column"], list)
    assert len(stats["cards_per_column"]) == 5


def test_board_stats_reflect_card_changes(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    initial = client.get(f"/api/boards/{board_id}/stats").json()["total_cards"]

    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]
    client.post(f"/api/boards/{board_id}/cards", json={"columnId": col_id, "title": "New", "details": ""})

    updated = client.get(f"/api/boards/{board_id}/stats").json()["total_cards"]
    assert updated == initial + 1


def test_board_stats_overdue_count(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Overdue card", "details": "", "due_date": "2020-01-01"},
    )

    stats = client.get(f"/api/boards/{board_id}/stats").json()
    assert stats["overdue_count"] >= 1


# --- Card comments ---


def test_comments_require_auth(client: TestClient) -> None:
    response = client.get("/api/boards/1/cards/1/comments")
    assert response.status_code == 401


def test_list_comments_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.get(f"/api/boards/{board_id}/cards/99999/comments")
    assert response.status_code == 404


def test_add_and_list_comments(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    add = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/comments",
        json={"content": "First comment"},
    )
    assert add.status_code == 200
    added = add.json()
    assert added["content"] == "First comment"
    assert added["author"] == "user"
    assert "id" in added
    assert "createdAt" in added

    comments = client.get(f"/api/boards/{board_id}/cards/{card_id}/comments").json()
    assert len(comments) == 1
    assert comments[0]["content"] == "First comment"


def test_add_multiple_comments_ordered_by_time(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    client.post(f"/api/boards/{board_id}/cards/{card_id}/comments", json={"content": "Alpha"})
    client.post(f"/api/boards/{board_id}/cards/{card_id}/comments", json={"content": "Beta"})

    comments = client.get(f"/api/boards/{board_id}/cards/{card_id}/comments").json()
    assert len(comments) >= 2
    contents = [c["content"] for c in comments]
    assert "Alpha" in contents
    assert "Beta" in contents
    assert contents.index("Alpha") < contents.index("Beta")


def test_add_comment_empty_content_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    response = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/comments",
        json={"content": "   "},
    )
    assert response.status_code == 400


def test_add_comment_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.post(
        f"/api/boards/{board_id}/cards/99999/comments",
        json={"content": "hello"},
    )
    assert response.status_code == 404


def test_comments_isolated_per_board(client: TestClient) -> None:
    login(client)
    b1 = get_board_id(client)
    card_id = client.get(f"/api/board/{b1}").json()["columns"][0]["cardIds"][0]

    # Add comment on board 1
    client.post(f"/api/boards/{b1}/cards/{card_id}/comments", json={"content": "Board1 comment"})

    # Create board 2 with its own card
    b2_resp = client.post("/api/boards", json={"name": "Second Board"})
    b2_id = b2_resp.json()["boardId"]
    b2_col_id = client.get(f"/api/board/{b2_id}").json()["columns"][0]["id"]
    b2_card_resp = client.post(
        f"/api/boards/{b2_id}/cards",
        json={"columnId": b2_col_id, "title": "Board2 card", "details": ""},
    )
    b2_card_id = b2_card_resp.json()["id"]

    b2_comments = client.get(f"/api/boards/{b2_id}/cards/{b2_card_id}/comments").json()
    assert not any(c["content"] == "Board1 comment" for c in b2_comments)

# --- Archive / restore cards ---


def test_archive_card_removes_from_board(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]

    response = client.delete(f"/api/boards/{board_id}/cards/{card_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"

    refreshed = client.get(f"/api/board/{board_id}").json()
    all_card_ids = [cid for col in refreshed["columns"] for cid in col["cardIds"]]
    assert card_id not in all_card_ids


def test_archived_cards_appear_in_archived_list(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]
    card_title = board["cards"][card_id]["title"]

    client.delete(f"/api/boards/{board_id}/cards/{card_id}")

    response = client.get(f"/api/boards/{board_id}/cards/archived")
    assert response.status_code == 200
    archived = response.json()
    assert any(c["id"] == card_id and c["title"] == card_title for c in archived)


def test_archived_list_requires_auth(client: TestClient) -> None:
    response = client.get("/api/boards/1/cards/archived")
    assert response.status_code == 401


def test_restore_card_returns_to_board(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]

    client.delete(f"/api/boards/{board_id}/cards/{card_id}")

    restore = client.post(f"/api/boards/{board_id}/cards/{card_id}/restore")
    assert restore.status_code == 200
    assert restore.json()["id"] == card_id

    refreshed = client.get(f"/api/board/{board_id}").json()
    all_card_ids = [cid for col in refreshed["columns"] for cid in col["cardIds"]]
    assert card_id in all_card_ids


def test_restore_requires_auth(client: TestClient) -> None:
    response = client.post("/api/boards/1/cards/1/restore")
    assert response.status_code == 401


def test_restore_non_archived_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]

    # card is NOT archived — restore should 404
    response = client.post(f"/api/boards/{board_id}/cards/{card_id}/restore")
    assert response.status_code == 404


def test_permanent_delete_removes_archived_card(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]

    client.delete(f"/api/boards/{board_id}/cards/{card_id}")

    del_resp = client.delete(f"/api/boards/{board_id}/cards/{card_id}/permanent")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    archived = client.get(f"/api/boards/{board_id}/cards/archived").json()
    assert not any(c["id"] == card_id for c in archived)


def test_permanent_delete_requires_archive_first(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]

    # Not archived — permanent delete should 404
    response = client.delete(f"/api/boards/{board_id}/cards/{card_id}/permanent")
    assert response.status_code == 404


def test_board_stats_exclude_archived_cards(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    stats_before = client.get(f"/api/boards/{board_id}/stats").json()
    total_before = stats_before["total_cards"]

    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]
    client.delete(f"/api/boards/{board_id}/cards/{card_id}")

    stats_after = client.get(f"/api/boards/{board_id}/stats").json()
    assert stats_after["total_cards"] == total_before - 1


# --- Board export ---


def test_export_board_json(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)

    response = client.get(f"/api/boards/{board_id}/export?format=json")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    body = response.json()
    assert "board" in body
    assert "columns" in body
    assert "cards" in body
    assert "exportedAt" in body
    assert isinstance(body["cards"], list)
    assert len(body["cards"]) > 0


def test_export_board_csv(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)

    response = client.get(f"/api/boards/{board_id}/export?format=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    lines = response.text.strip().split("\n")
    # First line is headers
    assert "column" in lines[0].lower()
    assert "title" in lines[0].lower()
    # At least one data row (seeded cards)
    assert len(lines) > 1


def test_export_board_default_is_json(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)

    response = client.get(f"/api/boards/{board_id}/export")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


def test_export_board_requires_auth(client: TestClient) -> None:
    response = client.get("/api/boards/1/export")
    assert response.status_code == 401


def test_export_board_invalid_format(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.get(f"/api/boards/{board_id}/export?format=xlsx")
    assert response.status_code == 422


def test_export_excludes_archived_cards(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]
    card_title = board["cards"][card_id]["title"]

    client.delete(f"/api/boards/{board_id}/cards/{card_id}")

    response = client.get(f"/api/boards/{board_id}/export?format=json")
    body = response.json()
    titles = [c["title"] for c in body["cards"]]
    assert card_title not in titles


# --- Activity log ---


def test_activity_log_requires_auth(client: TestClient) -> None:
    response = client.get("/api/boards/1/activity")
    assert response.status_code == 401


def test_activity_log_records_create_card(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Activity test card", "details": ""},
    )

    response = client.get(f"/api/boards/{board_id}/activity")
    assert response.status_code == 200
    log = response.json()
    assert any(e["action"] == "create_card" and e["detail"] == "Activity test card" for e in log)


def test_activity_log_records_archive_and_restore(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]

    client.delete(f"/api/boards/{board_id}/cards/{card_id}")
    client.post(f"/api/boards/{board_id}/cards/{card_id}/restore")

    log = client.get(f"/api/boards/{board_id}/activity").json()
    actions = [e["action"] for e in log]
    assert "archive_card" in actions
    assert "restore_card" in actions


def test_activity_log_records_move_card(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    card_id = board["columns"][0]["cardIds"][0]
    target_col = board["columns"][1]["id"]

    client.post(
        f"/api/boards/{board_id}/cards/{card_id}/move",
        json={"toColumnId": target_col, "toIndex": 0},
    )

    log = client.get(f"/api/boards/{board_id}/activity").json()
    assert any(e["action"] == "move_card" for e in log)


def test_activity_log_actor_matches_logged_in_user(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Actor test", "details": ""},
    )

    log = client.get(f"/api/boards/{board_id}/activity").json()
    create_entry = next(e for e in log if e["action"] == "create_card" and e["detail"] == "Actor test")
    assert create_entry["actor"] == "user"


def test_activity_log_not_found_for_wrong_board(client: TestClient) -> None:
    login(client)
    response = client.get("/api/boards/99999/activity")
    assert response.status_code == 404


def test_activity_log_limit_param(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    for i in range(5):
        client.post(
            f"/api/boards/{board_id}/cards",
            json={"columnId": col_id, "title": f"Log card {i}", "details": ""},
        )

    log = client.get(f"/api/boards/{board_id}/activity?limit=3").json()
    assert len(log) <= 3


# --- Estimate ---


def test_create_card_with_estimate(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    response = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Estimated card", "details": "", "estimate": 5},
    )
    assert response.status_code == 200
    assert response.json()["estimate"] == 5


def test_update_card_sets_estimate(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    response = client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "Updated", "details": "", "estimate": 8},
    )
    assert response.status_code == 200
    assert response.json()["estimate"] == 8


def test_update_card_clears_estimate(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "Set estimate", "details": "", "estimate": 3},
    )
    response = client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "Clear estimate", "details": "", "estimate": None},
    )
    assert response.status_code == 200
    assert response.json()["estimate"] is None


def test_create_card_negative_estimate_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    response = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Bad estimate", "details": "", "estimate": -1},
    )
    assert response.status_code == 422


def test_board_payload_includes_estimate(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Est card", "details": "", "estimate": 13},
    )
    board = client.get(f"/api/board/{board_id}").json()
    cards = list(board["cards"].values())
    est_card = next(c for c in cards if c["title"] == "Est card")
    assert est_card["estimate"] == 13


def test_stats_include_total_estimate(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Est A", "details": "", "estimate": 3},
    )
    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Est B", "details": "", "estimate": 5},
    )

    stats = client.get(f"/api/boards/{board_id}/stats").json()
    assert "total_estimate" in stats
    assert stats["total_estimate"] >= 8
    assert "total_estimate" in stats["cards_per_column"][0]


def test_export_includes_estimate(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Export est", "details": "", "estimate": 7},
    )

    export = client.get(f"/api/boards/{board_id}/export?format=json").json()
    est_card = next(c for c in export["cards"] if c["title"] == "Export est")
    assert est_card["estimate"] == 7


# --- Checklists ---


def test_checklist_requires_auth(client: TestClient) -> None:
    response = client.get("/api/boards/1/cards/1/checklist")
    assert response.status_code == 401


def test_checklist_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.get(f"/api/boards/{board_id}/cards/99999/checklist")
    assert response.status_code == 404


def test_add_and_list_checklist_items(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    add = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/checklist",
        json={"text": "Write tests"},
    )
    assert add.status_code == 200
    item = add.json()
    assert item["text"] == "Write tests"
    assert item["checked"] is False
    assert "id" in item
    assert "position" in item

    items = client.get(f"/api/boards/{board_id}/cards/{card_id}/checklist").json()
    assert len(items) == 1
    assert items[0]["text"] == "Write tests"


def test_add_multiple_checklist_items_ordered_by_position(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    client.post(f"/api/boards/{board_id}/cards/{card_id}/checklist", json={"text": "First"})
    client.post(f"/api/boards/{board_id}/cards/{card_id}/checklist", json={"text": "Second"})

    items = client.get(f"/api/boards/{board_id}/cards/{card_id}/checklist").json()
    assert len(items) == 2
    assert items[0]["text"] == "First"
    assert items[1]["text"] == "Second"
    assert items[0]["position"] < items[1]["position"]


def test_check_and_uncheck_checklist_item(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    item_id = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/checklist",
        json={"text": "Do the thing"},
    ).json()["id"]

    checked = client.put(
        f"/api/boards/{board_id}/cards/{card_id}/checklist/{item_id}",
        json={"checked": True},
    )
    assert checked.status_code == 200
    assert checked.json()["checked"] is True

    unchecked = client.put(
        f"/api/boards/{board_id}/cards/{card_id}/checklist/{item_id}",
        json={"checked": False},
    )
    assert unchecked.status_code == 200
    assert unchecked.json()["checked"] is False


def test_update_checklist_item_text(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    item_id = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/checklist",
        json={"text": "Original text"},
    ).json()["id"]

    updated = client.put(
        f"/api/boards/{board_id}/cards/{card_id}/checklist/{item_id}",
        json={"text": "Updated text"},
    )
    assert updated.status_code == 200
    assert updated.json()["text"] == "Updated text"


def test_delete_checklist_item(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    item_id = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/checklist",
        json={"text": "To be deleted"},
    ).json()["id"]

    delete = client.delete(f"/api/boards/{board_id}/cards/{card_id}/checklist/{item_id}")
    assert delete.status_code == 200

    items = client.get(f"/api/boards/{board_id}/cards/{card_id}/checklist").json()
    assert not any(i["id"] == item_id for i in items)


def test_delete_checklist_item_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    response = client.delete(f"/api/boards/{board_id}/cards/{card_id}/checklist/99999")
    assert response.status_code == 404


def test_add_checklist_item_empty_text_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    response = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/checklist",
        json={"text": "   "},
    )
    assert response.status_code == 400


def test_checklist_items_deleted_with_card(client: TestClient) -> None:
    """Checklist items are cascade-deleted when the card is permanently deleted."""
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    card_resp = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Card with checklist", "details": ""},
    )
    card_id = card_resp.json()["id"]

    client.post(
        f"/api/boards/{board_id}/cards/{card_id}/checklist",
        json={"text": "Item 1"},
    )

    # Archive then permanently delete
    client.delete(f"/api/boards/{board_id}/cards/{card_id}")
    client.delete(f"/api/boards/{board_id}/cards/{card_id}/permanent")

    # Card is gone; list should return 404
    response = client.get(f"/api/boards/{board_id}/cards/{card_id}/checklist")
    assert response.status_code == 404


# --- Card dependencies ---


def _get_two_card_ids(client: TestClient) -> tuple[str, str]:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    col = board["columns"][0]
    card_a = col["cardIds"][0]
    card_b = col["cardIds"][1]
    return board_id, card_a, card_b  # type: ignore[return-value]


def test_dependencies_require_auth(client: TestClient) -> None:
    response = client.get("/api/boards/1/cards/1/dependencies")
    assert response.status_code == 401


def test_get_dependencies_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.get(f"/api/boards/{board_id}/cards/99999/dependencies")
    assert response.status_code == 404


def test_add_and_get_dependency(client: TestClient) -> None:
    board_id, card_a, card_b = _get_two_card_ids(client)

    response = client.post(
        f"/api/boards/{board_id}/dependencies",
        json={"blocker_id": card_a, "blocked_id": card_b},
    )
    assert response.status_code == 200
    dep = response.json()
    assert dep["blocker_id"] == card_a
    assert dep["blocked_id"] == card_b
    assert "id" in dep

    deps_a = client.get(f"/api/boards/{board_id}/cards/{card_a}/dependencies").json()
    assert len(deps_a["blocks"]) == 1
    assert deps_a["blocks"][0]["card_id"] == card_b
    assert deps_a["blocked_by"] == []

    deps_b = client.get(f"/api/boards/{board_id}/cards/{card_b}/dependencies").json()
    assert len(deps_b["blocked_by"]) == 1
    assert deps_b["blocked_by"][0]["card_id"] == card_a
    assert deps_b["blocks"] == []


def test_blocked_card_has_is_blocked_true_in_board_payload(client: TestClient) -> None:
    board_id, card_a, card_b = _get_two_card_ids(client)

    client.post(
        f"/api/boards/{board_id}/dependencies",
        json={"blocker_id": card_a, "blocked_id": card_b},
    )

    board = client.get(f"/api/board/{board_id}").json()
    assert board["cards"][card_a]["is_blocked"] is False
    assert board["cards"][card_b]["is_blocked"] is True


def test_remove_dependency(client: TestClient) -> None:
    board_id, card_a, card_b = _get_two_card_ids(client)

    dep_id = client.post(
        f"/api/boards/{board_id}/dependencies",
        json={"blocker_id": card_a, "blocked_id": card_b},
    ).json()["id"]

    delete = client.delete(f"/api/boards/{board_id}/dependencies/{dep_id}")
    assert delete.status_code == 200

    deps = client.get(f"/api/boards/{board_id}/cards/{card_a}/dependencies").json()
    assert deps["blocks"] == []


def test_dependency_self_reference_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["cardIds"][0]

    response = client.post(
        f"/api/boards/{board_id}/dependencies",
        json={"blocker_id": card_id, "blocked_id": card_id},
    )
    assert response.status_code == 400
    assert "itself" in response.json()["detail"].lower()


def test_duplicate_dependency_rejected(client: TestClient) -> None:
    board_id, card_a, card_b = _get_two_card_ids(client)

    client.post(
        f"/api/boards/{board_id}/dependencies",
        json={"blocker_id": card_a, "blocked_id": card_b},
    )
    response = client.post(
        f"/api/boards/{board_id}/dependencies",
        json={"blocker_id": card_a, "blocked_id": card_b},
    )
    assert response.status_code == 400


def test_circular_dependency_rejected(client: TestClient) -> None:
    board_id, card_a, card_b = _get_two_card_ids(client)

    # A blocks B
    client.post(
        f"/api/boards/{board_id}/dependencies",
        json={"blocker_id": card_a, "blocked_id": card_b},
    )

    # B blocks A (circular) — should be rejected
    response = client.post(
        f"/api/boards/{board_id}/dependencies",
        json={"blocker_id": card_b, "blocked_id": card_a},
    )
    assert response.status_code == 400
    assert "circular" in response.json()["detail"].lower()


def test_transitive_circular_dependency_rejected(client: TestClient) -> None:
    """A blocks B, B blocks C — C blocks A should be rejected."""
    login(client)
    board_id = get_board_id(client)
    col_id = client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]

    c1 = client.post(f"/api/boards/{board_id}/cards", json={"columnId": col_id, "title": "C1", "details": ""}).json()["id"]
    c2 = client.post(f"/api/boards/{board_id}/cards", json={"columnId": col_id, "title": "C2", "details": ""}).json()["id"]
    c3 = client.post(f"/api/boards/{board_id}/cards", json={"columnId": col_id, "title": "C3", "details": ""}).json()["id"]

    client.post(f"/api/boards/{board_id}/dependencies", json={"blocker_id": c1, "blocked_id": c2})
    client.post(f"/api/boards/{board_id}/dependencies", json={"blocker_id": c2, "blocked_id": c3})

    response = client.post(f"/api/boards/{board_id}/dependencies", json={"blocker_id": c3, "blocked_id": c1})
    assert response.status_code == 400
    assert "circular" in response.json()["detail"].lower()


def test_remove_dependency_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.delete(f"/api/boards/{board_id}/dependencies/99999")
    assert response.status_code == 404


def test_add_dependency_requires_auth(client: TestClient) -> None:
    response = client.post("/api/boards/1/dependencies", json={"blocker_id": "1", "blocked_id": "2"})
    assert response.status_code == 401


def test_dependency_activity_logged(client: TestClient) -> None:
    board_id, card_a, card_b = _get_two_card_ids(client)

    client.post(
        f"/api/boards/{board_id}/dependencies",
        json={"blocker_id": card_a, "blocked_id": card_b},
    )

    log = client.get(f"/api/boards/{board_id}/activity").json()
    assert any(e["action"] == "add_dependency" for e in log)


# ── Sprint tests ──────────────────────────────────────────────────────────────

def _get_col_id(client: TestClient, board_id: str) -> str:
    return client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]


def test_list_sprints_empty(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.get(f"/api/boards/{board_id}/sprints")
    assert response.status_code == 200
    assert response.json() == []


def test_create_sprint(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.post(
        f"/api/boards/{board_id}/sprints",
        json={"name": "Sprint 1", "goal": "Ship MVP", "start_date": "2026-04-01", "end_date": "2026-04-14"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Sprint 1"
    assert data["goal"] == "Ship MVP"
    assert data["status"] == "planning"
    assert data["start_date"] == "2026-04-01"
    assert data["end_date"] == "2026-04-14"


def test_create_sprint_minimal(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.post(f"/api/boards/{board_id}/sprints", json={"name": "Minimal Sprint"})
    assert response.status_code == 200
    assert response.json()["name"] == "Minimal Sprint"


def test_create_sprint_duplicate_name_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    client.post(f"/api/boards/{board_id}/sprints", json={"name": "Dup Sprint"})
    response = client.post(f"/api/boards/{board_id}/sprints", json={"name": "Dup Sprint"})
    assert response.status_code == 400


def test_list_sprints_populated(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    client.post(f"/api/boards/{board_id}/sprints", json={"name": "S1"})
    client.post(f"/api/boards/{board_id}/sprints", json={"name": "S2"})
    sprints = client.get(f"/api/boards/{board_id}/sprints").json()
    assert len(sprints) == 2
    assert {s["name"] for s in sprints} == {"S1", "S2"}


def test_update_sprint(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "Old Name"}).json()["id"]
    response = client.put(
        f"/api/boards/{board_id}/sprints/{sprint_id}",
        json={"name": "New Name", "goal": "Updated goal"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["goal"] == "Updated goal"


def test_update_sprint_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.put(f"/api/boards/{board_id}/sprints/99999", json={"name": "X"})
    assert response.status_code == 404


def test_update_sprint_duplicate_name_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    client.post(f"/api/boards/{board_id}/sprints", json={"name": "A"})
    sid_b = client.post(f"/api/boards/{board_id}/sprints", json={"name": "B"}).json()["id"]
    response = client.put(f"/api/boards/{board_id}/sprints/{sid_b}", json={"name": "A"})
    assert response.status_code == 400


def test_delete_sprint_planning(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "Delete Me"}).json()["id"]
    response = client.delete(f"/api/boards/{board_id}/sprints/{sprint_id}")
    assert response.status_code == 200
    assert client.get(f"/api/boards/{board_id}/sprints").json() == []


def test_delete_sprint_active_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "Active S"}).json()["id"]
    client.post(f"/api/boards/{board_id}/sprints/{sprint_id}/start")
    response = client.delete(f"/api/boards/{board_id}/sprints/{sprint_id}")
    assert response.status_code == 400


def test_delete_sprint_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.delete(f"/api/boards/{board_id}/sprints/99999")
    assert response.status_code == 404


def test_start_sprint(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "To Start"}).json()["id"]
    response = client.post(f"/api/boards/{board_id}/sprints/{sprint_id}/start")
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_start_non_planning_sprint_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "S"}).json()["id"]
    client.post(f"/api/boards/{board_id}/sprints/{sprint_id}/start")
    # Try to start it again
    response = client.post(f"/api/boards/{board_id}/sprints/{sprint_id}/start")
    assert response.status_code == 400


def test_only_one_active_sprint_per_board(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    s1 = client.post(f"/api/boards/{board_id}/sprints", json={"name": "S1"}).json()["id"]
    s2 = client.post(f"/api/boards/{board_id}/sprints", json={"name": "S2"}).json()["id"]
    client.post(f"/api/boards/{board_id}/sprints/{s1}/start")
    response = client.post(f"/api/boards/{board_id}/sprints/{s2}/start")
    assert response.status_code == 400
    assert "active" in response.json()["detail"].lower()


def test_complete_sprint(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "To Complete"}).json()["id"]
    client.post(f"/api/boards/{board_id}/sprints/{sprint_id}/start")
    response = client.post(f"/api/boards/{board_id}/sprints/{sprint_id}/complete")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_complete_non_active_sprint_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "S"}).json()["id"]
    response = client.post(f"/api/boards/{board_id}/sprints/{sprint_id}/complete")
    assert response.status_code == 400


def test_update_completed_sprint_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sid = client.post(f"/api/boards/{board_id}/sprints", json={"name": "S"}).json()["id"]
    client.post(f"/api/boards/{board_id}/sprints/{sid}/start")
    client.post(f"/api/boards/{board_id}/sprints/{sid}/complete")
    response = client.put(f"/api/boards/{board_id}/sprints/{sid}", json={"name": "New"})
    assert response.status_code == 400


def test_get_sprint_stats(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = _get_col_id(client, board_id)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "Stats Sprint"}).json()["id"]
    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Card A", "details": "", "estimate": 3, "sprint_id": sprint_id},
    )
    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Card B", "details": "", "estimate": 5, "sprint_id": sprint_id},
    )
    response = client.get(f"/api/boards/{board_id}/sprints/{sprint_id}/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_cards"] == 2
    assert data["total_estimate"] == 8


def test_get_sprint_stats_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.get(f"/api/boards/{board_id}/sprints/99999/stats")
    assert response.status_code == 404


def test_assign_card_to_sprint(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = _get_col_id(client, board_id)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "Sprint X"}).json()["id"]
    card_id = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Sprint Card", "details": "", "sprint_id": sprint_id},
    ).json()["id"]
    board = client.get(f"/api/board/{board_id}").json()
    card = board["cards"][str(card_id)]
    assert card["sprint_id"] == str(sprint_id)
    assert card["sprint_name"] == "Sprint X"


def test_update_card_sprint_assignment(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = _get_col_id(client, board_id)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "Sprint Y"}).json()["id"]
    card_id = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Card", "details": ""},
    ).json()["id"]
    client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "Card", "details": "", "sprint_id": sprint_id},
    )
    board = client.get(f"/api/board/{board_id}").json()
    assert board["cards"][str(card_id)]["sprint_id"] == str(sprint_id)


def test_delete_sprint_unassigns_cards(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = _get_col_id(client, board_id)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "To Delete"}).json()["id"]
    card_id = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Card", "details": "", "sprint_id": sprint_id},
    ).json()["id"]
    client.delete(f"/api/boards/{board_id}/sprints/{sprint_id}")
    board = client.get(f"/api/board/{board_id}").json()
    assert board["cards"][str(card_id)]["sprint_id"] is None


def test_sprint_requires_auth(client: TestClient) -> None:
    response = client.get("/api/boards/1/sprints")
    assert response.status_code == 401


def test_start_sprint_requires_auth(client: TestClient) -> None:
    response = client.post("/api/boards/1/sprints/1/start")
    assert response.status_code == 401


def test_complete_sprint_requires_auth(client: TestClient) -> None:
    response = client.post("/api/boards/1/sprints/1/complete")
    assert response.status_code == 401


def test_sprint_activity_logged(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sprint_id = client.post(f"/api/boards/{board_id}/sprints", json={"name": "Log Sprint"}).json()["id"]
    client.post(f"/api/boards/{board_id}/sprints/{sprint_id}/start")
    client.post(f"/api/boards/{board_id}/sprints/{sprint_id}/complete")
    log = client.get(f"/api/boards/{board_id}/activity").json()
    actions = {e["action"] for e in log}
    assert "create_sprint" in actions
    assert "start_sprint" in actions
    assert "complete_sprint" in actions


def test_delete_completed_sprint(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sid = client.post(f"/api/boards/{board_id}/sprints", json={"name": "Done Sprint"}).json()["id"]
    client.post(f"/api/boards/{board_id}/sprints/{sid}/start")
    client.post(f"/api/boards/{board_id}/sprints/{sid}/complete")
    response = client.delete(f"/api/boards/{board_id}/sprints/{sid}")
    assert response.status_code == 200


# ── WIP limit tests ───────────────────────────────────────────────────────────

def _get_first_col_id(client: TestClient, board_id: str) -> str:
    return client.get(f"/api/board/{board_id}").json()["columns"][0]["id"]


def test_set_wip_limit(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    response = client.put(
        f"/api/boards/{board_id}/columns/{col_id}/wip-limit",
        json={"wip_limit": 3},
    )
    assert response.status_code == 200
    assert response.json()["wip_limit"] == 3


def test_wip_limit_reflected_in_board_payload(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    client.put(f"/api/boards/{board_id}/columns/{col_id}/wip-limit", json={"wip_limit": 5})
    board = client.get(f"/api/board/{board_id}").json()
    col = next(c for c in board["columns"] if c["id"] == col_id)
    assert col["wip_limit"] == 5


def test_clear_wip_limit(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    client.put(f"/api/boards/{board_id}/columns/{col_id}/wip-limit", json={"wip_limit": 3})
    response = client.put(
        f"/api/boards/{board_id}/columns/{col_id}/wip-limit",
        json={"wip_limit": None},
    )
    assert response.status_code == 200
    assert response.json()["wip_limit"] is None
    board = client.get(f"/api/board/{board_id}").json()
    col = next(c for c in board["columns"] if c["id"] == col_id)
    assert col["wip_limit"] is None


def test_wip_limit_zero_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    response = client.put(
        f"/api/boards/{board_id}/columns/{col_id}/wip-limit",
        json={"wip_limit": 0},
    )
    assert response.status_code == 422  # Pydantic validation (ge=1)


def test_wip_limit_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.put(
        f"/api/boards/{board_id}/columns/99999/wip-limit",
        json={"wip_limit": 3},
    )
    assert response.status_code == 404


def test_wip_limit_requires_auth(client: TestClient) -> None:
    response = client.put("/api/boards/1/columns/1/wip-limit", json={"wip_limit": 3})
    assert response.status_code == 401


def test_wip_limit_activity_logged(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    client.put(f"/api/boards/{board_id}/columns/{col_id}/wip-limit", json={"wip_limit": 4})
    log = client.get(f"/api/boards/{board_id}/activity").json()
    assert any(e["action"] == "set_wip_limit" for e in log)


def test_board_columns_default_no_wip_limit(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    for col in board["columns"]:
        assert col["wip_limit"] is None


# ── Time log tests ─────────────────────────────────────────────────────────────

def _create_card_simple(client: TestClient, board_id: str, title: str = "Test Card") -> str:
    col_id = _get_first_col_id(client, board_id)
    return client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": title, "details": ""},
    ).json()["id"]


def test_log_time(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    response = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/time-logs",
        json={"minutes": 60, "note": "Implemented feature"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["minutes"] == 60
    assert data["note"] == "Implemented feature"


def test_log_time_minimal(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    response = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/time-logs",
        json={"minutes": 30},
    )
    assert response.status_code == 200
    assert response.json()["minutes"] == 30


def test_log_time_zero_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    response = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/time-logs",
        json={"minutes": 0},
    )
    assert response.status_code == 422  # Pydantic validation


def test_log_time_over_limit_rejected(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    response = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/time-logs",
        json={"minutes": 481},
    )
    assert response.status_code == 422  # Pydantic validation (le=480)


def test_list_time_logs_empty(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    response = client.get(f"/api/boards/{board_id}/cards/{card_id}/time-logs")
    assert response.status_code == 200
    assert response.json() == []


def test_list_time_logs_populated(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    client.post(f"/api/boards/{board_id}/cards/{card_id}/time-logs", json={"minutes": 30, "note": "A"})
    client.post(f"/api/boards/{board_id}/cards/{card_id}/time-logs", json={"minutes": 45, "note": "B"})
    logs = client.get(f"/api/boards/{board_id}/cards/{card_id}/time-logs").json()
    assert len(logs) == 2
    assert {lg["note"] for lg in logs} == {"A", "B"}


def test_total_minutes_in_board_payload(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    client.post(f"/api/boards/{board_id}/cards/{card_id}/time-logs", json={"minutes": 30})
    client.post(f"/api/boards/{board_id}/cards/{card_id}/time-logs", json={"minutes": 45})
    board = client.get(f"/api/board/{board_id}").json()
    assert board["cards"][str(card_id)]["total_minutes"] == 75


def test_delete_time_log(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    log_id = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/time-logs",
        json={"minutes": 60},
    ).json()["id"]
    response = client.delete(f"/api/boards/{board_id}/cards/{card_id}/time-logs/{log_id}")
    assert response.status_code == 200
    assert client.get(f"/api/boards/{board_id}/cards/{card_id}/time-logs").json() == []


def test_delete_time_log_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    response = client.delete(f"/api/boards/{board_id}/cards/{card_id}/time-logs/99999")
    assert response.status_code == 404


def test_time_report_empty(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.get(f"/api/boards/{board_id}/time-report")
    assert response.status_code == 200
    data = response.json()
    assert data["total_minutes"] == 0
    assert data["by_user"] == []
    assert data["by_card"] == []


def test_time_report_populated(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id, "Timed Card")
    client.post(f"/api/boards/{board_id}/cards/{card_id}/time-logs", json={"minutes": 90, "note": ""})
    client.post(f"/api/boards/{board_id}/cards/{card_id}/time-logs", json={"minutes": 30, "note": ""})
    report = client.get(f"/api/boards/{board_id}/time-report").json()
    assert report["total_minutes"] == 120
    assert len(report["by_user"]) == 1
    assert report["by_user"][0]["total_minutes"] == 120
    assert len(report["by_card"]) == 1
    assert report["by_card"][0]["total_minutes"] == 120
    assert report["by_card"][0]["title"] == "Timed Card"


def test_time_log_requires_auth(client: TestClient) -> None:
    response = client.post("/api/boards/1/cards/1/time-logs", json={"minutes": 30})
    assert response.status_code == 401


def test_time_report_requires_auth(client: TestClient) -> None:
    response = client.get("/api/boards/1/time-report")
    assert response.status_code == 401


def test_time_log_activity_logged(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    client.post(f"/api/boards/{board_id}/cards/{card_id}/time-logs", json={"minutes": 45})
    log = client.get(f"/api/boards/{board_id}/activity").json()
    assert any(e["action"] == "log_time" for e in log)


def test_board_cards_have_total_minutes_zero_by_default(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    board = client.get(f"/api/board/{board_id}").json()
    for card in board["cards"].values():
        assert card["total_minutes"] == 0


# ── OpenRouter unit tests ─────────────────────────────────────────────────────
# These test openrouter.py logic directly using mocked httpx.

import importlib
from unittest.mock import MagicMock, patch

import pytest
from app import openrouter as or_module


def test_build_chat_payload_structure() -> None:
    payload = or_module.build_chat_payload("hello")
    assert payload["model"] == or_module.DEFAULT_MODEL
    assert payload["messages"] == [{"role": "user", "content": "hello"}]


def test_build_chat_payload_custom_model() -> None:
    payload = or_module.build_chat_payload("hi", model="custom/model")
    assert payload["model"] == "custom/model"


def test_extract_message_text_string_content() -> None:
    data = {"choices": [{"message": {"content": "hello world"}}]}
    assert or_module._extract_message_text(data) == "hello world"


def test_extract_message_text_list_content() -> None:
    data = {"choices": [{"message": {"content": [{"text": "part1"}, {"text": "part2"}]}}]}
    assert or_module._extract_message_text(data) == "part1\npart2"


def test_extract_message_text_empty_choices_raises() -> None:
    with pytest.raises(or_module.OpenRouterError) as exc_info:
        or_module._extract_message_text({"choices": []})
    assert exc_info.value.status_code == 502


def test_extract_message_text_missing_choices_raises() -> None:
    with pytest.raises(or_module.OpenRouterError):
        or_module._extract_message_text({})


def test_extract_message_text_malformed_choice_raises() -> None:
    with pytest.raises(or_module.OpenRouterError):
        or_module._extract_message_text({"choices": ["not_a_dict"]})


def test_extract_message_text_missing_message_raises() -> None:
    with pytest.raises(or_module.OpenRouterError):
        or_module._extract_message_text({"choices": [{"no_message": True}]})


def test_extract_message_text_missing_content_raises() -> None:
    with pytest.raises(or_module.OpenRouterError):
        or_module._extract_message_text({"choices": [{"message": {}}]})


def test_chat_completion_no_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(or_module.OpenRouterError) as exc_info:
        or_module.chat_completion("test")
    assert exc_info.value.status_code == 503


def test_chat_completion_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "model": "test/model",
        "choices": [{"message": {"content": "4"}}],
    }
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client
        result = or_module.chat_completion("2+2")
    assert result["response"] == "4"
    assert result["model"] == "test/model"


def test_chat_completion_timeout_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value = mock_client
        with pytest.raises(or_module.OpenRouterError) as exc_info:
            or_module.chat_completion("test")
    assert exc_info.value.status_code == 504


def test_chat_completion_request_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = httpx.RequestError("network error")
        mock_client_cls.return_value = mock_client
        with pytest.raises(or_module.OpenRouterError) as exc_info:
            or_module.chat_completion("test")
    assert exc_info.value.status_code == 502


def test_chat_completion_4xx_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"error": {"message": "Invalid API key"}}
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client
        with pytest.raises(or_module.OpenRouterError) as exc_info:
            or_module.chat_completion("test")
    assert exc_info.value.status_code == 502
    assert "Invalid API key" in str(exc_info.value)


def test_chat_completion_invalid_json_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("not json")
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client
        with pytest.raises(or_module.OpenRouterError) as exc_info:
            or_module.chat_completion("test")
    assert exc_info.value.status_code == 502


def test_chat_completion_non_dict_body_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = ["not", "a", "dict"]
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client
        with pytest.raises(or_module.OpenRouterError) as exc_info:
            or_module.chat_completion("test")
    assert exc_info.value.status_code == 502


# ── Time log error-branch tests ──────────────────────────────────────────────

def test_list_time_logs_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.get(f"/api/boards/{board_id}/cards/99999/time-logs")
    assert response.status_code == 404


def test_log_time_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    response = client.post(
        f"/api/boards/{board_id}/cards/99999/time-logs",
        json={"minutes": 30},
    )
    assert response.status_code == 404


def test_delete_time_log_forbidden_other_user(client: TestClient) -> None:
    """User can only delete their own time logs (unless admin)."""
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    log_id = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/time-logs",
        json={"minutes": 30},
    ).json()["id"]

    # Create a second non-admin user and try to delete
    admin_client = client
    admin_client.post("/api/admin/users", json={"username": "other_user_tl", "password": "pass", "role": "user"})

    second_client = TestClient(admin_client.app)
    second_client.post("/api/auth/login", json={"username": "other_user_tl", "password": "pass"})

    resp = second_client.delete(f"/api/boards/{board_id}/cards/{card_id}/time-logs/{log_id}")
    assert resp.status_code in (401, 403, 404)  # Not authorized or board not accessible


def test_time_report_board_not_found(client: TestClient) -> None:
    login(client)
    response = client.get("/api/boards/99999/time-report")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Notification tests
# ---------------------------------------------------------------------------

def _create_second_user(client: TestClient, username: str = "other_notify") -> None:
    """Create a non-admin user via the admin endpoint."""
    login(client)  # ensure logged in as admin
    client.post("/api/admin/users", json={"username": username, "password": "pass", "role": "user"})


def test_notifications_empty_on_fresh_user(client: TestClient) -> None:
    login(client)
    response = client.get("/api/notifications")
    assert response.status_code == 200
    data = response.json()
    assert data["notifications"] == []
    assert data["unread_count"] == 0


def test_notification_requires_auth(client: TestClient) -> None:
    response = client.get("/api/notifications")
    assert response.status_code == 401


def test_assignment_notification_on_create_card(client: TestClient) -> None:
    """Creating a card with an assignee notifies that assignee."""
    _create_second_user(client, "assignee_nc")

    # Get assignee user id via admin API
    users = client.get("/api/admin/users").json()["users"]
    assignee = next(u for u in users if u["username"] == "assignee_nc")
    assignee_id = assignee["id"]

    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Notify me", "details": "", "assignee_id": str(assignee_id)},
    )

    # Log in as assignee and check notifications
    second = TestClient(client.app)
    second.post("/api/auth/login", json={"username": "assignee_nc", "password": "pass"})
    resp = second.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unread_count"] >= 1
    assert any("Notify me" in n["detail"] for n in data["notifications"])
    assert all(n["type"] == "assignment" for n in data["notifications"])


def test_no_assignment_notification_self_assign(client: TestClient) -> None:
    """Assigning a card to yourself should not create a notification."""
    login(client)
    users = client.get("/api/admin/users").json()["users"]
    self_user = next(u for u in users if u["username"] == "user")
    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Self", "details": "", "assignee_id": str(self_user["id"])},
    )
    resp = client.get("/api/notifications")
    assert resp.json()["unread_count"] == 0


def test_assignment_notification_on_update_card(client: TestClient) -> None:
    """Updating a card to set a new assignee notifies them."""
    _create_second_user(client, "reassignee_nu")
    users = client.get("/api/admin/users").json()["users"]
    assignee = next(u for u in users if u["username"] == "reassignee_nu")
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id, "Reassign test")

    client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "Reassign test", "details": "", "assignee_id": str(assignee["id"])},
    )

    second = TestClient(client.app)
    second.post("/api/auth/login", json={"username": "reassignee_nu", "password": "pass"})
    resp = second.get("/api/notifications")
    assert resp.json()["unread_count"] >= 1


def test_no_notification_when_assignee_unchanged(client: TestClient) -> None:
    """Updating a card without changing assignee must not re-notify."""
    _create_second_user(client, "same_assignee_nu")
    users = client.get("/api/admin/users").json()["users"]
    assignee = next(u for u in users if u["username"] == "same_assignee_nu")
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id, "No re-notify")

    # First assign
    client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "No re-notify", "details": "", "assignee_id": str(assignee["id"])},
    )
    # Update again with same assignee
    client.put(
        f"/api/boards/{board_id}/cards/{card_id}",
        json={"title": "No re-notify v2", "details": "", "assignee_id": str(assignee["id"])},
    )

    second = TestClient(client.app)
    second.post("/api/auth/login", json={"username": "same_assignee_nu", "password": "pass"})
    data = second.get("/api/notifications").json()
    # Only one notification (from first assignment), not two
    assert data["unread_count"] == 1


def test_mention_notification_on_comment(client: TestClient) -> None:
    """@mention in a comment notifies the mentioned user."""
    _create_second_user(client, "mentioned_nu")
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)

    client.post(
        f"/api/boards/{board_id}/cards/{card_id}/comments",
        json={"content": "Hey @mentioned_nu please review"},
    )

    second = TestClient(client.app)
    second.post("/api/auth/login", json={"username": "mentioned_nu", "password": "pass"})
    resp = second.get("/api/notifications")
    data = resp.json()
    assert data["unread_count"] >= 1
    assert any(n["type"] == "mention" for n in data["notifications"])


def test_no_mention_notification_for_nonexistent_user(client: TestClient) -> None:
    """Mentioning a username that doesn't exist does not raise an error."""
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    resp = client.post(
        f"/api/boards/{board_id}/cards/{card_id}/comments",
        json={"content": "Hey @ghost_user_xyz please look"},
    )
    assert resp.status_code == 200  # no error


def test_no_self_mention_notification(client: TestClient) -> None:
    """Mentioning yourself in a comment does not create a notification."""
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id)
    client.post(
        f"/api/boards/{board_id}/cards/{card_id}/comments",
        json={"content": "Reminder for @user to finish this"},
    )
    resp = client.get("/api/notifications")
    assert resp.json()["unread_count"] == 0


def test_mark_notification_read(client: TestClient) -> None:
    """Mark a single notification as read."""
    _create_second_user(client, "mark_read_nu")
    users = client.get("/api/admin/users").json()["users"]
    assignee = next(u for u in users if u["username"] == "mark_read_nu")
    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Mark read test", "details": "", "assignee_id": str(assignee["id"])},
    )

    second = TestClient(client.app)
    second.post("/api/auth/login", json={"username": "mark_read_nu", "password": "pass"})
    notifs = second.get("/api/notifications").json()["notifications"]
    notif_id = notifs[0]["id"]

    resp = second.post(f"/api/notifications/{notif_id}/read")
    assert resp.status_code == 200
    assert resp.json()["status"] == "read"

    updated = second.get("/api/notifications").json()
    assert updated["unread_count"] == 0
    assert updated["notifications"][0]["is_read"] is True


def test_mark_notification_read_wrong_user(client: TestClient) -> None:
    """A user cannot mark another user's notification as read."""
    _create_second_user(client, "wrong_user_nread")
    users = client.get("/api/admin/users").json()["users"]
    assignee = next(u for u in users if u["username"] == "wrong_user_nread")
    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Other card", "details": "", "assignee_id": str(assignee["id"])},
    )

    second = TestClient(client.app)
    second.post("/api/auth/login", json={"username": "wrong_user_nread", "password": "pass"})
    notif_id = second.get("/api/notifications").json()["notifications"][0]["id"]

    # The original user (admin/user) tries to mark it — they don't own it
    resp = client.post(f"/api/notifications/{notif_id}/read")
    assert resp.status_code == 404


def test_mark_all_notifications_read(client: TestClient) -> None:
    """Mark all notifications as read at once."""
    _create_second_user(client, "mark_all_nu")
    users = client.get("/api/admin/users").json()["users"]
    assignee = next(u for u in users if u["username"] == "mark_all_nu")
    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    # Create two cards assigned to the user → two notifications
    for title in ("Card A", "Card B"):
        client.post(
            f"/api/boards/{board_id}/cards",
            json={"columnId": col_id, "title": title, "details": "", "assignee_id": str(assignee["id"])},
        )

    second = TestClient(client.app)
    second.post("/api/auth/login", json={"username": "mark_all_nu", "password": "pass"})
    assert second.get("/api/notifications").json()["unread_count"] == 2

    resp = second.post("/api/notifications/read-all")
    assert resp.status_code == 200
    assert second.get("/api/notifications").json()["unread_count"] == 0


def test_mark_all_read_requires_auth(client: TestClient) -> None:
    response = client.post("/api/notifications/read-all")
    assert response.status_code == 401


def test_notification_not_found_returns_404(client: TestClient) -> None:
    login(client)
    resp = client.post("/api/notifications/99999/read")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Card copy tests
# ---------------------------------------------------------------------------

def test_copy_card(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id, "Original card")

    resp = client.post(f"/api/boards/{board_id}/cards/{card_id}/copy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Original card (copy)"
    assert "id" in data
    assert data["id"] != card_id


def test_copy_card_appears_in_board(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id, "To be copied")

    resp = client.post(f"/api/boards/{board_id}/cards/{card_id}/copy")
    new_id = resp.json()["id"]

    board = client.get(f"/api/board/{board_id}").json()
    all_card_ids = [cid for col in board["columns"] for cid in col["cardIds"]]
    assert new_id in all_card_ids


def test_copy_card_preserves_fields(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    col_id = _get_first_col_id(client, board_id)
    original = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": col_id, "title": "Rich card", "details": "some details",
              "priority": "high", "labels": ["backend"], "estimate": 5},
    ).json()

    resp = client.post(f"/api/boards/{board_id}/cards/{original['id']}/copy")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Rich card (copy)"

    # Verify the copy is in the same column
    board = client.get(f"/api/board/{board_id}").json()
    col = next(c for c in board["columns"] if c["id"] == col_id)
    assert resp.json()["id"] in col["cardIds"]


def test_copy_card_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    resp = client.post(f"/api/boards/{board_id}/cards/99999/copy")
    assert resp.status_code == 404


def test_copy_card_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/boards/1/cards/1/copy")
    assert resp.status_code == 401


def test_copy_archived_card_not_found(client: TestClient) -> None:
    """Copying an archived card should fail with 404."""
    login(client)
    board_id = get_board_id(client)
    card_id = _create_card_simple(client, board_id, "To archive")
    client.delete(f"/api/boards/{board_id}/cards/{card_id}")  # archive it
    resp = client.post(f"/api/boards/{board_id}/cards/{card_id}/copy")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Sprint burndown tests
# ---------------------------------------------------------------------------

def _create_sprint_with_dates(client: TestClient, board_id: str, start: str, end: str, name: str = "Test Sprint") -> str:
    resp = client.post(
        f"/api/boards/{board_id}/sprints",
        json={"name": name, "goal": "finish", "start_date": start, "end_date": end},
    )
    return resp.json()["id"]


def test_sprint_burndown_no_cards(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sprint_id = _create_sprint_with_dates(client, board_id, "2026-01-01", "2026-01-14", "Empty Sprint")

    resp = client.get(f"/api/boards/{board_id}/sprints/{sprint_id}/burndown")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_points"] == 0
    assert data["remaining_points"] == 0
    assert data["completed_points"] == 0
    assert len(data["ideal_line"]) > 0  # has date points
    assert data["sprint"]["name"] == "Empty Sprint"


def test_sprint_burndown_with_estimates(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    sprint_id = _create_sprint_with_dates(client, board_id, "2026-01-01", "2026-01-10", "Estimate Sprint")
    col_id = _get_first_col_id(client, board_id)

    # Create two cards with estimates assigned to the sprint
    for pts in (3, 5):
        client.post(
            f"/api/boards/{board_id}/cards",
            json={"columnId": col_id, "title": f"Card {pts}pts", "details": "",
                  "estimate": pts, "sprint_id": sprint_id},
        )

    resp = client.get(f"/api/boards/{board_id}/sprints/{sprint_id}/burndown")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_points"] == 8
    assert data["remaining_points"] == 8
    assert data["completed_points"] == 0
    # Ideal line: start=8, end=0 over 9 days
    assert data["ideal_line"][0]["ideal"] == 8.0
    assert data["ideal_line"][-1]["ideal"] == 0.0


def test_sprint_burndown_completed_points(client: TestClient) -> None:
    """Cards in the Done column count as completed."""
    login(client)
    board_id = get_board_id(client)
    sprint_id = _create_sprint_with_dates(client, board_id, "2026-01-01", "2026-01-07", "Done Sprint")

    # Get done column id
    board = client.get(f"/api/board/{board_id}").json()
    done_col = next(c for c in board["columns"] if c["key"] == "done")
    done_col_id = done_col["id"]
    backlog_col_id = board["columns"][0]["id"]

    # Create card in backlog with sprint, then move to done
    card = client.post(
        f"/api/boards/{board_id}/cards",
        json={"columnId": backlog_col_id, "title": "Done card", "details": "",
              "estimate": 4, "sprint_id": sprint_id},
    ).json()
    client.post(
        f"/api/boards/{board_id}/cards/{card['id']}/move",
        json={"toColumnId": done_col_id, "toIndex": 0},
    )

    resp = client.get(f"/api/boards/{board_id}/sprints/{sprint_id}/burndown")
    data = resp.json()
    assert data["total_points"] == 4
    assert data["completed_points"] == 4
    assert data["remaining_points"] == 0


def test_sprint_burndown_no_dates_returns_empty_ideal_line(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    resp = client.post(
        f"/api/boards/{board_id}/sprints",
        json={"name": "No Dates Sprint", "goal": ""},
    )
    sprint_id = resp.json()["id"]

    resp = client.get(f"/api/boards/{board_id}/sprints/{sprint_id}/burndown")
    assert resp.status_code == 200
    assert resp.json()["ideal_line"] == []


def test_sprint_burndown_today_in_response(client: TestClient) -> None:
    import datetime
    login(client)
    board_id = get_board_id(client)
    sprint_id = _create_sprint_with_dates(client, board_id, "2026-01-01", "2026-01-05", "Today Sprint")
    resp = client.get(f"/api/boards/{board_id}/sprints/{sprint_id}/burndown")
    assert resp.json()["today"] == datetime.date.today().isoformat()


def test_sprint_burndown_not_found(client: TestClient) -> None:
    login(client)
    board_id = get_board_id(client)
    resp = client.get(f"/api/boards/{board_id}/sprints/99999/burndown")
    assert resp.status_code == 404


def test_sprint_burndown_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/boards/1/sprints/1/burndown")
    assert resp.status_code == 401
