import { categoryLabel, daysBetween, formatKRW, shortDate } from "@radar/shared";
import type { Item } from "./Explorer";

function badge(it: Item, today: string): { text: string; cls: string } {
  if (it.status === "open" && it.applyEnd) {
    const d = daysBetween(today, it.applyEnd);
    if (d < 0) return { text: "마감", cls: "muted" };
    return { text: d === 0 ? "오늘 마감" : `D-${d}`, cls: d <= 3 ? "urgent" : d <= 7 ? "soon" : "" };
  }
  if (it.status === "open") return { text: "마감일 미정", cls: "muted" };
  if (it.status === "upcoming") return { text: it.applyStart ? `${shortDate(it.applyStart)} 접수 시작` : "접수예정", cls: "muted" };
  if (it.status === "in_progress") return { text: it.lastEvent ? `본선 ~${shortDate(it.lastEvent)}` : "진행중", cls: "muted" };
  return { text: "마감", cls: "muted" };
}

export default function ContestCard({ it, today }: { it: Item; today: string }) {
  const b = badge(it, today);
  const period = it.applyStart || it.applyEnd ? `${shortDate(it.applyStart)} ~ ${it.applyEnd ? shortDate(it.applyEnd) : "미정"}` : null;
  const prize = it.prizeKRW ? `${formatKRW(it.prizeKRW)}${it.prize && !/^[\d,.\s만억원]+$/.test(it.prize) ? ` · ${it.prize}` : ""}` : it.prize;
  const rows: [string, string | null | undefined][] = [
    ["접수", period], ["일정", it.eventDates], ["상금", prize], ["대상", it.eligibility],
  ];
  const links = Object.entries(it.sources).filter(([n, u]) => n !== "초기조사" && u);
  return (
    <li className="card">
      <div className="card-top">
        <span className={`dday ${b.cls}`}>{b.text}</span>
        {it.fit.recommended && (
          <span className="tag fit" title={`추천 이유: ${it.fit.reasons.join(", ") || "조건 충족"}`}>추천 {it.fit.score}</span>
        )}
        <span className="tag">{categoryLabel(it.category)}</span>
        {it.prizeKRW && it.prizeKRW >= 1e7 && <span className="tag money">{formatKRW(it.prizeKRW)}</span>}
        {it.confidence === "low" && <span className="tag low">미확인</span>}
        {it.aiRelated === false && <span className="tag">AI 외</span>}
        {it.jev !== undefined && <span className="tag jev" title="TypeSafe Jev가 판정한 AI 대회일 확률">Jev {Math.round(it.jev * 100)}%</span>}
      </div>
      <h3>{it.url ? <a href={it.url} target="_blank" rel="noopener">{it.name}</a> : it.name}</h3>
      {(it.host || it.region) && <p className="host">{[it.host, it.region].filter(Boolean).join(" · ")}</p>}
      <dl className="meta">
        {rows.filter(([, v]) => v).map(([k, v]) => (
          <div key={k}><dt>{k}</dt><dd>{String(v).slice(0, 140)}</dd></div>
        ))}
      </dl>
      {links.length > 0 && (
        <p className="srcs">
          출처{" "}
          {links.slice(0, 5).map(([n, u]) => <a key={n} href={u!} target="_blank" rel="noopener">{n}</a>)}
        </p>
      )}
    </li>
  );
}
