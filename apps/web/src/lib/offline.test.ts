import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it } from "vitest";
import { clearSurahs, enqueue, flushQueue, getSurah, listDownloaded, listQueue, normaliseArabic, queuedCount, saveSurah, searchOffline } from "./offline";

const payload = (texts: string[]) => ({ ayahs: texts.map((arabic_text) => ({ arabic_text })) });

describe("offline Qur'an store", () => {
  beforeEach(async () => { await clearSurahs(); for (const q of await listQueue()) await flushQueue(async () => { void q; }); });

  it("stores and returns a surah exactly as given", async () => {
    await saveSurah(1, payload(["بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"]));
    const stored = await getSurah(1);
    expect(stored?.ayahCount).toBe(1);
    expect((stored?.payload as { ayahs: { arabic_text: string }[] }).ayahs[0].arabic_text).toBe("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ");
    expect((await listDownloaded()).map((r) => r.surah)).toEqual([1]);
  });

  it("searches downloaded text ignoring diacritics and alef variants, with no network", async () => {
    await saveSurah(1, payload(["ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَـٰلَمِينَ", "ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"]));
    const hits = await searchOffline("الرحيم");
    expect(hits).toEqual([{ surah: 1, ayahIndex: 1, text: "ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ" }]);
    expect(await searchOffline("x")).toEqual([]);
  });

  it("normalises Arabic consistently", () => {
    expect(normaliseArabic("ٱللَّهِ")).toBe(normaliseArabic("اللَّه"));
  });
});

describe("offline write queue", () => {
  beforeEach(async () => { await flushQueue(async () => undefined); });

  it("keeps only the newest write per key (reading position: last write wins)", async () => {
    await enqueue({ path: "/quran/me/progress", method: "PUT", body: { ayah_id: "a" }, key: "progress" });
    await enqueue({ path: "/quran/me/progress", method: "PUT", body: { ayah_id: "b" }, key: "progress" });
    const queue = await listQueue();
    expect(queue).toHaveLength(1);
    expect(queue[0].body).toEqual({ ayah_id: "b" });
  });

  it("replays in order, drops rejected writes as conflicts, and stops on a network failure", async () => {
    await enqueue({ path: "/one", method: "POST", body: 1, key: "k1" });
    await enqueue({ path: "/two", method: "POST", body: 2, key: "k2" });
    await enqueue({ path: "/three", method: "POST", body: 3, key: "k3" });
    const seen: string[] = [];
    const result = await flushQueue(async (path) => {
      seen.push(path);
      if (path === "/two") throw Object.assign(new Error("conflict"), { status: 409 });
      if (path === "/three") throw new TypeError("network");
    });
    expect(seen).toEqual(["/one", "/two", "/three"]);
    expect(result).toEqual({ sent: 1, dropped: 1, remaining: 1 });
    expect(await queuedCount()).toBe(1);
  });
});
