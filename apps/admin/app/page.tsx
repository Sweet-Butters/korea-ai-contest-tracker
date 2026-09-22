"use client";

import { useEffect, useState } from "react";
import { REPO, categoryLabel, type Keywords, type Meta } from "@radar/shared";
import ProfileEditor from "./ProfileEditor";
import WordGroup from "./WordGroup";

const SITE_ROOT = process.env.NEXT_PUBLIC_SITE_ROOT ?? "";
const TOKEN_KEY = "radar-gh-token";

const GROUPS: [keyof Keywords & string, string, string][] = [
  ["aiTerms", "AI 핵심어", "제목·요약에 있으면 AI 대회로 봅니다."],
  ["relatedTerms", "AI 관련어", "AI 대회일 수 있는 말 (데이터, 해커톤 등). 이것만 걸린 항목은 Jev가 한 번 더 확인합니다."],
  ["competitionTerms", "대회 표현", "행사 목록·뉴스에서 대회로 인정하는 말."],
  ["excludeTerms", "제외어", "교육 모집·서포터즈처럼 대회가 아닌 글을 거릅니다."],
  ["newsQueries", "뉴스 검색어", "네이버 뉴스에서 매일 검색하는 문구 (지역별 'OO AI 공모전'은 자동 추가)."],
];

// One line of data/jev_runs.jsonl, written by the collector after each run with Jev enabled.
interface JevRun { runDate: string; outcomes: Record<string, number>; [k: string]: unknown }

const OUTCOME_LABEL: Record<string, string> = {
  agreed_keep: "규칙과 같은 판단",
  recategorized: "분야 재분류",
  rescued: "AI 단어 없이 구제",
  dropped_weak: "약한 키워드 항목 제거",
  dropped_not_contest: "대회 아님으로 제거",
  agreed_drop: "규칙과 같이 제외",
  no_answer: "응답 없음(규칙만)",
};

interface Run { id: number; status: string; conclusion: string | null; event: string; created_at: string; html_url: string }

const b64decode = (s: string) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\n/g, "")), (c) => c.charCodeAt(0)));
const b64encode = (s: string) => {
  let bin = "";
  for (const byte of new TextEncoder().encode(s)) bin += String.fromCharCode(byte);
  return btoa(bin);
};

