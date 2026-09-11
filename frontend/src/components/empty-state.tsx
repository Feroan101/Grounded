"use client";

import { FunFactBubble } from "@/components/fun-fact-bubble";

interface EmptyStateProps {
  onSuggestionClick: (message: string) => void;
}

const SUGGESTIONS = [
  "Something cold and not too sweet",
  "What would I like if I enjoy caramel?",
  "Recommend something for a rainy day",
];

function SteamCup() {
  return (
    <div className="relative mb-6">
      <svg
        className="h-16 w-16 text-espresso/80"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M17 8h1a4 4 0 0 1 0 8h-1" />
        <path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V8z" />
        <line x1="6" y1="2" x2="6" y2="4" className="animate-pulse-dot" style={{ animationDelay: "0s" }} />
        <line x1="10" y1="2" x2="10" y2="4" className="animate-pulse-dot" style={{ animationDelay: "0.2s" }} />
        <line x1="14" y1="2" x2="14" y2="4" className="animate-pulse-dot" style={{ animationDelay: "0.4s" }} />
      </svg>
    </div>
  );
}

export function EmptyState({ onSuggestionClick }: EmptyStateProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-12 text-center">
      <SteamCup />

      <h2 className="mb-2 text-2xl font-semibold text-espresso sm:text-3xl">
        What are we brewing today?
      </h2>

      <p className="mb-8 max-w-sm text-sm text-latte sm:text-base">
        Tell me what you&apos;re in the mood for, and I&apos;ll find something
        you&apos;ll love.
      </p>

      <div className="flex flex-col gap-3">
        <p className="text-[10px] font-medium uppercase tracking-[0.2em] text-espresso/40">
          Try asking
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => onSuggestionClick(suggestion)}
              className="rounded-full border border-cafe/20 bg-ivory px-4 py-2 text-sm text-latte transition-all hover:border-cafe/40 hover:bg-cafe/10 hover:text-espresso hover:shadow-sm"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      <FunFactBubble />
    </div>
  );
}
