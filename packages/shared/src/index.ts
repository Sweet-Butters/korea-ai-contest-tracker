// Shapes of data/*.json written by the Python collector, plus helpers shared by web and admin.

export type Status = "open" | "upcoming" | "in_progress" | "ended";
export type Confidence = "high" | "medium" | "low";

export interface Contest {
  id: string;
  name: string;
  host?: string;
  category?: string;
  aiRelated?: boolean;
  confidence?: Confidence;
  /** Jev's probability that this is an AI-related contest (present when Jev reviewed it). */
  jev?: number;
  applyStart?: string | null;
  applyEnd?: string | null;
  eventDates?: string | null;
  lastEvent?: string | null;
  prize?: string | null;
  eligibility?: string | null;
  region?: string | null;
  url?: string | null;
  sources: Record<string, string | null>;
  firstSeen?: string;
  lastSeen?: string;
  upcoming?: boolean;
  status: Status;
}

export interface ContestData {
  updatedAt: string;
  items: Contest[];
}

export interface SourceMeta {
  fetched: number;
  kept: number;
  error: string | null;
  seconds: number;
}

export interface Meta {
  runDate: string;
  llm: boolean;
  jev?: boolean;
  sources: Record<string, SourceMeta>;
  total: number;
}

export interface Keywords {
  aiTerms: string[];
  relatedTerms: string[];
  competitionTerms: string[];
  excludeTerms: string[];
  extraTopics: Record<string, string[]>;
  categories: Record<string, string[]>;
  newsQueries: string[];
  regions: string[];
  [k: string]: unknown;
}

export const CATEGORY_LABEL: Record<string, string> = {
  hackathon: "해커톤",
  data: "데이터 분석",
  dev: "개발",
  idea: "아이디어",
  creative: "AI 창작",
  startup: "창업",
  tourism: "관광·투어",
  youth: "청소년",
  academic: "학술·논문",
  other: "기타",
};

export const STATUS_LABEL: Record<Status, string> = {
  open: "접수중",
  upcoming: "접수예정",
  in_progress: "본선·진행중",
  ended: "최근 마감",
};

export const categoryLabel = (c?: string) => (c && CATEGORY_LABEL[c]) || c || CATEGORY_LABEL.other;

const UNIT: Record<string, number> = { 억: 1e8, 천만: 1e7, 백만: 1e6, 만: 1e4, 천: 1e3, 원: 1 };
const USD_KRW = 1400;

/**
 * Largest money amount mentioned in a free-text prize, in KRW.
 * "총상금 1억 2,600만원" → 126,000,000 · "4,200만 원" → 42,000,000 · "$100K+" → 140,000,000.
 * Returns null when no amount is found (e.g. "장관상", "채용 연계").
 */
export function parsePrize(text?: string | null): number | null {
  if (!text) return null;
  const s = text.replace(/\s+/g, "");
  let best = 0;
  for (const m of s.matchAll(/\$(\d[\d,]*(?:\.\d+)?)([KkMm])?/g)) {
    const n = parseFloat(m[1].replace(/,/g, "")) * (m[2] ? (/k/i.test(m[2]) ? 1e3 : 1e6) : 1);
    best = Math.max(best, n * USD_KRW);
  }
  // Tokens like 1억 / 2,600만 / 500,000원; consecutive tokens ("1억2,600만") are summed.
  const re = /(\d[\d,]*(?:\.\d+)?)(억|천만|백만|만|천원|원)/g;
  let group = 0;
  let lastEnd = -1;
  let lastUnit = Infinity;
  for (const m of s.matchAll(re)) {
    const unitKey = m[2] === "천원" ? "천" : m[2];
    const unit = UNIT[unitKey];
    const value = parseFloat(m[1].replace(/,/g, "")) * unit;
    const idx = m.index ?? 0;
    const continues = idx === lastEnd && unit < lastUnit;
    group = continues ? group + value : value;
    best = Math.max(best, group);
    lastEnd = idx + m[0].length;
    lastUnit = unit;
  }
  return best >= 1e4 ? Math.round(best) : null;
}

export function formatKRW(n: number): string {
  if (n >= 1e8) {
    const eok = Math.floor(n / 1e8);
    const man = Math.round((n % 1e8) / 1e4);
    return man ? `${eok}억 ${man.toLocaleString()}만원` : `${eok}억원`;
  }
  return `${Math.round(n / 1e4).toLocaleString()}만원`;
}

/** Today's date in Korea as YYYY-MM-DD. */
export function todayKST(): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(new Date());
}

