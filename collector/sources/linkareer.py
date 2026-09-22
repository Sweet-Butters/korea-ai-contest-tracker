"""링커리어 (linkareer.com) — server-rendered Next.js pages carry an Apollo cache in __NEXT_DATA__."""
import json
import re

from .. import http
from ..util import clean, from_epoch_ms

NAME = "링커리어"
CONTEST_LIST = True
LIST = "https://linkareer.com/list/contest?orderBy_direction=DESC&orderBy_field=CREATED_AT&page={}"


def _apollo(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return {}
    return json.loads(m.group(1))["props"]["pageProps"].get("__APOLLO_STATE__", {})


def fetch():
    items = {}
    for page in range(1, 80):
        st = _apollo(http.get(LIST.format(page)).text)
        acts = [v for k, v in st.items() if k.startswith("Activity:")]
        if not acts:
            break
        for a in acts:
            items[a["id"]] = {
                "name": clean(a.get("title")),
                "host": clean(a.get("organizationName")),
                "applyEnd": from_epoch_ms(a.get("recruitCloseAt")),
                "url": f"https://linkareer.com/activity/{a['id']}",
            }
    return list(items.values())


def enrich(item):
    """Fetch the detail page for start date, prize and target audience (only for kept items)."""
    i = item["url"].rsplit("/", 1)[-1]
    st = _apollo(http.get(item["url"]).text)
    a = st.get(f"Activity:{i}") or {}
    targets = [st[t["__ref"]].get("name") for t in a.get("targets") or []
               if isinstance(t, dict) and t.get("__ref") in st]
    item["applyStart"] = from_epoch_ms(a.get("recruitStartAt")) or item.get("applyStart")
    benefit = a.get("additionalBenefit") or a.get("benefits")
    if isinstance(benefit, str):
        item["prize"] = clean(benefit)[:120]
    if targets:
        item["eligibility"] = ", ".join(t for t in targets if t)
    return item
