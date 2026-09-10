import { describe, it, expect } from "vitest";
import { COFFEE_FACTS, getRandomFact } from "@/lib/coffee-facts";

describe("coffee facts", () => {
  it("has a reasonable number of facts", () => {
    expect(COFFEE_FACTS.length).toBeGreaterThanOrEqual(20);
  });

  it("each fact has a title and fact string", () => {
    for (const item of COFFEE_FACTS) {
      expect(typeof item.title).toBe("string");
      expect(item.title.length).toBeGreaterThan(0);
      expect(typeof item.fact).toBe("string");
      expect(item.fact.length).toBeGreaterThan(0);
    }
  });

  it("getRandomFact returns a fact with an index", () => {
    const result = getRandomFact();
    expect(result).toHaveProperty("title");
    expect(result).toHaveProperty("fact");
    expect(result).toHaveProperty("index");
    expect(result.index).toBeGreaterThanOrEqual(0);
    expect(result.index).toBeLessThan(COFFEE_FACTS.length);
  });

  it("getRandomFact excludes the specified index", () => {
    const excludeIndex = 0;
    const results = new Set<number>();
    for (let i = 0; i < 50; i++) {
      results.add(getRandomFact(excludeIndex).index);
    }
    expect(results.has(excludeIndex)).toBe(false);
  });
});
