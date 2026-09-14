import { describe, expect, it } from "vitest";
import { search } from "./command-palette";

describe("command palette search", () => {
  it("returns nothing for an empty query", () => {
    expect(search("")).toHaveLength(0);
    expect(search("   ")).toHaveLength(0);
  });

  it("finds a feature by its exact name, case-insensitively", () => {
    const hits = search("qibl");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits.some((h) => h.feature.name.toLowerCase().includes("qibl"))).toBe(true);
  });

  it("finds \"Qur'an\" when the user types the plain-ASCII \"quran\" (no apostrophe)", () => {
    const hits = search("quran");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits.some((h) => h.feature.name === "Qur'an")).toBe(true);
  });

  it("finds features by their world name", () => {
    const hits = search("ibadah");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits.every((h) => h.world.slug === "ibadah")).toBe(true);
  });

  it("never returns more than 20 results", () => {
    const hits = search("a"); // deliberately broad
    expect(hits.length).toBeLessThanOrEqual(20);
  });
});
