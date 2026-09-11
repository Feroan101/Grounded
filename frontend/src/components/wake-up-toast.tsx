"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useBackendReadiness } from "@/lib/backend-readiness";

export function WakeUpToast() {
  const { status } = useBackendReadiness();
  const [dismissed, setDismissed] = useState(false);
  const [readyGone, setReadyGone] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset per-status state when the status transitions. This is adjusted
  // during render (React's recommended pattern) rather than in an effect.
  const [prevStatus, setPrevStatus] = useState(status);
  if (prevStatus !== status) {
    setPrevStatus(status);
    if (status === "waking" || status === "failed") {
      setDismissed(false);
    }
    if (status === "ready") {
      setReadyGone(false);
    }
  }

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
    if (status === "waking" && !dismissed) return true;
    if (status === "ready" && !readyGone) return true;
    if (status === "failed" && !dismissed) return true;
    return false;
  }, [status, dismissed, readyGone]);

  if (!visible) return null;

  const isReady = status === "ready";
  const isFailed = status === "failed";

  return (
    <div className="fixed inset-x-4 bottom-20 z-[60] animate-slide-up md:bottom-6 md:left-1/2 md:right-auto md:-translate-x-1/2">
      <div className="flex items-center gap-2.5 rounded-xl border border-cafe/20 bg-ivory px-3.5 py-2.5 shadow-lg shadow-cafe/5 md:max-w-md md:gap-3 md:px-4 md:py-3">
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
          <p className="text-xs font-medium break-words text-bean md:text-sm">
            {isReady
              ? "Grounded is ready"
              : isFailed
                ? "Grounded is taking longer than expected"
                : "Waking up Grounded"}
          </p>
          <p className="text-[11px] break-words text-latte md:text-xs">
            {isReady
              ? "The coffee machine is warmed up."
              : isFailed
                ? "We couldn\u2019t reach the backend. Check that it\u2019s running and try again."
                : "This can take a moment."}
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
