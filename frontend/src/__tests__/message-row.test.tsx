import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MessageRow } from "@/components/message-row";

describe("MessageRow", () => {
  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn().mockResolvedValue(undefined);
    try {
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText },
        configurable: true,
      });
    } catch {
      (navigator as unknown as { clipboard: unknown }).clipboard = { writeText };
    }
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders assistant content as markdown", () => {
    render(<MessageRow role="assistant" content="Try the **Cold Brew**." />);
    expect(screen.getByText("Cold Brew").tagName).toBe("STRONG");
  });

  it("copies the assistant response and confirms briefly", async () => {
    render(<MessageRow role="assistant" content="Cold Brew!" />);
    fireEvent.click(screen.getByRole("button", { name: "Copy response" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("Cold Brew!"));
    expect(screen.getByText("Copied")).toBeTruthy();
  });

  it("shows regenerate for the last assistant message and invokes it", () => {
    const onRegenerate = vi.fn();
    render(
      <MessageRow
        role="assistant"
        content="Try the Cold Brew."
        canRegenerate
        onRegenerate={onRegenerate}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Regenerate response" }));
    expect(onRegenerate).toHaveBeenCalledTimes(1);
  });

  it("hides regenerate when it is not the last assistant message", () => {
    render(<MessageRow role="assistant" content="Try the Cold Brew." />);
    expect(
      screen.queryByRole("button", { name: "Regenerate response" })
    ).toBeNull();
  });

  it("renders user messages as plain text without markdown", () => {
    render(<MessageRow role="user" content="I like **iced** coffee" />);
    expect(screen.getByText("I like **iced** coffee")).toBeTruthy();
  });
});