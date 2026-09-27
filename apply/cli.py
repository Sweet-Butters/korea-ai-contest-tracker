"""지원 준비 도구.

    python -m apply list                    확정 목록 보기
    python -m apply add <id|이름 일부> …     지원 목록에 추가
    python -m apply prep [id …]             공고를 읽고 초안 묶음 생성 (기본: 준비중인 것 전부)
    python -m apply status <id> <상태>       interested|preparing|ready|submitted|skipped
    python -m apply open <id>                접수 페이지를 브라우저로 열기 (대행 입력 시작점)

확정 목록(config/applications.json)에는 대회 id와 상태만 들어갑니다. 개인정보와 초안은
로컬(profile.local.json, drafts/)에만 있고 공개 저장소에 올라가지 않습니다.
"""
import json
import subprocess
import sys
from pathlib import Path

from . import draft, form, from_site, profile, requirements

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "config" / "applications.json"
DATA = ROOT / "data" / "contests.json"
STATUSES = ["interested", "preparing", "ready", "submitted", "skipped"]


def _contests() -> dict:
    return {c["id"]: c for c in json.loads(DATA.read_text(encoding="utf-8"))["items"]}


def _queue() -> list:
    if QUEUE.exists():
        return json.loads(QUEUE.read_text(encoding="utf-8")).get("items", [])
    return []


def _save(items):
    QUEUE.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _find(token: str, contests: dict) -> dict | None:
    if token in contests:
        return contests[token]
    hits = [c for c in contests.values() if token.lower() in c["name"].lower()]
    if len(hits) == 1:
        return hits[0]
    for c in hits[:8]:
        print(f"  {c['id']}  {c['name'][:60]}")
    print(f"'{token}': {'여러 건이 맞습니다. id로 지정하세요.' if hits else '찾지 못했습니다.'}")
    return None


def cmd_list():
    contests = _contests()
    items = _queue()
    if not items:
        return print("지원 목록이 비어 있습니다. python -m apply add <이름 일부>")
    for it in items:
        c = contests.get(it["id"], {})
        ready = (draft.DRAFTS / it["id"]).exists()
        print(f"[{it['status']:<10}] {c.get('applyEnd') or '마감 미정':<10} {c.get('name', it.get('name', it['id']))[:52]}"
              f"{'  · 초안 있음' if ready else ''}")


def cmd_add(tokens):
    contests, items = _contests(), _queue()
    known = {i["id"] for i in items}
    for t in tokens:
        c = _find(t, contests)
        if not c or c["id"] in known:
            continue
        items.append({"id": c["id"], "name": c["name"], "status": "preparing"})
        known.add(c["id"])
        print(f"추가: {c['name'][:60]}")
    _save(items)


def cmd_status(cid, status):
    if status not in STATUSES:
        return print(f"상태는 {', '.join(STATUSES)} 중 하나여야 합니다.")
    items = _queue()
    for it in items:
        if it["id"] == cid:
            it["status"] = status
            _save(items)
            return print(f"{it['name'][:50]} → {status}")
    print("목록에 없습니다.")


def cmd_prep(ids):
    contests = _contests()
    targets = ids or [i["id"] for i in _queue() if i["status"] in ("interested", "preparing")]
    if not targets:
        return print("준비할 대상이 없습니다.")
    try:
        p = profile.load()
    except profile.MissingProfile as e:
        return print(e)
    for cid in targets:
        c = contests.get(cid) or _find(cid, contests)
        if not c:
            continue
        if not c.get("url"):
            print(f"건너뜀(원문 링크 없음): {c['name'][:50]}")
            continue
        print(f"읽는 중: {c['name'][:50]}")
        try:
            req = requirements.extract(c["url"])
        except Exception as e:
            print(f"  공고를 읽지 못했습니다: {str(e)[:100]}")
            req = {"source": c["url"], "documents": [], "formats": [], "steps": [], "cautions": []}
        out = draft.build(c, req, p)
        print(f"  → {out}  ({', '.join(f.name for f in sorted(out.iterdir()))})")
        print(f"  접수: {req.get('applyMethod') or '확인 필요'} {req.get('applyUrl') or req.get('email') or ''}")


def cmd_open(cid):
    contests = _contests()
    c = contests.get(cid) or _find(cid, contests)
    if not c:
        return
    req_file = draft.DRAFTS / c["id"] / "requirements.json"
    req = json.loads(req_file.read_text(encoding="utf-8")) if req_file.exists() else {}
    url = req.get("applyUrl") or c.get("url")
    print(f"접수 페이지: {url}")
    print("Orca 브라우저 탭으로 엽니다. 로그인과 자격·동의 항목, 최종 제출은 직접 하세요.")
    try:
        subprocess.run(["orca", "tab", "create", "--url", url, "--json"], check=False)
    except FileNotFoundError:
        print("orca CLI가 없어 열지 못했습니다. 위 주소를 직접 여세요.")


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        return print(__doc__)
    cmd, *rest = argv
    if cmd == "list":
        cmd_list()
    elif cmd == "add":
        cmd_add(rest)
    elif cmd == "prep":
        cmd_prep(rest)
    elif cmd == "status" and len(rest) == 2:
        cmd_status(*rest)
    elif cmd == "open" and rest:
        cmd_open(rest[0])
    elif cmd == "profile":
        from_site.main(rest[0] if rest else None)
    elif cmd == "capture" and rest:
        c = _contests().get(rest[0]) or _find(rest[0], _contests())
        if c:
            form.capture(c["id"], rest[1] if len(rest) > 1 else None)
    elif cmd == "answers" and rest:
        c = _contests().get(rest[0]) or _find(rest[0], _contests())
        if c:
            form.answers(c["id"], c)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
