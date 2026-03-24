import clsx from "clsx";
import { useEffect, useState } from "react";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Card, Column, Priority } from "@/lib/kanban";
import { KanbanCard, type MoveDirection } from "@/components/KanbanCard";
import { NewCardForm } from "@/components/NewCardForm";

type KanbanColumnProps = {
  column: Column;
  cards: Card[];
  isFirstColumn?: boolean;
  isLastColumn?: boolean;
  onRename: (columnId: string, title: string) => void;
  onAddCard: (columnId: string, title: string, details: string) => void;
  onDeleteCard: (columnId: string, cardId: string) => void;
  onEditCard: (cardId: string, title: string, details: string, due_date: string | null, priority: Priority | null, labels: string[]) => void;
  onMoveCard?: (cardId: string, direction: MoveDirection) => void;
};

export const KanbanColumn = ({
  column,
  cards,
  isFirstColumn = false,
  isLastColumn = false,
  onRename,
  onAddCard,
  onDeleteCard,
  onEditCard,
  onMoveCard,
}: KanbanColumnProps) => {
  const { setNodeRef, isOver } = useDroppable({ id: column.id });
  const [draftTitle, setDraftTitle] = useState(column.title);
  const [titleError, setTitleError] = useState(false);

  useEffect(() => {
    // Keep draft title aligned when board data refreshes from the API.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraftTitle(column.title);
  }, [column.title]);

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
        "flex min-h-[520px] flex-col rounded-3xl border border-[var(--stroke)] bg-[var(--surface-strong)] p-4 shadow-[var(--shadow)] transition",
        isOver && "ring-2 ring-[var(--accent-yellow)]"
      )}
      data-testid={`column-${column.id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="w-full">
          <div className="flex items-center gap-3">
            <div className="h-2 w-10 rounded-full bg-[var(--accent-yellow)]" />
            <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
              {cards.length} cards
            </span>
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
          {cards.map((card, index) => (
            <KanbanCard
              key={card.id}
              card={card}
              onDelete={(cardId) => onDeleteCard(column.id, cardId)}
              onEdit={onEditCard}
              onMove={onMoveCard}
              canMove={{
                up: index > 0,
                down: index < cards.length - 1,
                left: !isFirstColumn,
                right: !isLastColumn,
              }}
            />
          ))}
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
