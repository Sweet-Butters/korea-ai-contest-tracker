"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CATEGORY_LABEL, STATUS_LABEL, categoryLabel, daysBetween, parsePrize, todayKST,
  type Contest, type ContestData, type Meta, type Status,
} from "@radar/shared";
import ContestCard from "./ContestCard";
import CalendarView from "./CalendarView";

export type Item = Contest & { prizeKRW: number | null };

type SortKey = "deadline" | "prize" | "new" | "sources" | "jev" | "name";
type View = "list" | "group" | "calendar";

interface Filters {
  q: string;
  status: Status[];
  cats: string[];
  aiOnly: boolean;
  hideLow: boolean;
  prizeOnly: boolean;
  region: string;
  source: string;
  sort: SortKey;
  view: View;
}

const DEFAULTS: Filters = {
  q: "", status: ["open", "upcoming"], cats: [], aiOnly: true, hideLow: false, prizeOnly: false,
  region: "", source: "", sort: "deadline", view: "list",
};

const SORTS: Record<SortKey, { label: string; cmp: (a: Item, b: Item) => number }> = {
  deadline: { label: "마감 임박순", cmp: (a, b) => (a.applyEnd || "9999").localeCompare(b.applyEnd || "9999") },
  prize: { label: "상금 높은순", cmp: (a, b) => (b.prizeKRW ?? -1) - (a.prizeKRW ?? -1) },
  new: { label: "새로 올라온 순", cmp: (a, b) => (b.firstSeen || "").localeCompare(a.firstSeen || "") },
  sources: { label: "많이 알려진 순", cmp: (a, b) => Object.keys(b.sources).length - Object.keys(a.sources).length },
  jev: { label: "Jev AI 확신도순", cmp: (a, b) => (b.jev ?? -1) - (a.jev ?? -1) },
  name: { label: "이름순", cmp: (a, b) => a.name.localeCompare(b.name, "ko") },
};

const STORAGE_KEY = "radar-filters-v2";
const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

function load(): Filters {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") };
  } catch {
    return DEFAULTS;
  }
}

const toggle = <T,>(arr: T[], v: T) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

function countBy<T>(arr: T[], key: (x: T) => string) {
  const out: Record<string, number> = {};
  for (const x of arr) out[key(x)] = (out[key(x)] || 0) + 1;
  return out;
}

