"""What changed today, written where you will actually see it.

    python -m collector.digest            # data/digest.md 갱신 (워크플로가 매일 실행)
    python -m collector.digest --issue    # 위 내용을 GitHub 이슈로도 올림 (gh 필요)

Running an agent to ask "anything new?" is the part worth removing: the daily collection already
knows. This turns its result into a short list — newly found contests that fit the profile, and
what closes within a week — so the only manual step left is deciding to apply.
"""
import json
import subprocess
import sys
from pathlib import Path

from .main import DATA, dump, load
from .util import today

ROOT = Path(__file__).resolve().parent.parent
DIGEST = ROOT / "data" / "digest.md"
PROFILE = ROOT / "config" / "profile.json"
SITE = "https://sweet-butters.github.io/korea-ai-contest-tracker/"
SOON_DAYS = 7


def _fit(rec: dict, profile: dict) -> int:
    """Same idea as the site's score, kept simple: category, interests, prize, region."""
    if rec.get("aiRelated") is False and rec.get("category") not in profile.get("categories", []):
        return 0
    score = 30 if rec.get("category") in profile.get("categories", []) else 0
    name = rec.get("name", "")
    score += min(30, 15 * sum(1 for w in profile.get("interests", []) if w and w.lower() in name.lower()))
    if rec.get("jev") is not None:
        score += round(15 * rec["jev"])
    region = rec.get("region")
    if not region or region in profile.get("regions", []):
        score += 10
    return score


def build() -> str:
    items = load(DATA, {"items": []})["items"]
    profile = load(PROFILE, {})
    t = today().isoformat()
    from datetime import date, timedelta
    soon_by = (date.fromisoformat(t) + timedelta(days=SOON_DAYS)).isoformat()

    new = [r for r in items if r.get("firstSeen") == t and r.get("status") in ("open", "upcoming")]
    new.sort(key=lambda r: -_fit(r, profile))
    closing = [r for r in items if r.get("status") == "open" and r.get("applyEnd")
               and t <= r["applyEnd"] <= soon_by and _fit(r, profile) >= profile.get("threshold", 60)]
    closing.sort(key=lambda r: r["applyEnd"])

    def row(r):
        bits = [r.get("applyEnd") or "마감 미정", r.get("host") or "", r.get("prize") or ""]
        line = f"- **{r['name']}** — {' · '.join(b for b in bits if b)}"
        return line + (f"\n  {r['url']}" if r.get("url") else "")

    out = [f"# {t} 새 공고", ""]
    fits = [r for r in new if _fit(r, profile) >= profile.get("threshold", 60)]
    out += [f"오늘 새로 들어온 {len(new)}건 중 조건에 맞는 것 {len(fits)}건.", ""]
    out += [row(r) for r in fits[:15]] or ["(조건에 맞는 새 공고 없음)"]
    out += ["", f"## {SOON_DAYS}일 안에 마감 ({len(closing)}건)", ""]
    out += [row(r) for r in closing[:15]] or ["(없음)"]
    out += ["", f"전체 목록: {SITE}", ""]
    return "\n".join(out)


def main(argv: list[str]):
    text = build()
    DIGEST.write_text(text, encoding="utf-8")
    print(text)
    if "--issue" in argv:
        title = f"새 공고 {today().isoformat()}"
        r = subprocess.run(["gh", "issue", "create", "--title", title, "--body", text],
                           capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip()[:200])


if __name__ == "__main__":
    main(sys.argv[1:])
