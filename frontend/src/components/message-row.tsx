"use client";

import { useEffect, useRef, useState } from "react";
import { MarkdownRenderer } from "@/components/markdown-renderer";

interface MessageRowProps {
  role: "user" | "assistant";
  content: string;
  entrance?: boolean;
  canRegenerate?: boolean;
  onRegenerate?: () => void;
}

function AssistantIcon() {
  return (
    <svg
      className="h-3.5 w-3.5 flex-shrink-0 text-latte/80"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M17 8h1a4 4 0 0 1 0 8h-1" />
      <path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V8z" />
      <line x1="6" y1="2" x2="6" y2="4" />
      <line x1="10" y1="2" x2="10" y2="4" />
      <line x1="14" y1="2" x2="14" y2="4" />
    </svg>
  );
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall through to the legacy path below.
  }
  try {
    const el = document.createElement("textarea");
    el.value = text;
    el.setAttribute("readonly", "");
    el.style.position = "fixed";
    el.style.opacity = "0";
    document.body.appendChild(el);
    el.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(el);
    return ok;
  } catch {
    return false;
  }
}

export function MessageRow({
  role,
  content,
  entrance,
  canRegenerate,
  onRegenerate,
}: MessageRowProps) {
  const [copied, setCopied] = useState(false);
  const copyTimerRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (copyTimerRef.current !== null) {
        window.clearTimeout(copyTimerRef.current);
      }
    },
    []
  );

  if (role === "user") {
    return (
      <div className={`flex justify-end${entrance ? " animate-message-in" : ""}`}>
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-cream px-4 py-3 text-sm leading-relaxed text-bean shadow-sm ring-1 ring-espresso/5 sm:max-w-[70%]">
          {content}
        </div>
      </div>
    );
  }

  function handleCopy() {
    void copyToClipboard(content).then((ok) => {
      if (!ok) return;
      setCopied(true);
      if (copyTimerRef.current !== null) {
        window.clearTimeout(copyTimerRef.current);
      }
      copyTimerRef.current = window.setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div className={`flex justify-start gap-2.5${entrance ? " animate-message-in" : ""}`}>
      <div className="mt-1 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-latte/15 ring-1 ring-latte/10">
        <AssistantIcon />
      </div>
      <div className="min-w-0 flex-1">
        <div className="pt-0.5 text-bean">
          <MarkdownRenderer content={content} />
        </div>
        <div className="mt-2 flex items-center gap-1">
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-latte/70 transition-colors hover:bg-espresso/5 hover:text-espresso focus:outline-none focus-visible:ring-2 focus-visible:ring-cafe/40"
            aria-label="Copy response"
          >
            {copied ? (
              <svg
                className="h-3.5 w-3.5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M20 6 9 17l-5-5" />
              </svg>
            ) : (
              <svg
                className="h-3.5 w-3.5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="9" y="9" width="13" height="13" rx="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
            )}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>
          {canRegenerate && onRegenerate && (
            <button
              type="button"
              onClick={onRegenerate}
              className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-latte/70 transition-colors hover:bg-espresso/5 hover:text-espresso focus:outline-none focus-visible:ring-2 focus-visible:ring-cafe/40"
              aria-label="Regenerate response"
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
                <path d="M21 12a9 9 0 1 1-2.64-6.36" />
                <path d="M21 3v6h-6" />
              </svg>
              <span>Regenerate</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}