"use client";

import { useState, useRef, useEffect } from "react";
import { useConversations } from "@/lib/conversation-context";
import { ConfirmDialog } from "@/components/confirm-dialog";

function formatDate(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return d.toLocaleDateString("en-US", { weekday: "long" });
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function groupByDate(
  conversations: { id: string; title: string; createdAt: number }[]
): { label: string; items: { id: string; title: string; createdAt: number }[] }[] {
  const groups: Record<string, { id: string; title: string; createdAt: number }[]> = {};
  for (const conv of conversations) {
    const label = formatDate(conv.createdAt);
    if (!groups[label]) groups[label] = [];
    groups[label].push(conv);
  }
  return Object.entries(groups).map(([label, items]) => ({
    label,
    items: items.sort((a, b) => b.createdAt - a.createdAt),
  }));
}

function RenameInput({
  initialTitle,
  onSave,
  onCancel,
}: {
  initialTitle: string;
  onSave: (title: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initialTitle);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSave(value);
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => onSave(value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onCancel();
        }}
        className="min-w-0 flex-1 rounded-lg border border-espresso/40 bg-ivory px-2 py-1 text-sm text-bean focus:outline-none focus:ring-1 focus:ring-espresso/30"
      />
    </form>
  );
}

export function HistoryView({ onSelect }: { onSelect: () => void }) {
  const {
    conversations,
    loading,
    activeConversationId,
    setActiveConversation,
    deleteConversation,
    renameConversation,
  } = useConversations();

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);

  const grouped = groupByDate(conversations);

  function handleSelect(id: string) {
    setActiveConversation(id);
    onSelect();
  }

  function handleDeleteConfirm() {
    if (deleteTarget) {
      deleteConversation(deleteTarget);
      setDeleteTarget(null);
    }
  }

  function handleRenameSave(title: string) {
    if (renameTarget) {
      renameConversation(renameTarget, title);
      setRenameTarget(null);
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex items-center gap-2 text-latte">
          <div className="h-1.5 w-1.5 rounded-full bg-espresso animate-pulse-dot" />
          <div className="h-1.5 w-1.5 rounded-full bg-espresso animate-pulse-dot" />
          <div className="h-1.5 w-1.5 rounded-full bg-espresso animate-pulse-dot" />
        </div>
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-4 py-12 text-center">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-espresso/10">
          <svg
            className="h-8 w-8 text-espresso"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M12 8v4l3 3" />
            <circle cx="12" cy="12" r="10" />
          </svg>
        </div>
        <h2 className="mb-2 text-2xl font-semibold text-espresso">
          No conversations yet
        </h2>
        <p className="max-w-sm text-sm text-latte">
          Start a chat and it will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-6 sm:px-6">
      <h2 className="mb-6 text-lg font-semibold text-espresso uppercase tracking-wider text-xs">
        Your Recent Tables
      </h2>

      <div className="space-y-6">
        {grouped.map((group) => (
          <div key={group.label}>
            <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-latte/70">
              {group.label}
            </h3>
            <div className="space-y-2">
              {group.items.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => handleSelect(conv.id)}
                  className={`group flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left text-sm cursor-pointer transition-all ${
                    conv.id === activeConversationId
                      ? "border-espresso/40 bg-cream/50 text-espresso"
                      : "border-stone/50 bg-ivory/80 text-bean hover:border-espresso/30 hover:bg-cream/30"
                  }`}
                >
                  {renameTarget === conv.id ? (
                    <RenameInput
                      initialTitle={conv.title}
                      onSave={handleRenameSave}
                      onCancel={() => setRenameTarget(null)}
                    />
                  ) : (
                    <>
                      <span className="truncate pr-4">{conv.title}</span>
                      <div className="flex flex-shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setRenameTarget(conv.id);
                          }}
                          className="rounded p-1 text-latte hover:text-espresso"
                          aria-label="Rename conversation"
                        >
                          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                          </svg>
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteTarget(conv.id);
                          }}
                          className="rounded p-1 text-latte hover:text-espresso"
                          aria-label="Delete conversation"
                        >
                          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                          </svg>
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {deleteTarget && (
        <ConfirmDialog
          title="Delete conversation?"
          message="This conversation and its saved messages will be permanently deleted."
          confirmLabel="Delete"
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