export default function Admin() {
  const [token, setToken] = useState("");
  const [kw, setKw] = useState<Keywords | null>(null);
  const [sha, setSha] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [msg, setMsg] = useState("");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [jevRuns, setJevRuns] = useState<JevRun[]>([]);

  const api = (path: string, init: RequestInit = {}) =>
    fetch(`https://api.github.com/repos/${REPO.owner}/${REPO.repo}/${path}`, {
      ...init,
      headers: {
        Accept: "application/vnd.github+json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    });

  async function loadKeywords() {
    setMsg("불러오는 중…");
    const r = await api(`contents/config/keywords.json?ref=${REPO.branch}`);
    if (!r.ok) return setMsg(`불러오기 실패 (${r.status})`);
    const j = await r.json();
    setKw(JSON.parse(b64decode(j.content)));
    setSha(j.sha);
    setDirty(false);
    setMsg(token ? "편집 후 저장하세요." : "토큰이 없으면 보기만 가능합니다.");
  }

  async function loadRuns() {
    const r = await api(`actions/workflows/${REPO.workflow}/runs?per_page=6`);
    if (r.ok) setRuns((await r.json()).workflow_runs ?? []);
  }

  useEffect(() => {
    try { setToken(localStorage.getItem(TOKEN_KEY) ?? ""); } catch { /* storage blocked */ }
    fetch(`${SITE_ROOT}/data/meta.json`, { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).then(setMeta).catch(() => {});
    fetch(`${SITE_ROOT}/data/jev_runs.jsonl`, { cache: "no-cache" })
      .then((r) => (r.ok ? r.text() : ""))
      .then((t) => setJevRuns(t.split(/\r?\n/).filter(Boolean).map((l) => JSON.parse(l) as JevRun)))
      .catch(() => {});
  }, []);
  useEffect(() => {
    loadKeywords();
    loadRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function saveToken(v: string) {
    setToken(v);
    try { localStorage.setItem(TOKEN_KEY, v); } catch { /* storage blocked */ }
  }

  const edit = (fn: (k: Keywords) => void) => {
    setKw((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      fn(next);
      return next;
    });
    setDirty(true);
  };

  async function save() {
    if (!kw) return;
    setMsg("저장 중…");
    const r = await api("contents/config/keywords.json", {
      method: "PUT",
      body: JSON.stringify({
        message: "chore: update keywords from admin",
        content: b64encode(JSON.stringify(kw, null, 2) + "\n"),
        sha, branch: REPO.branch,
      }),
    });
    if (!r.ok) return setMsg(r.status === 409 ? "다른 곳에서 먼저 바뀌었습니다. 다시 불러오세요." : `저장 실패 (${r.status})`);
    setSha((await r.json()).content.sha);
    setDirty(false);
    setMsg("저장했습니다. 이 커밋으로 수집이 바로 다시 돌고, 10분쯤 뒤 사이트에 반영됩니다.");
    setTimeout(loadRuns, 4000);
  }

  async function runNow() {
    const r = await api(`actions/workflows/${REPO.workflow}/dispatches`, { method: "POST", body: JSON.stringify({ ref: REPO.branch }) });
    setMsg(r.status === 204 ? "수집을 시작했습니다. 10분 정도 걸립니다." : `실행 실패 (${r.status})`);
    setTimeout(loadRuns, 4000);
  }

  return (
    <>
      <header className="top">
        <div className="wrap top-row">
          <div>
            <h1>키워드 관리</h1>
            <p className="sub">저장하면 <code>config/keywords.json</code>이 커밋되고 GitHub Actions가 바로 다시 수집합니다.</p>
          </div>
          <nav className="top-links">
            <a href={`${SITE_ROOT}/`}>← 대회 목록</a>
            <a href={`https://github.com/${REPO.owner}/${REPO.repo}`} target="_blank" rel="noopener">GitHub</a>
          </nav>
        </div>
      </header>

      <main className="wrap admin">
        <section className="panel token">
          <label htmlFor="token"><b>GitHub 토큰</b></label>
          <p className="hint">
            저장·실행에 필요합니다. <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">Fine-grained token</a>을
            이 저장소만, Contents·Actions <i>Read and write</i> 권한으로 만드세요. 토큰은 이 브라우저에만 저장됩니다.
          </p>
          <div className="token-row">
            <input id="token" type="password" value={token} onChange={(e) => saveToken(e.target.value.trim())} placeholder="github_pat_…" autoComplete="off" />
            <button type="button" className="ghost" onClick={loadKeywords}>다시 불러오기</button>
          </div>
        </section>

        <ProfileEditor api={api} token={token} />

        <h2 className="section-title">수집 키워드</h2>
        <div className="cols">
          <section className="panel kw-panel">
            {!kw && <p className="hint">{msg}</p>}
            {kw && GROUPS.map(([key, title, desc]) => (
              <WordGroup key={key} title={title} desc={desc} words={(kw[key] as string[]) ?? []}
                onChange={(words) => edit((k) => { (k as Record<string, unknown>)[key] = words; })} />
            ))}
            {kw && Object.entries(kw.extraTopics ?? {}).map(([topic, words]) => (
              <WordGroup key={topic} title={`추가 분야: ${categoryLabel(topic)}`} desc="AI가 없어도 수집하는 분야입니다 (사이트에 'AI 외'로 표시)."
                words={words} onChange={(w) => edit((k) => { k.extraTopics[topic] = w; })} />
            ))}
            {kw && <AddTopic onAdd={(name) => edit((k) => {
              k.extraTopics[name] = [name];
              k.categories[name] ??= [name];
            })} />}
          </section>

          <aside className="side">
            <section className="panel">
              <h2>수집 상태</h2>
              {meta ? (
                <>
                  <p className="hint">마지막 수집 {meta.runDate} · 총 {meta.total.toLocaleString()}건 · Gemini {meta.llm ? "켜짐" : "꺼짐"} · Jev {meta.jev ? "켜짐" : "꺼짐"}</p>
                  <table className="src-table">
                    <thead><tr><th>수집원</th><th>가져옴</th><th>남김</th><th>초</th></tr></thead>
                    <tbody>
                      {Object.entries(meta.sources).map(([name, s]) => (
                        <tr key={name} className={s.error ? "err" : ""} title={s.error ?? ""}>
                          <td>{name}</td><td>{s.fetched}</td><td>{s.kept}</td><td>{s.error ? "실패" : s.seconds}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              ) : <p className="hint">수집 기록이 아직 없습니다.</p>}
            </section>
            <section className="panel">
              <h2>Jev 판정 (최근 수집)</h2>
              {jevRuns.length ? <JevPanel runs={jevRuns} /> : <p className="hint">Jev가 켜진 수집 기록이 아직 없습니다.</p>}
            </section>
            <section className="panel">
              <h2>최근 실행</h2>
              <ul className="runs">
                {runs.map((r) => (
                  <li key={r.id}>
                    <a href={r.html_url} target="_blank" rel="noopener">
                      <span className={`run ${r.conclusion ?? r.status}`}>{r.conclusion ?? r.status}</span>
                      {new Date(r.created_at).toLocaleString("ko-KR", { timeZone: "Asia/Seoul", dateStyle: "short", timeStyle: "short" })} · {r.event}
                    </a>
                  </li>
                ))}
                {runs.length === 0 && <li className="hint">실행 기록 없음</li>}
              </ul>
            </section>
          </aside>
        </div>
      </main>

      <div className="save-bar">
        <div className="wrap save-row">
          <span role="status">{msg}</span>
          <button type="button" className="ghost" onClick={runNow} disabled={!token}>지금 수집 실행</button>
          <button type="button" onClick={save} disabled={!token || !dirty}>저장</button>
        </div>
      </div>
    </>
  );
}

function JevPanel({ runs }: { runs: JevRun[] }) {
  const last = runs[runs.length - 1];
  const total = Object.values(last.outcomes).reduce((a, b) => a + b, 0);
  return (
    <>
      <p className="hint">{last.runDate} · 판정 {total.toLocaleString()}건 · 누적 {runs.length}회</p>
      <table className="src-table">
        <tbody>
          {Object.entries(last.outcomes).sort((a, b) => b[1] - a[1]).map(([k, n]) => (
            <tr key={k}><td>{OUTCOME_LABEL[k] ?? k}</td><td>{n.toLocaleString()}</td><td>{total ? Math.round((n / total) * 100) : 0}%</td></tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function AddTopic({ onAdd }: { onAdd: (name: string) => void }) {
  const [name, setName] = useState("");
  return (
    <div className="token-row add-topic">
      <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="새 분야 이름 (예: 헬스케어)" />
      <button type="button" className="ghost" onClick={() => { if (name.trim()) { onAdd(name.trim()); setName(""); } }}>분야 추가</button>
    </div>
  );
}
