"use client";

import { useRef, useEffect, useMemo, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { useConversations } from "@/lib/conversation-context";
import { useBackendReadiness } from "@/lib/backend-readiness";
import { ChatInput } from "@/components/chat-input";
import { MessageBubble } from "@/components/message-bubble";
import { EmptyState } from "@/components/empty-state";
import { CoffeeFactsCard } from "@/components/coffee-facts-card";
import { ThinkingIndicator } from "@/components/thinking-indicator";

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
  const { activeConversation, sendMessage } = useConversations();
  const { status: backendStatus } = useBackendReadiness();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isUserNearBottomRef = useRef(true);

  const isThinking = useMemo(() => {
    if (!activeConversation) return false;
    const msgs = activeConversation.messages;
    return msgs.length > 0 && msgs[msgs.length - 1].role === "user";
  }, [activeConversation]);

  const messageCount = activeConversation?.messages.length ?? 0;
  const isBackendReady = backendStatus === "ready";
  const isBackendUnavailable = backendStatus === "checking" || backendStatus === "waking" || backendStatus === "failed";

  const checkIfNearBottom = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const threshold = 120;
    isUserNearBottomRef.current =
      container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
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
  }, [messageCount, isThinking]);

  function handleSend(content: string) {
    sendMessage(content);
  }

  const displayName = user?.displayName?.split(" ")[0] || "there";
  const showEmpty = !activeConversation || !hasActiveMessages(activeConversation);

  return (
    <div className="flex h-full flex-col">
      <main ref={scrollContainerRef} className="min-h-0 flex-1 overflow-y-auto">
        {showEmpty && isBackendUnavailable ? (
          <div className="flex h-full flex-col">
            <div className="px-4 pt-8 pb-2 sm:px-6 md:pt-12">
              <h2 className="text-2xl font-semibold text-espresso sm:text-3xl">
                {getGreeting()}, {displayName}
              </h2>
              <p className="mt-1 text-sm text-latte">
                Grounded is warming up...
              </p>
              <div className="mt-4 h-px bg-gradient-to-r from-cafe/20 via-cafe/10 to-transparent" />
            </div>
            <CoffeeFactsCard />
          </div>
        ) : showEmpty ? (
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
            <div className="space-y-6">
              {activeConversation!.messages.map((msg, i) => (
                <div
                  key={i}
                  className="animate-fade-in"
                  style={{ animationDelay: `${Math.min(i * 30, 150)}ms` }}
                >
                  <MessageBubble role={msg.role} content={msg.content} />
                </div>
              ))}
              {isThinking && <ThinkingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}
      </main>

      <ChatInput
        onSend={handleSend}
        disabled={isThinking}
        backendReady={isBackendReady}
        backendStatus={backendStatus}
      />
    </div>
  );
}
