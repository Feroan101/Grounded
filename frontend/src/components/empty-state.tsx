"use client";

interface EmptyStateProps {
  onSuggestionClick: (message: string) => void;
}

const SUGGESTIONS = [
  "Something cold and not too sweet",
  "What would I like if I enjoy caramel?",
  "Recommend something for a rainy day",
];

export function EmptyState({ onSuggestionClick }: EmptyStateProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-12 text-center">
      <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-espresso/10">
        <svg
          className="h-8 w-8 text-espresso"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M18 8h1a4 4 0 0 1 0 8h-1M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z" />
          <line x1="6" y1="1" x2="6" y2="4" />
          <line x1="10" y1="1" x2="10" y2="4" />
          <line x1="14" y1="1" x2="14" y2="4" />
        </svg>
      </div>

      <h2 className="mb-2 text-2xl font-semibold text-espresso sm:text-3xl">
        Good coffee starts with
        <br />
        knowing your taste.
      </h2>

      <p className="mb-8 max-w-sm text-sm text-latte sm:text-base">
        Tell me what you&apos;re in the mood for, and I&apos;ll find something
        you&apos;ll love.
      </p>

      <div className="flex flex-col gap-3">
        <p className="text-xs font-medium uppercase tracking-wider text-latte/70">
          Try asking
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => onSuggestionClick(suggestion)}
              className="rounded-full border border-stone/60 bg-ivory px-4 py-2 text-sm text-latte transition-all hover:border-espresso/40 hover:bg-cream/50 hover:text-espresso"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
