"use client";

import { useState } from "react";

export default function WordGroup({ title, desc, words, onChange }: { title: string; desc: string; words: string[]; onChange: (w: string[]) => void }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim();
    if (v && !words.includes(v)) onChange([...words, v]);
    setDraft("");
  };
  return (
    <div className="kw-group">
      <h3>{title} <small>{words.length}</small></h3>
      <p className="hint">{desc}</p>
      <div className="kw-list">
        {words.map((w) => (
          <span className="kw" key={w}>
            {w}
            <button type="button" aria-label={`${w} 삭제`} onClick={() => onChange(words.filter((x) => x !== w))}>×</button>
          </span>
        ))}
        <input type="text" className="kw-add" value={draft} placeholder="+ 추가 (Enter)"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) { e.preventDefault(); add(); } }} />
      </div>
    </div>
  );
}
