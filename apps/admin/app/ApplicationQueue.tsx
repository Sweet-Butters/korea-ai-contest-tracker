"use client";

import { useEffect, useMemo, useState } from "react";
import {
  APPLICATION_STATUS, REPO, categoryLabel, daysBetween, todayKST,
  type Application, type ApplicationStatus, type Contest, type ContestData,
} from "@radar/shared";

const SITE_ROOT = process.env.NEXT_PUBLIC_SITE_ROOT ?? "";
const PATH = "config/applications.json";

type Api = (path: string, init?: RequestInit) => Promise<Response>;

const b64decode = (s: string) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, "")), (c) => c.charCodeAt(0)));
const b64encode = (s: string) => {
  let bin = "";
  for (const byte of new TextEncoder().encode(s)) bin += String.fromCharCode(byte);
  return btoa(bin);
};

export default function ApplicationQueue({ api, token }: { api: Api; token: string }) {
  const [items, setItems] = useState<Application[] | null>(null);
  const [sha, setSha] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [contests, setContests] = useState<Record<string, Contest>>({});
  const [pending, setPending] = useState<Contest | null>(null); // from ?add=<id>
  const today = todayKST();

  async function load(): Promise<Application[]> {
    const r = await api(`contents/${PATH}?ref=${REPO.branch}`);
    if (r.status === 404) {
      setItems([]);
      setSha(null);
      return [];
    }
    if (!r.ok) {
      setMsg(`지원 목록을 불러오지 못했습니다 (${r.status})`);
      return [];
    }
    const j = await r.json();
    const list: Application[] = JSON.parse(b64decode(j.content)).items ?? [];
    setItems(list);
    setSha(j.sha);
    return list;
  }

  useEffect(() => {
    (async () => {
      const [list, data] = await Promise.all([
        load(),
        fetch(`${SITE_ROOT}/data/contests.json`, { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).catch(() => null),
      ]);
      const byId: Record<string, Contest> = {};
      for (const c of (data as ContestData | null)?.items ?? []) byId[c.id] = c;
      setContests(byId);
      const add = new URLSearchParams(location.search).get("add");
      if (add && byId[add] && !list.some((i) => i.id === add)) setPending(byId[add]);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function save(next: Application[], message: string) {
    setItems(next);
    setMsg("저장 중…");
    const r = await api(`contents/${PATH}`, {
      method: "PUT",
      body: JSON.stringify({
        message,
        content: b64encode(JSON.stringify({ items: next }, null, 1) + "\n"),
        ...(sha ? { sha } : {}),
        branch: REPO.branch,
      }),
    });
    if (!r.ok) return setMsg(r.status === 409 ? "다른 곳에서 먼저 바뀌었습니다. 새로고침하세요." : `저장 실패 (${r.status})`);
    setSha((await r.json()).content.sha);
    setMsg("저장했습니다. 이 PC에서 python -m apply prep 을 돌리면 초안이 만들어집니다.");
  }

  const rows = useMemo(() => {
    const order: ApplicationStatus[] = ["ready", "preparing", "interested", "submitted", "skipped"];
    return [...(items ?? [])].sort((a, b) => {
      const s = order.indexOf(a.status) - order.indexOf(b.status);
      if (s) return s;
      return (contests[a.id]?.applyEnd || "9999").localeCompare(contests[b.id]?.applyEnd || "9999");
    });
  }, [items, contests]);

  if (!items) return <section className="panel"><h2>지원 목록</h2><p className="hint">{msg || "불러오는 중…"}</p></section>;

  return (
    <section className="panel queue">
      <div className="profile-head">
        <div>
          <h2>지원 목록 <small>{items.length}</small></h2>
          <p className="hint">
            사이트 카드의 <b>지원하기</b>를 누르면 여기로 들어옵니다. 이 PC에서{" "}
            <code>python -m apply prep</code> 을 돌리면 요건 정리와 지원서 초안이 <code>drafts/</code> 에 생깁니다.
            자격 확인·동의·최종 제출은 직접 하세요.
          </p>
        </div>
        <span role="status" className="hint">{msg}</span>
      </div>

      {pending && (
        <div className="confirm">
          <div>
            <b>{pending.name}</b>
            <span className="hint">
              {[pending.host, pending.applyEnd && `마감 ${pending.applyEnd}`, categoryLabel(pending.category)].filter(Boolean).join(" · ")}
            </span>
          </div>
          <div className="confirm-actions">
            <button type="button" className="ghost" onClick={() => setPending(null)}>취소</button>
            <button type="button" disabled={!token}
              onClick={() => {
                save([...items, { id: pending.id, name: pending.name, status: "preparing" }],
                  `chore: queue application for ${pending.name}`);
                setPending(null);
              }}>
              지원 목록에 추가
            </button>
          </div>
        </div>
      )}

      {rows.length === 0 && !pending && <p className="hint">아직 확정한 대회가 없습니다.</p>}

      <ul className="queue-list">
        {rows.map((it) => {
          const c = contests[it.id];
          const left = c?.applyEnd ? daysBetween(today, c.applyEnd) : null;
          return (
            <li key={it.id}>
              <span className={`qday${left !== null && left <= 3 ? " urgent" : ""}`}>
                {left === null ? "미정" : left < 0 ? "마감" : `D-${left}`}
              </span>
              <span className="qname">
                {c?.url ? <a href={c.url} target="_blank" rel="noopener">{it.name}</a> : it.name}
                <small>{[c?.host, c?.applyEnd].filter(Boolean).join(" · ")}</small>
              </span>
              <select value={it.status} disabled={!token}
                onChange={(e) => save(items.map((x) => (x.id === it.id ? { ...x, status: e.target.value as ApplicationStatus } : x)),
                  `chore: ${it.name} → ${e.target.value}`)}>
                {(Object.keys(APPLICATION_STATUS) as ApplicationStatus[]).map((s) => (
                  <option key={s} value={s}>{APPLICATION_STATUS[s]}</option>
                ))}
              </select>
              <button type="button" className="ghost" disabled={!token} aria-label="목록에서 빼기"
                onClick={() => save(items.filter((x) => x.id !== it.id), `chore: drop ${it.name}`)}>✕</button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
