"use client";
import { useEffect, useState } from "react";
import { computeSalahTimes, qiblaBearing, hijriDate, DEFAULT_CONVENTION } from "@/lib/salah";

type Coords = { latitude: number; longitude: number };

function formatTime(date: Date, locale: string) {
  return date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
}

export function IbadahTools({ locale }: { locale: "en" | "ar" }) {
  const ar = locale === "ar";
  const [coords, setCoords] = useState<Coords | null>(null);
  const [manualLat, setManualLat] = useState("");
  const [manualLon, setManualLon] = useState("");
  const [locationError, setLocationError] = useState("");
  const [count, setCount] = useState(0);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("woi-dhikr-count");
      if (saved) setCount(Number(saved) || 0);
    } catch {
      // localStorage unavailable (private browsing, etc.) - counter still works for this session.
    }
    if (!("geolocation" in navigator)) {
      setLocationError(ar ? "الموقع الجغرافي غير متاح في هذا المتصفح." : "Geolocation is not available in this browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      () => setLocationError(ar ? "تعذّر الوصول إلى الموقع. أدخل الإحداثيات يدوياً." : "Could not access your location. Enter coordinates manually."),
    );
  }, [ar]);

  function increment() {
    setCount((c) => {
      const next = c + 1;
      try { window.localStorage.setItem("woi-dhikr-count", String(next)); } catch { /* best-effort only */ }
      return next;
    });
  }
  function reset() {
    setCount(0);
    try { window.localStorage.setItem("woi-dhikr-count", "0"); } catch { /* best-effort only */ }
  }

  function useManualCoords() {
    const lat = Number(manualLat);
    const lon = Number(manualLon);
    if (Number.isFinite(lat) && Number.isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
      setLocationError("");
      setCoords({ latitude: lat, longitude: lon });
    }
  }

  const today = new Date();
  const times = coords ? computeSalahTimes(today, coords.latitude, coords.longitude) : null;
  const bearing = coords ? qiblaBearing(coords.latitude, coords.longitude) : null;

  return (
    <div className="ibadah-tools">
      <section className="tool-card" aria-labelledby="hijri-heading">
        <h2 id="hijri-heading">{ar ? "التاريخ الهجري" : "Hijri date"}</h2>
        <p className="tool-value">{hijriDate(today, locale)}</p>
        <p className="tool-note">
          {ar
            ? "تقويم تقريبي (أم القرى). قد تختلف الجهات المحلية لرؤية الهلال بيوم واحد."
            : "An approximation (Umm al-Qura calendar). Local moon-sighting authorities may differ by a day."}
        </p>
      </section>

      <section className="tool-card" aria-labelledby="location-heading">
        <h2 id="location-heading">{ar ? "الموقع" : "Location"}</h2>
        {coords ? (
          <p className="tool-value">{coords.latitude.toFixed(4)}, {coords.longitude.toFixed(4)}</p>
        ) : (
          <div className="manual-coords">
            {locationError && <p role="status">{locationError}</p>}
            <label>{ar ? "خط العرض" : "Latitude"}<input inputMode="decimal" value={manualLat} onChange={(e) => setManualLat(e.target.value)} placeholder="21.4225" /></label>
            <label>{ar ? "خط الطول" : "Longitude"}<input inputMode="decimal" value={manualLon} onChange={(e) => setManualLon(e.target.value)} placeholder="39.8262" /></label>
            <button type="button" onClick={useManualCoords}>{ar ? "استخدام هذه الإحداثيات" : "Use these coordinates"}</button>
            <p className="tool-note">
              {ar
                ? "ملاحظة: تُعرض الأوقات بتوقيت جهازك. إذا أدخلت إحداثيات مكان في منطقة زمنية مختلفة عن جهازك، فستكون الأوقات المعروضة غير صحيحة له."
                : "Note: times are shown in your device's own timezone. If you enter coordinates for a place in a different timezone than your device, the displayed times will be wrong for that place."}
            </p>
          </div>
        )}
      </section>

      <section className="tool-card" aria-labelledby="qiblah-heading">
        <h2 id="qiblah-heading">{ar ? "اتجاه القبلة" : "Qiblah direction"}</h2>
        {bearing !== null ? (
          <>
            <div className="qiblah-compass" style={{ "--bearing": `${bearing}deg` } as React.CSSProperties} role="img" aria-label={ar ? `${bearing.toFixed(1)} درجة من الشمال الحقيقي` : `${bearing.toFixed(1)} degrees from true north`}>
              <span className="qiblah-needle" />
            </div>
            <p className="tool-value">{bearing.toFixed(1)}° {ar ? "من الشمال الحقيقي" : "from true north"}</p>
            <p className="tool-note">{ar ? "بحساب المسافة الدائرية الكبرى إلى الكعبة." : "Computed as the great-circle bearing to the Kaaba."}</p>
          </>
        ) : (
          <p className="tool-note">{ar ? "أدخل موقعك لحساب اتجاه القبلة." : "Provide your location to compute the Qiblah direction."}</p>
        )}
      </section>

      <section className="tool-card tool-card-wide" aria-labelledby="salah-heading">
        <h2 id="salah-heading">{ar ? "أوقات الصلاة" : "Salah times"}</h2>
        {times ? (
          <>
            <dl className="salah-times">
              <div><dt>{ar ? "الفجر" : "Fajr"}</dt><dd>{formatTime(times.fajr, locale)}</dd></div>
              <div><dt>{ar ? "الشروق" : "Sunrise"}</dt><dd>{formatTime(times.sunrise, locale)}</dd></div>
              <div><dt>{ar ? "الظهر" : "Dhuhr"}</dt><dd>{formatTime(times.dhuhr, locale)}</dd></div>
              <div><dt>{ar ? "العصر" : "Asr"}</dt><dd>{formatTime(times.asr, locale)}</dd></div>
              <div><dt>{ar ? "المغرب" : "Maghrib"}</dt><dd>{formatTime(times.maghrib, locale)}</dd></div>
              <div><dt>{ar ? "العشاء" : "Isha"}</dt><dd>{formatTime(times.isha, locale)}</dd></div>
            </dl>
            <p className="tool-note">
              {ar ? `الطريقة: ${DEFAULT_CONVENTION.label}. الأوقات تقريبية بدقة دقيقة أو دقيقتين، وليست بديلاً عن الجدول المعتمد من مسجدك المحلي.` : `Convention: ${DEFAULT_CONVENTION.label}. Accurate to within a minute or two - not a substitute for your local mosque's published schedule.`}
            </p>
          </>
        ) : (
          <p className="tool-note">{ar ? "أدخل موقعك لحساب أوقات الصلاة." : "Provide your location to compute Salah times."}</p>
        )}
      </section>

      <section className="tool-card" aria-labelledby="dhikr-heading">
        <h2 id="dhikr-heading">{ar ? "عداد الذكر" : "Dhikr counter"}</h2>
        <p className="dhikr-count" aria-live="polite">{count}</p>
        <div className="dhikr-actions">
          <button type="button" onClick={increment}>{ar ? "عدّ" : "Count"}</button>
          <button type="button" className="button-quiet" onClick={reset}>{ar ? "إعادة تعيين" : "Reset"}</button>
        </div>
        <p className="tool-note">{ar ? "يُحفظ على جهازك فقط - لا يُرسل إلى أي خادم." : "Stored only on your device - never sent to a server."}</p>
      </section>
    </div>
  );
}
