import clsx from "clsx";
import { useEffect, useState } from "react";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { AssignableUser, Card, Column, Priority, Sprint } from "@/lib/kanban";
import { KanbanCard, type MoveDirection } from "@/components/KanbanCard";
import { NewCardForm } from "@/components/NewCardForm";

type KanbanColumnProps = {
  column: Column;
  cards: Card[];
  boardId: string;
  assignableUsers: AssignableUser[];
  boardCards: Record<string, Card>;
  sprints: Sprint[];
  swimlaneGroup?: "none" | "priority" | "assignee";
  isFirstColumn?: boolean;
  isLastColumn?: boolean;
  onRename: (columnId: string, title: string) => void;
  onSetWipLimit: (columnId: string, wip_limit: number | null) => void;
  onAddCard: (columnId: string, title: string, details: string) => void;
  onArchiveCard: (columnId: string, cardId: string) => void;
  onEditCard: (cardId: string, title: string, details: string, due_date: string | null, priority: Priority | null, labels: string[], assignee_id: string | null, estimate: number | null, sprint_id: string | null) => void;
  onMoveCard?: (cardId: string, direction: MoveDirection) => void;
};

const PRIORITY_ORDER = ["critical", "high", "medium", "low", ""] as const;

function groupCards(cards: Card[], group: "none" | "priority" | "assignee"): { label: string; cards: Card[] }[] {
  if (group === "none") return [{ label: "", cards }];
  if (group === "priority") {
    const byPriority = new Map<string, Card[]>();
    for (const p of PRIORITY_ORDER) byPriority.set(p, []);
    for (const card of cards) {
      const key = card.priority ?? "";
      byPriority.get(key)?.push(card);
    }
    return [...byPriority.entries()]
      .filter(([, cs]) => cs.length > 0)
      .map(([label, cs]) => ({ label: label || "No priority", cards: cs }));
  }
  // group === "assignee"
  const byAssignee = new Map<string, Card[]>();
  byAssignee.set("", []);
  for (const card of cards) {
    const key = card.assignee_username ?? "";
    if (!byAssignee.has(key)) byAssignee.set(key, []);
    byAssignee.get(key)!.push(card);
  }
  return [...byAssignee.entries()]
    .filter(([, cs]) => cs.length > 0)
    .map(([label, cs]) => ({ label: label || "Unassigned", cards: cs }));
}

