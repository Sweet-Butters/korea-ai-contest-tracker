"""콘테스트코리아 (contestkorea.com) — server-rendered HTML list. int_gbn=1 공모전, 2 대외활동."""
import re

from .. import http
import datetime as dt

from ..util import clean, today

NAME = "콘테스트코리아"
CONTEST_LIST = True
LIST = "https://www.contestkorea.com/sub/list.php?int_gbn={}&displayrow=100&page={}"
ROW = re.compile(
    r'str_no=(\d+)">\s*<span class="category">(.*?)</span>.*?<span class="txt">(.*?)</span>.*?'
    r'<strong>주최</strong>\s*\.\s*(.*?)</li>.*?<strong>대상</strong>\s*\.(.*?)</li>.*?'
    r'<em>접수</em>\s*(.*?)</span>(.*?)<span class="day">(.*?)</span>\s*<span class="condition">(.*?)</span>', re.S)


def _period(str_no, rec):
    """'09.14~10.19' carries no year.

    The registration number starts with yyyymm, but yearly contests keep an old number, which
    put their deadline a year in the past. So pick the year that lands the deadline nearest to
    today, allowing a short grace period for one that has just closed.
    """
    m = re.match(r"(\d\d)\.(\d\d)~(\d\d)\.(\d\d)", rec)
    if not m:
        return None, None
    a, b, c, d = map(int, m.groups())
    t = today()

    def pick(month, day):
        best = None
        for year in (t.year - 1, t.year, t.year + 1):
            try:
                cand = dt.date(year, month, day)
            except ValueError:
                continue
            days = (cand - t).days
            score = (0 if days >= -45 else 1, abs(days))  # prefer upcoming or just-closed
            if best is None or score < best[0]:
                best = (score, cand)
        return best[1] if best else None

    end = pick(c, d)
    if end is None:
        return None, None
    try:
        start = dt.date(end.year, a, b)
    except ValueError:
        return None, end.isoformat()
    if start > end:  # the period crosses new year
        start = start.replace(year=end.year - 1)
    return start.isoformat(), end.isoformat()


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
