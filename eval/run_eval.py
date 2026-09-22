"""Step 3: ask Jev about every sampled listing and record answers plus operational tracking.

    python -m eval.run_eval              # writes eval/predictions.json

For each listing:
  runs      the production question set on the production state (title, description, site),
            asked REPEATS times to measure self-consistency
  rich      the same questions with host, eligibility and prize added to the state (ablation:
            would sending more fields help?)
Every HTTP attempt is tracked (latency, status, tokens, model version) for the ops metrics.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from collector import jev
from collector.classify import Rules

HERE = Path(__file__).resolve().parent
REPEATS = 3


def main():
    sample = json.loads((HERE / "sample.json").read_text(encoding="utf-8"))
    rules = Rules.load()
    questions = jev._questions(list(rules.cfg.get("categories", {})))
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {jev._key()}"
    calls: list = []

    def one(item):
        base = {"title": item["title"], "description": item["desc"], "site": item["site"]}
        rich = dict(base, host=item.get("host") or "", eligibility=item.get("eligibility") or "",
                    prize=item.get("prize") or "")
        runs = [jev._ask(session, base, questions, calls) for _ in range(REPEATS)]
        return {"id": item["id"], "runs": runs, "rich": jev._ask(session, rich, questions, calls)}

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=jev.WORKERS) as ex:
        preds = list(ex.map(one, sample["items"]))
    wall = time.perf_counter() - t0

    ops = dict(jev.summarize(calls), wallSeconds=round(wall, 1),
               itemsPerSecond=round(len(preds) * (REPEATS + 1) / wall, 1), workers=jev.WORKERS)
    (HERE / "predictions.json").write_text(json.dumps(
        {"model": jev.MODEL, "repeats": REPEATS, "questions": questions, "ops": ops, "calls": calls,
         "items": preds}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(ops, ensure_ascii=False))


if __name__ == "__main__":
    main()
