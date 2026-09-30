// Numeric Hijri helpers on top of the platform's ICU Umm al-Qura calendar.
// Approximation: local moon-sighting authorities may differ by a day.

export interface HijriParts { year: number; month: number; day: number }

const fmt = new Intl.DateTimeFormat("en-u-ca-islamic-umalqura-nu-latn", { day: "numeric", month: "numeric", year: "numeric", timeZone: "UTC" });

export function hijriParts(date: Date): HijriParts {
  const parts = fmt.formatToParts(date);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  return { year: get("year"), month: get("month"), day: get("day") };
}

const DAY = 86_400_000;
const HIJRI_EPOCH_UTC = Date.UTC(622, 6, 16);

/** Gregorian date (UTC midnight) of a Hijri date, or null if not found. */
export function gregorianOfHijri(year: number, month: number, day: number): Date | null {
  const estimate = HIJRI_EPOCH_UTC + ((year - 1) * 354.36707 + (month - 1) * 29.530588 + (day - 1)) * DAY;
  const start = Math.floor(estimate / DAY) * DAY;
  for (let offset = 0; offset <= 45; offset++) {
    for (const sign of offset === 0 ? [1] : [1, -1]) {
      const candidate = new Date(start + sign * offset * DAY);
      const h = hijriParts(candidate);
      if (h.year === year && h.month === month && h.day === day) return candidate;
    }
  }
  return null;
}

export const HIJRI_EVENTS = [
  { id: "ramadan", month: 9, day: 1 },
  { id: "eid-fitr", month: 10, day: 1 },
  { id: "arafah", month: 12, day: 9 },
  { id: "eid-adha", month: 12, day: 10 },
] as const;

export type HijriEventId = (typeof HIJRI_EVENTS)[number]["id"];

/** Next occurrence (today or later) of a Hijri event, as a Gregorian UTC date. */
export function nextHijriEvent(id: HijriEventId, from: Date): Date | null {
  const ev = HIJRI_EVENTS.find((e) => e.id === id)!;
  const today = Date.UTC(from.getUTCFullYear(), from.getUTCMonth(), from.getUTCDate());
  const y = hijriParts(from).year;
  for (const year of [y, y + 1]) {
    const d = gregorianOfHijri(year, ev.month, ev.day);
    if (d && d.getTime() >= today) return d;
  }
  return null;
}

export function daysBetween(from: Date, to: Date): number {
  const a = Date.UTC(from.getUTCFullYear(), from.getUTCMonth(), from.getUTCDate());
  const b = Date.UTC(to.getUTCFullYear(), to.getUTCMonth(), to.getUTCDate());
  return Math.round((b - a) / DAY);
}
