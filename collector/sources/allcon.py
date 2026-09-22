"""올콘 (all-con.co.kr) — AJAX list returning JSON. t=1 공모전, t=2 대외활동."""
import re

from .. import http
from ..util import clean

NAME = "올콘"
CONTEST_LIST = True
API = "https://www.all-con.co.kr/page/ajax.contest_list.php"


def fetch():
    items = {}
    for t in ("1", "2"):
        for page in range(1, 120):
            r = http.post(API, data={"page": page, "t": t, "sortname": "cl_order", "sortorder": "asc"},
                          headers={"X-Requested-With": "XMLHttpRequest"}, verify=False)
            d = r.json()
            rows = d.get("rows") or []
            rows = list(rows.values()) if isinstance(rows, dict) else rows
            if not rows:
                break
            for v in rows:
                if "cl_title" not in v:
                    continue
                status = clean(v.get("cl_status"))
                if "마감" in status:
                    continue
                m = re.match(r"(\d\d)\.(\d\d)\.(\d\d)~(\d\d)\.(\d\d)\.(\d\d)", v.get("cl_date") or "")
                start = end = None
                if m:
                    g = m.groups()
                    start, end = f"20{g[0]}-{g[1]}-{g[2]}", f"20{g[3]}-{g[4]}-{g[5]}"
                cats = re.findall(r'cl_cate">(.*?)<', v.get("cl_cate") or "")
                items[v["cl_srl"]] = {
                    "name": clean(v["cl_title"]),
                    "host": clean(v.get("cl_host")),
                    "applyStart": start,
                    "applyEnd": end,
                    "eligibility": ", ".join(cats[1:]) or None,
                    "url": f"https://www.all-con.co.kr/view/contest/{v['cl_srl']}",
                    "upcoming": "예정" in status,
                    # 대외활동 tab mixes in non-contests; flag so the classifier requires contest words.
                    "_needs_comp_word": t == "2",
                }
            if page >= int(d.get("totalPage") or 0):
                break
    return list(items.values())
