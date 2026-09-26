"""Read a contest's notice page and work out how to apply.

Rules find the obvious things (email address, form link, closing time, requested documents).
With GEMINI_API_KEY set, the page text is also summarised into the same shape, which fills in
what the rules miss. Everything here comes from public notices, so it is stored in data/.
"""
import html
import json
import re

from collector import http, llm
from collector.util import clean

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
FORM = re.compile(r"https?://(?:docs\.google\.com/forms|forms\.gle|naver\.me|form\.office\.com)[^\s\"'<>)]+")
TIME = re.compile(r"(\d{1,2})\s*[:시]\s*(\d{2})?\s*(?:분)?\s*(?:까지|마감)")
DOC_WORDS = ["신청서", "참가신청서", "지원서", "계획서", "제안서", "포트폴리오", "발표자료", "기획안",
             "동의서", "개인정보", "재학증명", "사업자등록", "통장사본", "요약서", "영상", "이미지", "소스코드"]
FILE_WORDS = ["hwp", "hwpx", "pdf", "docx", "pptx", "zip", "mp4", "png", "jpg"]

PROMPT = """아래는 한국 공모전·지원사업 공고 페이지의 본문이다. 지원하려는 사람 입장에서 다음을 추출해 JSON으로만 답하라.
모르면 null. 지어내지 말 것.
{{"applyMethod":"이메일|온라인폼|주최 사이트|우편·방문|기타|null","applyUrl":"접수 페이지 주소 또는 null",
"email":"접수 이메일 또는 null","deadlineTime":"HH:MM 마감 시각 또는 null",
"documents":["제출 서류 목록"],"formats":["파일 형식·분량 제한"],
"eligibility":"참가 자격 한 줄","steps":["지원 절차를 순서대로, 5개 이내"],"cautions":["주의사항 3개 이내"]}}

공고 본문:
{text}"""


def _text(url: str) -> str:
    body = http.get(url).text
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", html.unescape(body)).strip()


NEAR = re.compile(r"(접수|신청|제출|응모|지원서)")


def _near(text: str, match: re.Match, window: int = 140) -> bool:
    """True when 접수/신청/제출 appears right around the match, not just anywhere on the page."""
    lo, hi = max(0, match.start() - window), match.end() + window
    return bool(NEAR.search(text[lo:hi]))


def from_rules(text: str) -> dict:
    emails = [m for m in EMAIL.finditer(text) if not m.group(0).lower().endswith((".png", ".jpg"))]
    # A page's support address ("문의: cs@…") is not where an entry is sent.
    apply_emails = [m.group(0) for m in emails if _near(text, m)]
    forms = [m.group(0) for m in FORM.finditer(text) if _near(text, m)] or FORM.findall(text)
    times = TIME.findall(text)
    docs = [w for w in DOC_WORDS if w in text]
    formats = sorted({w.upper() for w in FILE_WORDS if re.search(rf"\.{w}|{w}\s*파일", text, re.I)})
    method = "온라인폼" if forms else ("이메일" if apply_emails else None)
    return {
        "applyMethod": method,
        "applyUrl": forms[0] if forms else None,
        "email": apply_emails[0] if apply_emails else None,
        "contactEmail": emails[0].group(0) if emails else None,
        "deadlineTime": f"{int(times[0][0]):02d}:{times[0][1] or '00'}" if times else None,
        "documents": docs,
        "formats": formats,
        "eligibility": None,
        "steps": [],
        "cautions": [],
        "guessed": [k for k, v in (("applyMethod", method), ("email", apply_emails), ("documents", docs)) if v],
    }


def extract(url: str, use_llm: bool = True) -> dict:
    """Requirements for one notice URL. Rules always run; the LLM only fills the gaps."""
    text = _text(url)[:8000]
    out = from_rules(text)
    out["source"] = url
    if use_llm and llm.available() and len(text) > 200:
        try:
            got = llm._gemini(PROMPT.format(text=text))
            if isinstance(got, list):
                got = got[0] if got else {}
            for k, v in (got or {}).items():
                if v and not out.get(k):
                    out[k] = v
            out["byLlm"] = True
        except Exception as e:  # quota, outage, bad JSON: the rule result still stands
            out["llmError"] = str(e)[:120]
    out["excerpt"] = clean(text[:600])
    return out