export default function Explorer({ data, meta }: { data: ContestData; meta: Meta | null }) {
  const [f, setF] = useState<Filters>(DEFAULTS);
  const [today, setToday] = useState(data.updatedAt.slice(0, 10) || "2026-01-01");
  const set = (patch: Partial<Filters>) => setF((prev) => ({ ...prev, ...patch }));

  useEffect(() => {
    // Saved filters, overridden by shareable URL params: ?view=calendar&sort=prize&cat=hackathon&q=...
    const p = new URLSearchParams(location.search);
    const fromUrl: Partial<Filters> = {};
    const view = p.get("view"), sort = p.get("sort");
    if (view === "list" || view === "group" || view === "calendar") fromUrl.view = view;
    if (sort && sort in SORTS) fromUrl.sort = sort as SortKey;
    if (p.get("cat")) fromUrl.cats = p.getAll("cat");
    if (p.get("q")) fromUrl.q = p.get("q")!;
    setF({ ...load(), ...fromUrl });
    setToday(todayKST());
  }, []);
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(f)); } catch { /* storage blocked */ }
  }, [f]);

  const items: Item[] = useMemo(
    () => data.items.map((c) => ({ ...c, prizeKRW: parsePrize(c.prize) })),
    [data.items],
  );
  const hasJev = items.some((i) => i.jev !== undefined);
  const regions = useMemo(() => [...new Set(items.map((i) => i.region).filter(Boolean) as string[])].sort(), [items]);
  const sourceNames = useMemo(
    () => [...new Set(items.flatMap((i) => Object.keys(i.sources)))].filter((s) => s !== "초기조사").sort(),
    [items],
  );

  // Filters applied in two stages so each chip row can show counts for the other filters.
  const base = items.filter((it) => {
    if (f.aiOnly && it.aiRelated === false) return false;
    if (f.hideLow && it.confidence === "low") return false;
    if (f.prizeOnly && !it.prizeKRW) return false;
    if (f.region && it.region !== f.region) return false;
    if (f.source && !(f.source in it.sources)) return false;
    if (f.q) {
      const hay = `${it.name} ${it.host ?? ""} ${it.eligibility ?? ""} ${it.prize ?? ""} ${it.region ?? ""} ${categoryLabel(it.category)}`.toLowerCase();
      if (!f.q.toLowerCase().split(/\s+/).every((w) => hay.includes(w))) return false;
    }
    return true;
  });
  const byStatus = countBy(base, (i) => i.status);
  const inStatus = base.filter((i) => f.status.includes(i.status));
  const byCat = countBy(inStatus, (i) => i.category || "other");
  const shown = inStatus
    .filter((i) => !f.cats.length || f.cats.includes(i.category || "other"))
    .sort(SORTS[f.sort].cmp);

  const ai = items.filter((i) => i.aiRelated !== false);
  const open = ai.filter((i) => i.status === "open");
  const stats: [string, string][] = [
    ["접수중", open.length.toLocaleString()],
    ["7일 안에 마감", open.filter((i) => i.applyEnd && daysBetween(today, i.applyEnd) <= 7).length.toLocaleString()],
    ["접수예정", ai.filter((i) => i.status === "upcoming").length.toLocaleString()],
    ["접수중 총상금", totalPrize(open)],
  ];

  const updated = data.updatedAt
    ? new Date(data.updatedAt).toLocaleString("ko-KR", { timeZone: "Asia/Seoul", dateStyle: "medium", timeStyle: "short" })
    : "";
  const failed = meta ? Object.entries(meta.sources).filter(([, v]) => v.error).map(([k]) => k) : [];

  return (
    <>
      <header className="top">
        <div className="wrap top-row">
          <div>
            <h1>AI 공모전 레이더</h1>
            <p className="sub">대한민국 AI 대회·공모전·해커톤·창업경진대회를 매일 자동 수집합니다.{updated && ` 마지막 업데이트 ${updated}`}</p>
          </div>
          <nav className="top-links">
            <a href={`${BASE}/admin/`}>키워드 관리</a>
            <a href="https://github.com/Sweet-Butters/korea-ai-contest-tracker" target="_blank" rel="noopener">GitHub</a>
          </nav>
        </div>
      </header>

      <main className="wrap">
        <section className="stats" aria-label="요약">
          {stats.map(([label, n]) => (
            <div className="stat" key={label}><b>{n}</b><span>{label}</span></div>
          ))}
        </section>

        <section className="controls" aria-label="필터">
          <input type="search" value={f.q} onChange={(e) => set({ q: e.target.value })} placeholder="대회명, 주최, 분야, 대상 검색" />
          <div className="chips" role="group" aria-label="상태">
            {(Object.keys(STATUS_LABEL) as Status[]).map((s) => (
              <Chip key={s} pressed={f.status.includes(s)} count={byStatus[s] || 0} onClick={() => set({ status: toggle(f.status, s) })}>
                {STATUS_LABEL[s]}
              </Chip>
            ))}
          </div>
          <div className="chips" role="group" aria-label="분야">
            <Chip pressed={!f.cats.length} onClick={() => set({ cats: [] })}>전체 분야</Chip>
            {Object.keys({ ...CATEGORY_LABEL, ...byCat }).filter((k) => byCat[k]).map((k) => (
              <Chip key={k} pressed={f.cats.includes(k)} count={byCat[k]} onClick={() => set({ cats: toggle(f.cats, k) })}>
                {categoryLabel(k)}
              </Chip>
            ))}
          </div>
          <div className="chips" role="group" aria-label="정렬">
            <span className="row-label">정렬</span>
            {(Object.keys(SORTS) as SortKey[]).filter((k) => k !== "jev" || hasJev).map((k) => (
              <Chip key={k} pressed={f.sort === k} onClick={() => set({ sort: k })}>{SORTS[k].label}</Chip>
            ))}
          </div>
          <div className="row">
            <div className="toggles">
              <label className="toggle"><input type="checkbox" checked={f.aiOnly} onChange={(e) => set({ aiOnly: e.target.checked })} /> AI 관련만</label>
              <label className="toggle"><input type="checkbox" checked={f.prizeOnly} onChange={(e) => set({ prizeOnly: e.target.checked })} /> 상금 있는 대회만</label>
              <label className="toggle"><input type="checkbox" checked={f.hideLow} onChange={(e) => set({ hideLow: e.target.checked })} /> 미확인 숨기기</label>
            </div>
            <div className="selects">
              <select value={f.region} onChange={(e) => set({ region: e.target.value })} aria-label="지역">
                <option value="">전체 지역</option>
                {regions.map((r) => <option key={r}>{r}</option>)}
              </select>
              <select value={f.source} onChange={(e) => set({ source: e.target.value })} aria-label="출처">
                <option value="">전체 출처</option>
                {sourceNames.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>
        </section>

        <div className="view-bar">
          <p className="count">{shown.length.toLocaleString()}개 대회</p>
          <div className="tabs" role="tablist" aria-label="보기">
            {([["list", "목록"], ["group", "분야별"], ["calendar", "일정표"]] as [View, string][]).map(([v, label]) => (
              <button key={v} type="button" role="tab" aria-selected={f.view === v} className="tab" onClick={() => set({ view: v })}>{label}</button>
            ))}
          </div>
        </div>

        {shown.length === 0 && <p className="empty">조건에 맞는 대회가 없습니다.</p>}
        {f.view === "list" && <ol className="list">{shown.map((it) => <ContestCard key={it.id} it={it} today={today} />)}</ol>}
        {f.view === "group" && <Grouped items={shown} today={today} />}
        {f.view === "calendar" && <CalendarView items={shown} today={today} />}
      </main>

      <footer className="wrap foot">
        <p>
          정보는 공모전 플랫폼(씽굿·링커리어·올콘·콘테스트코리아·요즘것들·위비티), DACON·AIFactory·이벤터스·Dev-Event,
          네이버 뉴스에서 자동 수집하고{meta?.jev ? ", TypeSafe Jev로 AI 대회 여부와 분야를 한 번 더 판정합니다" : "합니다"}.
          일정과 자격은 바뀔 수 있으니 반드시 원문 공고를 확인하세요.
        </p>
        {meta && (
          <p>마지막 수집 {meta.runDate} · 수집원 {Object.keys(meta.sources).length}곳{failed.length ? ` · 이번 수집 실패: ${failed.join(", ")}` : ""}</p>
        )}
      </footer>
    </>
  );
}

function totalPrize(items: Item[]) {
  const sum = items.reduce((s, i) => s + (i.prizeKRW ?? 0), 0);
  return sum >= 1e8 ? `${(sum / 1e8).toFixed(1)}억원` : `${Math.round(sum / 1e4).toLocaleString()}만원`;
}

function Chip({ pressed, count, onClick, children }: { pressed: boolean; count?: number; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" className="chip" aria-pressed={pressed} onClick={onClick}>
      {children}{count !== undefined && <small>{count}</small>}
    </button>
  );
}

function Grouped({ items, today }: { items: Item[]; today: string }) {
  const groups = new Map<string, Item[]>();
  for (const it of items) {
    const k = it.category || "other";
    groups.set(k, [...(groups.get(k) ?? []), it]);
  }
  const order = [...groups.keys()].sort((a, b) => (groups.get(b)!.length - groups.get(a)!.length));
  return (
    <div className="groups">
      {order.map((k) => (
        <section key={k} className="group">
          <h2>{categoryLabel(k)} <small>{groups.get(k)!.length}</small></h2>
          <ol className="list">{groups.get(k)!.map((it) => <ContestCard key={it.id} it={it} today={today} />)}</ol>
        </section>
      ))}
    </div>
  );
}
