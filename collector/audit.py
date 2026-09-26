"""Check stored deadlines against the source listings, and publish the hit rate.

Wrong deadlines are the one failure that actually costs the user a contest, so the site should
say how often they are right rather than just how many items it holds.

    python -m collector.audit [n]

Re-fetches the sources that published the sampled contests, compares their deadline with the one
we show, and appends a row to data/audit.json. The site footer and /admin show the latest rate.
"""
import json
import random
import sys
from pathlib import Path

from . import sources
from .main import DATA, dump, load
from .util import today

AUDIT = Path(__file__).resolve().parent.parent / "data" / "audit.json"
SAMPLE = 30
KEEP_ROWS = 52  # about a year of weekly runs


def _fresh_deadlines(names: set[str]) -> dict[str, dict[str, str]]:
    """{source name: {url: applyEnd}} for the sources that published the sampled items."""
    out: dict[str, dict[str, str]] = {}
    for src in sources.ALL:
        if src.NAME not in names:
            continue
        try:
            out[src.NAME] = {it["url"]: it.get("applyEnd") for it in src.fetch() if it.get("url")}
        except Exception as e:
            print(f"  {src.NAME}: {type(e).__name__}: {str(e)[:80]}")
    return out


def main(n: int = SAMPLE):
    items = load(DATA, {"items": []})["items"]
    pool = [r for r in items if r.get("applyEnd") and r.get("status") == "open" and r.get("endBySource")]
    if not pool:
        return print("검증할 항목이 없습니다.")
    random.seed()
    sample = random.sample(pool, min(n, len(pool)))
    names = {s for r in sample for s in r.get("endBySource", {})}
    print(f"{len(sample)}건 표본, 수집원 {len(names)}곳 재확인")
    fresh = _fresh_deadlines(names)

    checked = agree = 0
    misses = []
    for r in sample:
        for src, url in r.get("sources", {}).items():
            now = fresh.get(src, {}).get(url)
            if not now:
                continue
            checked += 1
            if now == r["applyEnd"]:
                agree += 1
            else:
                misses.append({"id": r["id"], "name": r["name"][:60], "source": src,
                               "shown": r["applyEnd"], "source_says": now})
            break  # one check per contest: its highest-ranked source

    rate = round(agree / checked, 3) if checked else None
    row = {"date": today().isoformat(), "sampled": len(sample), "checked": checked,
           "agree": agree, "rate": rate, "misses": misses[:10]}
    rows = load(AUDIT, {"rows": []})["rows"]
    rows = [r for r in rows if r["date"] != row["date"]] + [row]
    dump(AUDIT, {"rows": rows[-KEEP_ROWS:]})
    print(f"대조 {checked}건 중 일치 {agree}건" + (f" ({rate:.1%})" if rate is not None else ""))
    for m in misses[:5]:
        print(f"  다름: {m['name']} — 사이트 {m['shown']} / {m['source']} {m['source_says']}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if sys.argv[1:] else SAMPLE)
