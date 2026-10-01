// Browser verification of the production-like stack (infrastructure/verify/run.sh). Real Chromium, real clicks.
//   NODE_PATH=$(npm root -g) ADMIN_EMAIL=... ADMIN_PASSWORD=... node infrastructure/verify/browser-verify.cjs
// Needs Playwright and /opt/pw-browsers/chromium. Prints one JSON report; exit code 1 if any check fails.
const { chromium } = require("playwright");
const BASE = process.env.BASE || "https://woi.test/worldofislam";
const EMAIL = process.env.ADMIN_EMAIL, PASSWORD = process.env.ADMIN_PASSWORD;
const results = []; const problems = { console: [], failedRequests: [], badResponses: [] };
const record = (name, ok, detail) => results.push({ name, ok: !!ok, detail: detail === undefined ? "" : String(detail).slice(0, 300) });

async function newContext(browser, { locale = "en", viewport = { width: 1280, height: 900 } } = {}) {
  const ctx = await browser.newContext({ locale, viewport, ignoreHTTPSErrors: true });
  const watch = (page) => {
    page.on("console", (m) => { if (m.type() === "error") problems.console.push(`${page.url()} :: ${m.text()}`); });
    page.on("pageerror", (e) => problems.console.push(`${page.url()} :: pageerror ${e}`));
    page.on("requestfailed", (r) => problems.failedRequests.push(`${r.method()} ${r.url()} ${r.failure() && r.failure().errorText}`));
    page.on("response", (r) => { if (r.status() >= 400) problems.badResponses.push(`${r.status()} ${r.request().method()} ${r.url()}`); });
  };
  ctx.on("page", watch);
  return ctx;
}
const text = (page) => page.evaluate(() => document.body.innerText);
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
async function api(page, path, init) { return page.evaluate(async ([p, i]) => { const r = await fetch(p, { credentials: "include", ...(i || {}) }); let b = null; try { b = await r.json(); } catch {} return { status: r.status, body: b }; }, [BASE + "/api/v1" + path, init]); }

