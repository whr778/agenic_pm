import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import { useEffect, useRef, useState } from "react";
import type { AssignableUser, Card, Comment, Priority } from "@/lib/kanban";

export type MoveDirection = "up" | "down" | "left" | "right";

type KanbanCardProps = {
  card: Card;
  boardId: string;
  assignableUsers: AssignableUser[];
  onArchive: (cardId: string) => void;
  onEdit: (
    cardId: string,
    title: string,
    details: string,
    due_date: string | null,
    priority: Priority | null,
    labels: string[],
    assignee_id: string | null,
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
  const [titleError, setTitleError] = useState(false);

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
  }, [card.title, card.details, card.due_date, card.priority, card.labels, card.assignee_id]);

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

    onEdit(card.id, title, details, due_date, priority, labels, assignee_id);
    setIsEditing(false);
  };

  const cancelEdit = () => {
    setDraftTitle(card.title);
    setDraftDetails(card.details);
    setDraftDueDate(card.due_date ?? "");
    setDraftPriority(card.priority ?? "");
    setDraftLabels((card.labels ?? []).join(", "));
    setDraftAssigneeId(card.assignee_id ?? "");
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

  const dueDateStatus = getDueDateStatus(card.due_date);
  const assignee = card.assignee_username ?? null;

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
              {/* Priority + Labels row */}
              {(card.priority || (card.labels && card.labels.length > 0)) && (
                <div className="mb-2 flex flex-wrap gap-1">
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
