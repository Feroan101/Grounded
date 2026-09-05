"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { Header } from "@/components/header";
import { ChatInput } from "@/components/chat-input";
import { MessageBubble } from "@/components/message-bubble";
import { EmptyState } from "@/components/empty-state";
import { ThinkingIndicator } from "@/components/thinking-indicator";
import { LandingPage } from "@/components/landing-page";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function Home() {
  const { user, loading } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  function handleSend(content: string) {
    setMessages((prev) => [...prev, { role: "user", content }]);
    setIsThinking(true);

    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "I'd love to help you find the perfect coffee. What are you in the mood for today?",
        },
      ]);
      setIsThinking(false);
    }, 1500);
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#2B1B15]">
        <div className="flex items-center gap-2 text-white/60">
          <div className="h-1.5 w-1.5 rounded-full bg-white animate-pulse-dot" />
          <div className="h-1.5 w-1.5 rounded-full bg-white animate-pulse-dot" />
          <div className="h-1.5 w-1.5 rounded-full bg-white animate-pulse-dot" />
        </div>
      </div>
    );
  }

  if (!user) {
    return <LandingPage />;
  }

  return (
    <div className="flex h-screen flex-col marble-bg marble-veins">
      <Header />

      <main className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <EmptyState onSuggestionClick={handleSend} />
        ) : (
          <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
            <div className="space-y-6">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className="animate-fade-in"
                  style={{ animationDelay: `${i * 50}ms` }}
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

      <ChatInput onSend={handleSend} disabled={isThinking} />
    </div>
  );
}
