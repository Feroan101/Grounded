"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getRandomFact } from "@/lib/coffee-facts";
import { useBackendReadiness } from "@/lib/backend-readiness";
import { MessageBubble } from "@/components/message-bubble";

const ROTATION_INTERVAL_MS = 8_000;
const FADE_MS = 300;

export function FunFactBubble() {
  const { status } = useBackendReadiness();
  const active = status === "idle" || status === "failed";

  const [current, setCurrent] = useState(() => getRandomFact());
  const [isTransitioning, setIsTransitioning] = useState(false);
  const swapTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const rotateFact = useCallback(() => {
    setIsTransitioning(true);
    if (swapTimerRef.current) clearTimeout(swapTimerRef.current);
    swapTimerRef.current = setTimeout(() => {
      setCurrent((prev) => getRandomFact(prev.index));
      setIsTransitioning(false);
    }, FADE_MS);
  }, []);

  useEffect(() => {
    if (!active) return undefined;
    const interval = setInterval(rotateFact, ROTATION_INTERVAL_MS);
    return () => {
      clearInterval(interval);
      if (swapTimerRef.current) clearTimeout(swapTimerRef.current);
    };
  }, [active, rotateFact]);

  useEffect(() => {
    return () => {
      if (swapTimerRef.current) clearTimeout(swapTimerRef.current);
    };
  }, []);

  if (!active) return null;

  return (
    <div
      data-testid="fun-fact-bubble"
      className={`mx-auto mt-10 w-full max-w-md transition-opacity duration-300 ${
        isTransitioning ? "opacity-0" : "opacity-100"
      }`}
    >
      <MessageBubble role="assistant" content={`**${current.title}**\n\n${current.fact}`} />
    </div>
  );
}