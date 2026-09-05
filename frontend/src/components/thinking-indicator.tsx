"use client";

export function ThinkingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1.5 rounded-2xl bg-ivory/50 px-4 py-3">
        <div className="h-1.5 w-1.5 rounded-full bg-espresso animate-pulse-dot" />
        <div className="h-1.5 w-1.5 rounded-full bg-espresso animate-pulse-dot" />
        <div className="h-1.5 w-1.5 rounded-full bg-espresso animate-pulse-dot" />
      </div>
    </div>
  );
}
