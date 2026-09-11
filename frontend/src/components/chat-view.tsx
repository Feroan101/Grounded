"use client";

import { useRef, useEffect, useCallback, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useConversations } from "@/lib/conversation-context";
import { ChatInput } from "@/components/chat-input";
import { MessageRow } from "@/components/message-row";
import { EmptyState } from "@/components/empty-state";
import { ActivityIndicator } from "@/components/activity-indicator";

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function hasActiveMessages(conv: { messages: { role: string }[] } | undefined): boolean {
  return !!conv && conv.messages.length > 0;
}

export function ChatView() {
  const { user } = useAuth();
  const { activeConversation, sendMessage, regenerate, isSending, activity } =
    useConversations();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isUserNearBottomRef = useRef(true);
  const scrollRafRef = useRef<number | null>(null);

  const [isScrolledAway, setIsScrolledAway] = useState(false);
  const [newReplyAt, setNewReplyAt] = useState<number | null>(null);

  const messageCount = activeConversation?.messages.length ?? 0;
  const messages = activeConversation?.messages ?? [];

  // Queue an entrance animation when sending transitions to complete and
  // an assistant reply has just landed.
  useEffect(() => {
    if (!isSending && activeConversation) {
      const idx = activeConversation.messages.length - 1;
      const last = activeConversation.messages[idx];
      if (last?.role === "assistant") {
        const raf = requestAnimationFrame(() => setNewReplyAt(idx));
        return () => cancelAnimationFrame(raf);
      }
    }
    if (!isSending) {
      const raf = requestAnimationFrame(() => setNewReplyAt(null));
      return () => cancelAnimationFrame(raf);
    }
  }, [isSending, activeConversation]);

  const checkIfNearBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const threshold = 120;
    const near =
      container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
    isUserNearBottomRef.current = near;
    // Throttle state updates to once per frame.
    if (scrollRafRef.current !== null) return;
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = null;
      setIsScrolledAway(!near);
    });
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    container.addEventListener("scroll", checkIfNearBottom, { passive: true });
    return () => container.removeEventListener("scroll", checkIfNearBottom);
  }, [checkIfNearBottom]);

  useEffect(() => {
    if (isUserNearBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messageCount, isSending]);

  function handleSend(content: string) {
    sendMessage(content);
  }

  function handleRegenerate() {
    regenerate();
  }

  const jumpToLatest = useCallback(() => {
    isUserNearBottomRef.current = true;
    setIsScrolledAway(false);
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const displayName = user?.displayName?.split(" ")[0] || "there";
  const showEmpty = !activeConversation || !hasActiveMessages(activeConversation);
  const showJumpControl = !showEmpty && isScrolledAway;

  return (
    <div className="flex h-full flex-col">
      <div className="relative min-h-0 flex-1">
        <main ref={scrollContainerRef} className="h-full overflow-y-auto">
          {showEmpty ? (
            <div className="flex h-full flex-col">
              <div className="px-4 pt-8 pb-2 sm:px-6 md:pt-12">
                <h2 className="text-2xl font-semibold text-espresso sm:text-3xl">
                  {getGreeting()}, {displayName}
                </h2>
                <p className="mt-1 text-sm text-latte">
                  What can I get for you today?
                </p>
                <div className="mt-4 h-px bg-gradient-to-r from-cafe/20 via-cafe/10 to-transparent" />
              </div>
              <EmptyState onSuggestionClick={handleSend} />
            </div>
          ) : (
            <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
              <div className="mb-5 flex items-center gap-3">
                <div className="h-px flex-1 bg-cafe/15" />
                <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-cafe/40">
                  Table 01 · Grounded
                </span>
                <div className="h-px flex-1 bg-cafe/15" />
              </div>
              <div>
                {messages.map((msg, i) => {
                  const prev = i > 0 ? messages[i - 1] : undefined;
                  const grouped = prev?.role === msg.role;
                  const lastAssistant =
                    msg.role === "assistant" && i === messageCount - 1;
                  return (
                    <div key={i} className={i === 0 ? "" : grouped ? "mt-3" : "mt-6"}>
                      <MessageRow
                        role={msg.role}
                        content={msg.content}
                        entrance={newReplyAt === i}
                        canRegenerate={lastAssistant}
                        onRegenerate={lastAssistant ? handleRegenerate : undefined}
                      />
                    </div>
                  );
                })}
                {isSending && activity && <ActivityIndicator activity={activity} />}
                <div ref={messagesEndRef} />
              </div>
            </div>
          )}
        </main>

        {showJumpControl && (
          <button
            type="button"
            onClick={jumpToLatest}
            className="absolute bottom-4 right-3 flex h-9 items-center gap-1.5 rounded-full border border-cafe/25 bg-ivory px-3.5 text-xs font-medium text-espresso shadow-lg ring-1 ring-espresso/5 transition-colors hover:border-cafe/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-cafe/40 sm:right-6"
            aria-label="Jump to latest message"
          >
            <svg
              className="h-3.5 w-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 5v14M19 12l-7 7-7-7" />
            </svg>
            Latest
          </button>
        )}
      </div>

      <ChatInput onSend={handleSend} disabled={isSending} />
    </div>
  );
}