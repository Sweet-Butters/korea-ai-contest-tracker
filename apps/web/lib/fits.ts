import fs from "node:fs";
import path from "node:path";
import {
  DEFAULT_PROFILE, fitScore, packFit, parsePrize, todayKST,
  type CompactFit, type Contest, type Profile,
} from "@radar/shared";

// The recommendation profile lives in the private repo. CI copies it to config/profile.json
// (git-ignored) before the build; without it the defaults in @radar/shared apply. Only the
// per-contest scores below reach the page, never the profile itself.
const PROFILE_FILE = path.resolve(process.cwd(), "../../config/profile.json");

function profile(): Profile {
  try {
    const { _comment, ...p } = JSON.parse(fs.readFileSync(PROFILE_FILE, "utf8")) as Partial<Profile> & { _comment?: string };
    void _comment;
    return { ...DEFAULT_PROFILE, ...p };
  } catch {
    return DEFAULT_PROFILE;
  }
}

/** id -> compact fit for every contest, scored for today (KST) at build time. */
export function bakeFits(items: Contest[]): Record<string, CompactFit> {
  const p = profile();
  const today = todayKST();
  const out: Record<string, CompactFit> = {};
  for (const c of items) out[c.id] = packFit(fitScore({ ...c, prizeKRW: parsePrize(c.prize) }, p, today));
  return out;
}
