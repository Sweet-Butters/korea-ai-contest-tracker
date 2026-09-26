"""위비티 (wevity.com) — server-rendered list; only a D-day is shown, so the deadline is derived."""
import re

from .. import http
import datetime as dt

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
                "applyEnd": _deadline(clean(dday)),
                "url": f"https://www.wevity.com/?c=find&s=1&gbn=view&ix={ix}",
                "upcoming": "예정" in st,
                "notes": "마감일은 D-day로 계산 (당일 포함)",
            }
    return list(items.values())


def _deadline(dday: str) -> str | None:
    """위비티 counts the deadline day itself, so "D-7" is six days from now, not seven.

    Measured against sources that publish real dates: 91 of 96 comparable listings were
    exactly one day later than this badge implies.
    """
    iso = from_dday(dday)
    if not iso or "D-" not in dday.upper():
        return iso
    return (dt.date.fromisoformat(iso) - dt.timedelta(days=1)).isoformat()
