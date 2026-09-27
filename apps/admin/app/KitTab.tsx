"use client";

import { useEffect, useMemo, useState } from "react";
import { byteCounts, sensitiveKinds, type Kit } from "@radar/shared";
import { PRIVATE_REPO_NAME, readErrorText, readPrivateJson, writePrivateJson, type Api } from "./github";

const PATH = "kit.json"; // in the private repo

type Path = (string | number)[];
type Filter = "all" | "blind" | "flagged";

interface Snip {
  key: string;
  path: Path;
  label: string;
  text: string;
  /** Set when the whole section is personal (profile, a bio marked containsSchool). */
  forced?: string[];
  limitBytes?: number;
  tone?: "caveat";
}

interface Group {
  key: string;
  title: string;
  link?: string;
  note?: string;
  snips: Snip[];
  /** Extra "copy all" snippet built from several lines (not editable itself). */
  joined?: { label: string; text: string }[];
}

function setIn<T>(obj: T, path: Path, value: unknown): T {
  const next = structuredClone(obj) as unknown as Record<string | number, unknown>;
  let o = next;
  for (const k of path.slice(0, -1)) o = o[k] as Record<string | number, unknown>;
  o[path[path.length - 1]] = value;
  return next as unknown as T;
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Clipboard API is blocked (insecure context, permissions): fall back to a hidden textarea.
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}

function groups(kit: Kit): Group[] {
  const out: Group[] = [];
  const m = kit.motto;
  out.push({
    key: "motto", title: "모토와 한 줄 소개",
    snips: [
      { key: "m-ko", path: ["motto", "ko"], label: "모토 (한국어)", text: m.ko },
      { key: "m-en", path: ["motto", "en"], label: "모토 (영어)", text: m.en },
      { key: "m-one", path: ["motto", "oneLiner"], label: "한 줄 소개", text: m.oneLiner },
      { key: "m-thr", path: ["motto", "throughline"], label: "관통하는 이야기", text: m.throughline },
      { key: "m-thn", path: ["motto", "throughlineNote"], label: "관통하는 이야기 (설명)", text: m.throughlineNote },
    ],
  });
  const pf = kit.profile;
  const forced = [...(pf.containsSchool ? ["학교·전공"] : []), ...(pf.containsPersonal ? ["개인정보"] : [])];
  out.push({
    key: "profile", title: pf.title, note: pf.note,
    snips: pf.lines.map((t, i) => ({ key: `p-${i}`, path: ["profile", "lines", i], label: `프로필 ${i + 1}`, text: t, forced })),
    joined: [{ label: "프로필 전체", text: pf.lines.join("\n") }],
  });
  kit.projects.forEach((p, pi) => {
    const base: Path = ["projects", pi];
    const snips: Snip[] = [];
    if (p.oneLiner) snips.push({ key: `${p.id}-one`, path: [...base, "oneLiner"], label: "한 문장", text: p.oneLiner });
    p.threeLines.forEach((t, i) => snips.push({ key: `${p.id}-3-${i}`, path: [...base, "threeLines", i], label: `세 줄 · ${i + 1}`, text: t }));
    p.decisions.forEach((t, i) => snips.push({ key: `${p.id}-d-${i}`, path: [...base, "decisions", i], label: `내가 한 판단 · ${i + 1}`, text: t }));
    (p.materials ?? []).forEach((t, i) => snips.push({ key: `${p.id}-m-${i}`, path: [...base, "materials", i], label: `재료 · ${i + 1}`, text: t }));
    p.numbers.forEach((t, i) => snips.push({ key: `${p.id}-n-${i}`, path: [...base, "numbers", i], label: `숫자${p.numbersNote ? `(${p.numbersNote})` : ""} · ${i + 1}`, text: t }));
    p.caveats.forEach((t, i) => snips.push({ key: `${p.id}-c-${i}`, path: [...base, "caveats", i], label: "주의", text: t, tone: "caveat" }));
    const joined: { label: string; text: string }[] = [];
    if (p.threeLines.length) joined.push({ label: "세 줄 전체", text: p.threeLines.join("\n") });
    if (p.numbers.length > 1) joined.push({ label: "숫자 한 줄", text: p.numbers.join(" · ") });
    out.push({ key: p.id, title: p.title, link: p.link || undefined, snips, joined });
  });
  out.push({
    key: "bios", title: "길이별 자기소개",
    snips: kit.bios.map((b, i) => ({
      key: `b-${b.id}`, path: ["bios", i, "text"], label: b.label, text: b.text,
      forced: b.containsSchool ? ["학교·전공"] : undefined, limitBytes: b.limitBytes,
    })),
  });
  return out;
}

