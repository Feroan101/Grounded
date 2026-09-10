"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useBackendReadiness } from "@/lib/backend-readiness";

export function WakeUpToast() {
  const { status } = useBackendReadiness();
  const [dismissed, setDismissed] = useState(false);
  const [readyGone, setReadyGone] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset dismissed state when status transitions away from a dismissable state
  const prevStatusRef = useRef(status);
  useEffect(() => {
    const prev = prevStatusRef.current;
    prevStatusRef.current = status;
    if (prev !== status && (status === "checking" || status === "failed" || (prev !== "ready" && status === "waking"))) {
      setDismissed(false);
      setReadyGone(false);
    }
  }, [status]);

  // Auto-dismiss the "ready" toast after a delay
  useEffect(() => {
    if (status === "ready" && !readyGone) {
      timerRef.current = setTimeout(() => setReadyGone(true), 3500);
      return () => {
        if (timerRef.current) clearTimeout(timerRef.current);
      };
    }
    return undefined;
  }, [status, readyGone]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const visible = useMemo(() => {
    if (status === "checking") return true;
    if (status === "waking" && !dismissed) return true;
    if (status === "ready" && !readyGone) return true;
    if (status === "failed" && !dismissed) return true;
    return false;
  }, [status, dismissed, readyGone]);

  if (!visible) return null;

  const isReady = status === "ready";
  const isFailed = status === "failed";

  return (
    <div className="fixed bottom-20 left-1/2 z-[60] -translate-x-1/2 animate-slide-up md:bottom-6">
      <div className="flex items-center gap-3 rounded-xl border border-cafe/20 bg-ivory px-4 py-3 shadow-lg shadow-cafe/5">
        {isReady ? (
          <svg className="h-4 w-4 flex-shrink-0 text-espresso" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M20 6L9 17l-5-5" />
          </svg>
        ) : isFailed ? (
          <svg className="h-4 w-4 flex-shrink-0 text-espresso" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
        ) : (
          <div className="relative flex h-4 w-4 flex-shrink-0 items-center justify-center">
            <div className="absolute h-3 w-3 rounded-full border-2 border-espresso/30 border-t-espresso animate-spin" />
          </div>
        )}
        <div className="min-w-0">
          <p className="text-sm font-medium text-bean">
            {isReady
              ? "Grounded is ready"
              : isFailed
                ? "Grounded is taking longer than expected"
                : "Waking up Grounded"}
          </p>
          <p className="text-xs text-latte">
            {isReady
              ? "The coffee machine is warmed up."
              : isFailed
                ? "We\u2019re still trying. You can refresh the page or try again shortly."
                : "Give us a moment while the coffee machine starts up."}
          </p>
        </div>
        {!isReady && (
          <button
            onClick={() => setDismissed(true)}
            className="ml-2 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded text-latte hover:text-espresso"
            aria-label="Dismiss"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
