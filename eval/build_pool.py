"""Step 1: fetch every source once and record what the keyword rules decide, then draw a stratified sample.

    python -m eval.build_pool            # writes eval/pool.json and eval/sample.json

Strata are defined by the rules alone (not by Jev), so sampling does not favour either system:
  strong   rules kept it on a strong AI word (AI, 인공지능, LLM ...) or a topic
  weak     rules kept it on a weak word only (데이터, SW, 코딩 ...)
  dropped  a contest listing the rules dropped for having no AI word (Jev may rescue these)
Each stratum gets the same number of samples; metrics.py reweights by stratum size.
"""
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from collector.classify import Rules
from collector.main import run_source
from collector.sources import ALL, naver_news

HERE = Path(__file__).resolve().parent
PER_STRATUM = int(sys.argv[1]) if len(sys.argv) > 1 else 100
SEED = 20260922


def main():
    rules = Rules.load()
    selected = [s for s in ALL if s is not naver_news]  # news goes through Gemini, not Jev
    with ThreadPoolExecutor(max_workers=len(selected)) as ex:
        results = list(ex.map(run_source, selected))

    pool, seen = [], set()
    for src, raw, err, _ in results:
        print(f"{src.NAME:10} fetched={len(raw):5} {err or ''}")
        for it in raw:
            title = it["name"] or ""
            if not title or (title, src.NAME) in seen:
                continue
            seen.add((title, src.NAME))
            contest_list = src.CONTEST_LIST and not it.get("_needs_comp_word")
            labels = rules.judge(title, is_contest_list=contest_list, extra_text=it.get("_desc", ""))
            if labels:
                stratum = "weak" if labels["confidence"] == "medium" else "strong"
            elif rules.contest_gate(title, is_contest_list=contest_list):
                stratum = "dropped"
            else:
                continue  # excluded by the rules and never sent to Jev either
            pool.append({
                "title": title, "desc": (it.get("_desc") or "")[:800], "site": src.NAME, "url": it["url"],
                "host": it.get("host"), "eligibility": it.get("eligibility"), "prize": it.get("prize"),
                "stratum": stratum, "rules": labels,
            })

    sizes = {s: sum(1 for p in pool if p["stratum"] == s) for s in ("strong", "weak", "dropped")}
    rng = random.Random(SEED)
    sample = []
    for s in sizes:
        members = [p for p in pool if p["stratum"] == s]
        sample += rng.sample(members, min(PER_STRATUM, len(members)))
    for i, p in enumerate(sample):
        p["id"] = f"s{i:03d}"

    (HERE / "pool.json").write_text(json.dumps({"sizes": sizes, "items": pool}, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "sample.json").write_text(json.dumps({"sizes": sizes, "seed": SEED, "items": sample}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"pool {len(pool)} {sizes} -> sample {len(sample)}")


if __name__ == "__main__":
    main()
