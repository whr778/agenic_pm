import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AdminPage from "@/app/admin/page";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

type MockResponse = {
  ok: boolean;
  status?: number;
  payload?: object;
};

function jsonResponse({ ok, status = 200, payload = {} }: MockResponse): Response {
  return new Response(JSON.stringify(payload), { status: ok ? status : status || 500 });
}

type MutableUser = {
  id: string;
  username: string;
  role: "user" | "admin";
  suspended: boolean;
  createdAt?: string;
};

const initialUsers: MutableUser[] = [
  {
    id: "1",
    username: "user",
    role: "admin",
    suspended: false,
    createdAt: "2025-01-01T00:00:00Z",
  },
  {
    id: "2",
    username: "alice",
    role: "user",
    suspended: false,
    createdAt: "2025-01-02T00:00:00Z",
  },
];

function setupAdminFetch(options?: {
  role?: "user" | "admin";
  failCreateWithDetail?: string;
}) {
  const users = structuredClone(initialUsers);
  vi.mocked(global.fetch).mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url === "/api/auth/session" && method === "GET") {
      return jsonResponse({
        ok: true,
        payload: { authenticated: true, role: options?.role ?? "admin" },
      });
    }

    if (url === "/api/admin/users" && method === "GET") {
      return jsonResponse({ ok: true, payload: { users } });
    }

    if (url === "/api/admin/users" && method === "POST") {
      if (options?.failCreateWithDetail) {
        return jsonResponse({
          ok: false,
          status: 400,
          payload: { detail: options.failCreateWithDetail },
        });
      }
      const body = JSON.parse(String(init?.body ?? "{}")) as {
        username?: string;
        role?: "user" | "admin";
      };
      users.push({
        id: String(users.length + 1),
        username: body.username ?? "",
        role: body.role ?? "user",
        suspended: false,
        createdAt: "2025-01-03T00:00:00Z",
      });
      return jsonResponse({ ok: true, payload: users[users.length - 1] });
    }

    if (url.startsWith("/api/admin/users/") && method === "PUT") {
      const userId = url.split("/").at(-1) ?? "";
      const target = users.find((user) => user.id === userId);
      if (!target) {
        return jsonResponse({ ok: false, status: 404, payload: { detail: "User not found" } });
      }
      const body = JSON.parse(String(init?.body ?? "{}")) as {
        username?: string;
        role?: "user" | "admin";
        suspended?: boolean;
      };
      if (body.username !== undefined) target.username = body.username;
      if (body.role !== undefined) target.role = body.role;
      if (body.suspended !== undefined) target.suspended = body.suspended;
      return jsonResponse({ ok: true, payload: target });
    }

    if (url.startsWith("/api/admin/users/") && method === "DELETE") {
      const userId = url.split("/").at(-1) ?? "";
      const index = users.findIndex((user) => user.id === userId);
      if (index >= 0) {
        users.splice(index, 1);
      }
      return jsonResponse({ ok: true, payload: { status: "ok" } });
    }

    return jsonResponse({ ok: false, status: 404, payload: { detail: "Not found" } });
  });
}

describe("Admin page", () => {
  beforeEach(() => {
    vi.spyOn(global, "fetch");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    replaceMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("redirects non-admin users to home", async () => {
    setupAdminFetch({ role: "user" });

    render(<AdminPage />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/");
    });
  });

  it("loads and displays users for admin", async () => {
    setupAdminFetch();

    render(<AdminPage />);

    expect(await screen.findByRole("heading", { name: "User Management" })).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
  });

  it("creates a user and refreshes list", async () => {
    setupAdminFetch();

    render(<AdminPage />);

    await screen.findByText("alice");
    await userEvent.type(screen.getByLabelText("Username"), "bob");
    await userEvent.type(screen.getByLabelText("Password"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "Create user" }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/admin/users",
        expect.objectContaining({ method: "POST" })
      );
    });

    expect(await screen.findByText("User created")).toBeInTheDocument();
  });

  it("edits a user and saves changes", async () => {
    setupAdminFetch();

    render(<AdminPage />);

    await screen.findByText("alice");
    const aliceRow = screen.getByText("alice").closest("tr");
    expect(aliceRow).not.toBeNull();
    await userEvent.click(within(aliceRow as HTMLTableRowElement).getByRole("button", { name: "Edit" }));

    const usernameInput = screen.getByLabelText("Edit username for alice");
    await userEvent.clear(usernameInput);
    await userEvent.type(usernameInput, "alice2");

    await userEvent.selectOptions(screen.getByLabelText("Edit role for alice"), "admin");
    await userEvent.click(screen.getByLabelText("Edit suspended for alice"));
    await userEvent.type(screen.getByLabelText("Edit password for alice"), "new-password");

    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/admin/users/2",
        expect.objectContaining({ method: "PUT" })
      );
    });

    expect(await screen.findByText("User updated")).toBeInTheDocument();
  });

  it("deletes a user", async () => {
    setupAdminFetch();

    render(<AdminPage />);

    await screen.findByText("alice");
    const aliceRow = screen.getByText("alice").closest("tr");
    expect(aliceRow).not.toBeNull();
    await userEvent.click(within(aliceRow as HTMLTableRowElement).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/api/admin/users/2",
        expect.objectContaining({ method: "DELETE" })
      );
    });

    expect(await screen.findByText("User deleted")).toBeInTheDocument();
  });

  it("shows api errors", async () => {
    setupAdminFetch({ failCreateWithDetail: "Username already exists" });

    render(<AdminPage />);

    await screen.findByText("alice");
    await userEvent.type(screen.getByLabelText("Username"), "user");
    await userEvent.type(screen.getByLabelText("Password"), "secret");
    await userEvent.click(screen.getByRole("button", { name: "Create user" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Username already exists");
  });
});
