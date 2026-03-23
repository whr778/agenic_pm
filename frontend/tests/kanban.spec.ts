import { expect, test, type Page } from "@playwright/test";

const mockAuthApi = async (page: Page) => {
  type Role = "user" | "admin";
  type User = {
    id: string;
    username: string;
    password: string;
    role: Role;
    suspended: boolean;
    createdAt: string;
  };

  let authenticatedUsername: string | null = null;
  const users: User[] = [
    {
      id: "1",
      username: "user",
      password: "password",
      role: "admin",
      suspended: false,
      createdAt: "2025-01-01T00:00:00Z",
    },
  ];

  const requireUser = () => users.find((u) => u.username === authenticatedUsername) ?? null;

  const messages: Array<{ role: "user" | "assistant" | "system"; content: string }> = [];
  const board = {
    boardId: "1",
    name: "Main Board",
    columns: [
      { id: "1", key: "backlog", title: "Backlog", cardIds: ["1", "2"] },
      { id: "2", key: "todo", title: "To Do", cardIds: ["3"] },
      { id: "3", key: "in_progress", title: "In Progress", cardIds: ["4", "5"] },
      { id: "4", key: "review", title: "Review", cardIds: ["6"] },
      { id: "5", key: "done", title: "Done", cardIds: ["7", "8"] },
    ],
    cards: {
      "1": {
        id: "1",
        title: "Align roadmap themes",
        details: "Draft quarterly themes with impact statements and metrics.",
      },
      "2": {
        id: "2",
        title: "Gather customer signals",
        details: "Review support tags, sales notes, and churn feedback.",
      },
      "3": {
        id: "3",
        title: "Prototype analytics view",
        details: "Sketch initial dashboard layout and key drill-downs.",
      },
      "4": {
        id: "4",
        title: "Refine status language",
        details: "Standardize column labels and tone across the board.",
      },
      "5": {
        id: "5",
        title: "Design card layout",
        details: "Add hierarchy and spacing for scanning dense lists.",
      },
      "6": {
        id: "6",
        title: "QA micro-interactions",
        details: "Verify hover, focus, and loading states.",
      },
      "7": {
        id: "7",
        title: "Ship marketing page",
        details: "Final copy approved and asset pack delivered.",
      },
      "8": {
        id: "8",
        title: "Close onboarding sprint",
        details: "Document release notes and share internally.",
      },
    },
  };

  const boards = [
    {
      id: "1",
      name: "Main Board",
      createdAt: "2025-01-01T00:00:00Z",
      updatedAt: "2025-01-01T00:00:00Z",
    },
  ];

  await page.route("**/api/auth/session", async (route) => {
    const user = requireUser();
    const body = user && !user.suspended
      ? { authenticated: true, username: user.username, role: user.role }
      : { authenticated: false };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });

  await page.route("**/api/auth/login", async (route) => {
    const payload = route.request().postDataJSON() as { username?: string; password?: string };
    const username = String(payload.username ?? "");
    const password = String(payload.password ?? "");
    const user = users.find((entry) => entry.username === username);

    if (!user || user.password !== password) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid credentials" }),
      });
      return;
    }

    if (user.suspended) {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Account suspended" }),
      });
      return;
    }

    authenticatedUsername = user.username;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.route("**/api/auth/logout", async (route) => {
    authenticatedUsername = null;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.route("**/api/boards", async (route) => {
    const user = requireUser();
    if (!user) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
      return;
    }

    const method = route.request().method();
    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ boards }),
      });
      return;
    }

    if (method === "POST") {
      const payload = route.request().postDataJSON() as { name?: string };
      const name = String(payload.name ?? "").trim();
      if (!name) {
        await route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Board name is required" }),
        });
        return;
      }
      const dup = boards.find((entry) => entry.name.toLowerCase() === name.toLowerCase());
      if (dup) {
        await route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Board already exists" }),
        });
        return;
      }
      const id = String(boards.length + 1);
      const createdAt = "2025-01-02T00:00:00Z";
      boards.push({ id, name, createdAt, updatedAt: createdAt });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ boardId: id, name, columns: board.columns }),
      });
      return;
    }

    await route.fulfill({ status: 405 });
  });

  await page.route("**/api/boards/*", async (route) => {
    const user = requireUser();
    if (!user) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
      return;
    }

    const method = route.request().method();
    if (method !== "DELETE") {
      await route.fallback();
      return;
    }

    const boardId = route.request().url().split("/").pop() ?? "";
    const index = boards.findIndex((entry) => entry.id === boardId);
    if (index === -1) {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Board not found" }),
      });
      return;
    }
    if (boards.length <= 1) {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Cannot delete the last board" }),
      });
      return;
    }
    boards.splice(index, 1);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
  });

  await page.route("**/api/board/*", async (route) => {
    const user = requireUser();
    if (!user) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
      return;
    }

    const method = route.request().method();
    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(board),
      });
      return;
    }

    if (method === "PUT") {
      const body = route.request().postDataJSON() as { name: string };
      board.name = body.name;
      const current = boards.find((entry) => entry.id === board.boardId);
      if (current) {
        current.name = body.name;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ boardId: "1", name: board.name }),
      });
      return;
    }

    await route.fulfill({ status: 405 });
  });

  await page.route("**/api/chat/*", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fulfill({ status: 405 });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ messages }),
    });
  });

  await page.route("**/api/ai/chat", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fulfill({ status: 405 });
      return;
    }

    const body = route.request().postDataJSON() as { message?: string };
    const userMessage = body.message ?? "";
    messages.push({ role: "user", content: userMessage });

    let assistantMessage = "Acknowledged";
    let appliedUpdates = false;
    let updateCount = 0;

    if (/rename board/i.test(userMessage)) {
      board.name = "AI Planned Board";
      assistantMessage = "I renamed the board.";
      appliedUpdates = true;
      updateCount = 1;
    }

    messages.push({ role: "assistant", content: assistantMessage });

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        assistantMessage,
        appliedUpdates,
        updateCount,
        updatesError: null,
        board,
      }),
    });
  });

  await page.route("**/api/boards/*/columns/*", async (route) => {
    const method = route.request().method();
    if (method !== "PATCH") {
      await route.fulfill({ status: 405 });
      return;
    }
    const columnId = route.request().url().split("/").pop() ?? "";
    const body = route.request().postDataJSON() as { title: string };
    const column = board.columns.find((item) => item.id === columnId);
    if (column) {
      column.title = body.title;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: columnId, title: body.title }),
    });
  });

  await page.route("**/api/boards/*/cards", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fulfill({ status: 405 });
      return;
    }
    const body = route.request().postDataJSON() as {
      columnId: string;
      title: string;
      details: string;
    };
    const nextId = String(Object.keys(board.cards).length + 1);
    board.cards[nextId] = { id: nextId, title: body.title, details: body.details };
    const column = board.columns.find((item) => item.id === body.columnId);
    if (column) {
      column.cardIds.push(nextId);
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: nextId, columnId: body.columnId, title: body.title, details: body.details }),
    });
  });

  await page.route("**/api/boards/*/cards/*/move", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fulfill({ status: 405 });
      return;
    }
    const cardId = route.request().url().split("/").slice(-2, -1)[0];
    const body = route.request().postDataJSON() as { toColumnId: string; toIndex: number };
    const fromColumn = board.columns.find((column) => column.cardIds.includes(cardId));
    const toColumn = board.columns.find((column) => column.id === body.toColumnId);
    if (fromColumn && toColumn) {
      fromColumn.cardIds = fromColumn.cardIds.filter((id) => id !== cardId);
      const index = Math.max(0, Math.min(body.toIndex, toColumn.cardIds.length));
      toColumn.cardIds.splice(index, 0, cardId);
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: cardId, columnId: body.toColumnId, position: String(body.toIndex) }),
    });
  });

  await page.route("**/api/boards/*/cards/*", async (route) => {
    const method = route.request().method();
    const cardId = route.request().url().split("/").pop() ?? "";
    if (method === "PUT") {
      const body = route.request().postDataJSON() as { title: string; details: string };
      if (board.cards[cardId]) {
        board.cards[cardId] = {
          ...board.cards[cardId],
          title: body.title,
          details: body.details,
        };
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: cardId, title: body.title, details: body.details }),
      });
      return;
    }

    if (method === "DELETE") {
      delete board.cards[cardId];
      for (const column of board.columns) {
        column.cardIds = column.cardIds.filter((id) => id !== cardId);
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
      return;
    }

    await route.fulfill({ status: 405 });
  });

  await page.route("**/api/admin/users", async (route) => {
    const method = route.request().method();
    const user = requireUser();
    if (!user) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
      return;
    }
    if (user.role !== "admin") {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Admin access required" }),
      });
      return;
    }

    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          users: users.map((entry) => ({
            id: entry.id,
            username: entry.username,
            role: entry.role,
            suspended: entry.suspended,
            createdAt: entry.createdAt,
          })),
        }),
      });
      return;
    }

    if (method === "POST") {
      const payload = route.request().postDataJSON() as {
        username?: string;
        password?: string;
        role?: Role;
      };
      const username = String(payload.username ?? "").trim();
      const password = String(payload.password ?? "").trim();
      const role = (payload.role ?? "user") as Role;

      if (!username || !password) {
        await route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Username and password are required" }),
        });
        return;
      }
      if (users.some((entry) => entry.username.toLowerCase() === username.toLowerCase())) {
        await route.fulfill({
          status: 400,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Username already exists" }),
        });
        return;
      }

      const nextId = String(users.length + 1);
      const created: User = {
        id: nextId,
        username,
        password,
        role,
        suspended: false,
        createdAt: "2025-01-03T00:00:00Z",
      };
      users.push(created);

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: created.id,
          username: created.username,
          role: created.role,
          suspended: created.suspended,
        }),
      });
      return;
    }

    await route.fulfill({ status: 405 });
  });

  await page.route("**/api/admin/users/*", async (route) => {
    const method = route.request().method();
    const user = requireUser();
    if (!user) {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not authenticated" }),
      });
      return;
    }
    if (user.role !== "admin") {
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Admin access required" }),
      });
      return;
    }

    const userId = route.request().url().split("/").pop() ?? "";
    const target = users.find((entry) => entry.id === userId);

    if (!target) {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "User not found" }),
      });
      return;
    }

    if (method === "PUT") {
      const payload = route.request().postDataJSON() as {
        username?: string;
        password?: string;
        role?: Role;
        suspended?: boolean;
      };

      if (payload.username !== undefined) {
        const username = String(payload.username).trim();
        if (!username) {
          await route.fulfill({
            status: 400,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Username is required" }),
          });
          return;
        }
        const dup = users.find(
          (entry) => entry.id !== target.id && entry.username.toLowerCase() === username.toLowerCase()
        );
        if (dup) {
          await route.fulfill({
            status: 400,
            contentType: "application/json",
            body: JSON.stringify({ detail: "Username already exists" }),
          });
          return;
        }
        target.username = username;
      }
      if (payload.password !== undefined && String(payload.password).trim()) {
        target.password = String(payload.password).trim();
      }
      if (payload.role !== undefined) {
        target.role = payload.role;
      }
      if (payload.suspended !== undefined) {
        target.suspended = Boolean(payload.suspended);
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: target.id,
          username: target.username,
          role: target.role,
          suspended: target.suspended,
        }),
      });
      return;
    }

    if (method === "DELETE") {
      const index = users.findIndex((entry) => entry.id === userId);
      if (index >= 0) {
        users.splice(index, 1);
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok" }),
      });
      return;
    }

    await route.fulfill({ status: 405 });
  });
};

