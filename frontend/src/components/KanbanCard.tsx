import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import type { AssignableUser, Card, CardDependency, ChecklistItem, Comment, Priority, Sprint } from "@/lib/kanban";

export type MoveDirection = "up" | "down" | "left" | "right";

type KanbanCardProps = {
  card: Card;
  boardId: string;
  assignableUsers: AssignableUser[];
  boardCards: Record<string, Card>;
  sprints: Sprint[];
  onArchive: (cardId: string) => void;
  onEdit: (
    cardId: string,
    title: string,
    details: string,
    due_date: string | null,
    priority: Priority | null,
    labels: string[],
    assignee_id: string | null,
    estimate: number | null,
    sprint_id: string | null,
  ) => void;
  onMove?: (cardId: string, direction: MoveDirection) => void;
  canMove?: { up: boolean; down: boolean; left: boolean; right: boolean };
};

const PRIORITY_COLORS: Record<Priority, string> = {
  low: "bg-blue-100 text-blue-700",
  medium: "bg-yellow-100 text-yellow-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

type DueDateStatus = "overdue" | "due-today" | "due-soon" | "upcoming" | null;

function getDueDateStatus(due_date: string | null | undefined): DueDateStatus {
  if (!due_date) return null;
  const today = new Date().toISOString().slice(0, 10);
  if (due_date < today) return "overdue";
  if (due_date === today) return "due-today";
  const soon = new Date();
  soon.setDate(soon.getDate() + 3);
  const soonStr = soon.toISOString().slice(0, 10);
  if (due_date <= soonStr) return "due-soon";
  return "upcoming";
}

function dueDateLabel(due_date: string, status: DueDateStatus): string {
  if (status === "overdue") return `Overdue \u2014 ${due_date}`;
  if (status === "due-today") return "Due today";
  if (status === "due-soon") {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    const target = new Date(`${due_date}T00:00:00`);
    const days = Math.round((target.getTime() - now.getTime()) / 86400000);
    return `Due in ${days} day${days === 1 ? "" : "s"}`;
  }
  return `Due ${due_date}`;
}

const DUE_DATE_CLASSES: Record<NonNullable<DueDateStatus>, string> = {
  overdue: "text-red-600 font-semibold",
  "due-today": "text-amber-600 font-semibold",
  "due-soon": "text-yellow-600",
  upcoming: "text-[var(--gray-text)]",
};

function initials(username: string): string {
  return username
    .split(/[\s_-]+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export const KanbanCard = ({
  card,
  boardId,
  assignableUsers,
  boardCards,
  sprints,
  onArchive,
  onEdit,
  onMove,
  canMove,
}: KanbanCardProps) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id });
  const [isEditing, setIsEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(card.title);
  const [draftDetails, setDraftDetails] = useState(card.details);
  const [draftDueDate, setDraftDueDate] = useState(card.due_date ?? "");
  const [draftPriority, setDraftPriority] = useState<Priority | "">(card.priority ?? "");
  const [draftLabels, setDraftLabels] = useState((card.labels ?? []).join(", "));
  const [draftAssigneeId, setDraftAssigneeId] = useState(card.assignee_id ?? "");
  const [draftEstimate, setDraftEstimate] = useState(card.estimate != null ? String(card.estimate) : "");
  const [draftSprintId, setDraftSprintId] = useState(card.sprint_id ?? "");
  const [titleError, setTitleError] = useState(false);

  // Checklist state
  const [showChecklist, setShowChecklist] = useState(false);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [checklistLoaded, setChecklistLoaded] = useState(false);
  const [checklistInput, setChecklistInput] = useState("");
  const [checklistSubmitting, setChecklistSubmitting] = useState(false);

  // Dependencies state
  const [showDeps, setShowDeps] = useState(false);
  const [blocks, setBlocks] = useState<CardDependency[]>([]);
  const [blockedBy, setBlockedBy] = useState<CardDependency[]>([]);
  const [depsLoaded, setDepsLoaded] = useState(false);
  const [depPickMode, setDepPickMode] = useState<"blocks" | "blocked_by" | null>(null);
  const [depPickCardId, setDepPickCardId] = useState("");
  const [depError, setDepError] = useState<string | null>(null);

  // Comments state
  const [showComments, setShowComments] = useState(false);
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentsLoaded, setCommentsLoaded] = useState(false);
  const [commentInput, setCommentInput] = useState("");
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);
  const commentsEndRef = useRef<HTMLDivElement>(null);

  // Keep local edit drafts in sync when the server refreshes this card.
  useEffect(() => {
    setDraftTitle(card.title);
    setDraftDetails(card.details);
    setDraftDueDate(card.due_date ?? "");
    setDraftPriority(card.priority ?? "");
    setDraftLabels((card.labels ?? []).join(", "));
    setDraftAssigneeId(card.assignee_id ?? "");
    setDraftEstimate(card.estimate != null ? String(card.estimate) : "");
    setDraftSprintId(card.sprint_id ?? "");
  }, [card.title, card.details, card.due_date, card.priority, card.labels, card.assignee_id, card.estimate, card.sprint_id]);

  useEffect(() => {
    if (showDeps && !depsLoaded) {
      void fetch(`/api/boards/${boardId}/cards/${card.id}/dependencies`, { credentials: "include" })
        .then((r) => r.json())
        .then((data: { blocks: CardDependency[]; blocked_by: CardDependency[] }) => {
          setBlocks(data.blocks ?? []);
          setBlockedBy(data.blocked_by ?? []);
          setDepsLoaded(true);
        })
        .catch(() => {
          setDepsLoaded(true);
        });
    }
  }, [showDeps, depsLoaded, boardId, card.id]);

  useEffect(() => {
    if (showChecklist && !checklistLoaded) {
      void fetch(`/api/boards/${boardId}/cards/${card.id}/checklist`, { credentials: "include" })
        .then((r) => r.json())
        .then((data: ChecklistItem[]) => {
          setChecklist(data);
          setChecklistLoaded(true);
        })
        .catch(() => {
          setChecklistLoaded(true);
        });
    }
  }, [showChecklist, checklistLoaded, boardId, card.id]);

  useEffect(() => {
    if (showComments && !commentsLoaded) {
      void fetch(`/api/boards/${boardId}/cards/${card.id}/comments`, { credentials: "include" })
        .then((r) => r.json())
        .then((data: Comment[]) => {
          setComments(data);
          setCommentsLoaded(true);
        })
        .catch(() => {
          setCommentsLoaded(true);
        });
    }
  }, [showComments, commentsLoaded, boardId, card.id]);

  useEffect(() => {
    if (showComments) {
      commentsEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
    }
  }, [comments, showComments]);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const commitEdit = () => {
    const title = draftTitle.trim();
    const details = draftDetails.trim();
    if (!title) {
      setTitleError(true);
      return;
    }

    setTitleError(false);
    const due_date = draftDueDate.trim() || null;
    const priority = (draftPriority as Priority) || null;
    const labels = draftLabels
      .split(",")
      .map((l) => l.trim())
      .filter(Boolean);
    const assignee_id = draftAssigneeId || null;
    const parsedEstimate = draftEstimate.trim() !== "" ? parseInt(draftEstimate, 10) : null;
    const estimate = parsedEstimate !== null && !isNaN(parsedEstimate) && parsedEstimate >= 0 ? parsedEstimate : null;

    const sprint_id = draftSprintId || null;
    onEdit(card.id, title, details, due_date, priority, labels, assignee_id, estimate, sprint_id);
    setIsEditing(false);
  };

  const cancelEdit = () => {
    setDraftTitle(card.title);
    setDraftDetails(card.details);
    setDraftDueDate(card.due_date ?? "");
    setDraftPriority(card.priority ?? "");
    setDraftLabels((card.labels ?? []).join(", "));
    setDraftAssigneeId(card.assignee_id ?? "");
    setDraftEstimate(card.estimate != null ? String(card.estimate) : "");
    setDraftSprintId(card.sprint_id ?? "");
    setTitleError(false);
    setIsEditing(false);
  };

  const handleAddComment = async () => {
    const content = commentInput.trim();
    if (!content || commentSubmitting) return;
    setCommentSubmitting(true);
    setCommentError(null);
    try {
      const response = await fetch(
        `/api/boards/${boardId}/cards/${card.id}/comments`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        },
      );
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        throw new Error(payload.detail ?? "Failed to add comment");
      }
      const newComment = (await response.json()) as Comment;
      setComments((prev) => [...prev, newComment]);
      setCommentInput("");
    } catch (err) {
      setCommentError(err instanceof Error ? err.message : "Failed to add comment");
    } finally {
      setCommentSubmitting(false);
    }
  };

  const handleAddDependency = async () => {
    if (!depPickMode || !depPickCardId) return;
    const blocker_id = depPickMode === "blocks" ? card.id : depPickCardId;
    const blocked_id = depPickMode === "blocks" ? depPickCardId : card.id;
    setDepError(null);
    try {
      const response = await fetch(`/api/boards/${boardId}/dependencies`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ blocker_id, blocked_id }),
      });
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        throw new Error(payload.detail ?? "Failed to add dependency");
      }
      // Reload deps
      const refreshed = await fetch(`/api/boards/${boardId}/cards/${card.id}/dependencies`, {
        credentials: "include",
      });
      const data = (await refreshed.json()) as { blocks: CardDependency[]; blocked_by: CardDependency[] };
      setBlocks(data.blocks ?? []);
      setBlockedBy(data.blocked_by ?? []);
      setDepPickMode(null);
      setDepPickCardId("");
    } catch (err) {
      setDepError(err instanceof Error ? err.message : "Failed to add dependency");
    }
  };

  const handleRemoveDependency = async (depId: string) => {
    setDepError(null);
    try {
      await fetch(`/api/boards/${boardId}/dependencies/${depId}`, {
        method: "DELETE",
        credentials: "include",
      });
      setBlocks((prev) => prev.filter((d) => d.id !== depId));
      setBlockedBy((prev) => prev.filter((d) => d.id !== depId));
    } catch {
      setDepError("Failed to remove dependency");
    }
  };

  const handleAddChecklistItem = async () => {
    const text = checklistInput.trim();
    if (!text || checklistSubmitting) return;
    setChecklistSubmitting(true);
    try {
      const response = await fetch(
        `/api/boards/${boardId}/cards/${card.id}/checklist`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        },
      );
      if (!response.ok) throw new Error("Failed to add item");
      const newItem = (await response.json()) as ChecklistItem;
      setChecklist((prev) => [...prev, newItem]);
      setChecklistInput("");
    } finally {
      setChecklistSubmitting(false);
    }
  };

  const handleToggleChecklistItem = async (itemId: string, checked: boolean) => {
    const response = await fetch(
      `/api/boards/${boardId}/cards/${card.id}/checklist/${itemId}`,
      {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ checked }),
      },
    );
    if (response.ok) {
      const updated = (await response.json()) as ChecklistItem;
      setChecklist((prev) => prev.map((item) => (item.id === itemId ? updated : item)));
    }
  };

  const handleDeleteChecklistItem = async (itemId: string) => {
    const response = await fetch(
      `/api/boards/${boardId}/cards/${card.id}/checklist/${itemId}`,
      { method: "DELETE", credentials: "include" },
    );
    if (response.ok) {
      setChecklist((prev) => prev.filter((item) => item.id !== itemId));
    }
  };

  const dueDateStatus = getDueDateStatus(card.due_date);
  const assignee = card.assignee_username ?? null;
  const checkedCount = checklist.filter((i) => i.checked).length;
  const checklistProgress = checklist.length > 0 ? Math.round((checkedCount / checklist.length) * 100) : 0;

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={clsx(
        "rounded-2xl border border-transparent bg-white px-4 py-4 shadow-[0_12px_24px_rgba(3,33,71,0.08)]",
        "transition-all duration-150",
        isDragging && "opacity-60 shadow-[0_18px_32px_rgba(3,33,71,0.16)]"
      )}
      {...(!isEditing ? attributes : {})}
      {...(!isEditing ? listeners : {})}
      data-testid={`card-${card.id}`}
    >
      <div className="flex min-h-[88px] flex-col gap-3">
        {isEditing ? (
          <div className="w-full space-y-2">
            <input
              value={draftTitle}
              onChange={(event) => {
                setDraftTitle(event.target.value);
                setTitleError(false);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") cancelEdit();
              }}
              maxLength={512}
              className="w-full rounded-lg border border-[var(--stroke)] px-2 py-1 text-sm font-semibold text-[var(--navy-dark)] outline-none"
              aria-label={`Edit title for ${card.title}`}
            />
            {titleError && (
              <p className="text-xs text-red-600">Title is required</p>
            )}
            <textarea
              value={draftDetails}
              onChange={(event) => setDraftDetails(event.target.value)}
              maxLength={10000}
              onKeyDown={(event) => {
                if (event.key === "Escape") cancelEdit();
              }}
              rows={3}
              className="w-full resize-none rounded-lg border border-[var(--stroke)] px-2 py-1 text-sm text-[var(--gray-text)] outline-none"
              aria-label={`Edit details for ${card.title}`}
            />
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="block text-xs font-semibold text-[var(--gray-text)]">Due date</label>
                <input
                  type="date"
                  value={draftDueDate}
                  onChange={(e) => setDraftDueDate(e.target.value)}
                  className="w-full rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs text-[var(--navy-dark)] outline-none"
                  aria-label="Due date"
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs font-semibold text-[var(--gray-text)]">Priority</label>
                <select
                  value={draftPriority}
                  onChange={(e) => setDraftPriority(e.target.value as Priority | "")}
                  className="w-full rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs text-[var(--navy-dark)] outline-none"
                  aria-label="Priority"
                >
                  <option value="">None</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--gray-text)]">Labels (comma-separated)</label>
              <input
                value={draftLabels}
                onChange={(e) => setDraftLabels(e.target.value)}
                placeholder="e.g. bug, frontend, release"
                className="w-full rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs text-[var(--navy-dark)] outline-none"
                aria-label="Labels"
              />
            </div>
            {assignableUsers.length > 0 && (
              <div>
                <label className="block text-xs font-semibold text-[var(--gray-text)]">Assignee</label>
                <select
                  value={draftAssigneeId}
                  onChange={(e) => setDraftAssigneeId(e.target.value)}
                  className="w-full rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs text-[var(--navy-dark)] outline-none"
                  aria-label="Assignee"
                >
                  <option value="">Unassigned</option>
                  {assignableUsers.map((u) => (
                    <option key={u.id} value={u.id}>{u.username}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="block text-xs font-semibold text-[var(--gray-text)]">Estimate (points)</label>
              <input
                type="number"
                min={0}
                value={draftEstimate}
                onChange={(e) => setDraftEstimate(e.target.value)}
                placeholder="e.g. 3"
                className="w-full rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs text-[var(--navy-dark)] outline-none"
                aria-label="Estimate"
              />
            </div>
            {sprints.length > 0 && (
              <div>
                <label className="block text-xs font-semibold text-[var(--gray-text)]">Sprint</label>
                <select
                  value={draftSprintId}
                  onChange={(e) => setDraftSprintId(e.target.value)}
                  className="w-full rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs text-[var(--navy-dark)] outline-none"
                  aria-label="Sprint"
                >
                  <option value="">No sprint</option>
                  {sprints.map((s) => (
                    <option key={s.id} value={s.id}>{s.name} ({s.status})</option>
                  ))}
                </select>
              </div>
            )}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={commitEdit}
                className="rounded-full bg-[var(--secondary-purple)] px-3 py-1 text-xs font-semibold text-white"
              >
                Save
              </button>
              <button
                type="button"
                onClick={cancelEdit}
                className="rounded-full border border-[var(--stroke)] px-3 py-1 text-xs font-semibold text-[var(--gray-text)]"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="min-w-0 flex-1">
              {/* Priority + Labels + Blocked row */}
              {(card.priority || (card.labels && card.labels.length > 0) || card.is_blocked) && (
                <div className="mb-2 flex flex-wrap gap-1">
                  {card.is_blocked && (
                    <span
                      className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700"
                      data-testid={`card-blocked-${card.id}`}
                    >
                      Blocked
                    </span>
                  )}
                  {card.priority && (
                    <span className={clsx("rounded-full px-2 py-0.5 text-xs font-semibold capitalize", PRIORITY_COLORS[card.priority])}>
                      {card.priority}
                    </span>
                  )}
                  {(card.labels ?? []).map((label) => (
                    <span key={label} className="rounded-full bg-[var(--primary-blue)]/10 px-2 py-0.5 text-xs font-medium text-[var(--primary-blue)]">
                      {label}
                    </span>
                  ))}
                </div>
              )}
              <div className="flex items-start justify-between gap-2">
                <h4 className="font-display text-base font-semibold text-[var(--navy-dark)]">
                  {card.title}
                </h4>
                {assignee && (
                  <span
                    title={assignee}
                    className="ml-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--secondary-purple)]/15 text-[10px] font-bold text-[var(--secondary-purple)]"
                    data-testid={`card-assignee-${card.id}`}
                  >
                    {initials(assignee)}
                  </span>
                )}
              </div>
              {card.details && (
                <p className="mt-2 text-sm leading-6 text-[var(--gray-text)]">
                  {card.details}
                </p>
              )}
              {card.due_date && dueDateStatus && (
                <p
                  className={clsx("mt-2 text-xs", DUE_DATE_CLASSES[dueDateStatus])}
                  data-testid={`card-due-${card.id}`}
                >
                  {dueDateLabel(card.due_date, dueDateStatus)}
                </p>
              )}
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {card.estimate != null && (
                  <span
                    className="rounded-full bg-[var(--dark-navy)]/10 px-2 py-0.5 text-xs font-semibold text-[var(--dark-navy)]"
                    data-testid={`card-estimate-${card.id}`}
                  >
                    {card.estimate} pts
                  </span>
                )}
                {card.sprint_name && (
                  <span
                    className="rounded-full bg-[var(--accent-yellow)]/20 px-2 py-0.5 text-xs font-semibold text-[var(--navy-dark)]"
                    data-testid={`card-sprint-${card.id}`}
                  >
                    {card.sprint_name}
                  </span>
                )}
                {checklist.length > 0 && !showChecklist && (
                  <span
                    className="rounded-full bg-[var(--gray-text)]/10 px-2 py-0.5 text-xs font-medium text-[var(--gray-text)]"
                    data-testid={`checklist-progress-${card.id}`}
                  >
                    {checkedCount}/{checklist.length}
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={() => setIsEditing(true)}
                className="rounded-full border border-transparent px-3 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--stroke)] hover:text-[var(--navy-dark)]"
                aria-label={`Edit ${card.title}`}
              >
                Edit
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowChecklist((v) => !v);
                }}
                className="rounded-full border border-transparent px-3 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--stroke)] hover:text-[var(--navy-dark)]"
                aria-label={`${showChecklist ? "Hide" : "Show"} checklist for ${card.title}`}
              >
                {showChecklist ? "Hide checklist" : "Checklist"}
              </button>
              <button
                type="button"
                onClick={() => setShowDeps((v) => !v)}
                className="rounded-full border border-transparent px-3 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--stroke)] hover:text-[var(--navy-dark)]"
                aria-label={`${showDeps ? "Hide" : "Show"} dependencies for ${card.title}`}
              >
                {showDeps ? "Hide deps" : "Dependencies"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowComments((v) => !v);
                }}
                className="rounded-full border border-transparent px-3 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--stroke)] hover:text-[var(--navy-dark)]"
                aria-label={`${showComments ? "Hide" : "Show"} comments for ${card.title}`}
              >
                {showComments ? "Hide" : "Comments"}
                {comments.length > 0 && !showComments && (
                  <span className="ml-1 rounded-full bg-[var(--primary-blue)]/15 px-1.5 text-[10px] font-bold text-[var(--primary-blue)]">
                    {comments.length}
                  </span>
                )}
              </button>
              <button
                type="button"
                onClick={() => onArchive(card.id)}
                className="rounded-full border border-transparent px-3 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--stroke)] hover:text-[var(--navy-dark)]"
                aria-label={`Archive ${card.title}`}
              >
                Archive
              </button>
              {onMove && canMove && (
                <div className="ml-1 flex items-center gap-1 border-l border-[var(--stroke)] pl-2">
                  <button type="button" disabled={!canMove.left} onClick={() => onMove(card.id, "left")} aria-label={`Move ${card.title} left`} className="rounded px-1 py-0.5 text-xs text-[var(--gray-text)] enabled:hover:text-[var(--navy-dark)] disabled:opacity-30">&larr;</button>
                  <button type="button" disabled={!canMove.up} onClick={() => onMove(card.id, "up")} aria-label={`Move ${card.title} up`} className="rounded px-1 py-0.5 text-xs text-[var(--gray-text)] enabled:hover:text-[var(--navy-dark)] disabled:opacity-30">&uarr;</button>
                  <button type="button" disabled={!canMove.down} onClick={() => onMove(card.id, "down")} aria-label={`Move ${card.title} down`} className="rounded px-1 py-0.5 text-xs text-[var(--gray-text)] enabled:hover:text-[var(--navy-dark)] disabled:opacity-30">&darr;</button>
                  <button type="button" disabled={!canMove.right} onClick={() => onMove(card.id, "right")} aria-label={`Move ${card.title} right`} className="rounded px-1 py-0.5 text-xs text-[var(--gray-text)] enabled:hover:text-[var(--navy-dark)] disabled:opacity-30">&rarr;</button>
                </div>
              )}
            </div>

            {showDeps && (
              <div className="mt-2 space-y-2 border-t border-[var(--stroke)] pt-2" data-testid={`deps-${card.id}`}>
                {depError && (
                  <p className="text-xs text-red-600" role="alert">{depError}</p>
                )}
                {blockedBy.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-[var(--gray-text)]">Blocked by</p>
                    {blockedBy.map((dep) => (
                      <div key={dep.id} className="flex items-center justify-between gap-2 py-0.5">
                        <span className="flex-1 text-xs text-[var(--navy-dark)]">{dep.title}</span>
                        <button
                          type="button"
                          onClick={() => void handleRemoveDependency(dep.id)}
                          className="text-[10px] text-[var(--gray-text)] hover:text-red-500"
                          aria-label={`Remove blocked-by: ${dep.title}`}
                        >
                          x
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {blocks.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-[var(--gray-text)]">Blocks</p>
                    {blocks.map((dep) => (
                      <div key={dep.id} className="flex items-center justify-between gap-2 py-0.5">
                        <span className="flex-1 text-xs text-[var(--navy-dark)]">{dep.title}</span>
                        <button
                          type="button"
                          onClick={() => void handleRemoveDependency(dep.id)}
                          className="text-[10px] text-[var(--gray-text)] hover:text-red-500"
                          aria-label={`Remove blocks: ${dep.title}`}
                        >
                          x
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {depPickMode ? (
                  <div className="flex gap-1">
                    <select
                      value={depPickCardId}
                      onChange={(e) => setDepPickCardId(e.target.value)}
                      className="flex-1 rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs outline-none"
                      aria-label={`Pick card to ${depPickMode === "blocks" ? "be blocked by this card" : "block this card"}`}
                    >
                      <option value="">Select card...</option>
                      {Object.values(boardCards)
                        .filter((c) => c.id !== card.id)
                        .map((c) => (
                          <option key={c.id} value={c.id}>{c.title}</option>
                        ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => void handleAddDependency()}
                      disabled={!depPickCardId}
                      className="rounded-lg bg-[var(--primary-blue)] px-2 py-1 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      Add
                    </button>
                    <button
                      type="button"
                      onClick={() => { setDepPickMode(null); setDepPickCardId(""); setDepError(null); }}
                      className="rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs text-[var(--gray-text)]"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => { setDepPickMode("blocked_by"); setDepPickCardId(""); }}
                      className="rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs font-semibold text-[var(--gray-text)] hover:text-[var(--navy-dark)]"
                      aria-label="Add blocked-by dependency"
                    >
                      + Blocked by
                    </button>
                    <button
                      type="button"
                      onClick={() => { setDepPickMode("blocks"); setDepPickCardId(""); }}
                      className="rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs font-semibold text-[var(--gray-text)] hover:text-[var(--navy-dark)]"
                      aria-label="Add blocks dependency"
                    >
                      + Blocks
                    </button>
                  </div>
                )}
              </div>
            )}

            {showChecklist && (
              <div className="mt-2 space-y-2 border-t border-[var(--stroke)] pt-2" data-testid={`checklist-${card.id}`}>
                {checklist.length > 0 && (
                  <div className="mb-1">
                    <div className="mb-1 flex items-center justify-between text-xs text-[var(--gray-text)]">
                      <span>{checkedCount} of {checklist.length} done</span>
                      <span>{checklistProgress}%</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--stroke)]">
                      <div
                        className="h-full rounded-full bg-[var(--primary-blue)] transition-all"
                        style={{ width: `${checklistProgress}%` }}
                        data-testid={`checklist-bar-${card.id}`}
                      />
                    </div>
                  </div>
                )}
                {checklist.map((item) => (
                  <div key={item.id} className="flex items-center gap-2" data-testid={`checklist-item-${item.id}`}>
                    <input
                      type="checkbox"
                      checked={item.checked}
                      onChange={(e) => void handleToggleChecklistItem(item.id, e.target.checked)}
                      className="h-3.5 w-3.5 accent-[var(--primary-blue)]"
                      aria-label={`Toggle: ${item.text}`}
                    />
                    <span className={clsx("flex-1 text-xs", item.checked && "line-through text-[var(--gray-text)]")}>
                      {item.text}
                    </span>
                    <button
                      type="button"
                      onClick={() => void handleDeleteChecklistItem(item.id)}
                      className="text-[10px] text-[var(--gray-text)] hover:text-red-500"
                      aria-label={`Delete checklist item: ${item.text}`}
                    >
                      x
                    </button>
                  </div>
                ))}
                <div className="flex gap-1">
                  <input
                    value={checklistInput}
                    onChange={(e) => setChecklistInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") void handleAddChecklistItem(); }}
                    placeholder="Add checklist item..."
                    maxLength={1000}
                    className="flex-1 rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs outline-none"
                    aria-label="New checklist item"
                  />
                  <button
                    type="button"
                    onClick={() => void handleAddChecklistItem()}
                    disabled={checklistSubmitting || !checklistInput.trim()}
                    className="rounded-lg bg-[var(--primary-blue)] px-2 py-1 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    Add
                  </button>
                </div>
              </div>
            )}

            {showComments && (
              <div className="mt-2 space-y-2 border-t border-[var(--stroke)] pt-2" data-testid={`comments-${card.id}`}>
                {comments.length === 0 ? (
                  <p className="text-xs text-[var(--gray-text)]">No comments yet.</p>
                ) : (
                  comments.map((c) => (
                    <div key={c.id} className="rounded-lg bg-[var(--surface)] px-3 py-2 text-xs">
                      <span className="font-semibold text-[var(--navy-dark)]">{c.author}</span>
                      <span className="ml-2 text-[var(--gray-text)]">{c.content}</span>
                    </div>
                  ))
                )}
                <div ref={commentsEndRef} />
                {commentError && (
                  <p className="text-xs text-red-600" role="alert">{commentError}</p>
                )}
                <div className="flex gap-1">
                  <input
                    value={commentInput}
                    onChange={(e) => setCommentInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") void handleAddComment(); }}
                    placeholder="Add a comment..."
                    maxLength={4000}
                    className="flex-1 rounded-lg border border-[var(--stroke)] px-2 py-1 text-xs outline-none"
                    aria-label="New comment"
                  />
                  <button
                    type="button"
                    onClick={() => void handleAddComment()}
                    disabled={commentSubmitting || !commentInput.trim()}
                    className="rounded-lg bg-[var(--primary-blue)] px-2 py-1 text-xs font-semibold text-white disabled:opacity-50"
                  >
                    Post
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </article>
  );
};
