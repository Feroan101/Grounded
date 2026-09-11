import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { BackendReadinessProvider, useBackendReadiness } from "@/lib/backend-readiness";
import { FunFactBubble } from "@/components/fun-fact-bubble";
import { EmptyState } from "@/components/empty-state";

function StatusProbe() {
  const { setStatus } = useBackendReadiness();
  return (
    <div>
      <button onClick={() => setStatus("idle")}>idle</button>
      <button onClick={() => setStatus("waking")}>waking</button>
      <button onClick={() => setStatus("ready")}>ready</button>
      <button onClick={() => setStatus("failed")}>failed</button>
    </div>
  );
}

function renderBubble() {
  return render(
    <BackendReadinessProvider>
      <StatusProbe />
      <FunFactBubble />
    </BackendReadinessProvider>
  );
}

afterEach(() => {
  vi.useRealTimers();
});

describe("FunFactBubble", () => {
  it("shows a fact through the speech bubble while the backend has not been reached", () => {
    const { container } = renderBubble();
    expect(container.querySelectorAll("p").length).toBeGreaterThan(0);
  });

  it("cycles through facts on an interval while the backend has not been reached", () => {
    vi.useFakeTimers();
    const { container } = renderBubble();
    const before = container.textContent ?? "";

    act(() => {
      vi.advanceTimersByTime(8_000);
    });
    act(() => {
      vi.advanceTimersByTime(300);
    });

    expect(container.textContent).not.toBe(before);
  });

  it("stops cycling when the backend becomes ready", () => {
    const { container } = renderBubble();
    act(() => {
      screen.getByText("ready").click();
    });
    expect(container.querySelectorAll("p").length).toBe(0);
  });

  it("hides while the first request is loading (waking)", () => {
    const { container } = renderBubble();
    act(() => {
      screen.getByText("waking").click();
    });
    expect(container.querySelectorAll("p").length).toBe(0);
  });

  it("shows the facts again when the backend connection fails", () => {
    const { container } = renderBubble();
    act(() => {
      screen.getByText("ready").click();
    });
    expect(container.querySelectorAll("p").length).toBe(0);

    act(() => {
      screen.getByText("failed").click();
    });
    expect(container.querySelectorAll("p").length).toBeGreaterThan(0);
  });
});

describe("EmptyState", () => {
  it("renders the fun-fact bubble via the speech bubble, not a standalone facts section", () => {
    render(
      <BackendReadinessProvider>
        <EmptyState onSuggestionClick={() => {}} />
      </BackendReadinessProvider>
    );
    expect(screen.queryByText(/while you're deciding/i)).not.toBeInTheDocument();
    expect(screen.queryAllByText(/try asking/i).length).toBe(1);
    expect(screen.getByTestId("fun-fact-bubble")).toBeInTheDocument();
  });

  it("does not render fun facts once the backend is ready", () => {
    render(
      <BackendReadinessProvider>
        <StatusProbe />
        <EmptyState onSuggestionClick={() => {}} />
      </BackendReadinessProvider>
    );
    expect(screen.getByTestId("fun-fact-bubble")).toBeInTheDocument();

    act(() => {
      screen.getByText("ready").click();
    });
    expect(screen.queryByTestId("fun-fact-bubble")).not.toBeInTheDocument();
  });
});