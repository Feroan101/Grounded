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
    <div>
      <div
        className={`w-full max-w-md transition-opacity duration-300 ${
          isTransitioning ? "opacity-0" : "opacity-100"
        }`}
      >
        <div className="rounded-2xl border border-cafe/15 bg-ivory/60 px-5 py-4 text-left shadow-sm">
          <p className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.15em] text-cafe/50">
            {current.title}
          </p>
          <p className="text-sm leading-relaxed text-bean/75">{current.fact}</p>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-center gap-1.5">
        {COFFEE_FACTS.map((_, i) => (
          <div
            key={i}
            className={`h-1 rounded-full transition-all duration-300 ${
              i === current.index ? "w-4 bg-espresso/40" : "w-1 bg-stone"
            }`}
          />
        ))}
      </div>
    </div>
  );
}