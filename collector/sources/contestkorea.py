"""콘테스트코리아 (contestkorea.com) — server-rendered HTML list. int_gbn=1 공모전, 2 대외활동."""
import re

from .. import http
from ..util import clean

NAME = "콘테스트코리아"
CONTEST_LIST = True
LIST = "https://www.contestkorea.com/sub/list.php?int_gbn={}&displayrow=100&page={}"
ROW = re.compile(
    r'str_no=(\d+)">\s*<span class="category">(.*?)</span>.*?<span class="txt">(.*?)</span>.*?'
    r'<strong>주최</strong>\s*\.\s*(.*?)</li>.*?<strong>대상</strong>\s*\.(.*?)</li>.*?'
    r'<em>접수</em>\s*(.*?)</span>(.*?)<span class="day">(.*?)</span>\s*<span class="condition">(.*?)</span>', re.S)


def _period(str_no, rec):
    """'09.14~10.19' has no year; the registration number starts with yyyymm, so anchor on it."""
    m = re.match(r"(\d\d)\.(\d\d)~(\d\d)\.(\d\d)", rec)
    if not m:
        return None, None
    a, b, c, d = map(int, m.groups())
    year, reg_month = int(str_no[:4]), int(str_no[4:6])
    sy = year - 1 if a > reg_month + 3 else year
    ey = sy + 1 if (c, d) < (a, b) else sy
    return f"{sy}-{a:02d}-{b:02d}", f"{ey}-{c:02d}-{d:02d}"


def fetch():
    items = {}
    for gbn in (1, 2):
        for page in range(1, 60):
            rows = ROW.findall(http.get(LIST.format(gbn, page)).text)
            if not rows:
                break
            for str_no, _cat, title, host, target, rec, rest, _day, cond in rows:
                cond = cond.strip()
                if cond not in ("접수중", "접수예정"):
                    continue
                start, end = _period(str_no, rec.strip())
                items[str_no] = {
                    "name": clean(title),
                    "host": clean(host),
                    "applyStart": start,
                    "applyEnd": end,
                    "eventDates": clean(rest) or None,
                    "eligibility": clean(target) or None,
                    "url": f"https://www.contestkorea.com/sub/view.php?int_gbn={gbn}&str_no={str_no}",
                    "upcoming": cond == "접수예정",
                    "_needs_comp_word": gbn == 2,
                }
    return list(items.values())
