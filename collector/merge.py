"""Deduplicates contests across sources and runs, and computes their status."""
import hashlib
import re
from difflib import SequenceMatcher

from .util import dates_in

# When sources disagree on a field, the earlier one in this list wins.
SOURCE_RANK = ["DACON", "AIFactory", "씽굿", "링커리어", "올콘", "콘테스트코리아", "요즘것들",
               "이벤터스", "Dev-Event", "K-Startup", "스타트업레시피", "위비티", "네이버뉴스", "초기조사"]
FIELDS = ["host", "applyStart", "applyEnd", "eventDates", "prize", "eligibility", "region"]


NOISE = re.compile(r"주식회사|㈜|\(주\)|참가자|참가팀|참여자|모집|안내|공고|개최|접수")


def norm(name: str) -> str:
    s = re.sub(r"\(.*?\)|\[.*?\]|「|」|『|』", " ", name or "")
    s = re.sub(r"제?\s*\d+\s*회|20\d\d\s*년?", " ", s)
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", s).lower()


def _bigrams(name: str) -> set:
    """Character bigrams of the name with brackets kept but boilerplate words removed."""
    s = NOISE.sub(" ", name or "")
    s = re.sub(r"20\d\d\s*년?|제?\s*\d+\s*회", " ", s)
    s = re.sub(r"[^0-9a-zA-Z가-힣]", "", s).lower()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def rid(key: str) -> str:
    return hashlib.sha1(key.encode()).hexdigest()[:10]


def _rank(src: str) -> int:
    return SOURCE_RANK.index(src) if src in SOURCE_RANK else len(SOURCE_RANK)


class Index:
    """Finds the existing record a new item belongs to.

    Same contest, differently titled across sites ("[채용/해커톤] 2026 주식회사 소프트뱅크 채용 연계
    해커톤" vs "SoftBank Hackathon 2026 in Korea") is caught by: exact normalised name; a near match
    on the name; or the same deadline plus a clearly overlapping name.
    """

    def __init__(self):
        self.by_key: dict[str, dict] = {}
        self.by_end: dict[str, list[tuple[set, dict]]] = {}

    def find(self, key: str, name: str, end: str | None):
        if key in self.by_key:
            return self.by_key[key]
        if end:
            grams = _bigrams(name)
            best = max(((_jaccard(grams, g), r) for g, r in self.by_end.get(end, [])), default=(0, None), key=lambda x: x[0])
            # Short generic names ("AI 숏폼 공모전") need a closer match to count as the same contest.
            if best[0] >= (0.45 if len(grams) >= 12 else 0.7):
                return best[1]
        if len(key) < 6:
            return None
        for k, rec in self.by_key.items():
            if k[:4] != key[:4] or len(k) < 6:
                continue
            short, long_ = sorted((k, key), key=len)
            if (len(short) >= 10 and short in long_) or SequenceMatcher(None, k, key).ratio() >= 0.9:
                return rec
        return None

    def add(self, key, rec):
        self.by_key[key] = rec
        self.index_end(rec, rec.get("name"))

    def index_end(self, rec, name):
        if rec.get("applyEnd"):
            self.by_end.setdefault(rec["applyEnd"], []).append((_bigrams(name), rec))


def merge(previous: list[dict], fresh: list[dict], run_date: str) -> list[dict]:
    idx = Index()
    for rec in previous:
        key = norm(rec["name"])
        # Old runs may have stored duplicates; fold them together too.
        into = idx.find(key, rec["name"], rec.get("applyEnd"))
        if into is None:
            idx.add(key, rec)
        else:
            into["sources"] = {**rec.get("sources", {}), **into.get("sources", {})}
            into["firstSeen"] = min(into.get("firstSeen") or "9", rec.get("firstSeen") or "9")

    for item in sorted(fresh, key=lambda x: _rank(x["_source"])):
        key = norm(item["name"])
        rec = idx.find(key, item["name"], item.get("applyEnd"))
        src = item.pop("_source")
        if rec is None:
            rec = {"id": rid(key), "name": item["name"], "firstSeen": run_date, "sources": {}}
            idx.add(key, rec)
        else:
            idx.by_key.setdefault(key, rec)
            idx.index_end(rec, item["name"])
        # Fresh data from a better-or-equal source replaces what we had; worse sources only fill gaps.
        best = min((_rank(s) for s in rec["sources"]), default=99)
        rec["sources"][src] = item["url"]
        for f in FIELDS:
            v = item.get(f)
            if v and (not rec.get(f) or _rank(src) <= best):
                rec[f] = v
        for f in ("category", "aiRelated", "confidence", "jev"):
            if item.get(f) is not None and (rec.get(f) is None or _rank(src) <= best):
                rec[f] = item[f]
        if item.get("upcoming"):
            rec["upcoming"] = True
        rec["url"] = rec["sources"][min(rec["sources"], key=_rank)]
        rec["lastSeen"] = run_date
    return list({id(r): r for r in idx.by_key.values()}.values())


def finalize(records: list[dict], today: str, keep_ended_days=7) -> list[dict]:
    """Set status, drop what is long finished, sort by deadline."""
    from datetime import date, timedelta

    t = date.fromisoformat(today)
    cutoff = (t - timedelta(days=keep_ended_days)).isoformat()
    stale = (t - timedelta(days=30)).isoformat()
    out = []
    for r in records:
        start, end = r.get("applyStart"), r.get("applyEnd")
        events = [d for d in dates_in(r.get("eventDates"), t.year) if d >= (end or "")]
        last_event = max(events) if events else None
        if start and start > today:
            status = "upcoming"
        elif end is None:
            status = "upcoming" if r.get("upcoming") else "open"
        elif end >= today:
            status = "open"
        elif last_event and last_event >= today:
            status = "in_progress"
        else:
            status = "ended"
        if status == "ended" and max(end or "", last_event or "") < cutoff:
            continue
        if end is None and not last_event and r.get("lastSeen", today) < stale:
            continue  # undated item nobody lists any more
        r["status"] = status
        r["lastEvent"] = last_event
        out.append(r)
    order = {"open": 0, "upcoming": 1, "in_progress": 2, "ended": 3}
    out.sort(key=lambda r: (order[r["status"]], r.get("applyEnd") or "9999", r["name"]))
    return out
