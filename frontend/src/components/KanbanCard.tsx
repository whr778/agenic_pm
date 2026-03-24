import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import { useEffect, useState } from "react";
import type { Card, Priority } from "@/lib/kanban";

export type MoveDirection = "up" | "down" | "left" | "right";

type KanbanCardProps = {
  card: Card;
  onDelete: (cardId: string) => void;
  onEdit: (cardId: string, title: string, details: string, due_date: string | null, priority: Priority | null, labels: string[]) => void;
  onMove?: (cardId: string, direction: MoveDirection) => void;
  canMove?: { up: boolean; down: boolean; left: boolean; right: boolean };
};

const PRIORITY_COLORS: Record<Priority, string> = {
  low: "bg-blue-100 text-blue-700",
  medium: "bg-yellow-100 text-yellow-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

function isOverdue(due_date: string): boolean {
  const today = new Date().toISOString().slice(0, 10);
  return due_date < today;
}

export const KanbanCard = ({ card, onDelete, onEdit, onMove, canMove }: KanbanCardProps) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id });
  const [isEditing, setIsEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(card.title);
  const [draftDetails, setDraftDetails] = useState(card.details);
  const [draftDueDate, setDraftDueDate] = useState(card.due_date ?? "");
  const [draftPriority, setDraftPriority] = useState<Priority | "">(card.priority ?? "");
  const [draftLabels, setDraftLabels] = useState((card.labels ?? []).join(", "));
  const [titleError, setTitleError] = useState(false);

  // Keep local edit drafts in sync when the server refreshes this card.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setDraftTitle(card.title);
    setDraftDetails(card.details);
    setDraftDueDate(card.due_date ?? "");
    setDraftPriority(card.priority ?? "");
    setDraftLabels((card.labels ?? []).join(", "));
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [card.title, card.details, card.due_date, card.priority, card.labels]);

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

    onEdit(card.id, title, details, due_date, priority, labels);
    setIsEditing(false);
  };

  const cancelEdit = () => {
    setDraftTitle(card.title);
    setDraftDetails(card.details);
    setDraftDueDate(card.due_date ?? "");
    setDraftPriority(card.priority ?? "");
    setDraftLabels((card.labels ?? []).join(", "));
    setTitleError(false);
    setIsEditing(false);
  };

  const overdueClass = card.due_date && isOverdue(card.due_date) ? "text-red-600" : "text-[var(--gray-text)]";

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
              <h4 className="font-display text-base font-semibold text-[var(--navy-dark)]">
                {card.title}
              </h4>
              {card.details && (
                <p className="mt-2 text-sm leading-6 text-[var(--gray-text)]">
                  {card.details}
                </p>
              )}
              {card.due_date && (
                <p className={clsx("mt-2 text-xs font-medium", overdueClass)} data-testid={`card-due-${card.id}`}>
                  Due {card.due_date}{card.due_date && isOverdue(card.due_date) ? " (overdue)" : ""}
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
                onClick={() => onDelete(card.id)}
                className="rounded-full border border-transparent px-3 py-1 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--stroke)] hover:text-[var(--navy-dark)]"
                aria-label={`Delete ${card.title}`}
              >
                Remove
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
          </>
        )}
      </div>
    </article>
  );
};
