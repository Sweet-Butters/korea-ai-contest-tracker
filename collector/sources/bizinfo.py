"""기업마당 (bizinfo) — 중소벤처기업부 지원사업 공고, via the data.go.kr open API.

Needs DATA_GO_KR_KEY (a data.go.kr "일반 인증키"); without it the source is skipped.
The feed carries ~1,500 live notices, most of them small-business marketing support, so only
AI-related ones and the 창업 field are passed on; the keyword rules judge the rest as usual.
"""
import os
import re

from .. import http
from ..classify import Rules
from ..util import clean

NAME = "기업마당"
CONTEST_LIST = True  # a list of 지원사업 notices: titles need no "대회/공모" word
URL = "https://apis.data.go.kr/1421000/bizinfo/pblancBsnsService"
PAGE_SIZE = 100
MAX_PAGES = 20
# Fields of interest: 공고명, 링크, 소관기관, 접수기간("YYYY-MM-DD ~ YYYY-MM-DD"), 지원대상, 분야, 해시태그.
KEEP_REALMS = {"창업"}


def _period(text):
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", text or "")
    return (dates[0] if dates else None, dates[1] if len(dates) > 1 else None)


def fetch():
    key = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not key:
        raise RuntimeError("DATA_GO_KR_KEY not set; skipped")
    rules = Rules.load()
    items = {}
    for page in range(1, MAX_PAGES + 1):
        r = http.get(URL, params={"serviceKey": key, "numOfRows": PAGE_SIZE, "pageNo": page, "dataType": "json"},
                     check_robots=False)  # an official open-data API, not a crawl of the site
        body = r.json()["response"]["body"]
        rows = (body.get("items") or {}).get("item") or []
        for x in rows:
            name = clean(x.get("pblancNm"))
            desc = clean(x.get("bsnsSumryCn"))[:600]
            tags = clean(x.get("hashtags")).replace(",", " ")
            realm = clean(x.get("pldirSportRealmLclasCodeNm"))
            # Most notices are ordinary small-business support; keep AI ones and the 창업 field.
            if realm not in KEEP_REALMS and not rules.ai.search(f"{name} {desc} {tags}"):
                continue
            start, end = _period(x.get("reqstBeginEndDe"))
            items[x["pblancId"]] = {
                "name": name,
                "host": clean(x.get("jrsdInsttNm")) or clean(x.get("excInsttNm")) or None,
                "applyStart": start,
                "applyEnd": end,
                "eligibility": clean(x.get("trgetNm")) or None,
                "url": x.get("pblancUrl"),
                "notes": f"기업마당 {realm}".strip(),
                "_desc": desc,
            }
        if page * PAGE_SIZE >= int(body.get("totalCount") or 0):
            break
    return list(items.values())
