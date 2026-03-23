"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { KanbanBoard } from "@/components/KanbanBoard";
import type { BoardSummary } from "@/lib/kanban";

type SessionState = {
  loading: boolean;
  authenticated: boolean;
  role: "user" | "admin" | null;
};

const initialState: SessionState = {
  loading: true,
  authenticated: false,
  role: null,
};

export default function Home() {
  const [session, setSession] = useState<SessionState>(initialState);
  const [username, setUsername] = useState("user");
  const [password, setPassword] = useState("password");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [boards, setBoards] = useState<BoardSummary[]>([]);
  const [selectedBoardId, setSelectedBoardId] = useState<string | null>(null);
  const [newBoardName, setNewBoardName] = useState("");
  const [creatingBoard, setCreatingBoard] = useState(false);

  const loadBoards = useCallback(async () => {
    try {
      const response = await fetch("/api/boards", { credentials: "include" });
      if (!response.ok) return;
      const data = (await response.json()) as { boards: BoardSummary[] };
      setBoards(data.boards);
      if (!selectedBoardId && data.boards.length > 0) {
        setSelectedBoardId(data.boards[0].id);
      }
    } catch (err) {
      console.error("loadBoards failed", err);
    }
  }, [selectedBoardId]);

  useEffect(() => {
    const loadSession = async () => {
      try {
        const response = await fetch("/api/auth/session", { credentials: "include" });
        const data = (await response.json()) as { authenticated?: boolean; role?: string };
        const authed = Boolean(data.authenticated);
        setSession({
          loading: false,
          authenticated: authed,
          role: data.role === "admin" ? "admin" : data.role === "user" ? "user" : null,
        });
        if (authed) {
          const boardsRes = await fetch("/api/boards", { credentials: "include" });
          if (boardsRes.ok) {
            const boardsData = (await boardsRes.json()) as { boards: BoardSummary[] };
            setBoards(boardsData.boards);
            if (boardsData.boards.length > 0) {
              setSelectedBoardId(boardsData.boards[0].id);
            }
          }
        }
      } catch {
        setSession({ loading: false, authenticated: false, role: null });
      }
    };

    void loadSession();
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
        credentials: "include",
      });

      if (!response.ok) {
        setError("Invalid credentials. Use user/password.");
        return;
      }

      const loginPayload = (await response.json()) as { role?: string };
      const role =
        loginPayload.role === "admin"
          ? "admin"
          : loginPayload.role === "user"
            ? "user"
            : null;
      setSession({ loading: false, authenticated: true, role });
      setPassword("");
      await loadBoards();
    } catch {
      setError("Unable to sign in right now.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    setSession({ loading: false, authenticated: false, role: null });
    setBoards([]);
    setSelectedBoardId(null);
  };

  const handleCreateBoard = async () => {
    const name = newBoardName.trim();
    if (!name) return;
    setCreatingBoard(true);
    try {
      const response = await fetch("/api/boards", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
        credentials: "include",
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        setError(payload.detail ?? "Unable to create board");
        return;
      }
      const created = (await response.json()) as { boardId: string };
      setNewBoardName("");
      await loadBoards();
      setSelectedBoardId(created.boardId);
    } catch {
      setError("Unable to create board");
    } finally {
      setCreatingBoard(false);
    }
  };

  const handleDeleteBoard = async (boardId: string) => {
    try {
      const response = await fetch(`/api/boards/${boardId}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        setError(payload.detail ?? "Unable to delete board");
        return;
      }
      if (selectedBoardId === boardId) {
        setSelectedBoardId(null);
      }
      await loadBoards();
    } catch {
      setError("Unable to delete board");
    }
  };

  if (session.loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--surface)] px-6">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
          Loading session...
        </p>
      </main>
    );
  }

  if (!session.authenticated) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--surface)] px-6">
        <form
          className="w-full max-w-md rounded-3xl border border-[var(--stroke)] bg-white p-8 shadow-[var(--shadow)]"
          onSubmit={handleSubmit}
        >
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--gray-text)]">
            Project Management MVP
          </p>
          <h1 className="mt-3 font-display text-3xl font-semibold text-[var(--navy-dark)]">
            Sign in
          </h1>
          <p className="mt-2 text-sm text-[var(--gray-text)]">
            Use user/password to continue.
          </p>

          <label className="mt-6 block text-sm font-semibold text-[var(--navy-dark)]">
            Username
            <input
              className="mt-2 w-full rounded-xl border border-[var(--stroke)] px-4 py-3 outline-none ring-[var(--primary-blue)]/30 focus:ring"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
            />
          </label>

          <label className="mt-4 block text-sm font-semibold text-[var(--navy-dark)]">
            Password
            <input
              type="password"
              className="mt-2 w-full rounded-xl border border-[var(--stroke)] px-4 py-3 outline-none ring-[var(--primary-blue)]/30 focus:ring"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>

          {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}

          <button
            className="mt-6 w-full rounded-xl bg-[var(--secondary-purple)] px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </main>
    );
  }

  return (
    <>
      <div className="fixed right-5 top-5 z-20">
        <div className="flex items-center gap-2">
          {session.role === "admin" ? (
            <Link
              href="/admin"
              className="rounded-full border border-[var(--primary-blue)] bg-[var(--primary-blue)]/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--primary-blue)] shadow-[var(--shadow)]"
            >
              Admin
            </Link>
          ) : null}
          <button
            className="rounded-full border border-[var(--stroke)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)] shadow-[var(--shadow)]"
            onClick={handleLogout}
            type="button"
          >
            Log out
          </button>
        </div>
      </div>

      <div className="mx-auto max-w-[1500px] px-6 pt-4">
        <div className="flex flex-wrap items-center gap-3">
          {boards.map((b) => (
            <div key={b.id} className="flex items-center gap-1">
              <button
                type="button"
                className={`rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.15em] transition ${
                  b.id === selectedBoardId
                    ? "border-[var(--primary-blue)] bg-[var(--primary-blue)]/10 text-[var(--primary-blue)]"
                    : "border-[var(--stroke)] bg-white text-[var(--navy-dark)] hover:border-[var(--primary-blue)]"
                }`}
                onClick={() => setSelectedBoardId(b.id)}
              >
                {b.name}
              </button>
              {boards.length > 1 && (
                <button
                  type="button"
                  className="rounded-full px-1 text-xs text-[var(--gray-text)] hover:text-red-600"
                  onClick={() => handleDeleteBoard(b.id)}
                  aria-label={`Delete board ${b.name}`}
                >
                  x
                </button>
              )}
            </div>
          ))}
          <div className="flex items-center gap-2">
            <input
              className="rounded-lg border border-[var(--stroke)] px-3 py-2 text-xs outline-none ring-[var(--primary-blue)]/30 focus:ring"
              placeholder="New board name"
              value={newBoardName}
              onChange={(e) => setNewBoardName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleCreateBoard();
              }}
            />
            <button
              type="button"
              className="rounded-lg bg-[var(--secondary-purple)] px-3 py-2 text-xs font-semibold text-white disabled:opacity-60"
              onClick={handleCreateBoard}
              disabled={creatingBoard || !newBoardName.trim()}
            >
              {creatingBoard ? "Creating..." : "Add Board"}
            </button>
          </div>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      {selectedBoardId ? (
        <KanbanBoard key={selectedBoardId} boardId={selectedBoardId} />
      ) : null}
    </>
  );
}
