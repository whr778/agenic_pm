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
import { KeyboardShortcutsOverlay } from "@/components/KeyboardShortcutsOverlay";
import {
  initialData,
  type ActivityEntry,
  type ArchivedCard,
  type AssignableUser,
  type BoardData,
  type BoardStats,
  type Column,
  type Priority,
  type Sprint,
  type TimeReport,
} from "@/lib/kanban";
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

  // Users for card assignment
  const [assignableUsers, setAssignableUsers] = useState<AssignableUser[]>([]);

  // Board statistics
  const [stats, setStats] = useState<BoardStats | null>(null);

  // Filter state
  const [filterText, setFilterText] = useState("");
  const [filterPriority, setFilterPriority] = useState<Priority | "">("");
  const [filterLabel, setFilterLabel] = useState("");
  const [filterAssignee, setFilterAssignee] = useState("");

  // Archived cards panel
  const [showArchived, setShowArchived] = useState(false);
  const [archivedCards, setArchivedCards] = useState<ArchivedCard[]>([]);
  const [archivedLoading, setArchivedLoading] = useState(false);

  // Activity log panel
  const [showActivity, setShowActivity] = useState(false);
  const [activityLog, setActivityLog] = useState<ActivityEntry[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);

  // Time report panel
  const [showTimeReport, setShowTimeReport] = useState(false);
  const [timeReport, setTimeReport] = useState<TimeReport | null>(null);
  const [timeReportLoading, setTimeReportLoading] = useState(false);

  // Swimlane grouping
  const [swimlaneGroup, setSwimlaneGroup] = useState<"none" | "priority" | "assignee">("none");

  // Sprint management
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [showSprints, setShowSprints] = useState(false);
  const [filterSprint, setFilterSprint] = useState("");
  const [newSprintName, setNewSprintName] = useState("");
  const [newSprintGoal, setNewSprintGoal] = useState("");
  const [newSprintStart, setNewSprintStart] = useState("");
  const [newSprintEnd, setNewSprintEnd] = useState("");
  const [sprintFormError, setSprintFormError] = useState<string | null>(null);

  // Keyboard shortcuts overlay
  const [showShortcuts, setShowShortcuts] = useState(false);

  const filterInputRef = useRef<HTMLInputElement>(null);
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

  const loadUsers = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await apiRef.current("/api/users", { method: "GET", signal });
      const payload = (await response.json()) as AssignableUser[];
      if (!signal?.aborted) setAssignableUsers(payload);
    } catch {
      if (!signal?.aborted) setAssignableUsers([]);
    }
  }, []);

  const loadStats = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await apiRef.current(`/api/boards/${boardId}/stats`, { method: "GET", signal });
      const payload = (await response.json()) as BoardStats;
      if (!signal?.aborted) setStats(payload);
    } catch {
      // stats are non-critical; silently ignore failures
    }
  }, [boardId]);

  const loadSprints = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await apiRef.current(`/api/boards/${boardId}/sprints`, { method: "GET", signal });
      const payload = (await response.json()) as Sprint[];
      if (!signal?.aborted) setSprints(payload);
    } catch {
      if (!signal?.aborted) setSprints([]);
    }
  }, [boardId]);

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;
    void Promise.all([
      loadBoard(controller.signal),
      loadChat(controller.signal),
      loadUsers(controller.signal),
      loadStats(controller.signal),
      loadSprints(controller.signal),
    ]);
    return () => controller.abort();
  }, [loadBoard, loadChat, loadUsers, loadStats, loadSprints]);

  useEffect(() => {
    setBoardNameDraft(board?.name ?? initialData.name);
  }, [board?.name]);

  const keyboardActionsRef = useRef({
    toggleShortcuts: () => setShowShortcuts((v) => !v),
    closeShortcuts: () => setShowShortcuts(false),
    focusFilter: () => filterInputRef.current?.focus(),
    toggleArchived: () => { /* filled below */ },
    toggleActivity: () => { /* filled below */ },
  });

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const inInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable;

      if (e.key === "?" && !inInput) {
        keyboardActionsRef.current.toggleShortcuts();
      } else if (e.key === "Escape") {
        keyboardActionsRef.current.closeShortcuts();
      } else if (e.key === "f" && !inInput) {
        e.preventDefault();
        keyboardActionsRef.current.focusFilter();
      } else if (e.key === "a" && !inInput) {
        keyboardActionsRef.current.toggleArchived();
      } else if (e.key === "l" && !inInput) {
        keyboardActionsRef.current.toggleActivity();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

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

  // Compute filtered columns based on active filters
  const filteredColumns = useMemo(() => {
    if (!board) return [];
    const textLower = filterText.trim().toLowerCase();
    const labelLower = filterLabel.trim().toLowerCase();
    const hasFilters = textLower || filterPriority || labelLower || filterAssignee || filterSprint;
    if (!hasFilters) return board.columns;

    return board.columns.map((col) => {
      const filteredIds = col.cardIds.filter((cardId) => {
        const card = board.cards[cardId];
        if (!card) return false;
        if (textLower && !card.title.toLowerCase().includes(textLower) && !card.details.toLowerCase().includes(textLower)) return false;
        if (filterPriority && card.priority !== filterPriority) return false;
        if (labelLower && !(card.labels ?? []).some((l) => l.toLowerCase().includes(labelLower))) return false;
        if (filterAssignee && card.assignee_id !== filterAssignee) return false;
        if (filterSprint && card.sprint_id !== filterSprint) return false;
        return true;
      });
      return { ...col, cardIds: filteredIds };
    });
  }, [board, filterText, filterPriority, filterLabel, filterAssignee, filterSprint]);

  const hasActiveFilters = filterText || filterPriority || filterLabel || filterAssignee || filterSprint;

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
      await Promise.all([loadBoard(), loadStats()]);
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
        body: JSON.stringify({ columnId, title, details }),
      });
      await Promise.all([loadBoard(), loadStats()]);
    } catch (addError) {
      setError(addError instanceof Error ? addError.message : "Unable to add card");
    }
  };

  const handleArchiveCard = async (_columnId: string, cardId: string) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/cards/${cardId}`, { method: "DELETE" });
      await Promise.all([loadBoard(), loadStats()]);
    } catch (archiveError) {
      setError(archiveError instanceof Error ? archiveError.message : "Unable to archive card");
    }
  };

  const loadArchived = async () => {
    setArchivedLoading(true);
    try {
      const response = await apiRef.current(`/api/boards/${boardId}/cards/archived`);
      const payload = (await response.json()) as ArchivedCard[];
      setArchivedCards(payload);
    } catch {
      setArchivedCards([]);
    } finally {
      setArchivedLoading(false);
    }
  };

  const handleRestoreCard = async (cardId: string) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/cards/${cardId}/restore`, { method: "POST" });
      await Promise.all([loadBoard(), loadStats(), loadArchived()]);
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Unable to restore card");
    }
  };

  const handlePermanentDelete = async (cardId: string) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/cards/${cardId}/permanent`, { method: "DELETE" });
      await loadArchived();
    } catch (delError) {
      setError(delError instanceof Error ? delError.message : "Unable to delete card");
    }
  };

  const loadActivity = async () => {
    setActivityLoading(true);
    try {
      const response = await apiRef.current(`/api/boards/${boardId}/activity?limit=50`);
      const payload = (await response.json()) as ActivityEntry[];
      setActivityLog(payload);
    } catch {
      setActivityLog([]);
    } finally {
      setActivityLoading(false);
    }
  };

  const handleExport = (format: "json" | "csv") => {
    window.open(`/api/boards/${boardId}/export?format=${format}`, "_blank");
  };

  const handleToggleArchived = () => {
    const next = !showArchived;
    setShowArchived(next);
    if (next) void loadArchived();
  };

  const handleToggleActivity = () => {
    const next = !showActivity;
    setShowActivity(next);
    if (next) void loadActivity();
  };

  // Keep keyboard action refs fresh
  keyboardActionsRef.current.toggleArchived = handleToggleArchived;
  keyboardActionsRef.current.toggleActivity = handleToggleActivity;

  const handleEditCard = async (
    cardId: string,
    title: string,
    details: string,
    due_date: string | null,
    priority: Priority | null,
    labels: string[],
    assignee_id: string | null,
    estimate: number | null,
    sprint_id: string | null,
  ) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/cards/${cardId}`, {
        method: "PUT",
        body: JSON.stringify({ title, details, due_date, priority, labels, assignee_id, estimate, sprint_id }),
      });
      await Promise.all([loadBoard(), loadStats()]);
    } catch (editError) {
      setError(editError instanceof Error ? editError.message : "Unable to edit card");
    }
  };

  const handleCreateSprint = async () => {
    const name = newSprintName.trim();
    if (!name) { setSprintFormError("Sprint name is required"); return; }
    setSprintFormError(null);
    try {
      await apiRef.current(`/api/boards/${boardId}/sprints`, {
        method: "POST",
        body: JSON.stringify({
          name,
          goal: newSprintGoal.trim(),
          start_date: newSprintStart || null,
          end_date: newSprintEnd || null,
        }),
      });
      setNewSprintName(""); setNewSprintGoal(""); setNewSprintStart(""); setNewSprintEnd("");
      await loadSprints();
    } catch (err) {
      setSprintFormError(err instanceof Error ? err.message : "Failed to create sprint");
    }
  };

  const handleStartSprint = async (sprintId: string) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/sprints/${sprintId}/start`, { method: "POST" });
      await loadSprints();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start sprint");
    }
  };

  const handleCompleteSprint = async (sprintId: string) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/sprints/${sprintId}/complete`, { method: "POST" });
      await loadSprints();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete sprint");
    }
  };

  const handleDeleteSprint = async (sprintId: string) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/sprints/${sprintId}`, { method: "DELETE" });
      if (filterSprint === sprintId) setFilterSprint("");
      await Promise.all([loadSprints(), loadBoard()]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete sprint");
    }
  };

  const handleSetWipLimit = async (columnId: string, wip_limit: number | null) => {
    try {
      await apiRef.current(`/api/boards/${boardId}/columns/${columnId}/wip-limit`, {
        method: "PUT",
        body: JSON.stringify({ wip_limit }),
      });
      await loadBoard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set WIP limit");
    }
  };

  const loadTimeReport = useCallback(async () => {
    setTimeReportLoading(true);
    try {
      const response = await apiRef.current(`/api/boards/${boardId}/time-report`);
      setTimeReport((await response.json()) as TimeReport);
    } catch {
      setTimeReport(null);
    } finally {
      setTimeReportLoading(false);
    }
  }, [boardId]);

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
        void loadStats();
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
            <div className="flex flex-col gap-3">
              <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  Focus
                </p>
                <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                  Five columns. Zero clutter.
                </p>
              </div>
              {stats && (
                <div className="flex gap-3">
                  <div className="flex-1 rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-center" data-testid="stats-total">
                    <p className="text-2xl font-bold text-[var(--navy-dark)]">{stats.total_cards}</p>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">Cards</p>
                  </div>
                  {stats.total_estimate > 0 && (
                    <div className="flex-1 rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-center" data-testid="stats-estimate">
                      <p className="text-2xl font-bold text-[var(--secondary-purple)]">{stats.total_estimate}</p>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">Points</p>
                    </div>
                  )}
                  {stats.overdue_count > 0 && (
                    <div className="flex-1 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-center" data-testid="stats-overdue">
                      <p className="text-2xl font-bold text-red-600">{stats.overdue_count}</p>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-red-500">Overdue</p>
                    </div>
                  )}
                </div>
              )}
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

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-2" data-testid="action-bar">
            <button
              type="button"
              onClick={handleToggleArchived}
              className={`rounded-xl border px-3 py-2 text-sm font-semibold transition ${showArchived ? "border-[var(--secondary-purple)] bg-[var(--secondary-purple)]/10 text-[var(--secondary-purple)]" : "border-[var(--stroke)] text-[var(--gray-text)] hover:text-[var(--navy-dark)]"}`}
              aria-label="Toggle archived cards"
              data-testid="archived-toggle"
            >
              Archived
            </button>
            <button
              type="button"
              onClick={handleToggleActivity}
              className={`rounded-xl border px-3 py-2 text-sm font-semibold transition ${showActivity ? "border-[var(--primary-blue)] bg-[var(--primary-blue)]/10 text-[var(--primary-blue)]" : "border-[var(--stroke)] text-[var(--gray-text)] hover:text-[var(--navy-dark)]"}`}
              aria-label="Toggle activity log"
              data-testid="activity-toggle"
            >
              Activity
            </button>
            <button
              type="button"
              onClick={() => handleExport("json")}
              className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm font-semibold text-[var(--gray-text)] hover:text-[var(--navy-dark)]"
              aria-label="Export board as JSON"
              data-testid="export-json"
            >
              Export JSON
            </button>
            <button
              type="button"
              onClick={() => handleExport("csv")}
              className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm font-semibold text-[var(--gray-text)] hover:text-[var(--navy-dark)]"
              aria-label="Export board as CSV"
              data-testid="export-csv"
            >
              Export CSV
            </button>
            <button
              type="button"
              onClick={() => setShowSprints((v) => !v)}
              className={`rounded-xl border px-3 py-2 text-sm font-semibold transition ${showSprints ? "border-[var(--accent-yellow)] bg-[var(--accent-yellow)]/10 text-[var(--navy-dark)]" : "border-[var(--stroke)] text-[var(--gray-text)] hover:text-[var(--navy-dark)]"}`}
              aria-label="Toggle sprint management"
              data-testid="sprints-toggle"
            >
              Sprints
            </button>
            <button
              type="button"
              onClick={() => { setShowTimeReport((v) => { if (!v) void loadTimeReport(); return !v; }); }}
              className={`rounded-xl border px-3 py-2 text-sm font-semibold transition ${showTimeReport ? "border-[var(--accent-yellow)] bg-[var(--accent-yellow)]/10 text-[var(--navy-dark)]" : "border-[var(--stroke)] text-[var(--gray-text)] hover:text-[var(--navy-dark)]"}`}
              aria-label="Toggle time report"
              data-testid="time-report-toggle"
            >
              Time report
            </button>
            <select
              value={swimlaneGroup}
              onChange={(e) => setSwimlaneGroup(e.target.value as "none" | "priority" | "assignee")}
              className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none"
              aria-label="Swimlane grouping"
              data-testid="swimlane-select"
            >
              <option value="none">No swimlanes</option>
              <option value="priority">By priority</option>
              <option value="assignee">By assignee</option>
            </select>
            <button
              type="button"
              onClick={() => setShowShortcuts(true)}
              className="ml-auto rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm font-semibold text-[var(--gray-text)] hover:text-[var(--navy-dark)]"
              aria-label="Show keyboard shortcuts"
              data-testid="shortcuts-btn"
            >
              ?
            </button>
          </div>

          {/* Filter bar */}
          <div className="flex flex-wrap items-center gap-3" data-testid="filter-bar">
            <input
              ref={filterInputRef}
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              placeholder="Search cards..."
              className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none ring-[var(--primary-blue)]/30 focus:ring"
              aria-label="Search cards"
            />
            <select
              value={filterPriority}
              onChange={(e) => setFilterPriority(e.target.value as Priority | "")}
              className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none"
              aria-label="Filter by priority"
            >
              <option value="">All priorities</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
            <input
              value={filterLabel}
              onChange={(e) => setFilterLabel(e.target.value)}
              placeholder="Filter by label..."
              className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none ring-[var(--primary-blue)]/30 focus:ring"
              aria-label="Filter by label"
            />
            {assignableUsers.length > 0 && (
              <select
                value={filterAssignee}
                onChange={(e) => setFilterAssignee(e.target.value)}
                className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none"
                aria-label="Filter by assignee"
              >
                <option value="">All assignees</option>
                {assignableUsers.map((u) => (
                  <option key={u.id} value={u.id}>{u.username}</option>
                ))}
              </select>
            )}
            {sprints.length > 0 && (
              <select
                value={filterSprint}
                onChange={(e) => setFilterSprint(e.target.value)}
                className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none"
                aria-label="Filter by sprint"
                data-testid="filter-sprint"
              >
                <option value="">All sprints</option>
                {sprints.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            )}
            {hasActiveFilters && (
              <button
                type="button"
                onClick={() => {
                  setFilterText("");
                  setFilterPriority("");
                  setFilterLabel("");
                  setFilterAssignee("");
                  setFilterSprint("");
                }}
                className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm font-semibold text-[var(--gray-text)] hover:text-[var(--navy-dark)]"
                aria-label="Clear filters"
              >
                Clear filters
              </button>
            )}
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
              {filteredColumns.map((column, colIdx) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  boardId={boardId}
                  assignableUsers={assignableUsers}
                  boardCards={safeBoard.cards}
                  sprints={sprints}
                  cards={column.cardIds.map((cardId) => safeBoard.cards[cardId]).filter(Boolean)}
                  isFirstColumn={colIdx === 0}
                  isLastColumn={colIdx === safeBoard.columns.length - 1}
                  onRename={handleRenameColumn}
                  onSetWipLimit={handleSetWipLimit}
                  onAddCard={handleAddCard}
                  onArchiveCard={handleArchiveCard}
                  onEditCard={handleEditCard}
                  onMoveCard={handleMoveCard}
                  swimlaneGroup={swimlaneGroup}
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

          {/* Archived cards panel */}
          {showArchived && (
            <section
              className="rounded-[28px] border border-[var(--stroke)] bg-white/90 p-6 shadow-[var(--shadow)]"
              data-testid="archived-panel"
            >
              <h2 className="font-display text-xl font-semibold text-[var(--navy-dark)]">Archived Cards</h2>
              {archivedLoading ? (
                <p className="mt-4 text-sm text-[var(--gray-text)]">Loading...</p>
              ) : archivedCards.length === 0 ? (
                <p className="mt-4 text-sm text-[var(--gray-text)]">No archived cards.</p>
              ) : (
                <ul className="mt-4 space-y-3">
                  {archivedCards.map((card) => (
                    <li
                      key={card.id}
                      className="flex items-center justify-between gap-4 rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3"
                      data-testid={`archived-card-${card.id}`}
                    >
                      <div className="min-w-0">
                        <p className="font-semibold text-[var(--navy-dark)]">{card.title}</p>
                        <p className="text-xs text-[var(--gray-text)]">{card.columnTitle}</p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => void handleRestoreCard(card.id)}
                          className="rounded-xl border border-[var(--primary-blue)] px-3 py-1.5 text-xs font-semibold text-[var(--primary-blue)] hover:bg-[var(--primary-blue)]/10"
                          aria-label={`Restore ${card.title}`}
                        >
                          Restore
                        </button>
                        <button
                          type="button"
                          onClick={() => void handlePermanentDelete(card.id)}
                          className="rounded-xl border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50"
                          aria-label={`Permanently delete ${card.title}`}
                        >
                          Delete
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* Activity log panel */}
          {showActivity && (
            <section
              className="rounded-[28px] border border-[var(--stroke)] bg-white/90 p-6 shadow-[var(--shadow)]"
              data-testid="activity-panel"
            >
              <h2 className="font-display text-xl font-semibold text-[var(--navy-dark)]">Activity Log</h2>
              {activityLoading ? (
                <p className="mt-4 text-sm text-[var(--gray-text)]">Loading...</p>
              ) : activityLog.length === 0 ? (
                <p className="mt-4 text-sm text-[var(--gray-text)]">No activity yet.</p>
              ) : (
                <ul className="mt-4 space-y-2">
                  {activityLog.map((entry) => (
                    <li
                      key={entry.id}
                      className="flex items-baseline gap-3 rounded-xl px-3 py-2 even:bg-[var(--surface)]"
                      data-testid={`activity-entry-${entry.id}`}
                    >
                      <span className="w-28 shrink-0 text-xs text-[var(--gray-text)]">
                        {new Date(entry.createdAt).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <span className="text-xs font-semibold text-[var(--navy-dark)]">{entry.actor}</span>
                      <span className="text-xs text-[var(--gray-text)]">
                        {entry.action.replace(/_/g, " ")}
                        {entry.detail ? `: ${entry.detail}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* Sprint management panel */}
          {showSprints && (
            <section
              className="rounded-[28px] border border-[var(--stroke)] bg-white/90 p-6 shadow-[var(--shadow)]"
              data-testid="sprints-panel"
            >
              <h2 className="font-display text-xl font-semibold text-[var(--navy-dark)]">Sprint Management</h2>

              {/* Create sprint form */}
              <div className="mt-4 grid gap-3 rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] p-4 sm:grid-cols-2">
                <div>
                  <label className="block text-xs font-semibold text-[var(--gray-text)]">Sprint name</label>
                  <input
                    value={newSprintName}
                    onChange={(e) => setNewSprintName(e.target.value)}
                    placeholder="Sprint 1"
                    maxLength={256}
                    className="mt-1 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none"
                    aria-label="New sprint name"
                    data-testid="sprint-name-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--gray-text)]">Goal</label>
                  <input
                    value={newSprintGoal}
                    onChange={(e) => setNewSprintGoal(e.target.value)}
                    placeholder="What is the sprint goal?"
                    maxLength={1000}
                    className="mt-1 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none"
                    aria-label="New sprint goal"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--gray-text)]">Start date</label>
                  <input
                    type="date"
                    value={newSprintStart}
                    onChange={(e) => setNewSprintStart(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none"
                    aria-label="Sprint start date"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--gray-text)]">End date</label>
                  <input
                    type="date"
                    value={newSprintEnd}
                    onChange={(e) => setNewSprintEnd(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none"
                    aria-label="Sprint end date"
                  />
                </div>
                {sprintFormError && (
                  <p className="col-span-2 text-xs text-red-600" role="alert">{sprintFormError}</p>
                )}
                <div className="col-span-2">
                  <button
                    type="button"
                    onClick={() => void handleCreateSprint()}
                    className="rounded-xl bg-[var(--accent-yellow)] px-4 py-2 text-sm font-semibold text-[var(--navy-dark)]"
                    data-testid="create-sprint-btn"
                  >
                    Create sprint
                  </button>
                </div>
              </div>

              {/* Sprint list */}
              {sprints.length === 0 ? (
                <p className="mt-4 text-sm text-[var(--gray-text)]">No sprints yet.</p>
              ) : (
                <ul className="mt-4 space-y-3">
                  {sprints.map((sprint) => (
                    <li
                      key={sprint.id}
                      className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3"
                      data-testid={`sprint-${sprint.id}`}
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-semibold text-[var(--navy-dark)]">{sprint.name}</p>
                          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${sprint.status === "active" ? "bg-green-100 text-green-700" : sprint.status === "completed" ? "bg-gray-100 text-gray-500" : "bg-blue-100 text-blue-700"}`}>
                            {sprint.status}
                          </span>
                        </div>
                        {sprint.goal && (
                          <p className="text-xs text-[var(--gray-text)]">{sprint.goal}</p>
                        )}
                        {(sprint.start_date || sprint.end_date) && (
                          <p className="text-xs text-[var(--gray-text)]">
                            {sprint.start_date ?? "?"} &ndash; {sprint.end_date ?? "?"}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {sprint.status === "planning" && (
                          <button
                            type="button"
                            onClick={() => void handleStartSprint(sprint.id)}
                            className="rounded-xl border border-green-300 px-3 py-1.5 text-xs font-semibold text-green-700 hover:bg-green-50"
                            aria-label={`Start sprint ${sprint.name}`}
                            data-testid={`start-sprint-${sprint.id}`}
                          >
                            Start
                          </button>
                        )}
                        {sprint.status === "active" && (
                          <button
                            type="button"
                            onClick={() => void handleCompleteSprint(sprint.id)}
                            className="rounded-xl border border-[var(--primary-blue)] px-3 py-1.5 text-xs font-semibold text-[var(--primary-blue)] hover:bg-[var(--primary-blue)]/10"
                            aria-label={`Complete sprint ${sprint.name}`}
                            data-testid={`complete-sprint-${sprint.id}`}
                          >
                            Complete
                          </button>
                        )}
                        {sprint.status !== "active" && (
                          <button
                            type="button"
                            onClick={() => void handleDeleteSprint(sprint.id)}
                            className="rounded-xl border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50"
                            aria-label={`Delete sprint ${sprint.name}`}
                            data-testid={`delete-sprint-${sprint.id}`}
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* Time report panel */}
          {showTimeReport && (
            <section
              className="rounded-[28px] border border-[var(--stroke)] bg-white/90 p-6 shadow-[var(--shadow)]"
              data-testid="time-report-panel"
            >
              <div className="flex items-center justify-between">
                <h2 className="font-display text-xl font-semibold text-[var(--navy-dark)]">Time Report</h2>
                <button
                  type="button"
                  onClick={() => void loadTimeReport()}
                  className="text-xs text-[var(--gray-text)] hover:text-[var(--navy-dark)]"
                  aria-label="Refresh time report"
                >
                  Refresh
                </button>
              </div>
              {timeReportLoading ? (
                <p className="mt-4 text-sm text-[var(--gray-text)]">Loading...</p>
              ) : !timeReport || timeReport.total_minutes === 0 ? (
                <p className="mt-4 text-sm text-[var(--gray-text)]">No time logged yet.</p>
              ) : (
                <div className="mt-4 grid gap-6 sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">By team member</p>
                    <ul className="mt-2 space-y-1">
                      {timeReport.by_user.map((u) => (
                        <li key={u.user_id} className="flex items-center justify-between rounded-xl bg-[var(--surface)] px-3 py-2">
                          <span className="text-sm font-semibold text-[var(--navy-dark)]">{u.username}</span>
                          <span className="text-sm text-green-700">{u.total_minutes}m ({u.entry_count} entries)</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">By card (top 20)</p>
                    <ul className="mt-2 space-y-1">
                      {timeReport.by_card.map((c) => (
                        <li key={c.card_id} className="flex items-center justify-between rounded-xl bg-[var(--surface)] px-3 py-2">
                          <span className="max-w-[60%] truncate text-sm text-[var(--navy-dark)]">{c.title}</span>
                          <span className="text-sm text-green-700">{c.total_minutes}m{c.estimate_minutes != null ? ` / ${c.estimate_minutes}m est` : ""}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <p className="col-span-2 text-sm font-semibold text-[var(--navy-dark)]">
                    Total: {timeReport.total_minutes} minutes
                  </p>
                </div>
              )}
            </section>
          )}

          <DragOverlay>
            {activeCard ? (
              <div className="w-[260px]">
                <KanbanCardPreview card={activeCard} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </main>
      {showShortcuts && (
        <KeyboardShortcutsOverlay onClose={() => setShowShortcuts(false)} />
      )}
    </div>
  );
};
