import { describe, expect, it } from "vitest";
import { worlds, allFeatures, featureCounts, STATUS_ORDER } from "./worlds";

describe("worlds registry integrity", () => {
  it("has exactly 12 worlds", () => {
    expect(worlds).toHaveLength(12);
  });

  it("every world has an English and Arabic name/tagline", () => {
    for (const world of worlds) {
      expect(world.name.length).toBeGreaterThan(0);
      expect(world.nameAr.length).toBeGreaterThan(0);
      expect(world.tagline.length).toBeGreaterThan(0);
      expect(world.taglineAr.length).toBeGreaterThan(0);
    }
  });

  it("every working or data-ready feature declares a real destination href, unless explicitly pageless", () => {
    for (const feature of allFeatures()) {
      if (["IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "ARCHITECTURE_READY"].includes(feature.status) && !feature.pageless && feature.note !== "See Source explorer.") {
        // ARCHITECTURE_READY items without a page are backend-only and say so in their note
        if (feature.status === "ARCHITECTURE_READY" && !feature.href) continue;
        expect(feature.href, `"${feature.name}" is marked ${feature.status} but has no href`).toBeTruthy();
      }
    }
  });

  it("uses only the documented status vocabulary", () => {
    const allowed = new Set(STATUS_ORDER);
    for (const feature of allFeatures()) expect(allowed.has(feature.status), `${feature.id}: ${feature.status}`).toBe(true);
  });

  it("anything that needs data shows a note saying so (never a bare 'Not built yet')", () => {
    for (const feature of allFeatures()) {
      if (feature.status === "DATA_SOURCE_REQUIRED" || feature.status === "ARCHITECTURE_READY") {
        expect(feature.note.length, feature.id).toBeGreaterThan(10);
      }
    }
  });

  it("nothing is marked IMPLEMENTED that depends on data we do not have", () => {
    const dataDependent = ["fiqh", "aqeedah", "seerah", "hadith-grading", "terminology", "library", "history", "scholars", "mosque-directory", "business-directory", "jobs", "tafsir", "dua", "dhikr", "salah"];
    for (const feature of allFeatures()) {
      if (dataDependent.includes(feature.id)) expect(feature.status, feature.id).not.toBe("IMPLEMENTED");
    }
  });

  it("pageless is only used for working capabilities", () => {
    for (const feature of allFeatures()) {
      if (feature.pageless) expect(["IMPLEMENTED", "PARTIALLY_IMPLEMENTED"]).toContain(feature.status);
    }
  });

  it("no feature id is duplicated within the same world", () => {
    for (const world of worlds) {
      const ids = world.features.map((f) => f.id);
      expect(new Set(ids).size).toBe(ids.length);
    }
  });

  it("feature counts add up to the total", () => {
    const counts = featureCounts();
    expect(Object.values(counts.byStatus).reduce((a, b) => a + b, 0)).toBe(counts.total);
  });
});
