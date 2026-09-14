import { describe, expect, it } from "vitest";
import { worlds, allFeatures, featureCounts } from "./worlds";

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

  it("every 'available' feature declares a real destination href, unless explicitly pageless", () => {
    for (const feature of allFeatures()) {
      if (feature.status === "available" && !feature.pageless) {
        expect(feature.href, `"${feature.name}" is marked available but has no href`).toBeTruthy();
      }
    }
  });

  it("pageless is only ever used for genuinely available features", () => {
    for (const feature of allFeatures()) {
      if (feature.pageless) {
        expect(feature.status).toBe("available");
      }
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
    expect(counts.available + counts.backendOnly + counts.planned).toBe(counts.total);
  });
});
