"use client";

import { MarkdownRenderer } from "@/components/markdown-renderer";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
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

export function MessageBubble({ role, content }: MessageBubbleProps) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-cream px-4 py-3 text-sm leading-relaxed text-bean shadow-sm ring-1 ring-espresso/5 sm:max-w-[70%]">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start gap-2.5">
      <div className="mt-1 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-latte/15 ring-1 ring-latte/10">
        <AssistantIcon />
      </div>
      <div className="max-w-[85%] min-w-0 rounded-2xl rounded-tl-md border border-latte/10 bg-[#A8876A]/15 px-4 py-3 text-bean shadow-[0_1px_2px_rgba(43,27,21,0.04)] sm:max-w-[75%]">
        <MarkdownRenderer content={content} />
      </div>
    </div>
  );
}
