import { describe, it, expect, vi, afterEach } from "vitest";
import { checkBackendHealth } from "@/lib/backend-readiness";

function mockFetch(ok: boolean, shouldReject = false) {
  if (shouldReject) {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network error")));
  } else {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok, status: ok ? 200 : 500 })
    );
  }
}

describe("checkBackendHealth", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns true when health endpoint responds with 200", async () => {
    mockFetch(true);
    const result = await checkBackendHealth();
    expect(result).toBe(true);
  });

  it("returns false when health endpoint responds with non-200", async () => {
    mockFetch(false);
    const result = await checkBackendHealth();
    expect(result).toBe(false);
  });

  it("returns false when fetch throws (network error)", async () => {
    mockFetch(false, true);
    const result = await checkBackendHealth();
    expect(result).toBe(false);
  });

  it("calls the correct health endpoint", async () => {
    mockFetch(true);
    await checkBackendHealth();
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/health"),
      expect.objectContaining({ method: "GET" })
    );
  });
});
