import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { AUDIO_NOT_AVAILABLE, AUTHORITY_LABEL, COVERAGE_LABEL, DOMAIN_STATUS_LABEL, KNOWLEDGE_EMPTY, KNOWLEDGE_TYPES, LISTING_EMPTY, LISTING_TYPES } from "./copy";

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

describe("readiness vocabulary", () => {
  const registry = JSON.parse(readFileSync(resolve(process.cwd(), "../../data/domain-readiness.json"), "utf8"));
  it("has a label (English and Arabic) for every status and coverage value the registry can use", () => {
    for (const status of registry.statuses) {
      expect(DOMAIN_STATUS_LABEL[status].en.length).toBeGreaterThan(2);
      expect(DOMAIN_STATUS_LABEL[status].ar.length).toBeGreaterThan(2);
    }
    for (const coverage of registry.coverage_values) expect(COVERAGE_LABEL[coverage].en).toBeTruthy();
  });
  it("never labels anything but READY as ready", () => {
    for (const [status, label] of Object.entries(DOMAIN_STATUS_LABEL)) if (status !== "READY") expect(label.en.toLowerCase()).not.toBe("ready");
  });
  it("labels every authority class the assistant can return", () => {
    for (const cls of ["primary_source", "secondary_source", "community_dataset", "unverified", "disputed", "inferred", "unavailable"]) expect(AUTHORITY_LABEL[cls].en).toBeTruthy();
  });
});
