"""씽굿 (thinkcontest.com) — JSON list API, 50 per page, only open/upcoming contests."""
import json

from .. import http
from ..util import clean

NAME = "씽굿"
CONTEST_LIST = True
API = "https://www.thinkcontest.com/thinkgood/user/contest/subList.do"


def fetch():
    items = {}
    for page in range(1, 200):
        body = {"recordsPerPage": 50, "currentPageNo": page, "contest_field": "", "host_organ": "",
                "enter_qualified": "", "award_size": "", "searchStatus": "Y", "sidx": "", "sord": ""}
        r = http.post(API, data=json.dumps(body), headers={"Content-Type": "application/json"})
        rows = r.json().get("listJsonData") or []
        if not rows:
            break
        for x in rows:
            if x.get("process_nm") == "마감":
                continue
            items[x["contest_pk"]] = {
                "name": clean(x.get("program_nm")),
                "host": clean(x.get("host_company")),
                "applyStart": (x.get("accept_dt") or "")[:10] or None,
                "applyEnd": (x.get("finish_dt") or "")[:10] or None,
                "prize": clean(x.get("prize_money") or x.get("award_size_nm")) or None,
                "eligibility": clean(x.get("enter_qualified_nm")) or None,
                "url": f"https://www.thinkcontest.com/thinkgood/user/contest/view.do?contest_pk={x['contest_pk']}",
                "upcoming": x.get("process_nm") == "접수예정",
            }
    return list(items.values())
