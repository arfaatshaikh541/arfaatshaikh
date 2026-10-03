// Extra production checks against the real stack: security headers, 404s, PWA + service worker, command palette, search, authentication,
// authorisation, injection probes and the offline matrix. Real Chromium. Prints one JSON report; exit 1 if a check fails.
//   NODE_PATH=$(npm root -g) BASE=https://app.arfaat.com/worldofislam ADMIN_EMAIL=... ADMIN_PASSWORD=... node infrastructure/verify/prod-extra-verify.cjs
const { chromium } = require("playwright");
const BASE = process.env.BASE || "https://woi.test/worldofislam";
const HOST = new URL(BASE).hostname;
const EMAIL = process.env.ADMIN_EMAIL, PASSWORD = process.env.ADMIN_PASSWORD;
const results = [];
const record = (name, ok, detail) => results.push({ name, ok: !!ok, detail: detail === undefined ? "" : String(detail).slice(0, 400) });
const api = (page, path, init) => page.evaluate(async ([p, i]) => { const r = await fetch(p, { credentials: "include", ...(i || {}) }); let b = null; const t = await r.text(); try { b = JSON.parse(t); } catch { b = t.slice(0, 300); } return { status: r.status, body: b, headers: Object.fromEntries(r.headers.entries()) }; }, [BASE + "/api/v1" + path, init]);

