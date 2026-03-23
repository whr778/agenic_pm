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

beforeEach(() => {
  const boardState = structuredClone(boardPayload);

  vi.spyOn(global, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";

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
      return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
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
      name: /delete card one/i,
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

    await userEvent.click(screen.getByRole("button", { name: /delete card one/i }));
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
});
