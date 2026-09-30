// Mean-lunation moon phase. Accurate to roughly +/-0.5 day for age and a few
// percent for illumination - fine for display, NOT for moon-sighting decisions.

const SYNODIC = 29.530588853;
const REF_NEW_MOON_JD = 2451550.26; // 2000-01-06 18:14 UTC

export function moonAgeDays(date: Date): number {
  const jd = date.getTime() / 86_400_000 + 2440587.5;
  const age = (jd - REF_NEW_MOON_JD) % SYNODIC;
  return age < 0 ? age + SYNODIC : age;
}

export function moonIllumination(date: Date): number {
  return (1 - Math.cos((2 * Math.PI * moonAgeDays(date)) / SYNODIC)) / 2;
}

export type MoonPhase = "new" | "waxing-crescent" | "first-quarter" | "waxing-gibbous" | "full" | "waning-gibbous" | "last-quarter" | "waning-crescent";

export function moonPhase(date: Date): MoonPhase {
  const f = moonAgeDays(date) / SYNODIC;
  const names: MoonPhase[] = ["new", "waxing-crescent", "first-quarter", "waxing-gibbous", "full", "waning-gibbous", "last-quarter", "waning-crescent"];
  return names[Math.floor(((f + 1 / 16) % 1) * 8)];
}

/** Next date at which the mean phase fraction (0 = new, 0.5 = full) occurs. */
export function nextPhaseDate(from: Date, fraction: 0 | 0.5): Date {
  const age = moonAgeDays(from);
  let delta = fraction * SYNODIC - age;
  if (delta <= 0) delta += SYNODIC;
  return new Date(from.getTime() + delta * 86_400_000);
}
