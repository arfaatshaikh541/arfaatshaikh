import { describe, expect, it } from "vitest";
import { AUDIO_NOT_AVAILABLE, KNOWLEDGE_EMPTY, KNOWLEDGE_TYPES, LISTING_EMPTY, LISTING_TYPES } from "./copy";

describe("empty states", () => {
  it("every pending knowledge domain and every listing type has an honest empty state in both languages", () => {
    for (const id of ["fiqh", "aqeedah", "seerah", "hadith_grading", "terminology", "library_work", "history", "civilization", "scholar"]) {
      expect(KNOWLEDGE_TYPES.some((t) => t.id === id)).toBe(true);
      expect(KNOWLEDGE_EMPTY[id].en).toMatch(/not yet been imported/);
      expect(KNOWLEDGE_EMPTY[id].ar.length).toBeGreaterThan(10);
    }
    for (const t of LISTING_TYPES) {
      expect(LISTING_EMPTY[t.id].en).toMatch(/No (verified|upcoming verified) .* (currently )?available/);
      expect(LISTING_EMPTY[t.id].ar.length).toBeGreaterThan(10);
    }
  });
  it("uses the exact wording required for the main cases", () => {
    expect(KNOWLEDGE_EMPTY.fiqh.en).toBe("Verified Fiqh sources have not yet been imported.");
    expect(LISTING_EMPTY.mosque.en).toBe("No verified mosque data is currently available for this region.");
    expect(AUDIO_NOT_AVAILABLE.en).toBe("Recitation audio is not currently available for redistribution.");
  });
});
