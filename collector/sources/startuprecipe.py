"""스타트업레시피 공고 — aggregated startup funding, incubation and competition notices.

The list carries region and programme type but no deadline, so entries arrive without one
and the link goes to the notice itself.
"""
import html
import re

from .. import http
from ..util import clean

NAME = "스타트업레시피"
CONTEST_LIST = True
LIST = "https://startuprecipe.co.kr/announcement/page/{}"
ARTICLE = re.compile(r"<article.*?</article>", re.S)
TITLE = re.compile(r'<h3 class="jeg_post_title">(.*?)</h3>', re.S)
LINK = re.compile(r'href="(https://startuprecipe\.co\.kr/announcement/(\d+))"')
TAGS = re.compile(r"<span[^>]*>(.*?)</span>", re.S)
PAGES = 5


def fetch():
    items = {}
    for page in range(1, PAGES + 1):
        body = http.get(LIST.format(page)).text
        found = 0
        for block in ARTICLE.findall(body):
            link = LINK.search(block)
            title_block = TITLE.search(block)
            if not (link and title_block):
                continue
            found += 1
            # The title cell starts with a "지역 | 유형" pill, then the anchor with the real title.
            tags = [clean(html.unescape(t)) for t in TAGS.findall(title_block.group(1))]
            name = clean(html.unescape(re.sub(r"<[^>]+>", " ", title_block.group(1).split("</span>")[-1])))
            region_type = tags[0] if tags else ""
            items[link.group(2)] = {
                "name": name,
                "host": None,
                "url": link.group(1),
                "notes": region_type or None,
            }
        if not found:
            break
    return list(items.values())
