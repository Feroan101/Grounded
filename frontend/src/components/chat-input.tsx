"use client";

import { useState } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
  }

  return (
    <div className="border-t border-espresso/10 bg-marble/80 backdrop-blur-md">
      <div className="mx-auto max-w-3xl px-4 py-4 sm:px-6">
        <form onSubmit={handleSubmit} className="relative">
          <div className="flex items-end gap-3 rounded-2xl border border-espresso/20 bg-ivory p-2 shadow-sm transition-all focus-within:border-espresso/40 focus-within:shadow-md focus-within:ring-1 focus-within:ring-espresso/10">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder="Ask Grounded about coffee..."
              disabled={disabled}
              rows={1}
              className="flex-1 resize-none bg-transparent px-3 py-2 text-sm text-bean placeholder:text-latte/60 focus:outline-none disabled:opacity-50"
              style={{ minHeight: "40px", maxHeight: "120px" }}
            />
            <button
              type="submit"
              disabled={!input.trim() || disabled}
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-espresso text-ivory transition-all hover:bg-bean disabled:opacity-30 disabled:hover:bg-espresso"
              aria-label="Send message"
            >
              <svg
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
