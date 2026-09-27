"""Send the day's digest to Telegram.

    python -m collector.notify            # 조건에 맞는 새 공고 + 임박한 마감
    python -m collector.notify --force    # 보낼 것이 없어도 전송 (연결 확인용)

Uses the same bot as the mail-notifier project: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID.
Without them it prints the message instead, so the workflow can run either way.
"""
import os
import sys

import requests

from .digest import SITE, SOON_DAYS, _fit
from .main import DATA, load
from .util import today

PROFILE = __import__("pathlib").Path(__file__).resolve().parent.parent / "config" / "profile.json"
MAX_LINES = 12


def message() -> str | None:
    items = load(DATA, {"items": []})["items"]
    profile = load(PROFILE, {})
    t = today().isoformat()
    from datetime import date, timedelta
    soon_by = (date.fromisoformat(t) + timedelta(days=SOON_DAYS)).isoformat()
    threshold = profile.get("threshold", 60)

    new = [r for r in items if r.get("firstSeen") == t and r.get("status") in ("open", "upcoming")
           and _fit(r, profile) >= threshold]
    closing = [r for r in items if r.get("status") == "open" and r.get("applyEnd")
               and t <= r["applyEnd"] <= soon_by and _fit(r, profile) >= threshold]
    closing.sort(key=lambda r: r["applyEnd"])
    if not new and not closing:
        return None

    def line(r):
        left = (date.fromisoformat(r["applyEnd"]) - date.fromisoformat(t)).days if r.get("applyEnd") else None
        tag = f"D-{left}" if left is not None and left >= 0 else (r.get("applyEnd") or "미정")
        prize = f" · {r['prize']}" if r.get("prize") else ""
        return f'· <b>{tag}</b> <a href="{r.get("url") or SITE}">{r["name"][:60]}</a>{prize}'

    parts = [f"<b>AI 공모전 레이더</b> {t}"]
    if new:
        parts += ["", f"🆕 새 공고 {len(new)}건"] + [line(r) for r in new[:MAX_LINES]]
    if closing:
        parts += ["", f"⏳ {SOON_DAYS}일 안에 마감 {len(closing)}건"] + [line(r) for r in closing[:MAX_LINES]]
    parts += ["", f'<a href="{SITE}">전체 목록</a>']
    return "\n".join(parts)


def send(text: str) -> bool:
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("TELEGRAM_TOKEN/TELEGRAM_CHAT_ID 가 없어 출력만 합니다:\n")
        print(text)
        return False
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                            "disable_web_page_preview": True}, timeout=15)
    r.raise_for_status()
    print("텔레그램 전송 완료")
    return True


def main(argv: list[str]):
    text = message()
    if not text:
        if "--force" not in argv:
            return print("보낼 내용이 없습니다 (새 공고도, 임박한 마감도 없음).")
        text = f"AI 공모전 레이더 {today().isoformat()} — 오늘은 알릴 것이 없습니다."
    send(text)


if __name__ == "__main__":
    main(sys.argv[1:])
