"use client";

import { useState } from "react";
import { categoryLabel } from "@radar/shared";
import type { Item } from "./Explorer";

type Kind = "deadline" | "start" | "event";
interface Entry { it: Item; kind: Kind }

const KIND_LABEL: Record<Kind, string> = { deadline: "마감", start: "접수 시작", event: "본선·결선" };
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

function entriesByDate(items: Item[]) {
  const map = new Map<string, Entry[]>();
  const add = (d: string | null | undefined, e: Entry) => {
    if (!d) return;
    map.set(d, [...(map.get(d) ?? []), e]);
  };
  for (const it of items) {
    add(it.applyEnd, { it, kind: "deadline" });
    if (it.status === "upcoming") add(it.applyStart, { it, kind: "start" });
    if (it.lastEvent && it.lastEvent !== it.applyEnd) add(it.lastEvent, { it, kind: "event" });
  }
  return map;
}

const iso = (y: number, m: number, d: number) => `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

export default function CalendarView({ items, today }: { items: Item[]; today: string }) {
  const [ym, setYm] = useState(() => [+today.slice(0, 4), +today.slice(5, 7) - 1] as [number, number]);
  const [y, m] = ym;
  const byDate = entriesByDate(items);
  const first = new Date(Date.UTC(y, m, 1)).getUTCDay();
  const daysIn = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
  const cells: (number | null)[] = [...Array(first).fill(null), ...Array.from({ length: daysIn }, (_, i) => i + 1)];
  while (cells.length % 7) cells.push(null);
  const move = (delta: number) => setYm(([yy, mm]) => {
    const d = new Date(Date.UTC(yy, mm + delta, 1));
    return [d.getUTCFullYear(), d.getUTCMonth()];
  });

  // Agenda for the same month, used on narrow screens where a 7-column grid is unreadable.
  const monthDays = Array.from({ length: daysIn }, (_, i) => iso(y, m, i + 1)).filter((d) => byDate.has(d));

  return (
    <section className="calendar" aria-label="일정표">
      <div className="cal-head">
        <button type="button" className="ghost" onClick={() => move(-1)} aria-label="이전 달">‹</button>
        <h2>{y}년 {m + 1}월</h2>
        <button type="button" className="ghost" onClick={() => move(1)} aria-label="다음 달">›</button>
        <span className="cal-legend">
          {(Object.keys(KIND_LABEL) as Kind[]).map((k) => <span key={k} className={`ev ${k}`}>{KIND_LABEL[k]}</span>)}
        </span>
      </div>

      <div className="cal-grid">
        {WEEKDAYS.map((w) => <div key={w} className="cal-wd">{w}</div>)}
        {cells.map((d, i) => {
          const key = d ? iso(y, m, d) : `empty-${i}`;
          const list = d ? byDate.get(key) ?? [] : [];
          return (
            <div key={key} className={`cal-cell${d ? "" : " blank"}${key === today ? " today" : ""}`}>
              {d && <span className="cal-day">{d}</span>}
              {list.slice(0, 4).map((e, j) => <EntryLink key={j} e={e} />)}
              {list.length > 4 && <span className="cal-more">+{list.length - 4}</span>}
            </div>
          );
        })}
      </div>

      <ol className="agenda">
        {monthDays.length === 0 && <li className="empty">이 달에는 일정이 없습니다.</li>}
        {monthDays.map((d) => (
          <li key={d}>
            <h3 className={d === today ? "today" : ""}>{+d.slice(5, 7)}월 {+d.slice(8, 10)}일 ({WEEKDAYS[new Date(d + "T00:00:00Z").getUTCDay()]})</h3>
            <ul>
              {byDate.get(d)!.map((e, j) => (
                <li key={j}><EntryLink e={e} full /></li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </section>
  );
}

function EntryLink({ e, full }: { e: Entry; full?: boolean }) {
  const label = full ? `${KIND_LABEL[e.kind]} · ${e.it.name} (${categoryLabel(e.it.category)})` : e.it.name;
  const props = { className: `ev ${e.kind}`, title: `${KIND_LABEL[e.kind]}: ${e.it.name}` };
  return e.it.url ? <a {...props} href={e.it.url} target="_blank" rel="noopener">{label}</a> : <span {...props}>{label}</span>;
}
