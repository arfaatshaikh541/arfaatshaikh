// Offline storage for content that may lawfully be kept on the device, plus a write queue for actions taken offline.
//
// What is stored: the Arabic Qur'an text (CC BY 4.0) exactly as the API returns it for a surah *without* any
// translation, so no translation whose rights are unconfirmed is ever copied to a device. Nothing else
// from the library is stored here. User actions (bookmarks, reading position) made while offline are queued and
// replayed when the connection returns; for the reading position only the newest entry is kept (last write wins).

const DB_NAME = "woi-offline";
const DB_VERSION = 1;
export const SURAH_COUNT = 114;

export type StoredSurah = { surah: number; savedAt: number; payload: unknown; ayahCount: number; text: string };
export type QueuedWrite = { id?: number; path: string; method: "POST" | "PUT" | "DELETE"; body: unknown; key: string; queuedAt: number };

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("surahs")) db.createObjectStore("surahs", { keyPath: "surah" });
      if (!db.objectStoreNames.contains("outbox")) db.createObjectStore("outbox", { keyPath: "id", autoIncrement: true });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function run<T>(store: "surahs" | "outbox", mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return open().then((db) => new Promise<T>((resolve, reject) => {
    const tx = db.transaction(store, mode);
    const req = fn(tx.objectStore(store));
    tx.oncomplete = () => { db.close(); resolve(req.result); };
    tx.onerror = () => { db.close(); reject(tx.error); };
    tx.onabort = () => { db.close(); reject(tx.error); };
  }));
}

export function isOfflineStorageAvailable(): boolean {
  return typeof indexedDB !== "undefined";
}

/** Normalise Arabic for searching: drop diacritics, tatweel and alef variants. */
export function normaliseArabic(text: string): string {
  return text.normalize("NFKD").replace(/[ؐ-ًؚ-ٰٟۖ-ۭـ]/g, "").replace(/[إأآٱ]/g, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه").toLowerCase().trim();
}

export async function saveSurah(surah: number, payload: { ayahs?: { arabic_text: string }[] }): Promise<void> {
  const ayahs = payload.ayahs ?? [];
  const text = ayahs.map((a) => normaliseArabic(a.arabic_text)).join("\n");
  const record: StoredSurah = { surah, savedAt: Date.now(), payload, ayahCount: ayahs.length, text };
  await run("surahs", "readwrite", (s) => s.put(record));
}
export const getSurah = (surah: number) => run<StoredSurah | undefined>("surahs", "readonly", (s) => s.get(surah));
export const listDownloaded = () => run<StoredSurah[]>("surahs", "readonly", (s) => s.getAll());
export const clearSurahs = () => run("surahs", "readwrite", (s) => s.clear());

/** Search the downloaded text only (works with no connection). Returns surah numbers and matching ayah indexes. */
export async function searchOffline(query: string, limit = 50): Promise<{ surah: number; ayahIndex: number; text: string }[]> {
  const needle = normaliseArabic(query);
  if (needle.length < 2) return [];
  const hits: { surah: number; ayahIndex: number; text: string }[] = [];
  for (const record of (await listDownloaded()).sort((a, b) => a.surah - b.surah)) {
    const ayahs = (record.payload as { ayahs?: { arabic_text: string }[] }).ayahs ?? [];
    record.text.split("\n").forEach((line, index) => {
      if (hits.length < limit && line.includes(needle)) hits.push({ surah: record.surah, ayahIndex: index, text: ayahs[index]?.arabic_text ?? line });
    });
  }
  return hits;
}

export async function estimateBytes(): Promise<number> {
  return (await listDownloaded()).reduce((sum, r) => sum + JSON.stringify(r.payload).length, 0);
}

// ---------------------------------------------------------------- write queue
export const queuedCount = () => run<number>("outbox", "readonly", (s) => s.count());
export const listQueue = () => run<QueuedWrite[]>("outbox", "readonly", (s) => s.getAll());

/** Queue a write. A write with the same key replaces any earlier queued write (newest wins). */
export async function enqueue(write: Omit<QueuedWrite, "id" | "queuedAt">): Promise<void> {
  const existing = await listQueue();
  for (const item of existing.filter((x) => x.key === write.key)) await run("outbox", "readwrite", (s) => s.delete(item.id as number));
  await run("outbox", "readwrite", (s) => s.add({ ...write, queuedAt: Date.now() }));
}

export type Sender = (path: string, init: { method: string; body: string }) => Promise<unknown>;

/** Replay queued writes oldest first. A write the server rejects (4xx) is dropped as a conflict; a network failure stops the run. */
export async function flushQueue(send: Sender): Promise<{ sent: number; dropped: number; remaining: number }> {
  let sent = 0;
  let dropped = 0;
  for (const item of (await listQueue()).sort((a, b) => a.queuedAt - b.queuedAt)) {
    try {
      await send(item.path, { method: item.method, body: JSON.stringify(item.body) });
      sent += 1;
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status && status >= 400 && status < 500 && status !== 429) dropped += 1; // conflict or no longer valid: do not retry forever
      else break;                                                                  // offline / server error: keep it and stop
    }
    await run("outbox", "readwrite", (s) => s.delete(item.id as number));
  }
  return { sent, dropped, remaining: await queuedCount() };
}
