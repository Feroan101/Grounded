import { describe, it, expect, vi, afterEach } from "vitest";
import { sendChatMessage, ChatActivityEvent } from "@/lib/api";

function sseStream(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
}

function mockEventStream(chunks: string[]) {
  const res = {
    ok: true,
    status: 200,
    headers: {
      get: (name: string) =>
        name.toLowerCase() === "content-type" ? "text/event-stream" : null,
    },
    body: sseStream(...chunks),
  } as unknown as Response;
  const fetchMock = vi.fn().mockResolvedValue(res);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function jsonEvent(payload: Record<string, unknown>) {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

const opts = {
  messages: [{ role: "user" as const, content: "hi" }],
  idToken: "tok-1",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("sendChatMessage streaming", () => {
  it("requests the event-stream via Accept and resolves on done", async () => {
    const fetchMock = mockEventStream([
      jsonEvent({ type: "tool", name: "search_menu" }),
      jsonEvent({ type: "done", answer: "The cold brew is $4.", context: {} }),
    ]);

    const result = await sendChatMessage(opts);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/chat"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Accept: "text/event-stream" }),
      })
    );
    expect(result.answer).toBe("The cold brew is $4.");
  });

  it("reports real tool events in order to onActivity", async () => {
    const events: ChatActivityEvent[] = [];
    mockEventStream([
      jsonEvent({ type: "tool", name: "search_menu" }),
      jsonEvent({ type: "tool", name: "convert_currency" }),
      jsonEvent({ type: "generating" }),
      jsonEvent({ type: "done", answer: "Done.", context: {} }),
    ]);

    const result = await sendChatMessage({
      ...opts,
      onActivity: (event) => events.push(event),
    });

    expect(result.answer).toBe("Done.");
    expect(events).toEqual([
      { type: "tool", name: "search_menu" },
      { type: "tool", name: "convert_currency" },
      { type: "generating" },
    ]);
  });

it("buffers events that arrive split across chunks", async () => {
    const events: ChatActivityEvent[] = [];
    mockEventStream([
      'data: {"type": "tool", "name": "se',
      'arch_menu"}\n\ndata: {"type": "gener',
      'ating"}\n\ndata: {"type": "done", "answer": "Ok"',
      ', "context": {}}\n\n',
    ]);

    const result = await sendChatMessage({
      ...opts,
      onActivity: (event) => events.push(event),
    });

    expect(events).toEqual([
      { type: "tool", name: "search_menu" },
      { type: "generating" },
    ]);
    expect(result.answer).toBe("Ok");
  });

  it("rejects with the backend's safe message on an error event", async () => {
    mockEventStream([
      jsonEvent({
        type: "error",
        message: "Grounded is still warming up. Please try again in a moment.",
      }),
    ]);

    await expect(sendChatMessage(opts)).rejects.toMatchObject({
      name: "ChatApiError",
      message: "Grounded is still warming up. Please try again in a moment.",
    });
  });

  it("falls back to a safe message when the error event has none", async () => {
    mockEventStream([jsonEvent({ type: "error" })]);

    await expect(sendChatMessage(opts)).rejects.toMatchObject({
      name: "ChatApiError",
      status: 502,
      message: "Something went wrong while preparing the response.",
    });
  });

  it("rejects a stream that ends without a done event", async () => {
    mockEventStream([jsonEvent({ type: "tool", name: "search_menu" })]);

    await expect(sendChatMessage(opts)).rejects.toMatchObject({
      name: "ChatApiError",
      message: "The assistant response was cut short.",
    });
  });

  it("falls back to the plain JSON path when the backend does not stream", async () => {
    const res = {
      ok: true,
      status: 200,
      headers: {
        get: (name: string) =>
          name.toLowerCase() === "content-type" ? "application/json" : null,
      },
      json: vi.fn().mockResolvedValue({
        answer: "Plain JSON answer.",
        context: { used_preferences: false, retrieval_used: false, retrieval_count: 0 },
      }),
    } as unknown as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(res));

    const result = await sendChatMessage(opts);
    expect(result.answer).toBe("Plain JSON answer.");
  });

  it("still surfaces HTTP error details on the streaming endpoint", async () => {
    const res = {
      ok: false,
      status: 401,
      headers: { get: () => "text/event-stream" },
      json: vi.fn().mockResolvedValue({ detail: "Invalid or expired token" }),
    } as unknown as Response;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(res));

    await expect(sendChatMessage(opts)).rejects.toMatchObject({
      name: "ChatApiError",
      status: 401,
      message: "Invalid or expired token",
    });
  });
});