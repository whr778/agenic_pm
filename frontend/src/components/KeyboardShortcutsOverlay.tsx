"use client";

type KeyboardShortcutsOverlayProps = {
  onClose: () => void;
};

const SHORTCUTS = [
  { key: "?", description: "Show this help overlay" },
  { key: "Escape", description: "Close overlay / cancel editing" },
  { key: "f", description: "Focus the card filter input" },
  { key: "a", description: "Toggle archived cards panel" },
  { key: "l", description: "Toggle activity log panel" },
];

export const KeyboardShortcutsOverlay = ({ onClose }: KeyboardShortcutsOverlayProps) => (
  <div
    className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
    role="dialog"
    aria-modal="true"
    aria-label="Keyboard shortcuts"
    onClick={onClose}
    onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}
    data-testid="shortcuts-overlay"
  >
    <div
      className="w-full max-w-sm rounded-3xl border border-[var(--stroke)] bg-white p-8 shadow-[var(--shadow)]"
      onClick={(e) => e.stopPropagation()}
    >
      <h2 className="mb-6 font-display text-xl font-semibold text-[var(--navy-dark)]">
        Keyboard shortcuts
      </h2>
      <ul className="space-y-3">
        {SHORTCUTS.map(({ key, description }) => (
          <li key={key} className="flex items-center gap-4">
            <kbd className="min-w-[3rem] rounded-lg border border-[var(--stroke)] bg-[var(--surface)] px-2 py-1 text-center text-xs font-bold text-[var(--navy-dark)]">
              {key}
            </kbd>
            <span className="text-sm text-[var(--gray-text)]">{description}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={onClose}
        className="mt-8 w-full rounded-xl bg-[var(--primary-blue)] py-2 text-sm font-semibold text-white"
        aria-label="Close keyboard shortcuts"
      >
        Close
      </button>
    </div>
  </div>
);
