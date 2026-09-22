"""요즘것들 (allforyoung.com) — list data is embedded in the server-rendered page."""
import re

from .. import http
from ..util import clean, from_dday

NAME = "요즘것들"
CONTEST_LIST = True
LIST = "https://www.allforyoung.com/posts/contest?page={}"
ROW = re.compile(r'"id":(\d+),"category":"([^"]*)","title":"([^"]*)","organization":"([^"]*)".{0,600}?"dday":"([^"]*)".{0,400}?"is_expired":(true|false)')
DETAIL = r'"id":%s,"title":"[^"]*","organization":"([^"]*)","start_date":"?([^",]*)"?,"end_at":"?([^",]*)"?,"apply_url":"?([^",]*)'


def fetch():
    items = {}
    for page in range(1, 80):
        s = http.get(LIST.format(page)).text.replace('\\"', '"')
        rows = ROW.findall(s)
        if not rows:
            break
        for pid, _cat, title, org, dday, expired in rows:
            if expired == "true":
                continue
            items[pid] = {
                "name": clean(title.replace("\\u0026", "&")),
                "host": clean(org),
                "applyEnd": from_dday(dday),
                "url": f"https://www.allforyoung.com/posts/{pid}",
            }
    return list(items.values())


def enrich(item):
    pid = item["url"].rsplit("/", 1)[-1]
    s = http.get(item["url"]).text.replace('\\"', '"')
    m = re.search(DETAIL % pid, s)
    if m:
        item["host"] = clean(m.group(1)) or item.get("host")
        item["applyStart"] = m.group(2)[:10] if m.group(2) not in ("", "null") else None
        if m.group(3) not in ("", "null"):
            item["applyEnd"] = m.group(3)[:10]
    return item
