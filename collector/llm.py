"""Turns news-article candidates into contest records with a small LLM call.

Provider: Gemini API free tier (GEMINI_API_KEY). Only articles never seen before are sent, in
batches, so a daily run uses a handful of requests. Without a key, a regex fallback keeps the
article as a low-confidence entry.
"""
import json
import os
import time

import requests

from .util import deadline_from_text, today

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
BATCH = 20
MAX_PER_RUN = int(os.environ.get("LLM_MAX_ARTICLES", "200"))

PROMPT = """오늘은 {today}이다. 아래는 한국 뉴스 기사 제목과 요약 목록이다.
각 기사가 '참가자·참가팀을 모집하는 대회/공모전/해커톤/챌린지/창업경진대회'를 알리는지 판단하고, 맞으면 정보를 추출하라.
이미 끝난 대회의 시상·결과 기사, 단순 행사·교육·세미나 모집은 isContest=false.
날짜는 YYYY-MM-DD, 모르면 null. 기사에 없는 정보는 지어내지 말고 null.
JSON 배열만 출력: [{{"i":번호,"isContest":bool,"name":"공식 대회명","host":"주최","applyStart":null,"applyEnd":"접수 마감일","eventDates":"본선/결선/시상 일정 요약","prize":"상금 요약","eligibility":"참가 대상","region":"지역(광역시도) 또는 null"}}]

기사 목록:
{articles}"""


def available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def _gemini(prompt: str) -> list:
    model = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
    r = requests.post(
        GEMINI_URL.format(model=model),
        params={"key": os.environ["GEMINI_API_KEY"]},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 0}},
        timeout=120,
    )
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def extract(articles: list[dict]) -> dict[str, dict | None]:
    """url -> extracted fields (None = not a contest). Unprocessed articles are left out."""
    results: dict[str, dict | None] = {}
    articles = articles[:MAX_PER_RUN]
    for start in range(0, len(articles), BATCH):
        batch = articles[start:start + BATCH]
        listing = "\n".join(f"[{i}] ({a['_pub']}) {a['name']} — {a.get('_desc', '')}" for i, a in enumerate(batch))
        try:
            rows = _gemini(PROMPT.format(today=today().isoformat(), articles=listing))
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"  llm batch failed: {e}")
            break  # quota or outage: stop, the rest is retried next run
        for row in rows if isinstance(rows, list) else []:
            i = row.get("i")
            if not isinstance(i, int) or not 0 <= i < len(batch):
                continue
            results[batch[i]["url"]] = row if row.get("isContest") and row.get("name") else None
        time.sleep(4)  # stay under the free tier's requests-per-minute limit
    return results


def fallback(article: dict) -> dict:
    """No LLM: keep the headline, guess the deadline from the summary."""
    return {"name": article["name"], "applyEnd": deadline_from_text(article.get("_desc"))}
