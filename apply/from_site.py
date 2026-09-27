"""Fill profile.local.json from the applicant's own portfolio site.

    python -m apply profile                      # the site in config, plus its linked pages
    python -m apply profile https://example.com  # another site

Reads the page (and same-site pages it links to, a few), then asks Gemini to turn it into the
profile fields the drafts use. Contact details already in profile.local.json are kept as they are:
the site rarely carries them, and they should not be guessed.
"""
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from collector import http, llm

from . import profile as profile_mod

DEFAULT_SITE = "https://sweet-butters.github.io/"
MAX_PAGES = 8
PER_PAGE = 24000        # the SCPC write-up alone is 20k chars of text; a smaller cut dropped 본선
SKIP = ("/ko/",)        # the ko pages are generated copies — the source pages hold every language
KEEP = ("name", "email", "phone", "birth", "address", "region")  # never overwritten from a public site

PROMPT = """아래는 한 사람의 포트폴리오 웹사이트 본문이다(여러 페이지를 이어 붙였다).
지원서를 쓸 때 쓸 **소재**를 최대한 많이, 구체적으로 뽑아 JSON으로 답하라.

중요:
- 사이트에 적힌 사실만 쓴다. 없으면 null 또는 빈 배열. 추측 금지.
- **숫자는 반드시 숫자 그대로** 옮긴다 (예: "0.088 → 0.747", "96건 중 91건", "$0.11", "550여 건").
- stories 는 지원서에 그대로 인용할 수 있는 단위다. 문제 → 한 일 → 결과 순으로, 사이트의 서술을 살려 쓴다.
- decisions 는 "무엇을 하지 않기로 했는가"를 포함한 판단이다. 기능 나열이 아니다.
- **묶지 말고 쪼갠다.** 대회는 라운드별로(1차 예선 / 2차 예선 / 본선), 제품은 저장소별로 각각 하나씩
  projects 에 넣는다. 서로 다른 라운드나 제품을 한 항목에 합치면 지원서에서 쓸 수 없다.
- projects 는 사이트에 있는 만큼 전부(보통 5개 이상), stories 는 6개 이상 뽑는다. 라운드마다 한 개 이상.
- 포크·파생 프로젝트는 본인이 한 부분과 원저자의 것을 그 문장 그대로 구분해 적는다.

{{"school":null,"major":null,"grade":null,
"intro":"2~3문장",
"strengths":["강점 3~6개"],
"projects":[{{"name":"","summary":"한 문장","role":"본인 역할","result":"숫자 포함","link":"",
             "numbers":["사이트에 나온 수치 그대로"],
             "decisions":["내린 판단과 그 이유, 각 1~2문장"]}}],
"stories":[{{"title":"소재 제목","problem":"무엇이 문제였나","action":"무엇을 했나(방법·도구)","result":"결과(숫자)","source":"어느 페이지"}}],
"awards":["수상·성과. 대회명과 결과를 그대로"],
"teaching":["강의·발표 경력"],
"links":{{"portfolio":"","github":"","blog":""}}}}

사이트 본문:
{text}"""


def _text(url: str) -> str:
    body = http.get(url).text
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()


def _pages(root: str) -> list[str]:
    """The site itself plus a few same-site pages it links to (project write-ups, about …)."""
    host = urlsplit(root).netloc
    html = http.get(root).text
    urls = [root]
    for href in re.findall(r'href="([^"#?]+)"', html):
        u = urljoin(root, href)
        if (urlsplit(u).netloc == host and u not in urls and not any(k in u for k in SKIP)
                and not re.search(r"\.(png|jpg|svg|css|js|json)$", u)):
            urls.append(u)
    return urls[:MAX_PAGES]


def build(site: str = DEFAULT_SITE) -> dict:
    if not llm.available():
        raise RuntimeError("GEMINI_API_KEY 가 없어 사이트를 읽을 수 없습니다 (secrets/gemini_api_key.txt).")
    pages = _pages(site)
    text = "\n\n".join(f"[{u}]\n{_text(u)[:9000]}" for u in pages)
    print(f"읽은 페이지 {len(pages)}개: " + ", ".join(pages))
    got = llm._gemini(PROMPT.format(text=text[:120000]))
    return got[0] if isinstance(got, list) else got


def main(site: str | None = None):
    site = site or DEFAULT_SITE
    found = build(site)
    path = profile_mod.LOCAL
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    merged = dict(current)
    for k, v in (found or {}).items():
        if k in KEEP or not v:
            continue
        if k == "links":
            merged["links"] = {**(current.get("links") or {}), **{a: b for a, b in v.items() if b}}
        else:
            merged[k] = v
    merged.setdefault("_comment", "포트폴리오 사이트에서 채움. 이름·연락처는 직접 적으세요. git 제외 파일입니다.")
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    filled = [k for k in ("school", "major", "grade", "intro", "strengths", "projects", "stories",
                          "awards", "teaching", "links") if merged.get(k)]
    missing = [k for k in ("name", "email", "phone") if not merged.get(k) or str(merged[k]).startswith("[")]
    print(f"저장: {path}")
    print("채워진 항목: " + ", ".join(filled))
    print(f"프로젝트 {len(merged.get('projects') or [])}개 · 소재(stories) {len(merged.get('stories') or [])}개 · "
          f"판단 {sum(len(x.get('decisions') or []) for x in merged.get('projects') or [])}개 · "
          f"수상 {len(merged.get('awards') or [])}개")
    if missing:
        print("직접 적어야 하는 것: " + ", ".join(missing) + " (사이트에 없는 개인정보)")
