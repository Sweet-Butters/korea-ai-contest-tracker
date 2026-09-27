"""The application queue (applications.json) in the private repo Sweet-Butters/private-kit.

The admin page writes it there. This reads and writes the same file through the GitHub Contents
API with a token from PRIVATE_KIT_TOKEN, GITHUB_TOKEN, or the GitHub CLI (`gh auth token`).
Without a token it falls back to a local, git-ignored config/applications.json.
"""
import base64
import json
import os
import subprocess
from pathlib import Path

import requests

REPO = "Sweet-Butters/private-kit"
PATH = "applications.json"
API = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
LOCAL = Path(__file__).resolve().parent.parent / "config" / "applications.json"

_sha: str | None = None


def _token() -> str:
    for name in ("PRIVATE_KIT_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name, "").strip():
            return os.environ[name].strip()
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=15)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def load() -> list:
    global _sha
    token = _token()
    if not token:
        print(f"(토큰이 없어 로컬 {LOCAL.name} 을 씁니다. gh auth login 또는 PRIVATE_KIT_TOKEN 을 설정하면 {REPO} 와 맞춥니다.)")
        return json.loads(LOCAL.read_text(encoding="utf-8")).get("items", []) if LOCAL.exists() else []
    r = requests.get(API, headers=_headers(token), timeout=30)
    if r.status_code == 404:
        _sha = None
        return []
    r.raise_for_status()
    j = r.json()
    _sha = j["sha"]
    return json.loads(base64.b64decode(j["content"]).decode("utf-8")).get("items", [])


def save(items: list, message: str = "chore: update application queue from apply CLI"):
    global _sha
    body = json.dumps({"items": items}, ensure_ascii=False, indent=1) + "\n"
    token = _token()
    if not token:
        LOCAL.write_text(body, encoding="utf-8")
        return
    payload = {"message": message, "content": base64.b64encode(body.encode("utf-8")).decode("ascii"), "branch": "main"}
    if _sha:
        payload["sha"] = _sha
    r = requests.put(API, headers=_headers(token), json=payload, timeout=30)
    if r.status_code in (409, 422):
        raise SystemExit("지원 목록이 다른 곳(관리 페이지 등)에서 먼저 바뀌었습니다. 다시 실행하세요.")
    r.raise_for_status()
    _sha = r.json()["content"]["sha"]
