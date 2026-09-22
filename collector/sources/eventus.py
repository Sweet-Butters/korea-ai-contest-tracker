"""이벤터스 (event-us.kr) — the site's public search API, queried with a few keywords."""
from .. import http
from ..util import today

NAME = "이벤터스"
CONTEST_LIST = False  # mixes seminars and meetups, so titles must look like a contest
API = "https://api.event-us.kr/api/v1/engine/search"
QUERIES = ["AI", "인공지능", "해커톤", "경진대회", "공모전", "챌린지", "창업", "관광"]


def fetch():
    items = {}
    for q in QUERIES:
        for page in range(1, 6):
            body = {"query": q, "page": {"current": page, "size": 50},
                    "filters": {"all": [{"state": "Start"}, {"disclosure_status": "open"}, {"is_ignore": "false"}]}}
            d = http.post(API, json=body).json()
            for x in d.get("results", []):
                g = lambda k: (x.get(k) or {}).get("raw")
                i = g("id")
                if not i or i in items:
                    continue
                # The API's state filter is not reliable; drop anything already over.
                if max((g("close_date") or "")[:10], (g("end_date") or "")[:10]) < today().isoformat():
                    continue
                items[i] = {
                    "name": g("title"),
                    "host": g("host_name") or g("subdomain"),
                    "applyEnd": (g("close_date") or "")[:10] or None,
                    "eventDates": " ~ ".join(v[:10] for v in (g("start_date"), g("end_date")) if v) or None,
                    "url": f"https://event-us.kr/{g('subdomain')}/event/{i}",
                }
            if page >= d.get("meta", {}).get("page", {}).get("total_pages", 0):
                break
    return list(items.values())
