"use client";

import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  closestCorners,
  DndContext,
  DragOverlay,
  PointerSensor,
  type CollisionDetection,
  useSensor,
  useSensors,
  pointerWithin,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { initialData, type BoardData, type Column } from "@/lib/kanban";
import type { MoveDirection } from "@/components/KanbanCard";

export const KanbanBoard = ({ boardId }: { boardId: string }) => {
  type ChatMessage = { id?: string; role: "user" | "assistant" | "system"; content: string };

  const [board, setBoard] = useState<BoardData | null>(null);
  const [boardNameDraft, setBoardNameDraft] = useState(initialData.name);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatSubmitting, setChatSubmitting] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  const api = useCallback(async (path: string, init?: RequestInit) => {
    const response = await fetch(path, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });

    if (!response.ok) {
      const fallback = `Request failed: ${response.status}`;
      let detail = fallback;
      try {
        const payload = (await response.json()) as { detail?: string };
        detail = payload.detail || fallback;
      } catch {
        detail = fallback;
      }
      throw new Error(detail);
    }

    return response;
  }, []);

  const apiRef = useRef(api);
  apiRef.current = api;

  const loadBoard = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiRef.current(`/api/board/${boardId}`, { method: "GET", signal });
      const payload = (await response.json()) as BoardData;
      if (!signal?.aborted) setBoard(payload);
    } catch (loadError) {
      if (signal?.aborted) return;
      setError(loadError instanceof Error ? loadError.message : "Unable to load board");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [boardId]);

  const loadChat = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await apiRef.current(`/api/chat/${boardId}`, { method: "GET", signal });
      const payload = (await response.json()) as { messages?: ChatMessage[] };
      if (!signal?.aborted) setChatMessages(payload.messages ?? []);
    } catch {
      if (!signal?.aborted) setChatMessages([]);
    }
  }, [boardId]);

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;
    void Promise.all([loadBoard(controller.signal), loadChat(controller.signal)]);
    return () => controller.abort();
  }, [loadBoard, loadChat]);

  useEffect(() => {
    setBoardNameDraft(board?.name ?? initialData.name);
  }, [board?.name]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const collisionDetection: CollisionDetection = useCallback((args) => {
    const pointerHits = pointerWithin(args);
    if (pointerHits.length > 0) {
      return pointerHits;
    }
    return closestCorners(args);
  }, []);

  const cardsById = useMemo(() => board?.cards ?? {}, [board?.cards]);

  const findColumnByCardId = (columns: Column[], cardId: string) =>
    columns.find((column) => column.cardIds.includes(cardId));

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!board || !over || active.id === over.id) {
      return;
    }

    const activeId = String(active.id);
    const overId = String(over.id);
    const sourceColumn = findColumnByCardId(board.columns, activeId);
    if (!sourceColumn) {
      return;
    }

    const targetColumn = board.columns.find((column) => column.id === overId)
      ?? findColumnByCardId(board.columns, overId);
    if (!targetColumn) {
      return;
    }

    const overIsColumn = board.columns.some((column) => column.id === overId);
    const toIndex = overIsColumn
      ? targetColumn.cardIds.length
      : targetColumn.cardIds.indexOf(overId);

    try {
      await apiRef.current(`/api/boards/${boardId}/cards/${activeId}/move`, {
        method: "POST",
        body: JSON.stringify({
          toColumnId: targetColumn.id,
          toIndex: Math.max(0, toIndex),
        }),
      });
      await loadBoard();
    } catch (moveError) {
      setError(moveError instanceof Error ? moveError.message : "Unable to move card");
    }
  };

  const handleRenameColumn = async (columnId: string, title: string) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/columns/${columnId}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      await loadBoard();
    } catch (renameError) {
      setError(renameError instanceof Error ? renameError.message : "Unable to rename column");
    }
  };

  const handleRenameBoard = async (name: string) => {
    try {
      await apiRef.current(`/api/board/${boardId}`, {
        method: "PUT",
        body: JSON.stringify({ name }),
      });
      await loadBoard();
    } catch (renameError) {
      setError(renameError instanceof Error ? renameError.message : "Unable to rename board");
    }
  };

  const handleAddCard = async (columnId: string, title: string, details: string) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/cards`, {
        method: "POST",
        body: JSON.stringify({
          columnId,
          title,
          details,
        }),
      });
      await loadBoard();
    } catch (addError) {
      setError(addError instanceof Error ? addError.message : "Unable to add card");
    }
  };

  const handleDeleteCard = async (_columnId: string, cardId: string) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/cards/${cardId}`, { method: "DELETE" });
      await loadBoard();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Unable to delete card");
    }
  };

  const handleEditCard = async (cardId: string, title: string, details: string) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/cards/${cardId}`, {
        method: "PUT",
        body: JSON.stringify({ title, details }),
      });
      await loadBoard();
    } catch (editError) {
      setError(editError instanceof Error ? editError.message : "Unable to edit card");
    }
  };

  const handleMoveCard = async (cardId: string, direction: MoveDirection) => {
    if (!board) return;
    const colIndex = board.columns.findIndex((c) => c.cardIds.includes(cardId));
    if (colIndex === -1) return;
    const column = board.columns[colIndex];
    const cardIndex = column.cardIds.indexOf(cardId);

    let toColumnId = column.id;
    let toIndex = cardIndex;

    if (direction === "up") {
      toIndex = cardIndex - 1;
    } else if (direction === "down") {
      toIndex = cardIndex + 1;
    } else if (direction === "left" && colIndex > 0) {
      toColumnId = board.columns[colIndex - 1].id;
      toIndex = board.columns[colIndex - 1].cardIds.length;
    } else if (direction === "right" && colIndex < board.columns.length - 1) {
      toColumnId = board.columns[colIndex + 1].id;
      toIndex = board.columns[colIndex + 1].cardIds.length;
    } else {
      return;
    }

    try {
      await apiRef.current(`/api/boards/${boardId}/cards/${cardId}/move`, {
        method: "POST",
        body: JSON.stringify({ toColumnId, toIndex: Math.max(0, toIndex) }),
      });
      await loadBoard();
    } catch (moveError) {
      setError(moveError instanceof Error ? moveError.message : "Unable to move card");
    }
  };

  const handleSendChat = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message || chatSubmitting) {
      return;
    }

    setChatSubmitting(true);
    setError(null);

    try {
      const response = await apiRef.current("/api/ai/chat", {
        method: "POST",
        body: JSON.stringify({ message, boardId }),
      });
      const payload = (await response.json()) as {
        assistantMessage: string;
        updatesError?: string | null;
        board?: BoardData;
      };

      if (payload.board) {
        setBoard(payload.board);
      }
      setChatMessages((prev) => {
        const next = [
          ...prev,
          { id: crypto.randomUUID(), role: "user" as const, content: message },
          { id: crypto.randomUUID(), role: "assistant" as const, content: payload.assistantMessage },
        ];
        if (payload.updatesError) {
          next.push({ role: "system", content: payload.updatesError });
        }
        return next;
      });
      setChatInput("");
    } catch (chatError) {
      setError(chatError instanceof Error ? chatError.message : "Unable to send chat message");
    } finally {
      setChatSubmitting(false);
    }
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--surface)] px-6">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
          Loading board...
        </p>
      </main>
    );
  }

  if (!board) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--surface)] px-6">
        {error ? (
          <p className="text-sm font-semibold text-red-600" role="alert">
            {error}
          </p>
        ) : null}
      </main>
    );
  }

  const safeBoard = board;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Kanban Board
              </p>
              <input
                className="mt-3 w-full max-w-md bg-transparent font-display text-4xl font-semibold text-[var(--navy-dark)] outline-none"
                maxLength={256}
                aria-label="Board name"
                value={boardNameDraft}
                onChange={(event) => setBoardNameDraft(event.target.value)}
                onBlur={(event) => {
                  const next = event.target.value.trim();
                  if (next && next !== safeBoard.name) {
                    void handleRenameBoard(next);
                  } else {
                    setBoardNameDraft(safeBoard.name);
                  }
                }}
              />
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                Five columns. Zero clutter.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {safeBoard.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
        </header>

        <DndContext
          sensors={sensors}
          collisionDetection={collisionDetection}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            <section className="grid gap-6 lg:grid-cols-5">
              {safeBoard.columns.map((column, colIdx) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds.map((cardId) => safeBoard.cards[cardId])}
                  isFirstColumn={colIdx === 0}
                  isLastColumn={colIdx === safeBoard.columns.length - 1}
                  onRename={handleRenameColumn}
                  onAddCard={handleAddCard}
                  onDeleteCard={handleDeleteCard}
                  onEditCard={handleEditCard}
                  onMoveCard={handleMoveCard}
                />
              ))}
            </section>
            <aside className="flex h-[calc(100vh-220px)] min-h-[460px] flex-col rounded-[28px] border border-[var(--stroke)] bg-white/90 p-5 shadow-[var(--shadow)]">
              <div className="border-b border-[var(--stroke)] pb-3">
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  AI Assistant
                </p>
                <h2 className="mt-2 font-display text-2xl font-semibold text-[var(--navy-dark)]">
                  Board Copilot
                </h2>
              </div>

              <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1" data-testid="chat-messages">
                {chatMessages.length === 0 ? (
                  <p className="rounded-2xl border border-dashed border-[var(--stroke)] px-4 py-3 text-sm text-[var(--gray-text)]">
                    Ask for planning help, card rewrites, or board updates.
                  </p>
                ) : (
                  chatMessages.map((message, index) => (
                    <article
                      key={message.id ?? `${message.role}-${index}`}
                      className={`rounded-2xl px-4 py-3 text-sm leading-6 ${
                        message.role === "user"
                          ? "ml-5 bg-[var(--primary-blue)]/10 text-[var(--navy-dark)]"
                          : message.role === "assistant"
                            ? "mr-5 bg-[var(--surface)] text-[var(--navy-dark)]"
                            : "border border-[var(--accent-yellow)]/50 bg-[var(--accent-yellow)]/10 text-[var(--navy-dark)]"
                      }`}
                    >
                      {message.content}
                    </article>
                  ))
                )}
              </div>

              <form className="mt-4 flex gap-2" onSubmit={handleSendChat}>
                <input
                  aria-label="AI chat message"
                  className="flex-1 rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none ring-[var(--primary-blue)]/30 focus:ring"
                  placeholder="Ask AI to update the board..."
                  maxLength={4000}
                  value={chatInput}
                  onChange={(event) => setChatInput(event.target.value)}
                />
                <button
                  type="submit"
                  className="rounded-xl bg-[var(--secondary-purple)] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={chatSubmitting}
                >
                  {chatSubmitting ? "Sending..." : "Send"}
                </button>
              </form>
            </aside>
          </div>
          {error ? (
            <p className="text-sm font-semibold text-red-600" role="alert">
              {error}
            </p>
          ) : null}
          <DragOverlay>
            {activeCard ? (
              <div className="w-[260px]">
                <KanbanCardPreview card={activeCard} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </main>
    </div>
  );
};
