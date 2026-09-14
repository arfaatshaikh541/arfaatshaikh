import { describe, expect, it } from "vitest";
import { computeSalahTimes, qiblaBearing, hijriDate } from "./salah";

describe("qiblaBearing", () => {
  it("matches the commonly published New York bearing (~58.5 degrees) within one degree", () => {
    const bearing = qiblaBearing(40.7128, -74.006);
    expect(bearing).toBeGreaterThan(57.5);
    expect(bearing).toBeLessThan(59.5);
  });

  it("matches the commonly published London bearing (~118.9 degrees) within one degree", () => {
    const bearing = qiblaBearing(51.5074, -0.1278);
    expect(bearing).toBeGreaterThan(117.9);
    expect(bearing).toBeLessThan(119.9);
  });

  it("always returns a value in [0, 360)", () => {
    const bearing = qiblaBearing(-33.8688, 151.2093); // Sydney
    expect(bearing).toBeGreaterThanOrEqual(0);
    expect(bearing).toBeLessThan(360);
  });
});

describe("computeSalahTimes", () => {
  it("orders the five daily prayers correctly for a mid-latitude city on an equinox-ish date", () => {
    const date = new Date(Date.UTC(2026, 2, 20)); // near the March equinox, avoids polar-day edge cases
    const times = computeSalahTimes(date, 51.5074, -0.1278); // London
    expect(times.fajr.getTime()).toBeLessThan(times.sunrise.getTime());
    expect(times.sunrise.getTime()).toBeLessThan(times.dhuhr.getTime());
    expect(times.dhuhr.getTime()).toBeLessThan(times.asr.getTime());
    expect(times.asr.getTime()).toBeLessThan(times.maghrib.getTime());
    expect(times.maghrib.getTime()).toBeLessThan(times.isha.getTime());
  });

  it("places solar noon (dhuhr) close to the middle of the visible day", () => {
    const date = new Date(Date.UTC(2026, 2, 20));
    const times = computeSalahTimes(date, 21.4225, 39.8262); // Mecca
    const midpoint = (times.sunrise.getTime() + times.maghrib.getTime()) / 2;
    expect(Math.abs(times.dhuhr.getTime() - midpoint)).toBeLessThan(5 * 60_000); // within 5 minutes
  });
});

describe("hijriDate", () => {
  it("formats a real Gregorian date as a non-empty Islamic-calendar string", () => {
    const label = hijriDate(new Date(Date.UTC(2026, 0, 1)), "en");
    expect(label.length).toBeGreaterThan(0);
    expect(label).toMatch(/AH|هـ|\d{4}/); // some era marker or a plausible Hijri year
  });
});
