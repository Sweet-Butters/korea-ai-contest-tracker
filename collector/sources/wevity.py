"""위비티 (wevity.com) — server-rendered list; only a D-day is shown, so the deadline is derived."""
import re

from .. import http
from ..util import clean, from_dday

NAME = "위비티"
CONTEST_LIST = True
LIST = "https://www.wevity.com/?c=find&s=1&gp={}"
ROW = re.compile(r'<div class="tit">\s*<a href="[^"]*ix=(\d+)">(.*?)</a>.*?<div class="organ">(.*?)</div>\s*'
                 r'<div class="day">\s*(.*?)<span class="dday ([a-z]+)">(.*?)</span>', re.S)


def fetch():
    items = {}
    for page in range(1, 130):
        rows = ROW.findall(http.get(LIST.format(page)).text)
        if not rows:
            break
        if all(cls == "end" for *_, cls, _st in rows):
            break
        for ix, title, org, dday, cls, st in rows:
            if cls == "end":
                continue
            items[ix] = {
                "name": clean(re.sub(r"\s+(SPECIAL|신규|IDEA)(?=\s|$)", "", clean(title))),
                "host": clean(org),
                "applyEnd": from_dday(clean(dday)),
                "url": f"https://www.wevity.com/?c=find&s=1&gbn=view&ix={ix}",
                "upcoming": "예정" in st,
                "notes": "마감일은 D-day로 계산",
            }
    return list(items.values())
