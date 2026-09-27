import fs from "node:fs";
import path from "node:path";
import type { AuditRow, ContestData, Meta } from "@radar/shared";
import Explorer from "../components/Explorer";
import { bakeFits } from "../lib/fits";

// The collector writes data/*.json at the repo root; the page is rebuilt after every collection run,
// so the data is baked into the static HTML.
const DATA_DIR = path.resolve(process.cwd(), "../../data");

function read<T>(file: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), "utf8")) as T;
  } catch {
    return fallback;
  }
}

export default function Page() {
  const data = read<ContestData>("contests.json", { updatedAt: "", items: [] });
  const meta = read<Meta | null>("meta.json", null);
  const audit = read<{ rows: AuditRow[] }>("audit.json", { rows: [] }).rows.at(-1) ?? null;
  return <Explorer data={data} meta={meta} fits={bakeFits(data.items)} audit={audit} />;
}
