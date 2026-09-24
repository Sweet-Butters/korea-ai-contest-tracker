"""K-Startup 창업지원포털 사업공고 — government startup funding programs, not contests.

Only the first list page is served to anonymous visitors (later pages need the site's own
session), so this reads page 1 every day: new notices appear on top, and ones already stored
stay until their deadline passes.
"""
import html
import re

from .. import http
from ..util import clean

NAME = "K-Startup"
CONTEST_LIST = True  # the page lists only 사업공고, so titles need no "대회/공모" word
URL = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"
START = re.compile(r"go_view\((\d+)\)")
END = re.compile(r"마감일자\s*(\d{4}-\d{2}-\d{2})")
TITLE = re.compile(r'<p class="tit">\s*(.*?)</p>', re.S)
LIS = re.compile(r"<li>(.*?)</li>", re.S)


def fetch():
    page = http.get(URL).text
    # Cards differ between the top carousel and the list, so slice the page on each go_view(id)
    # and read the fields inside that slice.
    marks = [(m.group(1), m.start()) for m in START.finditer(page)]
    items = {}
    for i, (pid, pos) in enumerate(marks):
        block = page[pos:marks[i + 1][1] if i + 1 < len(marks) else pos + 4000]
        end_m, title_m = END.search(block), TITLE.search(block)
        if not (end_m and title_m):
            continue
        end = end_m.group(1)
        lines = [clean(x) for x in LIS.findall(block)]
        title = clean(html.unescape(title_m.group(1)))
        # <ul> holds: the title again, the organiser, then the view count.
        host = next((x for x in lines[1:] if x and not x.startswith("조회") and x != title), None)
        items[pid] = {
            "name": title,
            "host": host,
            "applyEnd": end,
            "url": f"{URL}?schM=view&pbancSn={pid}",
        }
    return list(items.values())
