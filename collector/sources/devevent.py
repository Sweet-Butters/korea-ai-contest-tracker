"""Dev-Event (github.com/brave-people/Dev-Event) — community-curated README of Korean dev events."""
import re

from .. import http
from ..util import today

NAME = "Dev-Event"
CONTEST_LIST = False
URL = "https://raw.githubusercontent.com/brave-people/Dev-Event/master/README.md"
MONTH = re.compile(r"^## `(\d\d)년 (\d\d)월`")
ITEM = re.compile(r"^- __\[(.+?)\]\((.+?)\)__")
PERIOD = re.compile(r"(\d\d)\. (\d\d)\([^)]*\)(?:\s*\d\d:\d\d)?\s*~\s*(\d\d)\. (\d\d)")


def fetch():
    items, year, cur = [], None, None
    for line in http.get(URL).text.splitlines():
        if line.startswith("## "):
            m = MONTH.match(line)
            year = 2000 + int(m.group(1)) if m else None
            continue
        if year is None:
            continue
        s = line.strip()
        if (m := ITEM.match(s)):
            cur = {"name": m.group(1), "url": m.group(2), "_tags": ""}
            items.append(cur)
        elif cur and s.startswith("- 분류:"):
            cur["_tags"] = s
        elif cur and s.startswith("- 주최:"):
            cur["host"] = s.split(":", 1)[1].strip()
        elif cur and (s.startswith("- 접수:") or s.startswith("- 일시:")):
            p = PERIOD.search(s)
            if p:
                a, b, c, d = map(int, p.groups())
                key = "applyEnd" if s.startswith("- 접수:") else "_eventEnd"
                cur["applyStart" if key == "applyEnd" else "_eventStart"] = f"{year}-{a:02d}-{b:02d}"
                cur[key] = f"{year + (1 if c < a else 0)}-{c:02d}-{d:02d}"
    out = []
    for it in items:
        if "`대회`" not in it.pop("_tags"):
            continue
        ev_start, ev_end = it.pop("_eventStart", None), it.pop("_eventEnd", None)
        if ev_end:
            it["eventDates"] = f"{ev_start} ~ {ev_end}"
        if max(it.get("applyEnd") or "", ev_end or "") < today().isoformat():
            continue
        out.append(it)
    return out
