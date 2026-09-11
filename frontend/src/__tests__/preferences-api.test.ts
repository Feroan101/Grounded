import { describe, it, expect, vi, afterEach } from "vitest";
import {
  getUserPreferences,
  updateUserPreferences,
  ApiUserPreferences,
} from "@/lib/api";

function mockFetch(response: Partial<Response>) {
  const res = {
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue({}),
    ...response,
  } as unknown as Response;
  const fetchMock = vi.fn().mockResolvedValue(res);
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, res };
}

const prefs: ApiUserPreferences = {
  coffee: {
    favoriteDrink: "Latte",
    temperature: "hot",
    milkPreference: "oat",
    sweetness: "less",
    strength: "",
    caffeinePreference: "",
    roastPreference: "",
    brewMethod: "",
    dietaryPreference: [],
    allergiesOrIntolerances: "",
  },
  aiContext: {
    customContext: "",
    responseStyle: "balanced",
    tone: "friendly",
    recommendationStyle: "best",
    usePreferencesInConversations: true,
  },
  conversationHistoryEnabled: true,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getUserPreferences", () => {
  it("GETs /api/preferences with the Firebase bearer token", async () => {
    const { fetchMock } = mockFetch({ json: vi.fn().mockResolvedValue(prefs) });

    const result = await getUserPreferences({ idToken: "tok-1" });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/preferences"),
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ Authorization: "Bearer tok-1" }),
      })
    );
    expect(result.coffee.favoriteDrink).toBe("Latte");
    expect(result.aiContext.responseStyle).toBe("balanced");
  });

  it("surfaces backend errors as ChatApiError", async () => {
    mockFetch({
      ok: false,
      status: 401,
      json: vi.fn().mockResolvedValue({ detail: "Invalid or expired token" }),
    });

    await expect(getUserPreferences({ idToken: "bad" })).rejects.toMatchObject({
      name: "ChatApiError",
      status: 401,
      message: "Invalid or expired token",
    });
  });

  it("surfaces network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    await expect(getUserPreferences({ idToken: "t" })).rejects.toMatchObject({
      name: "ChatApiError",
      status: 0,
    });
  });
});

describe("updateUserPreferences", () => {
  it("PATCHes partial preferences and returns the server state", async () => {
    const { fetchMock } = mockFetch({
      json: vi.fn().mockResolvedValue({ ...prefs, coffee: { ...prefs.coffee, temperature: "iced" } }),
    });

    const result = await updateUserPreferences({
      idToken: "tok-2",
      updates: { coffee: { temperature: "iced" } },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/preferences"),
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ coffee: { temperature: "iced" } }),
        headers: expect.objectContaining({ Authorization: "Bearer tok-2" }),
      })
    );
    expect(result.coffee.temperature).toBe("iced");
    expect(result.coffee.favoriteDrink).toBe("Latte");
  });

  it("can persist data controls like conversation history", async () => {
    mockFetch({
      json: vi.fn().mockResolvedValue({ ...prefs, conversationHistoryEnabled: false }),
    });

    const result = await updateUserPreferences({
      idToken: "tok-3",
      updates: { conversationHistoryEnabled: false },
    });

    expect(result.conversationHistoryEnabled).toBe(false);
  });
});