import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { KanbanBoard } from "@/components/KanbanBoard";

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];

const boardPayload = {
  boardId: "1",
  name: "Main Board",
  columns: [
    { id: "1", key: "backlog", title: "Backlog", cardIds: ["1", "2"] },
    { id: "2", key: "todo", title: "To Do", cardIds: ["3"] },
    { id: "3", key: "in_progress", title: "In Progress", cardIds: [] },
    { id: "4", key: "review", title: "Review", cardIds: [] },
    { id: "5", key: "done", title: "Done", cardIds: [] },
  ],
  cards: {
    "1": { id: "1", title: "Card one", details: "A" },
    "2": { id: "2", title: "Card two", details: "B" },
    "3": { id: "3", title: "Card three", details: "C" },
  },
};

const mockUsers = [{ id: "1", username: "user" }];
const mockStats = {
  total_cards: 3,
  total_estimate: 0,
  overdue_count: 1,
  cards_per_column: [
    { id: "1", title: "Backlog", count: 2, total_estimate: 0 },
    { id: "2", title: "To Do", count: 1, total_estimate: 0 },
    { id: "3", title: "In Progress", count: 0, total_estimate: 0 },
    { id: "4", title: "Review", count: 0, total_estimate: 0 },
    { id: "5", title: "Done", count: 0, total_estimate: 0 },
  ],
  cards_by_priority: { none: 3 },
};

