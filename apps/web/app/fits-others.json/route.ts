import fs from "node:fs";
import path from "node:path";
import type { ContestData } from "@radar/shared";
import { bakeFits } from "../../lib/fits";

// Scores for the off-topic list (data/others.json), which the page loads only on demand.
export const dynamic = "force-static";

export function GET() {
  let items: ContestData["items"] = [];
  try {
    items = (JSON.parse(fs.readFileSync(path.resolve(process.cwd(), "../../data/others.json"), "utf8")) as ContestData).items;
  } catch { /* no off-topic file yet */ }
  return Response.json(bakeFits(items));
}
