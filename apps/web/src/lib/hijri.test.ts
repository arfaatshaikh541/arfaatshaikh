import { describe, expect, it } from "vitest";
import { daysBetween, gregorianOfHijri, hijriParts, nextHijriEvent } from "./hijri";
import { moonAgeDays, moonIllumination, moonPhase, nextPhaseDate } from "./moon";

describe("hijri", () => {
  it("round-trips a Hijri date through the Gregorian calendar", () => {
    const g = gregorianOfHijri(1446, 9, 1)!;
    expect(hijriParts(g)).toEqual({ year: 1446, month: 9, day: 1 });
  });
  it("puts 1 Ramadan 1446 (Umm al-Qura) on 1 March 2025", () => {
    const g = gregorianOfHijri(1446, 9, 1)!;
    expect(g.toISOString().slice(0, 10)).toBe("2025-03-01");
  });
  it("finds the next Eid al-Adha on or after a date", () => {
    const d = nextHijriEvent("eid-adha", new Date(Date.UTC(2025, 0, 1)))!;
    expect(d.toISOString().slice(0, 10)).toBe("2025-06-06");
  });
  it("counts days between dates", () => {
    expect(daysBetween(new Date(Date.UTC(2025, 0, 1)), new Date(Date.UTC(2025, 0, 11)))).toBe(10);
  });
});

describe("moon", () => {
  it("is near new at the reference new moon", () => {
    const age = moonAgeDays(new Date("2000-01-06T18:14:00Z"));
    expect(Math.min(age, 29.53 - age)).toBeLessThan(0.1);
  });
  it("is about full on 2024-01-25 (true full moon 17:54 UTC)", () => {
    const d = new Date("2024-01-25T17:54:00Z");
    expect(moonPhase(d)).toBe("full");
    expect(moonIllumination(d)).toBeGreaterThan(0.97);
  });
  it("finds a new moon within half a day of the true 2024-01-11 11:57 UTC", () => {
    const d = nextPhaseDate(new Date("2024-01-05T00:00:00Z"), 0);
    expect(Math.abs(d.getTime() - Date.parse("2024-01-11T11:57:00Z")) / 86_400_000).toBeLessThan(0.75);
  });
});