beforeEach(() => {
  const boardState = structuredClone(boardPayload);

  vi.spyOn(global, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url === "/api/users" && method === "GET") {
      return new Response(JSON.stringify(mockUsers), { status: 200 });
    }

    if (url.includes("/stats") && method === "GET") {
      return new Response(JSON.stringify(mockStats), { status: 200 });
    }

    if (url.includes("/checklist") && method === "GET") {
      return new Response(JSON.stringify([]), { status: 200 });
    }

    if (url.includes("/dependencies") && method === "GET") {
      return new Response(JSON.stringify({ blocks: [], blocked_by: [] }), { status: 200 });
    }

    if (url.match(/\/boards\/\d+\/dependencies$/) && method === "POST") {
      return new Response(JSON.stringify({ id: "d1", blocker_id: "1", blocked_id: "2" }), { status: 200 });
    }

    if (url.match(/\/dependencies\/\d+$/) && method === "DELETE") {
      return new Response(JSON.stringify({ status: "deleted" }), { status: 200 });
    }

    if (url.includes("/checklist") && method === "POST" && !url.match(/\/checklist\/\d+/)) {
      const body = JSON.parse(String(init?.body ?? "{}")) as { text?: string };
      return new Response(
        JSON.stringify({ id: "cl1", text: body.text ?? "", checked: false, position: 0 }),
        { status: 200 }
      );
    }

    if (url.match(/\/checklist\/\d+/) && method === "PUT") {
      const body = JSON.parse(String(init?.body ?? "{}")) as { checked?: boolean; text?: string };
      return new Response(
        JSON.stringify({ id: "cl1", text: body.text ?? "item", checked: body.checked ?? false, position: 0 }),
        { status: 200 }
      );
    }

    if (url.match(/\/checklist\/\d+/) && method === "DELETE") {
      return new Response(JSON.stringify({ status: "deleted" }), { status: 200 });
    }

    if (url.includes("/comments") && method === "GET") {
      return new Response(JSON.stringify([]), { status: 200 });
    }

    if (url.includes("/comments") && method === "POST") {
      const body = JSON.parse(String(init?.body ?? "{}")) as { content?: string };
      return new Response(
        JSON.stringify({ id: "99", content: body.content ?? "", author: "user", createdAt: "2026-01-01T00:00:00" }),
        { status: 200 }
      );
    }

    if (url.includes("/archived") && method === "GET") {
      return new Response(JSON.stringify([
        { id: "99", columnId: "1", columnTitle: "Backlog", title: "Archived card", details: "", due_date: null, priority: null, labels: [] },
      ]), { status: 200 });
    }

    if (url.includes("/restore") && method === "POST") {
      return new Response(JSON.stringify({ id: "99", columnId: "1", title: "Archived card" }), { status: 200 });
    }

    if (url.includes("/permanent") && method === "DELETE") {
      return new Response(JSON.stringify({ status: "deleted" }), { status: 200 });
    }

    if (url.includes("/activity") && method === "GET") {
      return new Response(JSON.stringify([
        { id: "1", actor: "user", action: "create_card", entity_type: "card", entity_id: 1, detail: "Card one", createdAt: "2026-01-01T10:00:00" },
      ]), { status: 200 });
    }

    if (url.includes("/api/board") && method === "GET") {
      return new Response(JSON.stringify(boardState), { status: 200 });
    }

    if (url.includes("/api/chat") && method === "GET") {
      return new Response(JSON.stringify({ messages: [] }), { status: 200 });
    }

    if (url.includes("/api/ai/chat") && method === "POST") {
      const body = JSON.parse(String(init?.body ?? "{}")) as { message?: string };
      if (body.message?.includes("rename board")) {
        boardState.name = "AI Board";
      }

      return new Response(
        JSON.stringify({
          assistantMessage: "Done",
          appliedUpdates: body.message?.includes("rename board") ?? false,
          updateCount: body.message?.includes("rename board") ? 1 : 0,
          updatesError: null,
          board: boardState,
        }),
        { status: 200 }
      );
    }

    if (url.includes("/api/board") && method === "PUT") {
      return new Response(JSON.stringify({ boardId: "1", name: "Renamed" }), {
        status: 200,
      });
    }

    if (url.includes("/columns/") && method === "PATCH") {
      return new Response(JSON.stringify({ id: "1", title: "New Name" }), {
        status: 200,
      });
    }

    if (url.includes("/cards") && method === "POST" && !url.includes("/move") && !url.includes("/ai/")) {
      return new Response(
        JSON.stringify({ id: "9", columnId: "1", title: "New card", details: "Notes" }),
        { status: 200 }
      );
    }

    if (url.includes("/cards/") && method === "DELETE") {
      return new Response(JSON.stringify({ status: "archived" }), { status: 200 });
    }

    if (url.includes("/cards/") && method === "PUT") {
      return new Response(JSON.stringify({ id: "1", title: "Updated", details: "D" }), {
        status: 200,
      });
    }

    if (url.includes("/move") && method === "POST") {
      return new Response(JSON.stringify({ id: "1", columnId: "2", position: "0" }), {
        status: 200,
      });
    }

    return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("KanbanBoard", () => {
  it("shows loading state before board resolves", () => {
    render(<KanbanBoard boardId="1" />);
    expect(screen.getByText("Loading board...")).toBeInTheDocument();
  });

  it("renders five columns", async () => {
    render(<KanbanBoard boardId="1" />);
    expect(await screen.findAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("renames the board on blur when value changes", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const boardName = screen.getByLabelText("Board name");
    await userEvent.clear(boardName);
    await userEvent.type(boardName, "Renamed");
    boardName.blur();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/board/1",
        expect.objectContaining({ method: "PUT" })
      );
    });
  });

  it("resets board name draft when blur value is blank", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const boardName = screen.getByLabelText("Board name");
    await userEvent.clear(boardName);
    boardName.blur();

    await waitFor(() => {
      expect(screen.getByLabelText("Board name")).toHaveValue("Main Board");
    });
  });

  it("renames a column", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    input.blur();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/columns/1",
        expect.objectContaining({ method: "PATCH" })
      );
    });
  });

  it("adds and removes a card", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const column = getFirstColumn();
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/cards",
        expect.objectContaining({ method: "POST" })
      );
    });

    const deleteButton = within(column).getByRole("button", {
      name: /archive card one/i,
    });
    await userEvent.click(deleteButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/cards/1",
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });

  it("edits a card", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const firstCard = screen.getByTestId("card-1");

    await userEvent.click(within(firstCard).getByRole("button", { name: /edit card one/i }));
    const titleInput = within(firstCard).getByLabelText(/edit title for card one/i);
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Card one updated");
    await userEvent.click(within(firstCard).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/cards/1",
        expect.objectContaining({ method: "PUT" })
      );
    });
  });

  it("shows error when board load fails", async () => {
    vi.mocked(global.fetch).mockImplementationOnce(async () => {
      return new Response(JSON.stringify({ detail: "boom" }), { status: 500 });
    });

    render(<KanbanBoard boardId="1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
    expect(screen.queryAllByTestId(/column-/i)).toHaveLength(0);
  });

  it("sends chat and refreshes board from AI response", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const input = screen.getByLabelText("AI chat message");
    await userEvent.type(input, "rename board");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/ai/chat",
        expect.objectContaining({ method: "POST" })
      );
    });

    await waitFor(() => {
      expect(screen.getByLabelText("Board name")).toHaveValue("AI Board");
    });
    expect(screen.getByTestId("chat-messages")).toHaveTextContent("Done");
  });

  it("renders system chat message when updatesError is returned", async () => {
    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.includes("/api/board") && method === "GET") {
        return new Response(JSON.stringify(structuredClone(boardPayload)), { status: 200 });
      }

      if (url.includes("/api/chat") && method === "GET") {
        return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      }

      if (url.includes("/api/ai/chat") && method === "POST") {
        return new Response(
          JSON.stringify({
            assistantMessage: "Done",
            updatesError: "Could not apply update",
            board: structuredClone(boardPayload),
          }),
          { status: 200 }
        );
      }

      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.type(screen.getByLabelText("AI chat message"), "help");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Could not apply update")).toBeInTheDocument();
  });

  it("shows error when chat request fails", async () => {
    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.includes("/api/board") && method === "GET") {
        return new Response(JSON.stringify(structuredClone(boardPayload)), { status: 200 });
      }

      if (url.includes("/api/chat") && method === "GET") {
        return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      }

      if (url.includes("/api/ai/chat") && method === "POST") {
        return new Response(JSON.stringify({ detail: "AI unavailable" }), { status: 503 });
      }

      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.type(screen.getByLabelText("AI chat message"), "help");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("AI unavailable");
  });

  it("shows fallback status when API error payload is not json", async () => {
    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.includes("/api/board") && method === "GET") {
        return new Response(JSON.stringify(structuredClone(boardPayload)), { status: 200 });
      }

      if (url.includes("/api/chat") && method === "GET") {
        return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      }

      if (url.includes("/cards/") && method === "DELETE") {
        return new Response("boom", {
          status: 500,
          headers: { "content-type": "text/plain" },
        });
      }

      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.click(screen.getByRole("button", { name: /archive card one/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Request failed: 500");
  });

  it("reverts column title on Escape key", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "Temporary");
    await userEvent.keyboard("{Escape}");

    expect(input).toHaveValue("Backlog");
  });

  it("shows validation error when column title is cleared", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    input.blur();

    await waitFor(() => {
      expect(within(column).getByText("Title is required")).toBeInTheDocument();
    });
  });

  it("cancels card edit on Escape key", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const firstCard = screen.getByTestId("card-1");

    await userEvent.click(within(firstCard).getByRole("button", { name: /edit card one/i }));
    const titleInput = within(firstCard).getByLabelText(/edit title for card one/i);
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Temporary title");
    await userEvent.keyboard("{Escape}");

    expect(within(firstCard).queryByLabelText(/edit title/i)).not.toBeInTheDocument();
    expect(within(firstCard).getByText("Card one")).toBeInTheDocument();
  });

  it("shows validation error when card title is emptied", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const firstCard = screen.getByTestId("card-1");

    await userEvent.click(within(firstCard).getByRole("button", { name: /edit card one/i }));
    const titleInput = within(firstCard).getByLabelText(/edit title for card one/i);
    await userEvent.clear(titleInput);
    await userEvent.click(within(firstCard).getByRole("button", { name: "Save" }));

    expect(within(firstCard).getByText("Title is required")).toBeInTheDocument();
  });

  it("cancels card edit via Cancel button", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const firstCard = screen.getByTestId("card-1");

    await userEvent.click(within(firstCard).getByRole("button", { name: /edit card one/i }));
    await userEvent.click(within(firstCard).getByRole("button", { name: "Cancel" }));

    expect(within(firstCard).queryByLabelText(/edit title/i)).not.toBeInTheDocument();
    expect(within(firstCard).getByText("Card one")).toBeInTheDocument();
  });

  it("moves a card right via keyboard button", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const firstCard = screen.getByTestId("card-1");

    await userEvent.click(within(firstCard).getByRole("button", { name: /move card one right/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/cards/1/move",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("moves a card down via keyboard button", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const firstCard = screen.getByTestId("card-1");

    await userEvent.click(within(firstCard).getByRole("button", { name: /move card one down/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/cards/1/move",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("disables left move on first column cards", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const firstCard = screen.getByTestId("card-1");

    expect(within(firstCard).getByRole("button", { name: /move card one left/i })).toBeDisabled();
  });

  it("moves a card left via keyboard button", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const card3 = screen.getByTestId("card-3");

    await userEvent.click(within(card3).getByRole("button", { name: /move card three left/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/cards/3/move",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("moves a card up via keyboard button", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const secondCard = screen.getByTestId("card-2");

    await userEvent.click(within(secondCard).getByRole("button", { name: /move card two up/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/cards/2/move",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("disables right move on last column cards", async () => {
    const payload = structuredClone(boardPayload);
    payload.columns[4].cardIds = ["3"];
    payload.columns[1].cardIds = [];

    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/api/board") && method === "GET") {
        return new Response(JSON.stringify(payload), { status: 200 });
      }
      if (url.includes("/api/chat") && method === "GET") {
        return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      }
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const card3 = screen.getByTestId("card-3");

    expect(within(card3).getByRole("button", { name: /move card three right/i })).toBeDisabled();
  });

  it("shows error when rename board fails", async () => {
    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/api/board") && method === "GET") {
        return new Response(JSON.stringify(structuredClone(boardPayload)), { status: 200 });
      }
      if (url.includes("/api/chat") && method === "GET") {
        return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      }
      if (url.includes("/api/board") && method === "PUT") {
        return new Response(JSON.stringify({ detail: "rename failed" }), { status: 400 });
      }
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const boardName = screen.getByLabelText("Board name");
    await userEvent.clear(boardName);
    await userEvent.type(boardName, "Bad Name");
    boardName.blur();

    expect(await screen.findByRole("alert")).toHaveTextContent("rename failed");
  });

  it("shows error when move card fails", async () => {
    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/api/board") && method === "GET") {
        return new Response(JSON.stringify(structuredClone(boardPayload)), { status: 200 });
      }
      if (url.includes("/api/chat") && method === "GET") {
        return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      }
      if (url.includes("/move") && method === "POST") {
        return new Response(JSON.stringify({ detail: "move failed" }), { status: 400 });
      }
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const card = screen.getByTestId("card-1");
    await userEvent.click(within(card).getByRole("button", { name: /move card one right/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("move failed");
  });

  it("shows error when rename column fails", async () => {
    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/api/board") && method === "GET") {
        return new Response(JSON.stringify(structuredClone(boardPayload)), { status: 200 });
      }
      if (url.includes("/api/chat") && method === "GET") {
        return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      }
      if (url.includes("/columns/") && method === "PATCH") {
        return new Response(JSON.stringify({ detail: "rename col failed" }), { status: 400 });
      }
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "Bad Name");
    input.blur();

    expect(await screen.findByRole("alert")).toHaveTextContent("rename col failed");
  });

  it("shows error when add card fails", async () => {
    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/api/board") && method === "GET") {
        return new Response(JSON.stringify(structuredClone(boardPayload)), { status: 200 });
      }
      if (url.includes("/api/chat") && method === "GET") {
        return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      }
      if (url.includes("/cards") && method === "POST" && !url.includes("/move") && !url.includes("/ai/")) {
        return new Response(JSON.stringify({ detail: "add card failed" }), { status: 400 });
      }
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const column = getFirstColumn();
    await userEvent.click(within(column).getByRole("button", { name: /add a card/i }));
    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "Failing card");
    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("add card failed");
  });

  it("shows error when edit card fails", async () => {
    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/api/board") && method === "GET") {
        return new Response(JSON.stringify(structuredClone(boardPayload)), { status: 200 });
      }
      if (url.includes("/api/chat") && method === "GET") {
        return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      }
      if (url.includes("/cards/") && method === "PUT") {
        return new Response(JSON.stringify({ detail: "edit card failed" }), { status: 400 });
      }
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const firstCard = screen.getByTestId("card-1");
    await userEvent.click(within(firstCard).getByRole("button", { name: /edit card one/i }));
    const titleInput = within(firstCard).getByLabelText(/edit title for card one/i);
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Bad card");
    await userEvent.click(within(firstCard).getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("edit card failed");
  });

  it("does not send empty chat message", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    const chatCalls = vi.mocked(global.fetch).mock.calls.filter(
      ([url]) => String(url).includes("/api/ai/chat")
    );
    expect(chatCalls).toHaveLength(0);
  });

  it("loads chat history on mount", async () => {
    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/api/board") && method === "GET") {
        return new Response(JSON.stringify(structuredClone(boardPayload)), { status: 200 });
      }
      if (url.includes("/api/chat") && method === "GET") {
        return new Response(
          JSON.stringify({
            messages: [
              { id: "1", role: "user", content: "hello" },
              { id: "2", role: "assistant", content: "hi there" },
            ],
          }),
          { status: 200 }
        );
      }
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    expect(await screen.findByText("hello")).toBeInTheDocument();
    expect(screen.getByText("hi there")).toBeInTheDocument();
  });

  it("renders the filter bar", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    expect(screen.getByTestId("filter-bar")).toBeInTheDocument();
    expect(screen.getByLabelText("Search cards")).toBeInTheDocument();
    expect(screen.getByLabelText("Filter by priority")).toBeInTheDocument();
  });

  it("filters cards by text search", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const searchInput = screen.getByLabelText("Search cards");
    await userEvent.type(searchInput, "Card one");

    await waitFor(() => {
      expect(screen.getByTestId("card-1")).toBeInTheDocument();
      expect(screen.queryByTestId("card-2")).not.toBeInTheDocument();
    });
  });

  it("shows clear filters button when filters are active", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const searchInput = screen.getByLabelText("Search cards");
    await userEvent.type(searchInput, "test");

    expect(screen.getByLabelText("Clear filters")).toBeInTheDocument();
  });

  it("clears filters when clear button is clicked", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.type(screen.getByLabelText("Search cards"), "one");
    await userEvent.click(screen.getByLabelText("Clear filters"));

    await waitFor(() => {
      expect(screen.getByTestId("card-1")).toBeInTheDocument();
      expect(screen.getByTestId("card-2")).toBeInTheDocument();
    });
  });

  it("filters cards by priority", async () => {
    const payload = structuredClone(boardPayload);
    payload.cards["1"] = { ...payload.cards["1"], priority: "high" };
    payload.cards["2"] = { ...payload.cards["2"], priority: "low" };

    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url === "/api/users") return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/stats")) return new Response(JSON.stringify(mockStats), { status: 200 });
      if (url.includes("/comments")) return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/api/board") && method === "GET") return new Response(JSON.stringify(payload), { status: 200 });
      if (url.includes("/api/chat")) return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const priorityFilter = screen.getByLabelText("Filter by priority");
    await userEvent.selectOptions(priorityFilter, "high");

    await waitFor(() => {
      expect(screen.getByTestId("card-1")).toBeInTheDocument();
      expect(screen.queryByTestId("card-2")).not.toBeInTheDocument();
    });
  });

  it("shows stats panel when stats load", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    expect(await screen.findByTestId("stats-total")).toHaveTextContent("3");
    expect(screen.getByTestId("stats-overdue")).toHaveTextContent("1");
  });

  it("shows assignee badge on cards with assignee_username", async () => {
    const payload = structuredClone(boardPayload);
    payload.cards["1"] = { ...payload.cards["1"], assignee_username: "alice" };

    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url === "/api/users") return new Response(JSON.stringify(mockUsers), { status: 200 });
      if (url.includes("/stats")) return new Response(JSON.stringify(mockStats), { status: 200 });
      if (url.includes("/comments")) return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/api/board") && method === "GET") return new Response(JSON.stringify(payload), { status: 200 });
      if (url.includes("/api/chat")) return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    expect(await screen.findByTestId("card-assignee-1")).toBeInTheDocument();
    expect(screen.getByTestId("card-assignee-1")).toHaveTextContent("A");
  });

  it("shows and adds comments on a card", async () => {
    const commentsData = [
      { id: "c1", content: "First comment", author: "user", createdAt: "2026-01-01" },
    ];

    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url === "/api/users") return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/stats")) return new Response(JSON.stringify(mockStats), { status: 200 });
      if (url.includes("/comments") && method === "GET") return new Response(JSON.stringify(commentsData), { status: 200 });
      if (url.includes("/comments") && method === "POST") {
        const body = JSON.parse(String(init?.body ?? "{}")) as { content?: string };
        return new Response(
          JSON.stringify({ id: "c2", content: body.content ?? "", author: "user", createdAt: "2026-01-02" }),
          { status: 200 }
        );
      }
      if (url.includes("/api/board") && method === "GET") return new Response(JSON.stringify(boardPayload), { status: 200 });
      if (url.includes("/api/chat")) return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    // Open comments section
    const card1 = screen.getByTestId("card-1");
    await userEvent.click(within(card1).getByRole("button", { name: /show comments for card one/i }));

    expect(await within(card1).findByTestId("comments-1")).toBeInTheDocument();
    expect(within(card1).getByText("First comment")).toBeInTheDocument();

    // Add a new comment
    const commentInput = within(card1).getByLabelText("New comment");
    await userEvent.type(commentInput, "My new comment");
    await userEvent.click(within(card1).getByRole("button", { name: "Post" }));

    await waitFor(() => {
      expect(within(card1).getByText("My new comment")).toBeInTheDocument();
    });
  });

  it("renders action bar with archived, activity, and export buttons", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    expect(screen.getByTestId("action-bar")).toBeInTheDocument();
    expect(screen.getByLabelText("Toggle archived cards")).toBeInTheDocument();
    expect(screen.getByLabelText("Toggle activity log")).toBeInTheDocument();
    expect(screen.getByLabelText("Export board as JSON")).toBeInTheDocument();
    expect(screen.getByLabelText("Export board as CSV")).toBeInTheDocument();
  });

  it("shows archived panel with cards when toggle is clicked", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.click(screen.getByLabelText("Toggle archived cards"));

    expect(await screen.findByTestId("archived-panel")).toBeInTheDocument();
    expect(await screen.findByTestId("archived-card-99")).toBeInTheDocument();
    expect(screen.getByText("Archived card")).toBeInTheDocument();
  });

  it("restores a card from the archived panel", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.click(screen.getByLabelText("Toggle archived cards"));
    await screen.findByTestId("archived-card-99");

    await userEvent.click(screen.getByLabelText("Restore Archived card"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/cards/99/restore",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("permanently deletes a card from the archived panel", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.click(screen.getByLabelText("Toggle archived cards"));
    await screen.findByTestId("archived-card-99");

    await userEvent.click(screen.getByLabelText("Permanently delete Archived card"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/cards/99/permanent",
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });

  it("hides archived panel when toggle is clicked again", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const archivedToggle = screen.getByLabelText("Toggle archived cards");
    await userEvent.click(archivedToggle);
    await screen.findByTestId("archived-panel");

    await userEvent.click(archivedToggle);
    expect(screen.queryByTestId("archived-panel")).not.toBeInTheDocument();
  });

  it("shows activity panel when toggle is clicked", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.click(screen.getByLabelText("Toggle activity log"));

    expect(await screen.findByTestId("activity-panel")).toBeInTheDocument();
    expect(await screen.findByTestId("activity-entry-1")).toBeInTheDocument();
    expect(screen.getByText(/create card/i)).toBeInTheDocument();
  });

  it("hides activity panel when toggle is clicked again", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const activityToggle = screen.getByLabelText("Toggle activity log");
    await userEvent.click(activityToggle);
    await screen.findByTestId("activity-panel");

    await userEvent.click(activityToggle);
    expect(screen.queryByTestId("activity-panel")).not.toBeInTheDocument();
  });

  it("shows estimate badge on card with estimate set", async () => {
    const payload = structuredClone(boardPayload);
    payload.cards["1"] = { ...payload.cards["1"], estimate: 5 };

    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url === "/api/users") return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/stats")) return new Response(JSON.stringify(mockStats), { status: 200 });
      if (url.includes("/checklist")) return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/comments")) return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/api/board") && method === "GET") return new Response(JSON.stringify(payload), { status: 200 });
      if (url.includes("/api/chat")) return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    expect(await screen.findByTestId("card-estimate-1")).toHaveTextContent("5 pts");
    expect(screen.queryByTestId("card-estimate-2")).not.toBeInTheDocument();
  });

  it("shows estimate stat badge when total_estimate > 0", async () => {
    const statsWithEst = { ...mockStats, total_estimate: 13 };

    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url === "/api/users") return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/stats")) return new Response(JSON.stringify(statsWithEst), { status: 200 });
      if (url.includes("/checklist")) return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/comments")) return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/api/board") && method === "GET") return new Response(JSON.stringify(boardPayload), { status: 200 });
      if (url.includes("/api/chat")) return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    expect(await screen.findByTestId("stats-estimate")).toHaveTextContent("13");
  });

  it("does not show estimate stat badge when total_estimate is 0", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    await screen.findByTestId("stats-total");

    expect(screen.queryByTestId("stats-estimate")).not.toBeInTheDocument();
  });

  it("sends estimate when editing a card", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);
    const firstCard = screen.getByTestId("card-1");

    await userEvent.click(within(firstCard).getByRole("button", { name: /edit card one/i }));
    const estimateInput = within(firstCard).getByLabelText("Estimate");
    await userEvent.clear(estimateInput);
    await userEvent.type(estimateInput, "8");
    await userEvent.click(within(firstCard).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      const calls = vi.mocked(global.fetch).mock.calls;
      const putCall = calls.find(
        ([url, opts]) =>
          String(url).includes("/api/boards/1/cards/1") &&
          (opts as RequestInit)?.method === "PUT"
      );
      expect(putCall).toBeDefined();
      const body = JSON.parse(String((putCall![1] as RequestInit).body)) as { estimate?: number };
      expect(body.estimate).toBe(8);
    });
  });

  it("shows checklist panel when checklist button is clicked", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const card1 = screen.getByTestId("card-1");
    await userEvent.click(within(card1).getByRole("button", { name: /show checklist for card one/i }));

    expect(await within(card1).findByTestId("checklist-1")).toBeInTheDocument();
  });

  it("adds a checklist item", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const card1 = screen.getByTestId("card-1");
    await userEvent.click(within(card1).getByRole("button", { name: /show checklist for card one/i }));
    await within(card1).findByTestId("checklist-1");

    const checklistInput = within(card1).getByLabelText("New checklist item");
    await userEvent.type(checklistInput, "Write docs");
    await userEvent.click(within(card1).getByRole("button", { name: "Add" }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/1/cards/1/checklist",
        expect.objectContaining({ method: "POST" })
      );
    });

    await waitFor(() => {
      expect(within(card1).getByText("Write docs")).toBeInTheDocument();
    });
  });

  it("hides checklist panel when hide checklist button is clicked", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const card1 = screen.getByTestId("card-1");
    const toggleBtn = within(card1).getByRole("button", { name: /show checklist for card one/i });
    await userEvent.click(toggleBtn);
    await within(card1).findByTestId("checklist-1");

    await userEvent.click(within(card1).getByRole("button", { name: /hide checklist/i }));
    expect(within(card1).queryByTestId("checklist-1")).not.toBeInTheDocument();
  });

  it("shows blocked badge when card has is_blocked true", async () => {
    const payload = structuredClone(boardPayload);
    payload.cards["1"] = { ...payload.cards["1"], is_blocked: true };

    vi.mocked(global.fetch).mockImplementation(async (input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url === "/api/users") return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/stats")) return new Response(JSON.stringify(mockStats), { status: 200 });
      if (url.includes("/checklist")) return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/dependencies")) return new Response(JSON.stringify({ blocks: [], blocked_by: [] }), { status: 200 });
      if (url.includes("/comments")) return new Response(JSON.stringify([]), { status: 200 });
      if (url.includes("/api/board") && method === "GET") return new Response(JSON.stringify(payload), { status: 200 });
      if (url.includes("/api/chat")) return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      return new Response(JSON.stringify({ detail: "Not found" }), { status: 404 });
    });

    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    expect(await screen.findByTestId("card-blocked-1")).toBeInTheDocument();
    expect(screen.queryByTestId("card-blocked-2")).not.toBeInTheDocument();
  });

  it("shows dependencies panel when Dependencies button is clicked", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const card1 = screen.getByTestId("card-1");
    await userEvent.click(within(card1).getByRole("button", { name: /show dependencies for card one/i }));

    expect(await within(card1).findByTestId("deps-1")).toBeInTheDocument();
  });

  it("hides dependencies panel when hide deps button is clicked", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    const card1 = screen.getByTestId("card-1");
    await userEvent.click(within(card1).getByRole("button", { name: /show dependencies for card one/i }));
    await within(card1).findByTestId("deps-1");

    await userEvent.click(within(card1).getByRole("button", { name: /hide dependencies/i }));
    expect(within(card1).queryByTestId("deps-1")).not.toBeInTheDocument();
  });

  it("shows shortcuts button in action bar", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    expect(screen.getByTestId("shortcuts-btn")).toBeInTheDocument();
  });

  it("opens keyboard shortcuts overlay when ? button is clicked", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.click(screen.getByTestId("shortcuts-btn"));
    expect(await screen.findByTestId("shortcuts-overlay")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
  });

  it("closes shortcuts overlay when Close button is clicked", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.click(screen.getByTestId("shortcuts-btn"));
    await screen.findByTestId("shortcuts-overlay");

    await userEvent.click(screen.getByLabelText("Close keyboard shortcuts"));
    expect(screen.queryByTestId("shortcuts-overlay")).not.toBeInTheDocument();
  });

  it("opens shortcuts overlay with ? keyboard shortcut", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.keyboard("?");
    expect(await screen.findByTestId("shortcuts-overlay")).toBeInTheDocument();
  });

  it("closes shortcuts overlay with Escape key", async () => {
    render(<KanbanBoard boardId="1" />);
    await screen.findAllByTestId(/column-/i);

    await userEvent.click(screen.getByTestId("shortcuts-btn"));
    await screen.findByTestId("shortcuts-overlay");

    await userEvent.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByTestId("shortcuts-overlay")).not.toBeInTheDocument();
    });
  });
});
