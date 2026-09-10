"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  ReactNode,
} from "react";

export type BackendStatus = "checking" | "ready" | "waking" | "failed";

interface BackendReadinessValue {
  status: BackendStatus;
}

const BackendReadinessContext = createContext<BackendReadinessValue>({ status: "checking" });

export function useBackendReadiness(): BackendReadinessValue {
  return useContext(BackendReadinessContext);
}

const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const INITIAL_RETRY_MS = 5_000;
const MAX_RETRY_MS = 30_000;
const MAX_RETRIES = 12;

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      signal: AbortSignal.timeout(10_000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export function BackendReadinessProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const retriesRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const scheduleRef = useRef<() => void>(() => {});

  useEffect(() => {
    mountedRef.current = true;
    retriesRef.current = 0;

    scheduleRef.current = () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      if (!mountedRef.current) return;
      if (retriesRef.current >= MAX_RETRIES) {
        setStatus("failed");
        return;
      }
      const delay = Math.min(
        INITIAL_RETRY_MS * Math.pow(1.5, retriesRef.current),
        MAX_RETRY_MS
      );
      retriesRef.current += 1;
      timerRef.current = setTimeout(async () => {
        if (!mountedRef.current) return;
        const ok = await checkBackendHealth();
        if (!mountedRef.current) return;
        if (ok) {
          setStatus("ready");
        } else {
          setStatus("waking");
          scheduleRef.current();
        }
      }, delay);
    };

    (async () => {
      const ok = await checkBackendHealth();
      if (!mountedRef.current) return;
      if (ok) {
        setStatus("ready");
      } else {
        setStatus("waking");
        scheduleRef.current();
      }
    })();

    return () => {
      mountedRef.current = false;
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  return (
    <BackendReadinessContext.Provider value={{ status }}>
      {children}
    </BackendReadinessContext.Provider>
  );
}
