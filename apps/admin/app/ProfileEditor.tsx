"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CATEGORY_LABEL, DEFAULT_PROFILE, fitScore, formatKRW, todayKST,
  type ContestData, type Profile,
} from "@radar/shared";
import WordGroup from "./WordGroup";
import { PRIVATE_REPO_NAME, readErrorText, readPrivateJson, writePrivateJson, type Api } from "./github";

const SITE_ROOT = process.env.NEXT_PUBLIC_SITE_ROOT ?? "";
const PATH = "profile.json"; // in the private repo

const WORD_FIELDS: [keyof Profile, string, string][] = [
  ["interests", "관심 주제", "대회 이름에 들어 있으면 점수를 더합니다 (하나당 15점, 최대 30점)."],
  ["eligibility", "내 참가 자격", "공고의 참가 대상에 이 말이 있으면 참가 가능으로 봅니다."],
  ["notEligible", "참가 불가 표현", "내 자격 표현이 없고 이 말만 있으면 제외합니다 (예: 청소년 전용)."],
  ["regions", "오프라인 참석 가능 지역", "지역이 없거나 온라인인 대회는 항상 통과합니다."],
  ["exclude", "보고 싶지 않은 단어", "대회 이름에 있으면 추천에서 뺍니다."],
];

export default function ProfileEditor({ api, token }: { api: Api; token: string }) {
  const [p, setP] = useState<Profile | null>(null);
  const [sha, setSha] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [msg, setMsg] = useState("");
  const [blocked, setBlocked] = useState(""); // no token / no access: show only this
  const [data, setData] = useState<ContestData | null>(null);
  const today = todayKST();

  async function load() {
    setMsg("불러오는 중…");
    const r = await readPrivateJson<Partial<Profile> & { _comment?: string }>(api, token, PATH);
    if (r.kind === "missing") {
      setP({ ...DEFAULT_PROFILE });
      setSha(null);
      setBlocked("");
      return setMsg("아직 저장된 조건이 없어 기본값을 보여줍니다.");
    }
    if (r.kind !== "ok") {
      setP(null);
      setSha(null);
      setBlocked(readErrorText(r));
      return setMsg("");
    }
    const { _comment, ...rest } = r.data;
    void _comment;
    setP({ ...DEFAULT_PROFILE, ...rest });
    setSha(r.sha);
    setBlocked("");
    setDirty(false);
    setMsg("");
  }

  useEffect(() => {
    fetch(`${SITE_ROOT}/data/contests.json`, { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).then(setData).catch(() => {});
  }, []);
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const edit = (patch: Partial<Profile>) => {
    setP((prev) => (prev ? { ...prev, ...patch } : prev));
    setDirty(true);
  };

  // Live preview with the unsaved profile: what the main site would recommend.
  const preview = useMemo(() => {
    if (!p || !data) return null;
    const scored = data.items
      .filter((it) => it.status === "open" || it.status === "upcoming")
      .map((it) => ({ it, fit: fitScore(it, p, today) }));
    const rec = scored.filter((x) => x.fit.recommended).sort((a, b) => b.fit.score - a.fit.score);
    const blockedBy: Record<string, number> = {};
    for (const x of scored) if (x.fit.blocked) blockedBy[x.fit.blocked] = (blockedBy[x.fit.blocked] ?? 0) + 1;
    return { total: scored.length, rec, blocked: blockedBy };
  }, [p, data, today]);

  async function save() {
    if (!p) return;
    setMsg("저장 중…");
    const body = {
      _comment: "추천 조건. /admin 의 '내 추천 조건'에서 편집합니다. 비공개 저장소(private-kit)에 있고, 공개 사이트에는 대회별 추천 점수만 실립니다.",
      ...p,
    };
    const r = await writePrivateJson(api, PATH, body, sha, "chore: update recommendation profile from admin");
    if (!r.ok) return setMsg(r.error);
    setSha(r.sha);
    setDirty(false);
    setMsg("저장했습니다. 다음 수집(매일 06:00) 또는 '지금 수집 실행' 뒤 메인 사이트 점수에 반영됩니다.");
  }

  if (!p) {
    return (
      <section className="panel">
        <h2>내 추천 조건</h2>
        <p className={blocked ? "empty-note" : "hint"}>{blocked || msg || "불러오는 중…"}</p>
      </section>
    );
  }

  return (
    <section className="panel profile">
      <div className="profile-head">
        <div>
          <h2>내 추천 조건</h2>
          <p className="hint">
            조건에 맞는 대회에 메인 사이트가 <b>추천 점수</b>를 붙이고, &quot;나에게 맞는 대회만&quot; 필터와 &quot;나에게 맞는 순&quot; 정렬에 씁니다.
            조건은 비공개 저장소 <code>{PRIVATE_REPO_NAME}</code>에 저장되고, 공개 사이트에는 대회별 점수만 실립니다.
          </p>
        </div>
        <div className="profile-save">
          <span role="status">{msg}</span>
          <button type="button" onClick={save} disabled={!token || !dirty}>추천 조건 저장</button>
        </div>
      </div>

      <div className="cols">
        <div className="kw-panel">
          <div className="kw-group">
            <h3>선호 분야 <small>30점</small></h3>
            <div className="kw-list">
              {Object.entries(CATEGORY_LABEL).map(([k, label]) => (
                <label key={k} className="check">
                  <input type="checkbox" checked={p.categories.includes(k)}
                    onChange={(e) => edit({ categories: e.target.checked ? [...p.categories, k] : p.categories.filter((c) => c !== k) })} />
                  {label}
                </label>
              ))}
            </div>
          </div>
          {WORD_FIELDS.map(([key, title, desc]) => (
            <WordGroup key={key} title={title} desc={desc} words={p[key] as string[]} onChange={(w) => edit({ [key]: w } as Partial<Profile>)} />
          ))}
          <div className="kw-group nums">
            <label>최소 상금 <input type="number" min={0} step={50} value={p.minPrizeManwon} onChange={(e) => edit({ minPrizeManwon: +e.target.value })} /> 만원 이상이면 가산점</label>
            <label>마감까지 <input type="number" min={0} value={p.minDaysLeft} onChange={(e) => edit({ minDaysLeft: +e.target.value })} /> 일 이상 남은 대회만</label>
            <label>추천 기준 <input type="number" min={0} max={100} step={5} value={p.threshold} onChange={(e) => edit({ threshold: +e.target.value })} /> 점 이상</label>
          </div>
        </div>

        <aside className="preview">
          <h3>미리보기 {dirty && <small>(저장 전)</small>}</h3>
          {preview ? (
            <>
              <p className="hint">
                접수중·예정 {preview.total}건 중 <b>{preview.rec.length}건 추천</b>
                {Object.keys(preview.blocked).length > 0 && ` · 제외: ${Object.entries(preview.blocked).map(([k, n]) => `${k} ${n}`).join(", ")}`}
              </p>
              <ol className="rec-list">
                {preview.rec.slice(0, 15).map(({ it, fit }) => (
                  <li key={it.id}>
                    <span className="score">{fit.score}</span>
                    <span>
                      {it.url ? <a href={it.url} target="_blank" rel="noopener">{it.name}</a> : it.name}
                      <small>{[it.applyEnd && `~${it.applyEnd.slice(5)}`, ...fit.reasons].filter(Boolean).join(" · ")}</small>
                    </span>
                  </li>
                ))}
              </ol>
              {preview.rec.length === 0 && <p className="hint">추천 기준을 낮추거나 관심 주제를 늘려보세요.</p>}
              <p className="hint">점수: 선호 분야 30 · 관심 주제 최대 30 · 상금 10~15 · 참석 가능 지역 10 · AI 확신도(Jev) 최대 15{p.minPrizeManwon > 0 && ` · 상금 기준 ${formatKRW(p.minPrizeManwon * 1e4)}`}</p>
            </>
          ) : <p className="hint">대회 데이터를 불러오는 중…</p>}
        </aside>
      </div>
    </section>
  );
}