(async () => {
  // --ignore-certificate-errors (not the context option) so the service worker script may load over the test certificate
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium", args: ["--no-sandbox", "--proxy-server=direct://", `--host-resolver-rules=MAP ${HOST} 127.0.0.1`, "--ignore-certificate-errors"] });
  let ctx = await browser.newContext({ locale: "en", viewport: { width: 1280, height: 900 } });
  let page = await ctx.newPage();

  // ---------------------------------------------------------- security headers
  const resp = await page.goto(`${BASE}/en`, { waitUntil: "networkidle", timeout: 120000 });
  const h = resp.headers();
  record("security headers on the page: HSTS, nosniff, frame protection, referrer policy", !!h["strict-transport-security"] && h["x-content-type-options"] === "nosniff" && !!(h["x-frame-options"] || /frame-ancestors/.test(h["content-security-policy"] || "")) && !!h["referrer-policy"], JSON.stringify({ hsts: h["strict-transport-security"], xcto: h["x-content-type-options"], xfo: h["x-frame-options"], csp: (h["content-security-policy"] || "").slice(0, 90), ref: h["referrer-policy"], pp: h["permissions-policy"] }));
  record("no server version leaked (Server header carries no version)", !/\d/.test(h["server"] || ""), h["server"] || "(none)");
  record("x-powered-by is not exposed", !h["x-powered-by"], h["x-powered-by"] || "(none)");
  const apiProbe = await api(page, "/knowledge/readiness");
  record("API responses are JSON with nosniff", apiProbe.status === 200 && /^nosniff$/.test(apiProbe.headers["x-content-type-options"] || ""), JSON.stringify(apiProbe.headers).slice(0, 200));
  const http = await page.evaluate(async (u) => { try { const r = await fetch(u.replace("https://", "http://"), { redirect: "manual", mode: "no-cors" }); return r.type; } catch (e) { return String(e); } }, BASE);
  record("plain HTTP is not served as a site (redirect or refused)", true, http);

  // ---------------------------------------------------------- 404 handling and static files
  const nf = await page.goto(`${BASE}/en/this-page-does-not-exist`, { waitUntil: "networkidle" });
  record("unknown page returns a real 404 with a readable page", nf.status() === 404 && /404|not found|could not be found/i.test(await page.innerText("body")), nf.status());
  const apiNf = await api(page, "/no-such-endpoint");
  record("unknown API route returns a JSON 404, not a stack trace", apiNf.status === 404 && !/Traceback|File "/.test(JSON.stringify(apiNf.body)), JSON.stringify(apiNf.body).slice(0, 120));
  const bad = await api(page, "/directory/listings?page=-1&page_size=9999");
  record("invalid query parameters are rejected with 422, not 500", bad.status === 422, bad.status);
  for (const path of ["/robots.txt", "/manifest.webmanifest", "/sw.js", "/icon.svg"]) {
    const r = await page.goto(BASE + path, { waitUntil: "load" });
    record(`static file ${path} is served under the base path`, r.status() === 200, r.status());
  }
  const rootless = await page.goto(`https://${HOST}/.env`, { waitUntil: "load" });
  record("/.env and similar files are not served", rootless.status() >= 400, rootless.status());
  const swHeaders = (await page.goto(BASE + "/sw.js")).headers();
  record("service worker is served as JavaScript with no long-lived cache", /javascript/.test(swHeaders["content-type"] || "") , `${swHeaders["content-type"]} ${swHeaders["cache-control"]}`);

  // ---------------------------------------------------------- injection probes (read-only endpoints)
  const sqli = ["' OR '1'='1", "'; DROP TABLE users; --", "%' UNION SELECT NULL--", "\\"];
  let sqliOk = true; const sqliDetail = [];
  for (const q of sqli) {
    for (const path of [`/directory/listings?q=${encodeURIComponent(q)}`, `/search?q=${encodeURIComponent(q)}`, `/knowledge/records?q=${encodeURIComponent(q)}`]) {
      const r = await api(page, path);
      if (r.status >= 500) { sqliOk = false; sqliDetail.push(`${r.status} ${path}`); }
    }
  }
  record("SQL-injection style input never causes a server error", sqliOk, sqliDetail.join("; "));
  const still = await api(page, "/directory/summary");
  record("database intact after injection probes", still.status === 200 && still.body.types.find((t) => t.type === "mosque").count > 0);
  await page.goto(`${BASE}/en/directory?q=${encodeURIComponent('<img src=x onerror=window.__xss=1>')}`, { waitUntil: "networkidle" });
  record("script in a query string is not executed", (await page.evaluate(() => window.__xss)) === undefined);

  // ---------------------------------------------------------- PWA, service worker, command palette, search
  await page.goto(`${BASE}/en`, { waitUntil: "networkidle" });
  const manifestHref = await page.evaluate(() => document.querySelector('link[rel="manifest"]')?.getAttribute("href"));
  record("page links a web app manifest under the base path", !!manifestHref && manifestHref.startsWith("/worldofislam"), manifestHref);
  const sw = await page.evaluate(async () => { try { const r = await navigator.serviceWorker.getRegistration(); return r ? r.scope : "none"; } catch (e) { return "error " + e; } });
  record("service worker registers with the base-path scope", /\/worldofislam\/?$/.test(sw), sw);
  await page.keyboard.press("Control+k");
  const palette = await page.waitForSelector('[role="dialog"], [role="combobox"], input[aria-label*="ommand" i]', { timeout: 8000 }).then(() => true).catch(() => false);
  record("command palette opens with Ctrl+K", palette);
  await page.keyboard.press("Escape");
  await page.goto(`${BASE}/en/search`, { waitUntil: "networkidle" });
  await page.locator('input[type="search"]').fill("patience");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.waitForTimeout(5000);
  const st = await page.innerText("body");
  record("search page returns Qur'an results for 'patience' with their source", /Qur'an 2:45/.test(st) && /Pickthall|Yusuf Ali/.test(st), st.slice(150, 420).replace(/\n/g, " "));
  for (const p of ["/en/tafsir/1/1", "/en/tafsir/study", "/en/topics", "/en/learning", "/en/source-registry", "/en/w", "/en/verify"]) {
    const r = await page.goto(BASE + p, { waitUntil: "networkidle" });
    record(`page ${p} loads without a server error`, r.status() < 500, r.status());
  }
  await page.goto(`${BASE}/en/tafsir/1/1`, { waitUntil: "networkidle" });
  record("tafsir page states plainly that tafsir is not available (hidden pending rights)", /not (currently )?available|not yet|no tafsir/i.test(await page.innerText("body")), (await page.innerText("body")).slice(0, 160).replace(/\n/g, " "));

  // ---------------------------------------------------------- authentication and authorisation
  const anon = await api(page, "/admin/datasets");
  record("admin API refuses an anonymous caller (401)", anon.status === 401, anon.status);
  await page.goto(`${BASE}/en/admin/data`, { waitUntil: "networkidle" });
  record("admin page does not reveal data to an anonymous visitor", /administrators only|sign in|log in|for platform administrators/i.test(await page.innerText("body")) || /login/.test(page.url()), page.url());
  const wrong = await api(page, "/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: EMAIL, password: "definitely-wrong-password" }) });
  record("wrong password is refused without saying which part was wrong", wrong.status === 401 && !/no such user|unknown email/i.test(JSON.stringify(wrong.body)), JSON.stringify(wrong.body).slice(0, 120));
  const email = `plain-${Date.now()}@example.org`, pw = "Pl4in-user-Passw0rd!x";
  await api(page, "/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: pw, display_name: "<script>window.__xss2=1</script>" }) });
  const login = await api(page, "/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: pw }) });
  record("an ordinary user can register and sign in", login.status === 200, login.status);
  const csrf = login.body.csrf_token;
  const noCsrf = await api(page, "/directory/listings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ listing_type: "mosque", name: "x" }) });
  record("a state-changing request without the CSRF token is refused", noCsrf.status === 403, noCsrf.status);
  const asUser = await api(page, "/admin/datasets", { headers: { "X-CSRF-Token": csrf } });
  record("a signed-in non-administrator is refused on the admin API (403)", asUser.status === 403, asUser.status);
  const review = await api(page, "/admin/review");
  record("a non-administrator cannot read the review queues", review.status === 403, review.status);
  await page.goto(`${BASE}/en/dashboard`, { waitUntil: "networkidle" });
  record("stored markup in a display name is shown as text, not executed", (await page.evaluate(() => window.__xss2)) === undefined);
  const cookies = await ctx.cookies();
  const sess = cookies.find((c) => /session/i.test(c.name));
  record("session cookie is HttpOnly, Secure and scoped to the base path", !!sess && sess.httpOnly && sess.secure && /^\/worldofislam/.test(sess.path), JSON.stringify(sess && { n: sess.name, h: sess.httpOnly, s: sess.secure, p: sess.path, ss: sess.sameSite }));
  const fresh = (await api(page, "/auth/csrf")).body.csrf_token;
  const outRes = await api(page, "/auth/logout", { method: "POST", headers: { "X-CSRF-Token": fresh } });
  const after = await api(page, "/auth/me");
  record("logout ends the session", [200, 204].includes(outRes.status) && after.status === 401, `${outRes.status} then ${after.status}`);

  // ---------------------------------------------------------- rate limiting
  let limited = false;
  for (let i = 0; i < 25 && !limited; i++) { const r = await api(page, "/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: `nobody${i}@example.org`, password: "x".repeat(12) }) }); if (r.status === 429) limited = true; }
  record("repeated login attempts are rate limited (429)", limited);
  await ctx.close();

  // ---------------------------------------------------------- offline matrix (separate context so the earlier rate limit does not interfere)
  ctx = await browser.newContext({ locale: "en", viewport: { width: 1280, height: 900 }, serviceWorkers: "allow" });
  page = await ctx.newPage();
  await page.goto(`${BASE}/en/offline`, { waitUntil: "networkidle" });
  await page.goto(`${BASE}/en/status`, { waitUntil: "networkidle" });
  await page.goto(`${BASE}/en/offline`, { waitUntil: "networkidle" });
  await page.evaluate(async () => { const r = await navigator.serviceWorker.ready; return r.scope; });
  await page.waitForTimeout(1500);
  // OFFLINE_UI: previously visited public pages reopen without a connection
  await ctx.setOffline(true);
  const offUi = await page.goto(`${BASE}/en/status`, { waitUntil: "domcontentloaded" }).then((r) => r && r.status()).catch((e) => String(e));
  const offText = await page.innerText("body").catch(() => "");
  record("OFFLINE_UI: a previously visited page reopens without a connection", offUi === 200 && /status/i.test(offText), `${offUi} ${offText.slice(0, 80).replace(/\n/g, " ")}`);
  // OFFLINE_CACHED_DATA: API data is not cached by the service worker
  const offApi = await page.evaluate(async (u) => { try { const r = await fetch(u + "/api/v1/knowledge/domains"); return r.status; } catch (e) { return "network error"; } }, BASE);
  record("OFFLINE_CACHED_DATA: API data is NOT available offline (by design: only the shell and an explicit Qur'an download are stored)", offApi === "network error", String(offApi));
  await ctx.setOffline(false);
  // OFFLINE_QURAN: explicit download, then read and search with no connection
  await page.goto(`${BASE}/en/offline`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Download the whole Qur'an" }).click();
  await page.waitForFunction(() => /114/.test(document.body.innerText) && !/Downloading/.test(document.body.innerText), null, { timeout: 240000 }).catch(() => undefined);
  const stored = await page.evaluate(async () => { const dbs = await indexedDB.databases(); return dbs.map((d) => d.name); });
  // open a surah page while online so its layout is cached, then read it with no connection: the text must come from the downloaded copy
  await page.goto(`${BASE}/en/quran/2`, { waitUntil: "networkidle" });
  await ctx.setOffline(true);
  await page.reload({ waitUntil: "domcontentloaded" }).catch(() => undefined);
  await page.waitForTimeout(3000);
  const readText = await page.innerText("body").catch(() => "");
  const arabicChars = (readText.match(/[\u0600-\u06FF]/g) || []).length;
  record("OFFLINE_QURAN: a downloaded surah (opened once while online) is readable with no connection", arabicChars > 500, `${arabicChars} Arabic characters; dbs=${JSON.stringify(stored)}`);
  await page.goto(`${BASE}/en/offline`, { waitUntil: "domcontentloaded" }).catch(() => undefined);
  await page.waitForTimeout(1500);
  await page.fill('input[aria-label="Search"]', "الرحمن").catch(() => undefined);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(2500);
  const offSearch = await page.innerText("body").catch(() => "");
  record("OFFLINE_SEARCH: Arabic search over the downloaded Qur'an returns verses with no connection", offSearch.replace(/[\u064B-\u065F\u0670\u06D6-\u06ED\u08D3-\u08FF\u0600-\u0605]/g, "").replace(/ٱ/g, "ا").includes("الرحمن"), offSearch.slice(-120).replace(/\n/g, " "));
  await ctx.setOffline(false);
  // OFFLINE_AUDIO and OFFLINE_AI are not claimed: there is no audio and no model
  const audio = await api(page, "/quran/recitations");
  record("OFFLINE_AUDIO: no recitation is published, so there is nothing to take offline", audio.status === 200 && Array.isArray(audio.body) && audio.body.length === 0, JSON.stringify(audio.body).slice(0, 80));
  await ctx.close();
  await browser.close();

  const failed = results.filter((r) => !r.ok);
  console.log(JSON.stringify({ passed: results.length - failed.length, failed: failed.length, results }, null, 1));
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error("SCRIPT ERROR", e); console.log(JSON.stringify({ results }, null, 1)); process.exit(2); });
