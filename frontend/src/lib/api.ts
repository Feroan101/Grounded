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
}): Promise<ApiChatResponse> {
  const res = await apiFetch(
    "/api/chat",
    {
      method: "POST",
      body: JSON.stringify({
        messages: opts.messages,
        conversation_id: opts.conversationId ?? null,
      }),
    },
    opts.idToken
  );

  const data = (await res.json()) as ApiChatResponse;
  if (!data.answer) {
    throw new ChatApiError("The assistant returned an empty response.", 502);
  }
  return data;
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