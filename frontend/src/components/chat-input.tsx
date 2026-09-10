"use client";

import { useState, useRef, useEffect } from "react";
import type { BackendStatus } from "@/lib/backend-readiness";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  backendReady?: boolean;
  backendStatus?: BackendStatus;
}

export function ChatInput({ onSend, disabled, backendReady = true, backendStatus }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isDisabled = disabled || isSending || !backendReady;

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
    <div className="flex flex-shrink-0 border-t border-cafe/15 bg-marble/80 backdrop-blur-md">
      <div className="w-full px-4 py-3 sm:px-6 sm:py-4">
        <form onSubmit={handleSubmit} className="relative">
          <div className="flex items-end gap-2 rounded-2xl border border-cafe/20 bg-ivory p-2 shadow-sm transition-all focus-within:border-cafe/40 focus-within:shadow-md focus-within:ring-1 focus-within:ring-cafe/10">
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
                  : backendStatus === "checking" || backendStatus === "waking"
                    ? "Grounded is warming up..."
                    : backendStatus === "failed"
                      ? "Grounded is unavailable right now"
                      : "Ask Grounded about coffee..."
              }
              disabled={isDisabled}
              rows={1}
              className="flex-1 resize-none bg-transparent px-3 py-2 text-sm text-bean placeholder:text-latte/50 focus:outline-none disabled:opacity-40"
              style={{ minHeight: "40px", maxHeight: "120px" }}
              aria-label="Message input"
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
        </form>
      </div>
    </div>
  );
}
