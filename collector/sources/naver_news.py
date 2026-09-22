"""네이버 뉴스 검색 API — finds contests announced only in press releases (government, local, corporate).

Needs NAVER_CLIENT_ID / NAVER_CLIENT_SECRET (free, 25,000 calls/day). Without them this source is skipped.
Articles are only candidates: main.py turns them into contests with llm.extract() or a regex fallback.
"""
import email.utils
import os

from .. import http
from ..classify import Rules
from ..util import clean, today

NAME = "네이버뉴스"
CONTEST_LIST = False
API = "https://openapi.naver.com/v1/search/news.json"
MAX_AGE_DAYS = 45


def queries(rules: Rules):
    qs = list(rules.cfg.get("newsQueries", []))
    qs += [f"{r} AI 공모전" for r in rules.regions]
    return list(dict.fromkeys(qs))


def fetch():
    cid, secret = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not (cid and secret):
        raise RuntimeError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET not set; skipped")
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
    cutoff = today().toordinal() - MAX_AGE_DAYS
    items = {}
    for q in queries(Rules.load()):
        r = http.get(API, params={"query": q, "display": 100, "sort": "date"}, headers=headers, check_robots=False)
        for a in r.json().get("items", []):
            pub = email.utils.parsedate_to_datetime(a["pubDate"]).date()
            if pub.toordinal() < cutoff:
                continue
            url = a.get("originallink") or a["link"]
            items.setdefault(url, {
                "name": clean(a["title"]),
                "url": url,
                "_desc": clean(a["description"]),
                "_pub": pub.isoformat(),
            })
    return list(items.values())
