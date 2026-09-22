"""Daily collection run: fetch every source, filter by keywords, merge, write data/*.json.

    python -m collector.main            # all sources
    python -m collector.main 씽굿 DACON  # only the named sources (for debugging)
"""
import json
import sys
import time
import urllib3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import http, jev, llm, sources
from .classify import Rules
from .merge import finalize, merge
from .sources import naver_news
from .util import dt, today

urllib3.disable_warnings()  # 올콘 serves an incomplete certificate chain

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contests.json"
META = ROOT / "data" / "meta.json"
NEWS_CACHE = ROOT / "data" / "news_cache.json"
NEWS_CACHE_DAYS = 60
JEV_CACHE = ROOT / "data" / "jev_cache.json"
JEV_RUNS = ROOT / "data" / "jev_runs.jsonl"  # one line of Jev stats per run, for tracking over time


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def run_source(src):
    t0 = time.time()
    try:
        return src, src.fetch(), None, time.time() - t0
    except http.RobotsDisallowed as e:
        return src, [], f"robots.txt disallows {e}", time.time() - t0
    except Exception as e:  # one broken site must not stop the others
        return src, [], f"{type(e).__name__}: {e}", time.time() - t0


def record(item, labels, source_name):
    rec = {k: v for k, v in item.items() if not k.startswith("_") and v not in (None, "")}
    rec.update(labels)
    rec["_source"] = source_name
    return rec


def process_news(candidates, cache, run_date):
    """Resolve news candidates (article, labels) into records, reusing cached LLM answers."""
    todo = [a for a, _ in candidates if a["url"] not in cache]
    use_llm = llm.available()
    if todo and use_llm:
        print(f"  llm: {len(todo)} new articles")
        for url, res in llm.extract(todo).items():
            cache[url] = {"seen": run_date, "result": res, "llm": True}
    for a in todo:
        if a["url"] not in cache and not use_llm:
            cache[a["url"]] = {"seen": run_date, "result": llm.fallback(a), "llm": False}
    out = []
    for a, labels in candidates:
        hit = cache.get(a["url"])
        if not hit or not hit["result"]:
            continue
        res = hit["result"]
        item = {k: res.get(k) for k in ("name", "host", "applyStart", "applyEnd", "eventDates", "prize", "eligibility", "region")}
        item["url"] = a["url"]
        labels = dict(labels, confidence="medium" if hit["llm"] else "low")
        if res.get("region"):
            labels["region"] = res["region"]
        out.append(record(item, labels, naver_news.NAME))
    return out


def main(only=None):
    run_date = today().isoformat()
    rules = Rules.load()
    previous = load(DATA, {"items": []})["items"]
    known_urls = {u for r in previous for u in r.get("sources", {}).values()}
    cache = load(NEWS_CACHE, {})
    jev_cache = load(JEV_CACHE, {})
    selected = [s for s in sources.ALL if not only or s.NAME in only]

    with ThreadPoolExecutor(max_workers=len(selected) or 1) as ex:
        results = list(ex.map(run_source, selected))

    judged = []  # (source, item, rule labels or None, rescuable by Jev)
    for src, raw, err, secs in results:
        for it in raw:
            title = it["name"] or ""
            contest_list = src.CONTEST_LIST and not it.get("_needs_comp_word")
            labels = rules.judge(title, is_contest_list=contest_list, extra_text=it.get("_desc", ""))
            rescuable = (labels is None and src is not naver_news
                         and rules.contest_gate(title, is_contest_list=contest_list))
            if labels or rescuable:
                judged.append((src, it, labels, rescuable))

    use_jev = jev.available()
    jev_stats, outcomes = None, {}
    if use_jev:
        jev_stats = jev.ask_all([dict(it, _source=src.NAME) for src, it, _, _ in judged if src is not naver_news],
                    list(rules.cfg.get("categories", {})), jev_cache, run_date)

    fresh, news, kept = [], [], {}
    for src, it, labels, rescuable in judged:
        if use_jev and src is not naver_news:
            ans = jev_cache.get(jev.cache_key(it["name"] or "", it.get("_desc") or ""))
            labels, outcome = jev.decide(labels, ans, rescuable=rescuable)
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            if labels and not labels.get("region"):
                labels["region"] = rules.region(f"{it['name']} {it.get('_desc', '')}")
        if not labels:
            continue
        kept[src.NAME] = kept.get(src.NAME, 0) + 1
        if src is naver_news:
            news.append((it, labels))
            continue
        if hasattr(src, "enrich") and it["url"] not in known_urls:
            try:
                src.enrich(it)
            except Exception as e:
                print(f"  enrich failed {it['url']}: {e}")
        fresh.append(record(it, labels, src.NAME))

    meta = {}
    for src, raw, err, secs in results:
        n = kept.get(src.NAME, 0)
        meta[src.NAME] = {"fetched": len(raw), "kept": n, "error": err, "seconds": round(secs)}
        print(f"{src.NAME:10} fetched={len(raw):5} kept={n:4} {err or ''}")

    if news:
        fresh += process_news(news, cache, run_date)
    cutoff = (today() - dt.timedelta(days=NEWS_CACHE_DAYS)).isoformat()
    cache = {u: v for u, v in cache.items() if v["seen"] >= cutoff}
    jev_cache = {k: v for k, v in jev_cache.items() if v["seen"] >= cutoff}

    items = finalize(merge(previous, fresh, run_date), run_date)
    dump(DATA, {"updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "items": items})
    dump(META, {"runDate": run_date, "llm": llm.available(), "jev": use_jev, "sources": meta, "total": len(items)})
    dump(NEWS_CACHE, cache)
    if use_jev:
        dump(JEV_CACHE, jev_cache)
        with JEV_RUNS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(dict(runDate=run_date, outcomes=outcomes, **jev_stats), ensure_ascii=False) + "\n")
    print(f"total {len(items)} items")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