export const KanbanColumn = ({
  column,
  cards,
  boardId,
  assignableUsers,
  boardCards,
  sprints,
  swimlaneGroup = "none",
  isFirstColumn = false,
  isLastColumn = false,
  onRename,
  onSetWipLimit,
  onAddCard,
  onArchiveCard,
  onEditCard,
  onMoveCard,
}: KanbanColumnProps) => {
  const { setNodeRef, isOver } = useDroppable({ id: column.id });
  const [draftTitle, setDraftTitle] = useState(column.title);
  const [titleError, setTitleError] = useState(false);
  const [editingWip, setEditingWip] = useState(false);
  const [wipDraft, setWipDraft] = useState(column.wip_limit != null ? String(column.wip_limit) : "");

  useEffect(() => {
    // Keep draft title aligned when board data refreshes from the API.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraftTitle(column.title);
  }, [column.title]);

  useEffect(() => {
    if (!editingWip) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setWipDraft(column.wip_limit != null ? String(column.wip_limit) : "");
    }
  }, [column.wip_limit, editingWip]);

  const commitWipLimit = () => {
    const trimmed = wipDraft.trim();
    const parsed = trimmed === "" ? null : parseInt(trimmed, 10);
    if (trimmed !== "" && (isNaN(parsed!) || parsed! < 1)) {
      setWipDraft(column.wip_limit != null ? String(column.wip_limit) : "");
      setEditingWip(false);
      return;
    }
    onSetWipLimit(column.id, parsed);
    setEditingWip(false);
  };

  const isOverWip = column.wip_limit != null && cards.length > column.wip_limit;

  const commitRename = () => {
    const normalized = draftTitle.trim();
    if (normalized && normalized !== column.title) {
      setTitleError(false);
      onRename(column.id, normalized);
    } else if (!normalized) {
      setTitleError(true);
      setDraftTitle(column.title);
    } else {
      setDraftTitle(column.title);
    }
  };

  return (
    <section
      ref={setNodeRef}
      className={clsx(
        "flex min-h-[520px] flex-col rounded-3xl border p-4 shadow-[var(--shadow)] transition",
        isOverWip
          ? "border-red-400 bg-red-50/60 ring-2 ring-red-300"
          : "border-[var(--stroke)] bg-[var(--surface-strong)]",
        isOver && !isOverWip && "ring-2 ring-[var(--accent-yellow)]"
      )}
      data-testid={`column-${column.id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="w-full">
          <div className="flex items-center gap-3">
            <div className="h-2 w-10 rounded-full bg-[var(--accent-yellow)]" />
            <span className={clsx(
              "text-xs font-semibold uppercase tracking-[0.2em]",
              isOverWip ? "text-red-600" : "text-[var(--gray-text)]"
            )}>
              {cards.length}{column.wip_limit != null ? `/${column.wip_limit}` : ""} cards
            </span>
            {/* WIP limit inline edit */}
            {editingWip ? (
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  value={wipDraft}
                  onChange={(e) => setWipDraft(e.target.value)}
                  onBlur={commitWipLimit}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitWipLimit();
                    if (e.key === "Escape") { setEditingWip(false); setWipDraft(column.wip_limit != null ? String(column.wip_limit) : ""); }
                  }}
                  placeholder="Limit"
                  min={1}
                  className="w-14 rounded border border-[var(--stroke)] px-1 py-0.5 text-xs outline-none"
                  aria-label="WIP limit"
                  data-testid={`wip-input-${column.id}`}
                  autoFocus
                />
                <button type="button" onClick={commitWipLimit} className="text-[10px] text-green-600 hover:text-green-800">ok</button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setEditingWip(true)}
                className="text-[10px] text-[var(--gray-text)] hover:text-[var(--navy-dark)]"
                aria-label={column.wip_limit != null ? `Edit WIP limit (${column.wip_limit})` : "Set WIP limit"}
                data-testid={`wip-btn-${column.id}`}
              >
                {column.wip_limit != null ? "WIP" : "+ WIP"}
              </button>
            )}
          </div>
          <input
            value={draftTitle}
            onChange={(event) => {
              setDraftTitle(event.target.value);
              setTitleError(false);
            }}
            onBlur={commitRename}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                commitRename();
              }
              if (event.key === "Escape") {
                setDraftTitle(column.title);
                (event.target as HTMLInputElement).blur();
              }
            }}
            className="mt-3 w-full bg-transparent font-display text-lg font-semibold text-[var(--navy-dark)] outline-none"
            aria-label="Column title"
          />
          {titleError && (
            <p className="mt-1 text-xs text-red-600">Title is required</p>
          )}
        </div>
      </div>
      <div className="mt-4 flex flex-1 flex-col gap-3">
        <SortableContext items={column.cardIds} strategy={verticalListSortingStrategy}>
          {swimlaneGroup === "none" ? (
            cards.map((card, index) => (
              <KanbanCard
                key={card.id}
                card={card}
                boardId={boardId}
                assignableUsers={assignableUsers}
                boardCards={boardCards}
                sprints={sprints}
                onArchive={(cardId) => onArchiveCard(column.id, cardId)}
                onEdit={onEditCard}
                onMove={onMoveCard}
                canMove={{
                  up: index > 0,
                  down: index < cards.length - 1,
                  left: !isFirstColumn,
                  right: !isLastColumn,
                }}
              />
            ))
          ) : (
            groupCards(cards, swimlaneGroup).map((group) => (
              <div key={group.label} className="space-y-2">
                <p className="sticky top-0 z-10 rounded-lg bg-[var(--surface)] px-2 py-1 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]" data-testid={`swimlane-${column.id}-${group.label}`}>
                  {group.label}
                </p>
                {group.cards.map((card, index) => (
                  <KanbanCard
                    key={card.id}
                    card={card}
                    boardId={boardId}
                    assignableUsers={assignableUsers}
                    boardCards={boardCards}
                    sprints={sprints}
                    onArchive={(cardId) => onArchiveCard(column.id, cardId)}
                    onEdit={onEditCard}
                    onMove={onMoveCard}
                    canMove={{
                      up: index > 0,
                      down: index < group.cards.length - 1,
                      left: !isFirstColumn,
                      right: !isLastColumn,
                    }}
                  />
                ))}
              </div>
            ))
          )}
        </SortableContext>
        {cards.length === 0 && (
          <div className="flex flex-1 items-center justify-center rounded-2xl border border-dashed border-[var(--stroke)] px-3 py-6 text-center text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
            Drop a card here
          </div>
        )}
      </div>
      <NewCardForm
        onAdd={(title, details) => onAddCard(column.id, title, details)}
      />
    </section>
  );
};
