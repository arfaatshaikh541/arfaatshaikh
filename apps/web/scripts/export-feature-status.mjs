// Writes docs/FEATURE_STATUS.md from src/lib/worlds.ts (the single source of truth for capability status).
//   node scripts/export-feature-status.mjs          write
//   node scripts/export-feature-status.mjs --check  exit 1 if the document is stale
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const out = mkdtempSync(path.join(tmpdir(), "woi-worlds-"));
execFileSync("npx", ["tsc", "src/lib/worlds.ts", "--outDir", out, "--module", "esnext", "--target", "es2022", "--moduleResolution", "bundler", "--skipLibCheck"], { cwd: path.join(here, ".."), stdio: "inherit" });
const worlds = await import(pathToFileURL(path.join(out, "worlds.js")).href);

const labels = {
  IMPLEMENTED: "Built, tested, and backed by real data or on-device logic that was checked.",
  PARTIALLY_IMPLEMENTED: "Works, with a stated gap (limited data, an approximation, or a missing layer).",
  NOT_VERIFIED: "Built, but its correctness has not been verified against an authority.",
  DATA_SOURCE_REQUIRED: "Built; needs a licensed/verified dataset or the owner's rights confirmation before it can show content.",
  ARCHITECTURE_READY: "Backend, data contract and UI framework exist; nothing is loaded yet.",
  NOT_IMPLEMENTED: "Nothing built.",
};
const counts = worlds.featureCounts();
const lines = ["# Feature status", "", "Generated from `apps/web/src/lib/worlds.ts` by `apps/web/scripts/export-feature-status.mjs`. Do not edit by hand.", "",
  `${counts.total} capabilities across ${worlds.worlds.length} worlds.`, "", "| Status | Count | Meaning |", "|---|---|---|"];
for (const s of worlds.STATUS_ORDER) lines.push(`| ${s} | ${counts.byStatus[s]} | ${labels[s]} |`);
for (const w of worlds.worlds) {
  lines.push("", `## ${w.name} (${w.nameAr})`, "", "| Capability | Status | Note |", "|---|---|---|");
  for (const f of w.features) lines.push(`| ${f.name} | ${f.status} | ${f.note.replace(/\|/g, "/")} |`);
}
const text = lines.join("\n") + "\n";
const target = path.join(here, "..", "..", "..", "docs", "FEATURE_STATUS.md");
if (process.argv.includes("--check")) process.exit(existsSync(target) && readFileSync(target, "utf8") === text ? 0 : 1);
writeFileSync(target, text);
console.log("wrote", target);
