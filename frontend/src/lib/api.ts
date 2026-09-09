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

export class ChatApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ChatApiError";
    this.status = status;
  }
}

export async function sendChatMessage(opts: {
  messages: ApiChatMessage[];
  conversationId?: string | null;
  idToken: string;
}): Promise<ApiChatResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${opts.idToken}`,
      },
      body: JSON.stringify({
        messages: opts.messages,
        conversation_id: opts.conversationId ?? null,
      }),
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

  const data = (await res.json()) as ApiChatResponse;
  if (!data.answer) {
    throw new ChatApiError("The assistant returned an empty response.", 502);
  }
  return data;
}