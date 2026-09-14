// Real astronomical calculations - no fabricated or looked-up data.
//
// Prayer times use the standard sun-altitude hour-angle method described in
// Jean Meeus, "Astronomical Algorithms" (the same public-domain formulas
// every prayer-time calculator implements independently). Qiblah uses the
// standard great-circle initial-bearing formula to the Kaaba's published
// coordinates. Accuracy is typically within a minute or two of official
// local timetables, which is the normal tolerance for this method - it is
// not a substitute for a local mosque's published schedule.

const KAABA_LAT = 21.4225;
const KAABA_LON = 39.8262;

const sinD = (deg: number) => Math.sin((deg * Math.PI) / 180);
const cosD = (deg: number) => Math.cos((deg * Math.PI) / 180);
const tanD = (deg: number) => Math.tan((deg * Math.PI) / 180);
const asinD = (x: number) => (Math.asin(x) * 180) / Math.PI;
const acosD = (x: number) => (Math.acos(Math.max(-1, Math.min(1, x))) * 180) / Math.PI;
const atan2D = (y: number, x: number) => (Math.atan2(y, x) * 180) / Math.PI;
const acotD = (x: number) => (Math.atan(1 / x) * 180) / Math.PI;
const fixAngle = (a: number) => ((a % 360) + 360) % 360;
const fixHour = (h: number) => ((h % 24) + 24) % 24;

export function julianDay(year: number, month: number, day: number): number {
  let y = year;
  let m = month;
  if (m <= 2) { y -= 1; m += 12; }
  const A = Math.floor(y / 100);
  const B = 2 - A + Math.floor(A / 4);
  return Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + day + B - 1524.5;
}

function sunPosition(jd: number): { declination: number; equationOfTimeHours: number } {
  const D = jd - 2451545.0;
  const g = fixAngle(357.529 + 0.98560028 * D);
  const q = fixAngle(280.459 + 0.98564736 * D);
  const L = fixAngle(q + 1.915 * sinD(g) + 0.02 * sinD(2 * g));
  const e = 23.439 - 0.00000036 * D;
  const RA = atan2D(cosD(e) * sinD(L), cosD(L)) / 15;
  const equationOfTimeHours = q / 15 - fixHour(RA);
  const declination = asinD(sinD(e) * sinD(L));
  return { declination, equationOfTimeHours };
}

function hourAngle(altitudeDeg: number, latitude: number, declination: number): number {
  const val = (sinD(altitudeDeg) - sinD(latitude) * sinD(declination)) / (cosD(latitude) * cosD(declination));
  return acosD(val) / 15;
}

export interface SalahConvention {
  id: string;
  label: string;
  fajrAngle: number;
  ishaAngle: number;
}

// Fixed, disclosed convention. A single default keeps this tool honest about
// what it computes rather than offering a menu of conventions with no way to
// verify which one matches a given local authority.
export const DEFAULT_CONVENTION: SalahConvention = {
  id: "mwl",
  label: "Muslim World League (Fajr 18°, Isha 17°)",
  fajrAngle: 18,
  ishaAngle: 17,
};

const ASR_SHADOW_FACTOR = 1; // standard (Shafi'i/Maliki/Hanbali) shadow-length convention

export interface SalahTimes {
  fajr: Date;
  sunrise: Date;
  dhuhr: Date;
  asr: Date;
  maghrib: Date;
  isha: Date;
}

export function computeSalahTimes(
  date: Date,
  latitude: number,
  longitude: number,
  convention: SalahConvention = DEFAULT_CONVENTION,
): SalahTimes {
  const jd = julianDay(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
  const { declination, equationOfTimeHours } = sunPosition(jd);
  const solarNoonUtc = 12 - longitude / 15 - equationOfTimeHours;

  const asrAltitude = acotD(ASR_SHADOW_FACTOR + tanD(Math.abs(latitude - declination)));

  const toDate = (utcHours: number) => {
    const base = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
    return new Date(base + fixHour(utcHours) * 3600_000);
  };

  return {
    fajr: toDate(solarNoonUtc - hourAngle(-convention.fajrAngle, latitude, declination)),
    sunrise: toDate(solarNoonUtc - hourAngle(-0.833, latitude, declination)),
    dhuhr: toDate(solarNoonUtc),
    asr: toDate(solarNoonUtc + hourAngle(asrAltitude, latitude, declination)),
    maghrib: toDate(solarNoonUtc + hourAngle(-0.833, latitude, declination)),
    isha: toDate(solarNoonUtc + hourAngle(-convention.ishaAngle, latitude, declination)),
  };
}

/** Great-circle initial bearing from (lat, lon) to the Kaaba, in degrees from true north. */
export function qiblaBearing(latitude: number, longitude: number): number {
  const dLon = KAABA_LON - longitude;
  const y = sinD(dLon) * cosD(KAABA_LAT);
  const x = cosD(latitude) * sinD(KAABA_LAT) - sinD(latitude) * cosD(KAABA_LAT) * cosD(dLon);
  return fixAngle(atan2D(y, x));
}

/** Hijri date via the platform's ICU Islamic (Umm al-Qura) calendar - an approximation; local moon-sighting authorities may differ by a day. */
export function hijriDate(date: Date, locale: "en" | "ar"): string {
  const formatter = new Intl.DateTimeFormat(`${locale}-u-ca-islamic-umalqura`, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  return formatter.format(date);
}
