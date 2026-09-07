"use client";

import { useConversations } from "@/lib/conversation-context";

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

export function HistoryView() {
  const {
    conversations,
    loading,
    activeConversationId,
    setActiveConversation,
    deleteConversation,
  } = useConversations();

  const grouped = groupByDate(conversations);

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
                  onClick={() => setActiveConversation(conv.id)}
                  className={`group flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left text-sm cursor-pointer transition-all ${
                    conv.id === activeConversationId
                      ? "border-espresso/40 bg-cream/50 text-espresso"
                      : "border-stone/50 bg-ivory/80 text-bean hover:border-espresso/30 hover:bg-cream/30"
                  }`}
                >
                  <span className="truncate pr-4">{conv.title}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteConversation(conv.id);
                    }}
                    className="flex-shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                    aria-label="Delete conversation"
                  >
                    <svg
                      className="h-4 w-4 text-latte hover:text-espresso"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