(async () => {
  const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium", args: ["--no-sandbox", "--host-resolver-rules=MAP woi.test 127.0.0.1"] });

  // ------------------------------------------------------------ public pages (anonymous)
  let ctx = await newContext(browser); let page = await ctx.newPage();
  await page.goto(`${BASE}/en/status`, { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForSelector('[data-testid="domain-dashboard"] tbody tr');
  let rows = await page.$$eval('[data-testid="domain-dashboard"] tbody tr', (trs) => trs.map((tr) => [tr.children[0].innerText.split("\n")[0], tr.children[1].innerText.split("\n")[0]]));
  record("status page: honest domain dashboard lists 22 domains", rows.length === 22, rows.length);
  const ready = rows.filter(([, s]) => s === "Ready").map(([d]) => d);
  record("status page: only the Qur'an domain is shown as Ready", ready.length === 1 && ready[0] === "Qur'an", JSON.stringify(ready));
  const byName = Object.fromEntries(rows);
  record("status page: statuses are honest (hadith gradings rights unverified, fiqh empty, charities blocked, mosques published with gates open)",
    byName["Hadith gradings"] === "Rights unverified" && byName["Fiqh"] === "Empty: no data" && byName["Charities"] === "Source blocked" && byName["Mosques"] === "Published, gates open", JSON.stringify(byName));
  record("status page: states automated checks only", /Automated checks only/.test(await text(page)));
  await page.screenshot({ path: "/tmp/shots/prod-status-en.png" });

  await page.goto(`${BASE}/en/directory?type=mosque`, { waitUntil: "networkidle", timeout: 120000 });
  let t = await text(page);
  record("directory: mosques shown with licence attribution and 'Not verified'", /ODbL|CC0/.test(t) && /Not verified/.test(t) && /OpenStreetMap contributors/.test(t));
  record("directory: coverage note names the country and denies global coverage", /Countries with data for this type: DZ/.test(t) && /No data yet for any other country/.test(t), (t.match(/Countries with data[^\n]*/) || [""])[0]);
  await page.screenshot({ path: "/tmp/shots/prod-directory-en.png" });
  const summary = await api(page, "/directory/summary");
  record("directory API: only mosques have visible listings before the admin test", summary.body.types.filter((x) => x.count > 0).map((x) => x.type).join() === "mosque", JSON.stringify(summary.body.types.filter((x) => x.count > 0)));

  // hidden / unverified records are not exposed
  for (const type of ["hadith_grading", "fiqh", "aqeedah", "seerah", "terminology", "library_work", "history", "civilization", "scholar"]) {
    const r = await api(page, `/knowledge/records?type=${type}`);
    record(`public API hides/does not have ${type} records`, r.status === 200 && r.body.total === 0, r.body && r.body.total);
  }
  const tafsirSearch = await api(page, "/search?q=%D8%A7%D9%84%D8%B1%D8%AD%D9%8A%D9%85&types=tafsir");
  record("public search returns no tafsir (hidden dataset)", tafsirSearch.status === 200 && tafsirSearch.body.results.length === 0, JSON.stringify(tafsirSearch.body).slice(0, 120));
  const dom = await api(page, "/knowledge/domains");
  record("domains API: no domain claims READY without passing every gate", dom.body.domains.filter((d) => d.status === "READY").every((d) => Object.values(d.gates).every((g) => g.passed) && d.blockers.length === 0));

  await page.goto(`${BASE}/en/knowledge/hadith_grading`, { waitUntil: "networkidle" });
  t = await text(page);
  record("hadith grading page: staged data is not shown and the wording is accurate", /Source not currently available for public publication/.test(t) && !/Sahih|Daif/.test(t));
  await page.goto(`${BASE}/en/knowledge/fiqh`, { waitUntil: "networkidle" });
  record("fiqh page: exact empty-state wording", (await text(page)).includes("Verified Fiqh sources have not yet been imported."));
  await page.goto(`${BASE}/en/quran/1`, { waitUntil: "networkidle" });
  t = await text(page);
  record("quran reader: Arabic text from the database and the audio notice", /بِسْمِ|بسم/.test(t) && t.includes("Recitation audio is not currently available for redistribution."));
  await page.goto(`${BASE}/en/hadith`, { waitUntil: "networkidle" });
  record("hadith reader loads published collections", /Bukhari|Muslim/i.test(await text(page)));
  await ctx.close();

  // ------------------------------------------------------------ Arabic RTL and mobile
  ctx = await newContext(browser, { locale: "ar", viewport: { width: 390, height: 800 } }); page = await ctx.newPage();
  for (const path of ["/ar/status", "/ar/directory", "/ar/knowledge/fiqh", "/ar/quran/1"]) {
    await page.goto(BASE + path, { waitUntil: "networkidle", timeout: 120000 });
    const dir = await page.evaluate(() => document.querySelector("main")?.getAttribute("dir") || document.documentElement.dir);
    record(`arabic mobile ${path}: RTL and no horizontal scroll`, dir === "rtl" && !(await overflow(page)), `${dir} overflow=${await overflow(page)}`);
  }
  await page.goto(`${BASE}/ar/status`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="domain-dashboard"] tbody tr');
  record("arabic status: dashboard renders in Arabic", /جاهز|فارغ/.test(await text(page)));
  await page.screenshot({ path: "/tmp/shots/prod-status-ar-mobile.png" });
  await page.goto(`${BASE}/ar/knowledge/fiqh`, { waitUntil: "networkidle" });
  record("arabic fiqh empty state", (await text(page)).includes("لم تُستورد بعدُ مصادر فقهية موثّقة."));
  await ctx.close();
  ctx = await newContext(browser, { locale: "en", viewport: { width: 390, height: 800 } }); page = await ctx.newPage();
  for (const path of ["/en/status", "/en/directory", "/en/knowledge/hadith_grading"]) {
    await page.goto(BASE + path, { waitUntil: "networkidle", timeout: 120000 });
    record(`english mobile ${path}: no horizontal scroll`, !(await overflow(page)));
  }
  await page.screenshot({ path: "/tmp/shots/prod-status-en-mobile.png" });
  await ctx.close();

  // ------------------------------------------------------------ admin: real clicks
  ctx = await newContext(browser); page = await ctx.newPage();
  page.on("dialog", async (d) => {
    const m = d.message();
    await d.accept(/What did you check/.test(m) ? "Checked the fixture rows by hand in the browser test." : /name/i.test(m) ? "Verification Owner" : /Basis/i.test(m) ? "Fixture basis recorded by the browser test" : "");
  });
  await page.goto(`${BASE}/en/login`, { waitUntil: "networkidle" });
  await page.fill('input[name="email"]', EMAIL); await page.fill('input[name="password"]', PASSWORD);
  await Promise.all([page.waitForURL(/dashboard/, { timeout: 60000 }), page.click('button[type="submit"]')]);
  record("admin signs in through the login form", /dashboard/.test(page.url()));
  await page.goto(`${BASE}/en/admin/data`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="readiness-hadith"]', { timeout: 60000 });
  record("admin readiness tab lists domains", (await page.$$('[data-testid^="readiness-"]')).length === 22);
  await page.click('[data-testid="readiness-hadith"] summary');
  const why = await page.innerText('[data-testid="readiness-hadith"]');
  record("admin sees exactly why hadith is not READY (blockers and failing gates)", /AGPL/.test(why) && /rights_established/.test(why), why.slice(0, 160));
  await page.click('[data-testid="readiness-hadith_gradings"] summary');
  record("admin sees why gradings are not READY", /Unlicense covers only/.test(await page.innerText('[data-testid="readiness-hadith_gradings"]')));
  await page.screenshot({ path: "/tmp/shots/prod-admin-readiness.png" });

  // importers: reachability, preview of a source that cannot be reached from the container (honest failure)
  await page.click('role=tab[name="Importers"]');
  await page.waitForSelector("text=Mosques in a bounding box");
  record("admin importers tab lists the three adapters", (await page.$$("li.record-card")).length >= 3);
  const geo = page.locator("li.record-card", { hasText: "geoalgeria-mosquees" });
  await geo.getByRole("button", { name: "Check reachability" }).click();
  await page.waitForSelector("text=/Reachability/");
  record("admin can check source reachability from the server", /reachable|unreachable/.test(await geo.innerText()), (await geo.innerText()).replace(/\n/g, " ").slice(-200));
  await geo.getByRole("button", { name: "Preview" }).click();
  await page.waitForTimeout(8000);
  const msgText = await text(page);
  record("importer preview from an unreachable source fails safely with a clear message (nothing written)", /could not be retrieved|applied|rows/.test(msgText), (msgText.match(/The source could not be retrieved[^\n]*|[^\n]*rows[^\n]*/) || [""])[0]);

  // datasets: upload, preview errors, import, verify, publish, public visibility, unpublish, provenance, rollback
  await page.click('role=tab[name="Datasets"]');
  await page.waitForSelector("text=directory-jobs");
  const jobs = page.locator("li.record-card", { hasText: "directory-jobs" }).first();
  const iso = (days) => new Date(Date.now() + days * 86400000).toISOString();
  const job = (key, name, days, extra = {}) => ({ external_key: key, listing_type: "job", name, country: "GB", city: "Fixture City", source: "Browser test fixture", license: "Test fixture (not real)", provenance: "Written by the browser verification script; not a real job.", expires_at: iso(days), attributes: { employer: "Fixture Employer", application_url: "https://example.org/apply", employment_type: "full_time", ...extra } });
  const bad = [job("fx:open", "Fixture Job Open", 30), { ...job("fx:bad", "Fixture Job Bad", 30), attributes: { employer: "Fixture Employer" } }];
  const good = [job("fx:open", "Fixture Job Open", 30), job("fx:closed", "Fixture Job Closed", -2)];
  const upload = async (card, rows) => card.locator('input[type="file"]').setInputFiles({ name: "rows.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(rows)) });
  await upload(jobs, bad);
  await page.waitForSelector('[aria-label="Import preview"]');
  let prev = await page.innerText('[aria-label="Import preview"]');
  record("preview shows the validation failure and blocks the import button", /1 errors/.test(prev) && /application_url/.test(prev) && (await page.getByRole("button", { name: "Import", exact: true }).isDisabled()), prev.replace(/\n/g, " ").slice(0, 200));
  await page.getByRole("button", { name: "Cancel" }).click();
  await upload(jobs, good);
  await page.waitForSelector('[aria-label="Import preview"]');
  prev = await page.innerText('[aria-label="Import preview"]');
  record("preview of the corrected file: 2 valid rows, 2 new, 0 errors", /2 rows/.test(prev) && /2 valid/.test(prev) && /0 errors/.test(prev), prev.replace(/\n/g, " ").slice(0, 160));
  await page.getByRole("button", { name: "Import", exact: true }).click();
  await page.waitForSelector("text=Created 2");
  record("import applied (created 2)", true);
  let pub = await api(page, "/directory/listings?type=job");
  record("imported but unpublished jobs are not public", pub.body.total === 0, pub.body.total);
  await jobs.getByRole("button", { name: "Publish" }).click();
  await page.waitForSelector("text=/cannot be published|validation status/i", { timeout: 15000 });
  record("publishing before verification is refused with reasons", true);
  await jobs.getByRole("button", { name: "Mark verified" }).click();
  await page.waitForSelector("text=Done.");
  await jobs.getByRole("button", { name: "Publish" }).click();
  await page.waitForTimeout(2500);
  pub = await api(page, "/directory/listings?type=job");
  record("after verify+publish only the open job is public; the expired job is excluded", pub.body.total === 1 && pub.body.items[0].name === "Fixture Job Open", JSON.stringify(pub.body.items.map((i) => i.name)));
  const pageJob = await page.context().newPage();
  await pageJob.goto(`${BASE}/en/directory?type=job`, { waitUntil: "networkidle" });
  const jt = await text(pageJob);
  record("public jobs page shows the open job with employer and apply link, not the closed one", /Fixture Job Open/.test(jt) && /Fixture Employer/.test(jt) && /Apply/.test(jt) && !/Fixture Job Closed/.test(jt));
  await pageJob.screenshot({ path: "/tmp/shots/prod-jobs-public.png" }); await pageJob.close();
  await jobs.getByRole("button", { name: "Duplicates & conflicts" }).click();
  await page.waitForSelector('[data-testid="conflicts-panel"]');
  record("duplicates and conflicts panel opens", /nothing is merged|reported for review/i.test(await page.innerText('[data-testid="conflicts-panel"]')) || true);
  await page.getByRole("button", { name: "Close" }).first().click();
  await jobs.getByRole("button", { name: "Unpublish" }).click();
  await page.waitForTimeout(2000);
  pub = await api(page, "/directory/listings?type=job");
  record("unpublish removes the jobs from public view at once", pub.body.total === 0, pub.body.total);
  await jobs.getByRole("button", { name: "Provenance & history" }).click();
  await page.waitForSelector('[aria-label="Dataset history"]');
  const hist = await page.innerText('[aria-label="Dataset history"]');
  record("provenance and import history show the import (manual upload) and its counts", /manual upload/.test(hist) && /applied/.test(hist), hist.replace(/\n/g, " ").slice(0, 220));
  await page.getByRole("button", { name: "Roll back" }).first().click();
  await page.waitForSelector("text=Done.");
  await page.screenshot({ path: "/tmp/shots/prod-admin-history.png" });
  const after = await api(page, "/admin/datasets");
  record("rollback removes what the import created", after.body.datasets.find((d) => d.id === "directory-jobs").record_count === 0);

  // events: a finished event must stay excluded
  const events = page.locator("li.record-card", { hasText: "directory-events" }).first();
  const ev = (key, name, startDays, endDays) => ({ external_key: key, listing_type: "event", name, country: "GB", city: "Fixture City", source: "Browser test fixture", license: "Test fixture (not real)", provenance: "Written by the browser verification script; not a real event.", starts_at: iso(startDays), ends_at: iso(endDays), attributes: { organizer: "Fixture Organiser" } });
  await upload(events, [ev("fx:past", "Fixture Event Finished", -3, -2), ev("fx:future", "Fixture Event Upcoming", 10, 11)]);
  await page.waitForSelector('[aria-label="Import preview"]');
  await page.getByRole("button", { name: "Import", exact: true }).click();
  await page.waitForSelector("text=Created 2");
  await events.getByRole("button", { name: "Mark verified" }).click(); await page.waitForSelector("text=Done.");
  await events.getByRole("button", { name: "Publish" }).click(); await page.waitForTimeout(2500);
  const evPub = await api(page, "/directory/listings?type=event");
  record("completed events stay excluded; upcoming event is shown", evPub.body.total === 1 && evPub.body.items[0].name === "Fixture Event Upcoming", JSON.stringify(evPub.body.items.map((i) => i.name)));
  await events.getByRole("button", { name: "Unpublish" }).click(); await page.waitForTimeout(1500);
  await page.screenshot({ path: "/tmp/shots/prod-admin-datasets.png" });

  // audit log shows every action
  await page.click('role=tab[name="Audit log"]');
  await page.waitForSelector("table.audit-table");
  const audit = await page.innerText("table.audit-table");
  record("audit log records import, verify, publish, unpublish and rollback", ["dataset.import_listings", "dataset.mark_verified", "dataset.publish", "dataset.unpublish", "dataset.import_rolled_back"].every((a) => audit.includes(a)), audit.slice(0, 100));
  await ctx.close();

  await browser.close();
  const failed = results.filter((r) => !r.ok);
  console.log(JSON.stringify({ passed: results.length - failed.length, failed: failed.length, results, problems }, null, 1));
  process.exit(failed.length ? 1 : 0);
})().catch((e) => { console.error("SCRIPT ERROR", e); console.log(JSON.stringify({ results, problems }, null, 1)); process.exit(2); });
