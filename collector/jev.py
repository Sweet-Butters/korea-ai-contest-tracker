"""Second opinion on the keyword rules from TypeSafe's Jev model (typed answers with probabilities).

Provider: TypeSafe System One API (TYPESAFE_API_KEY, or typesafe_api_key.txt at the repo root for
local runs). Each distinct title+description is asked once and cached, so a daily run only sends
new listings. Without a key, or when a request fails, the keyword rules decide alone.

Jev reads English best and Korean less well, so it only overrides the rules when it is sure:
see decide() for the thresholds.
"""
import hashlib
import os
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = os.environ.get("JEV_MODEL", "jev-latest")
KEY_FILE = Path(__file__).resolve().parent.parent / "typesafe_api_key.txt"
MAX_PER_RUN = int(os.environ.get("JEV_MAX_ITEMS", "4000"))
WORKERS = 4
DESC_CHARS = 1500

# Thresholds on the probability that a listing is an AI-related contest.
DROP_BELOW = 0.15   # a rule-kept listing with only weak AI words is dropped below this
RESCUE_ABOVE = 0.85  # a contest listing the rules dropped for lacking AI words is kept above this
NOT_CONTEST_BELOW = 0.1  # any listing is dropped when Jev is this sure it is not an open contest
CATEGORY_CONFIDENCE = 0.6  # Jev's category replaces the keyword category above this
PRICE_PER_MTOK = 0.042  # USD, input tokens only; output is free

CATEGORY_HINTS = {
    "hackathon": "A hackathon, ideathon, or other time-boxed team build event",
    "startup": "A startup, business plan, commercialization, or investment/IR pitch competition",
    "funding": "A government or institutional support programme open for applications: grants, "
               "incubation, office tenancy, accelerator or scholarship recruitment (not a competition)",
    "tourism": "A tourism, travel, or MICE themed competition",
    "academic": "An academic paper, research, or scholarly competition",
    "data": "A data analysis, data science, or machine learning modeling competition",
    "creative": "A creative contest: video, image, music, design, writing, webtoon, character, advertising",
    "youth": "A competition only for children, teenagers, or school students",
    "dev": "A software development, coding, app/web, robotics, or security competition",
    "idea": "An idea, policy proposal, or planning competition",
    "other": "None of the above",
}


def _key() -> str | None:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    return key or None


def available() -> bool:
    return bool(_key())


# Bump when the questions or their criteria change, so cached answers are asked again.
QUESTION_VERSION = 3


def cache_key(title: str, desc: str) -> str:
    return hashlib.sha1(f"v{QUESTION_VERSION}\n{title}\n{desc[:DESC_CHARS]}".encode()).hexdigest()[:16]


def _questions(categories: list[str]) -> dict:
    return {
        "ai": {
            "type": "noul",
            "instructions": "Is this Korean listing a competition whose topic or required work involves "
                            "artificial intelligence (AI, machine learning, LLMs, generative AI, data science)?",
            "criteria": {
                "true": "Participants use, build, or propose AI, or the contest theme is AI",
                "false": "AI is not part of the contest, or it is only mentioned in passing",
            },
        },
        "contest": {
            "type": "noul",
            "instructions": "Does this Korean listing invite people, teams or companies to apply now — "
                            "to a competition, contest, hackathon or challenge, or to a government or "
                            "institutional support programme (grant, incubation, tenancy, accelerator)?",
            "criteria": {
                "true": "An open call for entries or applications, with a deadline to apply",
                "false": "A lecture, education program, job posting, event to attend, or a results/award announcement",
            },
        },
        "category": {
            "type": "choice",
            "instructions": "Which kind of competition is this Korean listing?",
            "criteria": {c: CATEGORY_HINTS.get(c) for c in categories + ["other"]},
        },
    }


def _ask(session: requests.Session, state: dict, questions: dict, calls: list) -> dict | None:
    """One evaluation. Appends a tracking row per HTTP attempt to calls."""
    for attempt in range(4):
        t0 = time.perf_counter()
        try:
            r = session.post(URL, json={"state": state, "model": MODEL, "questions": questions}, timeout=30)
        except requests.RequestException:
            r = None
        row = {"ms": round((time.perf_counter() - t0) * 1000), "status": r.status_code if r is not None else 0,
               "attempt": attempt}
        calls.append(row)
        if r is not None and r.ok:
            body = r.json()
            row.update(model=body.get("model"), tokens=body.get("usage", {}).get("input_tokens", 0))
            return parse(body["answers"])
        if r is not None and r.status_code not in (429, 529) and r.status_code < 500:
            print(f"  jev {r.status_code}: {r.text[:200]}")
            return None
        time.sleep(float(r.headers.get("retry-after", 0)) if r is not None and r.headers.get("retry-after") else 2 ** attempt)
    return None