function Counts({ text, limitBytes }: { text: string; limitBytes?: number }) {
  const c = byteCounts(text);
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  const over = limitBytes !== undefined && c.eucKr > limitBytes;
  return (
    <span className={`counts${over ? " over" : ""}`} aria-live="polite">
      EUC-KR {c.eucKr}B{limitBytes !== undefined && ` / ${limitBytes}B`} · UTF-8 {c.utf8}B · {c.chars}자 · {words}단어
    </span>
  );
}

function SnipRow({ s, editing, onEdit, onChange, onDone }: {
  s: Snip; editing: boolean; onEdit: () => void; onChange: (v: string) => void; onDone: () => void;
}) {
  const [copied, setCopied] = useState<"" | "ok" | "fail">("");
  const kinds = [...new Set([...(s.forced ?? []), ...sensitiveKinds(s.text)])];
  async function copy() {
    setCopied((await copyText(s.text)) ? "ok" : "fail");
    setTimeout(() => setCopied(""), 1500);
  }
  return (
    <li className={`snip${s.tone === "caveat" ? " caveat" : ""}`}>
      <div className="snip-head">
        <span className="snip-label">{s.label}</span>
        {kinds.length
          ? <span className="badge warn" title="블라인드 심사에 내면 안 되는 정보가 들어 있습니다.">⚠ {kinds.join("·")} 포함</span>
          : <span className="badge blind">블라인드용</span>}
      </div>
      {editing ? (
        <textarea value={s.text} onChange={(e) => onChange(e.target.value)} rows={Math.min(10, Math.max(2, Math.ceil(s.text.length / 60)))} autoFocus />
      ) : (
        <p className="snip-text">{s.text}</p>
      )}
      <div className="snip-foot">
        <Counts text={s.text} limitBytes={s.limitBytes} />
        <span className="snip-actions">
          {editing
            ? <button type="button" className="ghost" onClick={onDone}>완료</button>
            : <button type="button" className="ghost" onClick={onEdit}>수정</button>}
          <button type="button" onClick={copy} aria-label={`${s.label} 복사`}>
            {copied === "ok" ? "복사됨" : copied === "fail" ? "복사 실패" : "복사"}
          </button>
        </span>
      </div>
    </li>
  );
}

function JoinedRow({ label, text }: { label: string; text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button type="button" className="ghost joined" onClick={async () => {
      if (await copyText(text)) { setCopied(true); setTimeout(() => setCopied(false), 1500); }
    }}>
      {copied ? "복사됨" : `${label} 복사`} <small>{byteCounts(text).eucKr}B</small>
    </button>
  );
}

