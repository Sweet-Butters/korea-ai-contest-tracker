"""Where the applicant's personal details come from.

Never in the public repo. In order of preference:
1. APPLICANT_PROFILE_JSON — the whole profile as JSON in an environment variable
2. APPLICANT_PROFILE_PATH — a path to a JSON file
3. profile.local.json at the repo root (git-ignored; copy profile.local.example.json)
4. A private GitHub repo: APPLICANT_PROFILE_REPO=owner/repo[:path] plus GITHUB_TOKEN
"""
import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "profile.local.json"


class MissingProfile(Exception):
    pass


def load() -> dict:
    raw = os.environ.get("APPLICANT_PROFILE_JSON", "").strip()
    if raw:
        return json.loads(raw)

    path = os.environ.get("APPLICANT_PROFILE_PATH", "").strip()
    for candidate in (Path(path) if path else None, LOCAL):
        if candidate and candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))

    repo = os.environ.get("APPLICANT_PROFILE_REPO", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if repo and token:
        name, _, file = repo.partition(":")
        r = requests.get(
            f"https://api.github.com/repos/{name}/contents/{file or 'profile.json'}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.raw"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json() if isinstance(r.json(), dict) else json.loads(r.text)

    raise MissingProfile(
        "지원자 정보를 찾지 못했습니다. profile.local.example.json 을 profile.local.json 으로 "
        "복사해 채우거나, APPLICANT_PROFILE_PATH / APPLICANT_PROFILE_REPO 를 설정하세요."
    )


# Never sent to an LLM: these identify the person and add nothing to a draft.
PRIVATE_FIELDS = ("name", "email", "phone", "birth", "address")


def summary(p: dict, for_llm: bool = False) -> str:
    """The applicant's facts as a short block.

    for_llm=True leaves out contact details and the name. Free LLM tiers may keep what they are
    sent, and a draft does not need them — local templates fill those in afterwards.
    """
    lines = []
    if not for_llm:
        lines += [f"이름: {p.get('name', '')}", f"연락처: {p.get('email', '')} {p.get('phone', '')}".strip()]
    lines += [
        f"소속: {' '.join(x for x in (p.get('school'), p.get('major'), p.get('grade')) if x)}",
        f"지역: {p.get('region', '')}",
    ]
    if p.get("intro"):
        lines.append(f"소개: {p['intro']}")
    if p.get("strengths"):
        lines.append("강점: " + ", ".join(p["strengths"]))
    for pr in p.get("projects", []):
        lines.append(
            f"프로젝트: {pr.get('name')} — {pr.get('summary')} (역할: {pr.get('role')}, 결과: {pr.get('result')}, {pr.get('link')})"
        )
    for a in p.get("awards", []):
        lines.append(f"수상: {a}")
    if p.get("links"):
        lines.append("링크: " + ", ".join(f"{k} {v}" for k, v in p["links"].items()))
    return "\n".join(x for x in lines if x.strip(" :"))


def redacted(p: dict) -> dict:
    """The profile with identifying fields removed, for anything leaving this machine."""
    return {k: v for k, v in p.items() if k not in PRIVATE_FIELDS}
