"use client";

import { useEffect, useMemo, useState } from "react";
import {
  APPLICATION_STATUS, categoryLabel, daysBetween, todayKST,
  type Application, type ApplicationStatus, type Contest, type ContestData,
} from "@radar/shared";
import { PRIVATE_REPO_NAME, readErrorText, readPrivateJson, writePrivateJson, type Api } from "./github";

const SITE_ROOT = process.env.NEXT_PUBLIC_SITE_ROOT ?? "";
const PATH = "applications.json"; // in the private repo

export default function ApplicationQueue({ api, token }: { api: Api; token: string }) {
  const [items, setItems] = useState<Application[] | null>(null);
  const [sha, setSha] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const [blocked, setBlocked] = useState(""); // no token / no access: show only this
  const [contests, setContests] = useState<Record<string, Contest>>({});
  const [pending, setPending] = useState<Contest | null>(null); // from ?add=<id>
  const [addId, setAddId] = useState<string | null>(null);
  const today = todayKST();

  async function load() {
    const r = await readPrivateJson<{ items?: Application[] }>(api, token, PATH);
    if (r.kind === "missing") {
      setItems([]);
      setSha(null);
      setBlocked("");
      return;
    }
    if (r.kind !== "ok") {
      setItems(null);
      setSha(null);
      setBlocked(readErrorText(r));
      return;
    }
    setItems(r.data.items ?? []);
    setSha(r.sha);
    setBlocked("");
    setMsg("");
  }

  useEffect(() => {
    setAddId(new URLSearchParams(location.search).get("add"));
    fetch(`${SITE_ROOT}/data/contests.json`, { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
      .then((data: ContestData | null) => {
        const byId: Record<string, Contest> = {};
        for (const c of data?.items ?? []) byId[c.id] = c;
        setContests(byId);
      });
  }, []);
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  // A card's "지원하기" link arrives as ?add=<id>; offer it once the private list is readable.
  useEffect(() => {
    if (addId && items && contests[addId] && !items.some((i) => i.id === addId)) setPending(contests[addId]);
  }, [addId, items, contests]);

  async function save(next: Application[], message: string) {
    const before = items;
    setItems(next);
    setMsg("저장 중…");
    const r = await writePrivateJson(api, PATH, { items: next }, sha, message, 1);
    if (!r.ok) {
      setItems(before);
      return setMsg(r.error);
    }
    setSha(r.sha);
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

  if (!items) {
    return (
      <section className="panel">
        <h2>지원 목록</h2>
        <p className={blocked ? "empty-note" : "hint"}>{blocked || msg || "불러오는 중…"}</p>
      </section>
    );
  }

  return (
    <section className="panel queue">
      <div className="profile-head">
        <div>
          <h2>지원 목록 <small>{items.length}</small></h2>
          <p className="hint">
            사이트 카드의 <b>지원하기</b>를 누르면 여기로 들어옵니다. 이 PC에서{" "}
            <code>python -m apply prep</code> 을 돌리면 요건 정리와 지원서 초안이 <code>drafts/</code> 에 생깁니다.
            자격 확인·동의·최종 제출은 직접 하세요. 목록은 비공개 저장소 <code>{PRIVATE_REPO_NAME}</code>에 저장됩니다.
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
