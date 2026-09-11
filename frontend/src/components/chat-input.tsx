"use client";

import { useState, useRef, useEffect } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isDisabled = disabled || isSending;

  useEffect(() => {
    if (!isDisabled && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isDisabled]);

  function autoResize() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isDisabled) return;
    setIsSending(true);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    try {
      void Promise.resolve(onSend(trimmed)).finally(() => setIsSending(false));
    } catch {
      setIsSending(false);
    }
  }

  return (
    <div className="flex flex-shrink-0 border-t border-cafe/15 bg-marble/85 backdrop-blur-md">
      <div className="mx-auto w-full max-w-3xl px-4 py-3 sm:px-6 sm:py-4">
        <form onSubmit={handleSubmit} className="relative">
          <div className="flex items-end gap-2 rounded-2xl border border-cafe/20 bg-ivory p-2 shadow-sm transition-all focus-within:border-cafe/40 focus-within:ring-[3px] focus-within:ring-cafe/10">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                autoResize();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder={
                isSending
                  ? "Sending..."
                  : "Ask Grounded about coffee..."
              }
              disabled={isDisabled}
              rows={1}
              className="min-w-0 flex-1 resize-none bg-transparent px-3 py-2 text-sm leading-relaxed text-bean placeholder:text-latte/50 focus:outline-none disabled:opacity-40"
              style={{ minHeight: "40px", maxHeight: "120px" }}
              aria-label="Message input"
              aria-describedby={isDisabled ? undefined : "chat-input-hint"}
            />
            <button
              type="submit"
              disabled={!input.trim() || isDisabled}
              className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-espresso text-ivory transition-all hover:bg-bean disabled:opacity-25 disabled:hover:bg-espresso"
              aria-label={isSending ? "Sending message" : "Send message"}
            >
              {isSending ? (
                <svg
                  className="h-4 w-4 animate-spin"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeDasharray="32"
                    strokeDashoffset="8"
                    strokeLinecap="round"
                  />
                </svg>
              ) : (
                <svg
                  className="h-4 w-4"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              )}
            </button>
          </div>
          <p
            id="chat-input-hint"
            className="mt-1.5 hidden text-center text-[10px] tracking-wide text-latte/40 sm:block"
          >
            Enter to send · Shift + Enter for a new line
          </p>
        </form>
      </div>
    </div>
  );
}
