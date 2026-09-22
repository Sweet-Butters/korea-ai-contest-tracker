import fs from "node:fs";
import path from "node:path";
import { DEFAULT_PROFILE, type ContestData, type Meta, type Profile } from "@radar/shared";
import Explorer from "../components/Explorer";

// The collector writes data/*.json at the repo root; the page is rebuilt after every collection run,
// so the data is baked into the static HTML.
const DATA_DIR = path.resolve(process.cwd(), "../../data");
const CONFIG_DIR = path.resolve(process.cwd(), "../../config");

function read<T>(file: string, fallback: T, dir = DATA_DIR): T {
  try {
    return JSON.parse(fs.readFileSync(path.join(dir, file), "utf8")) as T;
  } catch {
    return fallback;
  }
}

export default function Page() {
  const data = read<ContestData>("contests.json", { updatedAt: "", items: [] });
  const meta = read<Meta | null>("meta.json", null);
  const profile = { ...DEFAULT_PROFILE, ...read<Partial<Profile>>("profile.json", {}, CONFIG_DIR) };
  return <Explorer data={data} meta={meta} profile={profile} />;
}
