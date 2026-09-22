"""Step 4: turn the reviewed labels into eval/labels.json.

    python -m eval.collect_labels <dump_dir>   # dump_dir: the review page's items/*.json, saved by Claude
    python -m eval.collect_labels --draft      # dry run: use Claude's draft labels as if reviewed

A reviewed item uses the reviewer's answer; an unreviewed one is left out, so metrics only ever
count human-checked labels. "unsure" (null) answers are kept and excluded per metric.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATS = {"hackathon", "startup", "tourism", "academic", "data", "creative", "youth", "dev", "idea", "other"}


def parse_draft():
    v = {"1": True, "0": False, "?": None}
    out = {}
    for line in (HERE / "draft_labels.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        p = line.split(" ", 4)
        out[p[0]] = {"ai": v[p[1]], "contest": v[p[2]], "category": p[3], "note": p[4] if len(p) > 4 else ""}
    return out


def main():
    draft = parse_draft()
    if sys.argv[1:] == ["--draft"]:
        items = {i: dict(d, draft=d, reviewed=False) for i, d in draft.items()}
        source = "draft (not reviewed)"
    else:
        dump = Path(sys.argv[1])
        items = {}
        for f in sorted(dump.rglob("s*.json")):
            doc = json.loads(f.read_text(encoding="utf-8"))
            doc = doc.get("data", doc)
            r = doc.get("review")
            if not r:
                continue
            assert r["category"] in CATS, f"{f.stem}: bad category {r['category']}"
            items[f.stem] = {"ai": r["ai"], "contest": r["contest"], "category": r["category"],
                             "note": r.get("note", ""), "draft": draft[f.stem], "reviewed": True}
        source = f"review page ({len(items)} of {len(draft)} reviewed)"
    (HERE / "labels.json").write_text(json.dumps({"source": source, "items": items}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print(f"labels.json: {len(items)} items from {source}")


if __name__ == "__main__":
    main()
