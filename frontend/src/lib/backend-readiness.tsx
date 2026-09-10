"use client";

import {
  createContext,
  useContext,
  useState,
  ReactNode,
  Dispatch,
  SetStateAction,
} from "react";

export type BackendStatus = "idle" | "waking" | "ready" | "failed";

interface BackendReadinessValue {
  status: BackendStatus;
  setStatus: Dispatch<SetStateAction<BackendStatus>>;
}

const BackendReadinessContext = createContext<BackendReadinessValue>({
  status: "idle",
  setStatus: () => {},
});

export function useBackendReadiness(): BackendReadinessValue {
  return useContext(BackendReadinessContext);
}

export function BackendReadinessProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<BackendStatus>("idle");

  return (
    <BackendReadinessContext.Provider value={{ status, setStatus }}>
      {children}
    </BackendReadinessContext.Provider>
  );
}
