import { describe, it, expect } from "vitest";
import {
  friendlyActivity,
  ACTIVITY_FALLBACK,
  ACTIVITY_STARTING,
} from "@/lib/activity-labels";

describe("friendlyActivity", () => {
  it("maps the real backend menu tool", () => {
    expect(friendlyActivity({ type: "tool", name: "search_menu" })).toBe(
      "Fetching the menu..."
    );
  });

  it("maps the currency conversion tool", () => {
    expect(friendlyActivity({ type: "tool", name: "convert_currency" })).toBe(
      "Converting the price..."
    );
  });

  it("maps the customer preference tools", () => {
    expect(
      friendlyActivity({ type: "tool", name: "get_customer_preferences" })
    ).toBe("Checking your preferences...");
    expect(friendlyActivity({ type: "tool", name: "save_preference" })).toBe(
      "Remembering that preference..."
    );
  });

  it("maps the conversation and order history tools", () => {
    expect(
      friendlyActivity({ type: "tool", name: "get_conversation_history" })
    ).toBe("Looking back at our conversation...");
    expect(friendlyActivity({ type: "tool", name: "get_order_history" })).toBe(
      "Looking through your previous orders..."
    );
  });

  it("uses the final-answer label for the generating event", () => {
    expect(friendlyActivity({ type: "generating" })).toBe(ACTIVITY_STARTING);
  });

  it("falls back to a safe generic label for unknown tools", () => {
    expect(friendlyActivity({ type: "tool", name: "mystery_tool" })).toBe(
      ACTIVITY_FALLBACK
    );
    expect(ACTIVITY_FALLBACK).toBe("Working on your request...");
  });
});