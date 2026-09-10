"use client";

import { useState, useEffect, useCallback } from "react";
import { getRandomFact, COFFEE_FACTS } from "@/lib/coffee-facts";

const ROTATION_INTERVAL_MS = 8_000;

export function CoffeeFactsCard() {
  const [current, setCurrent] = useState(() => getRandomFact());
  const [isTransitioning, setIsTransitioning] = useState(false);

  const rotateFact = useCallback(() => {
    setIsTransitioning(true);
    setTimeout(() => {
      setCurrent((prev) => getRandomFact(prev.index));
      setIsTransitioning(false);
    }, 300);
  }, []);

  useEffect(() => {
    const interval = setInterval(rotateFact, ROTATION_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [rotateFact]);

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-12 text-center">
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

      <p className="mb-1 text-[10px] font-medium uppercase tracking-[0.2em] text-cafe/50">
        While you wait
      </p>

      <h2 className="mb-2 text-2xl font-semibold text-espresso sm:text-3xl">
        Coffee Break
      </h2>

      <p className="mb-8 max-w-sm text-sm text-latte sm:text-base">
        Grounded is warming up. Here&apos;s a little something to enjoy while you wait.
      </p>

      <div
        className={`w-full max-w-md transition-opacity duration-300 ${isTransitioning ? "opacity-0" : "opacity-100"}`}
      >
        <div className="rounded-2xl border border-cafe/15 bg-ivory/80 px-6 py-5 text-left shadow-sm">
          <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.15em] text-cafe/50">
            {current.title}
          </p>
          <p className="text-sm leading-relaxed text-bean/80">
            {current.fact}
          </p>
        </div>
      </div>

      <div className="mt-6 flex items-center gap-1.5">
        {COFFEE_FACTS.map((_, i) => (
          <div
            key={i}
            className={`h-1 rounded-full transition-all duration-300 ${
              i === current.index
                ? "w-4 bg-espresso/40"
                : "w-1 bg-stone"
            }`}
          />
        ))}
      </div>
    </div>
  );
}
