"use client";

const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface ApiChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ApiChatResponse {
  answer: string;
  context: {
    used_preferences: boolean;
    retrieval_used: boolean;
    retrieval_count: number;
  };
}

export type ChatActivityEvent =
  | { type: "tool"; name: string }
  | { type: "generating" };

export type ChatActivityHandler = (event: ChatActivityEvent) => void;

export interface ApiCoffeePreferences {
  favoriteDrink: string;
  temperature: "hot" | "iced" | "either";
  milkPreference: string;
  sweetness: string;
  strength: string;
  caffeinePreference: string;
  roastPreference: string;
  brewMethod: string;
  dietaryPreference: string[];
  allergiesOrIntolerances: string;
}

export interface ApiAIContextPreferences {
  customContext: string;
  responseStyle: "short" | "balanced" | "detailed";
  tone: "friendly" | "casual" | "professional" | "playful";
  recommendationStyle: "best" | "few" | "explain";
  usePreferencesInConversations: boolean;
}

export interface ApiUserPreferences {
  coffee: ApiCoffeePreferences;
  aiContext: ApiAIContextPreferences;
  conversationHistoryEnabled: boolean;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface ApiPreferencesUpdate {
  coffee?: Partial<ApiCoffeePreferences>;
  aiContext?: Partial<ApiAIContextPreferences>;
  conversationHistoryEnabled?: boolean;
}

export class ChatApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ChatApiError";
    this.status = status;
  }
}

async function apiFetch(path: string, init: RequestInit, idToken: string) {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${idToken}`,
        ...init.headers,
      },
    });
  } catch {
    throw new ChatApiError("Can't reach the Grounded backend. Is it running?", 0);
  }

  if (!res.ok) {
    let detail = `Backend error (${res.status})`;
    try {
      const data = await res.json();
      if (data && typeof data.detail === "string") {
        detail = data.detail;
      }
    } catch {
      // keep the fallback detail
    }
    throw new ChatApiError(detail, res.status);
  }

  return res;
}

export async function sendChatMessage(opts: {
  messages: ApiChatMessage[];
  conversationId?: string | null;
  idToken: string;
  onActivity?: ChatActivityHandler;
}): Promise<ApiChatResponse> {
  const res = await apiFetch(
    "/api/chat",
    {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        messages: opts.messages,
        conversation_id: opts.conversationId ?? null,
      }),
    },
    opts.idToken
  );

  const contentType = res.headers.get("content-type") || "";
  if (!contentType.includes("text/event-stream")) {
    // A proxy, or an older/misbehaving backend, answered with plain JSON.
    const data = (await res.json()) as ApiChatResponse;
    if (!data.answer) {
      throw new ChatApiError("The assistant returned an empty response.", 502);
    }
    return data;
  }

  return await new Promise((resolve, reject) => {
    let settled = false;

    readEventStream(res, (payload) => {
      if (!payload) return;
      if (settled) return;
      let data: unknown;
      try {
        data = JSON.parse(payload);
      } catch {
        return;
      }
      const obj = data as Record<string, unknown>;
      if (obj.type === "tool" && typeof obj.name === "string") {
        opts.onActivity?.({ type: "tool", name: obj.name });
      } else if (obj.type === "generating") {
        opts.onActivity?.({ type: "generating" });
      } else if (obj.type === "done") {
        const answer = typeof obj.answer === "string" ? obj.answer : "";
        if (!answer) {
          reject(new ChatApiError("The assistant returned an empty response.", 502));
          settled = true;
          return;
        }
        settled = true;
        resolve({
          answer,
          context: (obj.context ?? {}) as ApiChatResponse["context"],
        });
      } else if (obj.type === "error") {
        const message =
          typeof obj.message === "string" && obj.message
            ? obj.message
            : "Something went wrong while preparing the response.";
        settled = true;
        reject(new ChatApiError(message, 502));
      }
    })
      .then(() => {
        if (!settled) {
          settled = true;
          reject(new ChatApiError("The assistant response was cut short.", 502));
        }
      })
      .catch((err: unknown) => {
        if (settled) return;
        settled = true;
        if (err instanceof Error) {
          reject(err);
        } else {
          reject(new ChatApiError("Something went wrong while preparing the response.", 502));
        }
      });
  });
}

async function readEventStream(
  res: Response,
  onData: (payload: string) => void
): Promise<void> {
  const reader = res.body?.getReader();
  if (!reader) {
    throw new ChatApiError("The assistant response could not be read.", 502);
  }
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of block.split("\n")) {
        // Comment lines (`: ping`) are SSE keepalives — ignore them.
        if (line.startsWith("data:")) {
          onData(line.slice(5).trim());
        }
      }
    }
  }
}

export async function getUserPreferences(opts: {
  idToken: string;
}): Promise<ApiUserPreferences> {
  const res = await apiFetch("/api/preferences", { method: "GET" }, opts.idToken);
  return (await res.json()) as ApiUserPreferences;
}

export async function updateUserPreferences(opts: {
  idToken: string;
  updates: ApiPreferencesUpdate;
}): Promise<ApiUserPreferences> {
  const res = await apiFetch(
    "/api/preferences",
    { method: "PATCH", body: JSON.stringify(opts.updates) },
    opts.idToken
  );
  return (await res.json()) as ApiUserPreferences;
}