export default function KitTab({ api, token }: { api: Api; token: string }) {
  const [kit, setKit] = useState<Kit | null>(null);
  const [sha, setSha] = useState<string | null>(null);
  const [blocked, setBlocked] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  async function load() {
    setMsg("불러오는 중…");
    setErr(false);
    const r = await readPrivateJson<Kit>(api, token, PATH);
    if (r.kind === "ok") {
      setKit(r.data);
      setSha(r.sha);
      setBlocked("");
      setDirty(false);
      setEditing(null);
      return setMsg("");
    }
    setKit(null);
    setSha(null);
    setMsg("");
    setBlocked(r.kind === "missing"
      ? `${PRIVATE_REPO_NAME} 저장소에 ${PATH} 파일이 없습니다.`
      : readErrorText(r));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const all = useMemo(() => (kit ? groups(kit) : []), [kit]);
  const shown = useMemo(() => {
    const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return all.map((g) => ({
      ...g,
      snips: g.snips.filter((s) => {
        const flagged = (s.forced?.length ?? 0) > 0 || sensitiveKinds(s.text).length > 0;
        if (filter === "blind" && flagged) return false;
        if (filter === "flagged" && !flagged) return false;
        const hay = `${g.title} ${s.label} ${s.text}`.toLowerCase();
        return words.every((w) => hay.includes(w));
      }),
    })).filter((g) => g.snips.length > 0);
  }, [all, q, filter]);
  const total = all.reduce((n, g) => n + g.snips.length, 0);
  const count = shown.reduce((n, g) => n + g.snips.length, 0);

  function change(path: Path, v: unknown) {
    setKit((k) => (k ? setIn(k, path, v) : k));
    setDirty(true);
  }

  async function save() {
    if (!kit) return;
    setSaving(true);
    setMsg("저장 중…");
    setErr(false);
    const r = await writePrivateJson(api, PATH, kit, sha, "chore: update application kit from admin");
    setSaving(false);
    if (!r.ok) {
      setErr(true);
      return setMsg(r.error);
    }
    setSha(r.sha);
    setDirty(false);
    setEditing(null);
    setMsg(`${PRIVATE_REPO_NAME}에 저장했습니다.`);
  }

  function reload() {
    if (dirty && !confirm("저장하지 않은 수정 내용이 사라집니다. 다시 불러올까요?")) return;
    load();
  }

  if (!kit) {
    return (
      <section className="panel kit-empty">
        <h2>지원서 재료함</h2>
        <p className={blocked ? "empty-note" : "hint"}>{blocked || msg || "불러오는 중…"}</p>
        {blocked && (
          <p className="hint">
            재료함에는 학교·연락처 같은 개인정보가 들어 있어 공개 사본을 두지 않습니다. 토큰이 있어야만 보입니다.
          </p>
        )}
      </section>
    );
  }

  return (
    <>
      <section className="panel kit-bar">
        <div className="kit-tools">
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="검색 (예: SCPC, 숫자, 블라인드)" aria-label="재료 검색" />
          <div className="seg" role="group" aria-label="보기">
            {([["all", "전체"], ["blind", "블라인드용만"], ["flagged", "개인정보 포함만"]] as [Filter, string][]).map(([k, label]) => (
              <button key={k} type="button" className={filter === k ? "on" : ""} aria-pressed={filter === k} onClick={() => setFilter(k)}>{label}</button>
            ))}
          </div>
        </div>
        <div className="kit-save">
          <span role="status" className={err ? "err" : ""}>{msg || `${count}/${total}개 · ${kit.asOf} 기준`}</span>
          <button type="button" className="ghost" onClick={reload}>다시 불러오기</button>
          <button type="button" onClick={save} disabled={!dirty || saving}>{dirty ? "저장" : "저장됨"}</button>
        </div>
      </section>

      {!q && filter === "all" && (
        <section className="panel kit-intro">
          {kit.intro.map((t, i) => <p key={i} className="hint">{t}</p>)}
          <ul className="kit-links">
            {kit.links.map((l) => (
              <li key={l.url}><a href={l.url} target="_blank" rel="noopener">{l.label}</a> <JoinedRow label="링크" text={l.url} /></li>
            ))}
          </ul>
        </section>
      )}

      {shown.map((g) => (
        <section key={g.key} className="panel kit-group">
          <div className="kit-group-head">
            <h2>{g.title}</h2>
            {g.link && <a className="hint" href={g.link} target="_blank" rel="noopener">{g.link.replace(/^https:\/\//, "")}</a>}
          </div>
          {g.note && <p className="hint">{g.note}</p>}
          {g.joined && g.joined.length > 0 && !q && filter === "all" && (
            <div className="joined-row">{g.joined.map((j) => <JoinedRow key={j.label} {...j} />)}</div>
          )}
          <ul className="snips">
            {g.snips.map((s) => (
              <SnipRow key={s.key} s={s} editing={editing === s.key}
                onEdit={() => setEditing(s.key)} onDone={() => setEditing(null)}
                onChange={(v) => change(s.path, v)} />
            ))}
          </ul>
        </section>
      ))}
      {shown.length === 0 && <section className="panel"><p className="hint">맞는 재료가 없습니다.</p></section>}

      {!q && filter === "all" && (
        <section className="panel kit-group">
          <h2>쓰기 전에 확인할 것</h2>
          <ul className="checklist">
            {kit.checklist.map((c, i) => (
              <li key={i}>
                <label>
                  <input type="checkbox" checked={c.done} onChange={(e) => change(["checklist", i, "done"], e.target.checked)} />
                  {c.text}
                </label>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
