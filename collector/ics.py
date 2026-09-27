"""Publish the deadlines as a calendar feed you can subscribe to.

    python -m collector.ics

Writes data/calendar.ics (추천 조건에 맞는 것) and data/calendar-all.ics (AI 관련 전체).
Google Calendar and iPhone both subscribe to a URL and refresh on their own, so nothing has to
be connected or authorised — the daily run updates the file and the phone follows.
"""
from pathlib import Path

from .digest import _fit, load_profile
from .main import DATA, load
from .util import dates_in, today

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://sweet-butters.github.io/korea-ai-contest-tracker/"
FEEDS = {"calendar.ics": "AI 공모전 (내 조건)", "calendar-all.ics": "AI 공모전 (전체)"}


def _esc(s) -> str:
    return (str(s or "").replace("\\", "\\\\").replace(";", r"\;")
            .replace(",", r"\,").replace("\n", r"\n"))


def _event(uid: str, date: str, summary: str, desc: str, url: str | None) -> list[str]:
    stamp = date.replace("-", "")
    # All-day event: DTEND is the next day, per RFC 5545.
    from datetime import date as d, timedelta
    end = (d.fromisoformat(date) + timedelta(days=1)).isoformat().replace("-", "")
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}@korea-ai-contest-tracker",
        f"DTSTAMP:{today().isoformat().replace('-', '')}T000000Z",
        f"DTSTART;VALUE=DATE:{stamp}",
        f"DTEND;VALUE=DATE:{end}",
        f"SUMMARY:{_esc(summary)}",
        f"DESCRIPTION:{_esc(desc)}",
    ]
    if url:
        lines.append(f"URL:{url}")
    lines += [
        "BEGIN:VALARM", "TRIGGER:-P2D", "ACTION:DISPLAY",
        f"DESCRIPTION:{_esc(summary)}", "END:VALARM",
        "END:VEVENT",
    ]
    return lines


def _describe(r: dict) -> str:
    bits = [r.get("host"), r.get("prize") and f"상금 {r['prize']}", r.get("eligibility") and f"대상 {r['eligibility']}"]
    if r.get("dateNote"):
        bits.append(f"※ 마감일 {r['dateNote']} — 원문 확인")
    bits.append(r.get("url") or SITE)
    return "\n".join(b for b in bits if b)


def build(items: list[dict], name: str) -> str:
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//korea-ai-contest-tracker//KR",
           "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
           f"X-WR-CALNAME:{_esc(name)}", "X-WR-TIMEZONE:Asia/Seoul",
           f"X-WR-CALDESC:{_esc('매일 자동 수집됩니다 — ' + SITE)}"]
    t = today().isoformat()
    for r in items:
        end = r.get("applyEnd")
        if end and end >= t:
            out += _event(f"{r['id']}-end", end, f"[마감] {r['name']}", _describe(r), r.get("url"))
        start = r.get("applyStart")
        if start and start > t:
            out += _event(f"{r['id']}-start", start, f"[접수 시작] {r['name']}", _describe(r), r.get("url"))
        for i, d in enumerate(sorted(set(dates_in(r.get("eventDates"))))):
            if d > t and d != end:
                out += _event(f"{r['id']}-ev{i}", d, f"[일정] {r['name']}", _describe(r), r.get("url"))
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


def main():
    items = load(DATA, {"items": []})["items"]
    profile = load_profile()
    live = [r for r in items if r.get("status") in ("open", "upcoming", "in_progress")]
    mine = [r for r in live if _fit(r, profile) >= profile.get("threshold", 60)]
    for file, name in FEEDS.items():
        rows = mine if file == "calendar.ics" else [r for r in live if r.get("aiRelated") is not False]
        (ROOT / "data" / file).write_text(build(rows, name), encoding="utf-8")
        print(f"{file}: 대회 {len(rows)}건")


if __name__ == "__main__":
    main()
