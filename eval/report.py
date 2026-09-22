"""Step 6: build eval/report.html from results.json, the run log and narrative.json.

    python -m eval.report

narrative.json holds the prose (verdict, findings, limits) written after reading the numbers;
everything numeric comes from results.json and data/jev_runs.jsonl.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main():
    results = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    labels = json.loads((HERE / "labels.json").read_text(encoding="utf-8"))
    narrative = json.loads((HERE / "narrative.json").read_text(encoding="utf-8"))
    runs_file = ROOT / "data" / "jev_runs.jsonl"
    runs = [json.loads(l) for l in runs_file.read_text(encoding="utf-8").splitlines() if l.strip()] if runs_file.exists() else []
    payload = {"results": results, "labelSource": labels["source"], "narrative": narrative, "runs": runs}
    template = (HERE / "report_template.html").read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    (HERE / "report.html").write_text(template.replace("/*__DATA__*/null", blob), encoding="utf-8")
    print("wrote eval/report.html")


if __name__ == "__main__":
    main()