export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(to + "T00:00:00Z") - Date.parse(from + "T00:00:00Z")) / 864e5);
}

export const shortDate = (iso?: string | null) => (iso ? `${+iso.slice(5, 7)}/${+iso.slice(8, 10)}` : "");

/** Repository holding config/keywords.json and the update workflow (used by the admin app). */
export const REPO = { owner: "Sweet-Butters", repo: "korea-ai-contest-tracker", branch: "main", workflow: "update.yml" };

// ---- Personal fit: config/profile.json, edited in /admin, scored in the browser ----

export interface Profile {
  /** Who I am, as contests word eligibility: 대학생, 대학원생, 일반인, 누구나 … */
  eligibility: string[];
  /** Eligibility words that mean "not for me" when none of mine appear: 청소년, 군장병 … */
  notEligible: string[];
  /** Topics I care about; each hit in the name adds points. */
  interests: string[];
  /** Preferred categories (keys of CATEGORY_LABEL). */
  categories: string[];
  /** Regions I can attend in person; contests with no region or "온라인" always pass. */
  regions: string[];
  /** Hide anything whose name contains one of these. */
  exclude: string[];
  /** Minimum prize in 만원 for the prize bonus (0 = no bonus). */
  minPrizeManwon: number;
  /** Deadline must be at least this many days away to be worth starting. */
  minDaysLeft: number;
  /** Score at or above which a contest is marked as recommended. */
  threshold: number;
}

export const DEFAULT_PROFILE: Profile = {
  eligibility: ["대학생", "대학원생", "일반인", "누구나", "제한 없음", "전 국민", "국민"],
  notEligible: ["청소년", "초등", "중학생", "고등학생", "고교", "군장병", "재직자", "기업만"],
  interests: ["AI", "에이전트", "LLM", "해커톤", "데이터"],
  categories: ["hackathon", "data", "dev", "idea", "startup"],
  regions: ["서울", "경기", "인천"],
  exclude: [],
  minPrizeManwon: 100,
  minDaysLeft: 3,
  threshold: 60,
};

export interface Fit {
  score: number;
  recommended: boolean;
  /** Short reasons, shown as a tooltip and in the admin preview. */
  reasons: string[];
  /** A hard "no" (not eligible, excluded word, too late). */
  blocked?: string;
}

const hasAny = (text: string, words: string[]) => words.some((w) => w && text.includes(w));

/**
 * 0–100 fit of one contest for a profile. Hard blocks come first (status, excluded words,
 * eligibility, days left); then points for category (30), interests (up to 30), prize (15),
 * reachable region (10), Jev/keyword AI confidence (15).
 */
export function fitScore(it: Contest & { prizeKRW?: number | null }, p: Profile, today: string): Fit {
  const name = it.name;
  const elig = it.eligibility ?? "";
  if (it.status === "ended") return { score: 0, recommended: false, reasons: [], blocked: "마감" };
  if (hasAny(name, p.exclude)) return { score: 0, recommended: false, reasons: [], blocked: "제외 단어" };
  if (elig && !hasAny(elig, p.eligibility) && hasAny(elig + " " + name, p.notEligible)) {
    return { score: 0, recommended: false, reasons: [], blocked: "참가 자격" };
  }
  if (it.status === "open" && it.applyEnd && daysBetween(today, it.applyEnd) < p.minDaysLeft) {
    return { score: 0, recommended: false, reasons: [], blocked: "마감 임박" };
  }

  let score = 0;
  const reasons: string[] = [];
  if (it.category && p.categories.includes(it.category)) {
    score += 30;
    reasons.push(categoryLabel(it.category));
  }
  const hits = p.interests.filter((w) => w && name.toLowerCase().includes(w.toLowerCase()));
  if (hits.length) {
    score += Math.min(30, 15 * hits.length);
    reasons.push(hits.join("·"));
  }
  const prize = it.prizeKRW ?? parsePrize(it.prize);
  if (prize && p.minPrizeManwon > 0 && prize >= p.minPrizeManwon * 1e4) {
    score += prize >= 10 * p.minPrizeManwon * 1e4 ? 15 : 10;
    reasons.push(`상금 ${formatKRW(prize)}`);
  }
  if (!it.region || hasAny(it.region, p.regions) || /온라인/.test(name + elig)) {
    score += 10;
    if (it.region && hasAny(it.region, p.regions)) reasons.push(it.region);
  }
  if (it.jev !== undefined) score += Math.round(15 * it.jev);
  else if (it.aiRelated !== false && it.confidence === "high") score += 10;

  score = Math.min(100, score);
  return { score, recommended: score >= p.threshold, reasons };
}
