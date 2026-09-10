import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import {
  BackendReadinessProvider,
  useBackendReadiness,
} from "@/lib/backend-readiness";

function Probe() {
  const { status, setStatus } = useBackendReadiness();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <button onClick={() => setStatus("waking")}>waking</button>
      <button onClick={() => setStatus("ready")}>ready</button>
      <button onClick={() => setStatus("failed")}>failed</button>
      <button onClick={() => setStatus("idle")}>idle</button>
    </div>
  );
}

describe("BackendReadinessProvider", () => {
  it("starts in the idle state", () => {
    render(
      <BackendReadinessProvider>
        <Probe />
      </BackendReadinessProvider>
    );
    expect(screen.getByTestId("status")).toHaveTextContent("idle");
  });

  it("exposes setStatus for downstream updates", () => {
    render(
      <BackendReadinessProvider>
        <Probe />
      </BackendReadinessProvider>
    );

    act(() => {
      screen.getByText("waking").click();
    });
    expect(screen.getByTestId("status")).toHaveTextContent("waking");

    act(() => {
      screen.getByText("ready").click();
    });
    expect(screen.getByTestId("status")).toHaveTextContent("ready");

    act(() => {
      screen.getByText("failed").click();
    });
    expect(screen.getByTestId("status")).toHaveTextContent("failed");

    act(() => {
      screen.getByText("idle").click();
    });
    expect(screen.getByTestId("status")).toHaveTextContent("idle");
  });
});