// Combines the two static exports and the collected data into one GitHub Pages site.
//   node scripts/assemble.mjs [outDir]   (default: _site)
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";

const out = process.argv[2] ?? "_site";
rmSync(out, { recursive: true, force: true });
cpSync("apps/web/out", out, { recursive: true });
cpSync("apps/admin/out", `${out}/admin`, { recursive: true });
mkdirSync(`${out}/data`, { recursive: true });
// Published as open data too; jev_runs.jsonl is the per-run log of what Jev changed.
for (const f of ["contests.json", "meta.json", "jev_runs.jsonl"]) {
  if (existsSync(`data/${f}`)) cpSync(`data/${f}`, `${out}/data/${f}`);
}
console.log(`assembled ${out}`);
