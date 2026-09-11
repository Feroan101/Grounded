"use client";

export function ActivityIndicator({ activity }: { activity: string }) {
  return (
    <div className="mt-6 flex justify-start gap-2.5" role="status" aria-live="polite" aria-busy="true">
      <div className="mt-1 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-latte/15 ring-1 ring-latte/10">
        <svg
          className="h-3.5 w-3.5 text-latte/80"
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
      </div>
      <div className="flex min-w-0 items-center gap-2 pt-1.5">
        <span className="text-xs font-medium text-latte">{activity}</span>
        <span className="flex items-center gap-1">
          <span className="h-1 w-1 rounded-full bg-latte/60 animate-pulse-dot" />
          <span className="h-1 w-1 rounded-full bg-latte/60 animate-pulse-dot" />
          <span className="h-1 w-1 rounded-full bg-latte/60 animate-pulse-dot" />
        </span>
      </div>
    </div>
  );
}