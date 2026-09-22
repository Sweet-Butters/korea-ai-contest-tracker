"""AIFactory (aifactory.space) — Next.js flight data (self.__next_f) holds the task list."""
import json
import re

from .. import http
from ..util import today

NAME = "AIFactory"
CONTEST_LIST = True
URL = "https://aifactory.space/ko/competition"


def _flight(html):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    return "".join(json.loads(f'"{c}"') for c in chunks)


def fetch():
    s = _flight(http.get(URL).text)
    # Rows look like  20:{"id":"9306",...,"name":"주제 3: ...","page":"$21",...}  21:{"name":"2026 ... 챌린지"}
    refs = dict(re.findall(r'(?m)^([0-9a-f]+):(\{"name":"[^"]*"\})$', s))
    items = {}
    for m in re.finditer(r'\{"id":"(\d+)","type":\d+,"endDate":"[^"]*"[^{}]*\}', s):
        try:
            t = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        end = (t.get("participationDeadline") or t.get("endDate") or "")[:10]
        if end and end < today().isoformat():
            continue
        parent = ""
        ref = (t.get("page") or "").lstrip("$")
        if ref in refs:
            parent = json.loads(refs[ref])["name"]
        name = f"{parent} - {t['name']}" if parent and parent not in t["name"] else t["name"]
        items[t["id"]] = {
            "name": name,
            "host": "AIFactory",
            "applyStart": (t.get("participationStartDate") or t.get("startDate") or "")[:10] or None,
            "applyEnd": end or None,
            "prize": t.get("totalReward"),
            "url": f"https://aifactory.space/task/{t['id']}/overview",
        }
    return list(items.values())
