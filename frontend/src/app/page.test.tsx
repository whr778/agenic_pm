import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Home from "@/app/page";

vi.mock("@/components/KanbanBoard", () => ({
  KanbanBoard: ({ boardId }: { boardId: string }) => <div data-testid="mock-kanban-board">Board {boardId}</div>,
}));

const boardsPayload = {
  boards: [{ id: "1", name: "Main Board", createdAt: "2025-01-01", updatedAt: "2025-01-01" }],
};

type MockResponse = {
  ok: boolean;
  status?: number;
  payload?: object;
};

function jsonResponse({ ok, status = 200, payload = {} }: MockResponse): Response {
  return new Response(JSON.stringify(payload), { status: ok ? status : status || 500 });
}

describe("Home page auth flow", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows sign-in when session is unauthenticated", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      jsonResponse({ ok: true, payload: { authenticated: false } })
    );

    render(<Home />);

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByText("Use user/password to continue.")).toBeInTheDocument();
  });

  it("shows generic sign-in state when session check fails", async () => {
    vi.mocked(global.fetch).mockRejectedValueOnce(new Error("offline"));

    render(<Home />);

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("shows invalid credentials error on failed login", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: false } }))
      .mockResolvedValueOnce(jsonResponse({ ok: false, status: 401, payload: { detail: "bad" } }));

    render(<Home />);

    await screen.findByRole("heading", { name: "Sign in" });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Invalid credentials. Use user/password.")).toBeInTheDocument();
  });

  it("signs in and shows the board", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: false } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: boardsPayload }));

    render(<Home />);

    await screen.findByRole("heading", { name: "Sign in" });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByTestId("mock-kanban-board")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
  });

  it("shows admin navigation for admin session", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true, role: "admin" } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: boardsPayload }));

    render(<Home />);

    expect(await screen.findByTestId("mock-kanban-board")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Admin" })).toHaveAttribute("href", "/admin");
  });

  it("hides admin navigation for non-admin session", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true, role: "user" } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: boardsPayload }));

    render(<Home />);

    expect(await screen.findByTestId("mock-kanban-board")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Admin" })).not.toBeInTheDocument();
  });

  it("handles login network error", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: false } }))
      .mockRejectedValueOnce(new Error("network"));

    render(<Home />);

    await screen.findByRole("heading", { name: "Sign in" });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Unable to sign in right now.")).toBeInTheDocument();
  });

  it("logs out from authenticated session", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: boardsPayload }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { status: "ok" } }));

    render(<Home />);

    expect(await screen.findByTestId("mock-kanban-board")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    });

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("creates a new board", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: boardsPayload }))
      .mockResolvedValueOnce(
        jsonResponse({
          ok: true,
          payload: { boardId: "2", name: "Sprint Board", columns: [] },
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ok: true,
          payload: {
            boards: [
              ...boardsPayload.boards,
              { id: "2", name: "Sprint Board", createdAt: "2025-01-02", updatedAt: "2025-01-02" },
            ],
          },
        })
      );

    render(<Home />);
    await screen.findByTestId("mock-kanban-board");

    const boardInput = screen.getByPlaceholderText("New board name");
    await userEvent.type(boardInput, "Sprint Board");
    await userEvent.click(screen.getByRole("button", { name: "Add Board" }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("creates a board via Enter key", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: boardsPayload }))
      .mockResolvedValueOnce(
        jsonResponse({
          ok: true,
          payload: { boardId: "2", name: "Board X", columns: [] },
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ok: true,
          payload: {
            boards: [
              ...boardsPayload.boards,
              { id: "2", name: "Board X", createdAt: "2025-01-02", updatedAt: "2025-01-02" },
            ],
          },
        })
      );

    render(<Home />);
    await screen.findByTestId("mock-kanban-board");

    const boardInput = screen.getByPlaceholderText("New board name");
    await userEvent.type(boardInput, "Board X{Enter}");

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("shows error on board creation failure", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: boardsPayload }))
      .mockResolvedValueOnce(
        jsonResponse({ ok: false, status: 400, payload: { detail: "already exists" } })
      );

    render(<Home />);
    await screen.findByTestId("mock-kanban-board");

    const boardInput = screen.getByPlaceholderText("New board name");
    await userEvent.type(boardInput, "Main Board");
    await userEvent.click(screen.getByRole("button", { name: "Add Board" }));

    expect(await screen.findByText("already exists")).toBeInTheDocument();
  });

  it("shows error on board creation network failure", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: boardsPayload }))
      .mockRejectedValueOnce(new Error("network"));

    render(<Home />);
    await screen.findByTestId("mock-kanban-board");

    const boardInput = screen.getByPlaceholderText("New board name");
    await userEvent.type(boardInput, "New Board");
    await userEvent.click(screen.getByRole("button", { name: "Add Board" }));

    expect(await screen.findByText("Unable to create board")).toBeInTheDocument();
  });

  it("deletes a board", async () => {
    const twoBoards = {
      boards: [
        { id: "1", name: "Board A", createdAt: "2025-01-01", updatedAt: "2025-01-01" },
        { id: "2", name: "Board B", createdAt: "2025-01-02", updatedAt: "2025-01-02" },
      ],
    };

    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: twoBoards }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { status: "ok" } }))
      .mockResolvedValueOnce(
        jsonResponse({
          ok: true,
          payload: { boards: [twoBoards.boards[0]] },
        })
      );

    render(<Home />);
    await screen.findByTestId("mock-kanban-board");

    await userEvent.click(screen.getByLabelText("Delete board Board B"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/boards/2",
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });

  it("shows error on board deletion failure", async () => {
    const twoBoards = {
      boards: [
        { id: "1", name: "Board A", createdAt: "2025-01-01", updatedAt: "2025-01-01" },
        { id: "2", name: "Board B", createdAt: "2025-01-02", updatedAt: "2025-01-02" },
      ],
    };

    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: twoBoards }))
      .mockResolvedValueOnce(
        jsonResponse({ ok: false, status: 400, payload: { detail: "Cannot delete last board" } })
      );

    render(<Home />);
    await screen.findByTestId("mock-kanban-board");

    await userEvent.click(screen.getByLabelText("Delete board Board B"));

    expect(await screen.findByText("Cannot delete last board")).toBeInTheDocument();
  });

  it("shows error on board deletion network failure", async () => {
    const twoBoards = {
      boards: [
        { id: "1", name: "Board A", createdAt: "2025-01-01", updatedAt: "2025-01-01" },
        { id: "2", name: "Board B", createdAt: "2025-01-02", updatedAt: "2025-01-02" },
      ],
    };

    vi.mocked(global.fetch)
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: { authenticated: true } }))
      .mockResolvedValueOnce(jsonResponse({ ok: true, payload: twoBoards }))
      .mockRejectedValueOnce(new Error("network"));

    render(<Home />);
    await screen.findByTestId("mock-kanban-board");

    await userEvent.click(screen.getByLabelText("Delete board Board B"));

    expect(await screen.findByText("Unable to delete board")).toBeInTheDocument();
  });
});