def parse(a: dict) -> dict:
    return {"ai": a["ai"]["noul"], "contest": a["contest"]["noul"],
            "category": a["category"]["choice"], "categoryConf": a["category"]["confidence"],
            "categoryProbs": a["category"]["probabilities"]}


def summarize(calls: list) -> dict:
    """Operational stats for one run: volume, errors, latency, tokens, cost, model versions."""
    ok = [c for c in calls if 200 <= c["status"] < 300]
    ms = sorted(c["ms"] for c in ok)
    tokens = sum(c.get("tokens", 0) for c in ok)
    pct = lambda q: ms[min(len(ms) - 1, int(q * len(ms)))] if ms else None
    return {
        "requests": len(calls),
        "ok": len(ok),
        "retries": sum(1 for c in calls if c["attempt"] > 0),
        "errors": dict(Counter(str(c["status"]) for c in calls if not 200 <= c["status"] < 300)),
        "latencyMs": {"p50": pct(0.5), "p95": pct(0.95), "p99": pct(0.99),
                      "mean": round(statistics.fmean(ms)) if ms else None},
        "inputTokens": tokens,
        "costUsd": round(tokens / 1e6 * PRICE_PER_MTOK, 6),
        "models": dict(Counter(c["model"] for c in ok if c.get("model"))),
    }


def ask_all(items: list[dict], categories: list[str], cache: dict, run_date: str) -> dict:
    """Fill cache[cache_key] with Jev's answers for every item not asked before; return run stats.

    items: dicts with "name", optional "_desc" and "_source".
    """
    todo, seen = [], set()
    for it in items:
        k = cache_key(it["name"] or "", it.get("_desc") or "")
        if k in cache:
            cache[k]["seen"] = run_date
        elif k not in seen:
            seen.add(k)
            todo.append((k, it))
    todo = todo[:MAX_PER_RUN]
    calls: list = []
    if not todo:
        return dict(summarize(calls), asked=0, failed=0, cached=len(items))
    print(f"  jev: {len(todo)} new listings")
    questions = _questions(categories)
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {_key()}"

    def one(pair):
        k, it = pair
        state = {"title": it["name"] or "", "description": (it.get("_desc") or "")[:DESC_CHARS],
                 "site": it.get("_source", "")}
        return k, _ask(session, state, questions, calls)

    failed = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for k, ans in ex.map(one, todo):
            if ans:
                cache[k] = dict(ans, seen=run_date)
            else:
                failed += 1  # left out of the cache, retried next run
    if failed:
        print(f"  jev: {failed} requests failed")
    return dict(summarize(calls), asked=len(todo), failed=failed, cached=len(items) - len(todo))


def decide(labels: dict | None, ans: dict | None, *, rescuable: bool) -> tuple[dict | None, str]:
    """Combine the keyword verdict with Jev's answers.

    Returns (labels or None to drop, outcome) where outcome names what Jev did, for tracking.
    rescuable: the rules dropped the item only because no AI word was found in a contest listing.
    """
    if not ans:
        return labels, "no_answer"
    if ans["contest"] < NOT_CONTEST_BELOW:
        return None, "dropped_not_contest" if labels else "agreed_drop"
    if labels is None:
        if not (rescuable and ans["ai"] >= RESCUE_ABOVE and ans["contest"] >= 0.5):
            return None, "agreed_drop"
        labels, outcome = {"aiRelated": True, "confidence": "medium", "category": "other", "region": None}, "rescued"
    elif labels["confidence"] == "medium" and ans["ai"] < DROP_BELOW:
        return None, "dropped_weak"  # only a weak word like "데이터" or "SW" matched, and Jev says it isn't about AI
    else:
        outcome = "agreed_keep"
    labels = dict(labels, jev=round(ans["ai"], 2))
    if ans["ai"] >= RESCUE_ABOVE:
        labels["confidence"] = "high"
    if ans["category"] != "other" and ans["categoryConf"] >= CATEGORY_CONFIDENCE:
        if outcome == "agreed_keep" and labels["category"] != ans["category"]:
            outcome = "recategorized"
        labels["category"] = ans["category"]
    return labels, outcome