const signIn = async (page: Page, credentials?: { username: string; password: string }) => {
  await mockAuthApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();

  if (credentials) {
    await page.getByLabel("Username").fill(credentials.username);
    await page.getByLabel("Password").fill(credentials.password);
  }

  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
};

test("loads the kanban board", async ({ page }) => {
  await signIn(page);
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await signIn(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();
});

test("renames a column", async ({ page }) => {
  await signIn(page);
  const firstColumn = page.getByTestId("column-1");
  const input = firstColumn.getByLabel("Column title");
  await input.fill("Ideas");
  await input.blur();
  await expect(input).toHaveValue("Ideas");
});

test("edits and deletes a card", async ({ page }) => {
  await signIn(page);

  const card = page.getByTestId("card-1");
  await card.getByRole("button", { name: /edit align roadmap themes/i }).click();
  await card.getByLabel(/edit title for align roadmap themes/i).fill("Roadmap aligned");
  await card.getByRole("button", { name: "Save" }).click();

  await expect(page.getByText("Roadmap aligned")).toBeVisible();

  await card.getByRole("button", { name: /delete roadmap aligned/i }).click();
  await expect(page.getByTestId("card-1")).toHaveCount(0);
});

test("moves a card between columns", async ({ page }) => {
  await signIn(page);

  const card = page.getByTestId("card-1");
  await card.getByRole("button", { name: /move align roadmap themes right/i }).click();
  await expect(page.getByTestId("column-2").getByTestId("card-1")).toBeVisible();
});

test("logs out back to sign in screen", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("keeps board changes after reload", async ({ page }) => {
  await signIn(page);

  const boardName = page.getByLabel("Board name");
  await boardName.fill("Roadmap Board");
  await boardName.blur();

  await page.reload();

  await expect(page.getByLabel("Board name")).toHaveValue("Roadmap Board");
});

test("sends a chat message and applies AI board update", async ({ page }) => {
  await signIn(page);

  await page.getByLabel("AI chat message").fill("please rename board");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByLabel("Board name")).toHaveValue("AI Planned Board");
  await expect(page.getByTestId("chat-messages")).toContainText("I renamed the board.");
});

test("admin manages users and non-admin is blocked from admin panel", async ({ page }) => {
  await signIn(page);

  // Role is fully reflected in UI after session recheck.
  await page.reload();

  await page.getByRole("link", { name: "Admin" }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole("heading", { name: "User Management" })).toBeVisible();

  await page.getByLabel("Username").fill("qa-user");
  await page.getByLabel("Password").fill("qa-pass");
  await page.getByRole("button", { name: "Create user" }).click();

  const createdRow = page.locator("tr", { hasText: "qa-user" });
  await expect(createdRow).toBeVisible();
  await expect(createdRow).toContainText("user");

  await createdRow.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Edit role for qa-user").selectOption("admin");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.locator("tr", { hasText: "qa-user" })).toContainText("admin");

  await page.getByRole("link", { name: "Back to board" }).click();
  await page.getByRole("button", { name: "Log out" }).click();

  await page.getByLabel("Username").fill("qa-user");
  await page.getByLabel("Password").fill("qa-pass");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: "Admin" })).toBeVisible();

  await page.getByRole("link", { name: "Admin" }).click();
  const promotedRow = page.locator("tr", { hasText: "qa-user" });
  await promotedRow.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Edit role for qa-user").selectOption("user");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.locator("tr", { hasText: "qa-user" })).toContainText("user");

  await page.getByRole("link", { name: "Back to board" }).click();
  await page.getByRole("button", { name: "Log out" }).click();

  await page.getByLabel("Username").fill("qa-user");
  await page.getByLabel("Password").fill("qa-pass");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: "Admin" })).toHaveCount(0);

  await page.goto("/admin");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
});
