"""Step 5: score Jev, the keyword rules, and the production hybrid against the reviewed labels.

    python -m eval.metrics               # writes eval/results.json

Standard classifier-evaluation metrics, reported with stratified bootstrap 95% CIs:
  thresholded   accuracy, precision, recall, F1, MCC (population-weighted by stratum size)
  ranking       ROC-AUC, average precision (PR-AUC)
  calibration   Brier score, log loss, expected calibration error (10 equal-width bins), reliability bins
  selective     accuracy vs coverage when only the most confident answers are acted on
  comparison    McNemar exact test, hybrid vs rules, on the "AI contest" decision
  robustness    self-consistency over repeated calls; ablation with a richer state
  annotation    Cohen's kappa between Claude's draft labels and the reviewed labels
No third-party packages: every metric is implemented below.
"""
import json
import math
import random
from collections import Counter
from datetime import date
from pathlib import Path

from collector import jev

HERE = Path(__file__).resolve().parent
BOOT = 1000
SEED = 7
EPS = 1e-6


# ---------- metric primitives (w = per-item weight) ----------

def confusion(y, p, w):
    tp = sum(wi for yi, pi, wi in zip(y, p, w) if yi and pi)
    fp = sum(wi for yi, pi, wi in zip(y, p, w) if not yi and pi)
    fn = sum(wi for yi, pi, wi in zip(y, p, w) if yi and not pi)
    tn = sum(wi for yi, pi, wi in zip(y, p, w) if not yi and not pi)
    return tp, fp, fn, tn


def cls_metrics(y, p, w):
    tp, fp, fn, tn = confusion(y, p, w)
    n = tp + fp + fn + tn
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return {"accuracy": (tp + tn) / n if n else None, "precision": prec, "recall": rec, "f1": f1,
            "mcc": (tp * tn - fp * fn) / den if den else 0.0}


def auroc(y, s, w):
    """Weighted Mann-Whitney AUC (ties count half)."""
    pos = [(si, wi) for yi, si, wi in zip(y, s, w) if yi]
    neg = [(si, wi) for yi, si, wi in zip(y, s, w) if not yi]
    if not pos or not neg:
        return None
    num = sum(wp * wn * (1.0 if sp > sn else 0.5 if sp == sn else 0.0) for sp, wp in pos for sn, wn in neg)
    return num / (sum(w for _, w in pos) * sum(w for _, w in neg))


def avg_precision(y, s, w):
    order = sorted(zip(s, y, w), key=lambda t: -t[0])
    total_pos = sum(wi for _, yi, wi in order if yi)
    if not total_pos:
        return None
    tp = fp = ap = 0.0
    for _, yi, wi in order:
        if yi:
            tp += wi
            ap += wi / total_pos * (tp / (tp + fp))
        else:
            fp += wi
    return ap


def brier(y, s, w):
    return sum(wi * (si - yi) ** 2 for yi, si, wi in zip(y, s, w)) / sum(w)


def log_loss(y, s, w):
    return -sum(wi * (math.log(max(si, EPS)) if yi else math.log(max(1 - si, EPS)))
                for yi, si, wi in zip(y, s, w)) / sum(w)


def reliability(y, s, w, bins=10):
    rows = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, si in enumerate(s) if lo <= si < hi or (b == bins - 1 and si == 1.0)]
        wt = sum(w[i] for i in idx)
        if not idx:
            continue
        rows.append({"lo": lo, "hi": hi, "n": len(idx), "weight": wt,
                     "meanPred": sum(w[i] * s[i] for i in idx) / wt,
                     "fracPos": sum(w[i] * y[i] for i in idx) / wt})
    return rows


def ece(rows, total):
    return sum(r["weight"] / total * abs(r["meanPred"] - r["fracPos"]) for r in rows)


def cohen_kappa(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        return None
    n = len(pairs)
    po = sum(x == y for x, y in pairs) / n
    ca, cb = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def mcnemar_exact(b, c):
    """Two-sided exact binomial test on the discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def macro_f1(y, p, labels):
    f1s = []
    for c in labels:
        tp = sum(1 for a, b in zip(y, p) if a == c and b == c)
        fp = sum(1 for a, b in zip(y, p) if a != c and b == c)
        fn = sum(1 for a, b in zip(y, p) if a == c and b != c)
        if tp + fp + fn:
            f1s.append(2 * tp / (2 * tp + fp + fn))
    return sum(f1s) / len(f1s) if f1s else None


# ---------- bootstrap ----------

def bootstrap(rows, fn, strata):
    """95% percentile CI, resampling within each stratum."""
    rng = random.Random(SEED)
    groups = {s: [r for r in rows if r["stratum"] == s] for s in strata}
    vals = []
    for _ in range(BOOT):
        res = [rng.choice(g) for g in groups.values() for _ in g]
        v = fn(res)
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    vals.sort()
    return [vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]]


def with_ci(rows, fn, strata):
    return {"value": fn(rows), "ci95": bootstrap(rows, fn, strata)}


# ---------- assemble ----------

def main():
    sample = json.loads((HERE / "sample.json").read_text(encoding="utf-8"))
    preds = {p["id"]: p for p in json.loads((HERE / "predictions.json").read_text(encoding="utf-8"))["items"]}
    pred_meta = json.loads((HERE / "predictions.json").read_text(encoding="utf-8"))
    labels = json.loads((HERE / "labels.json").read_text(encoding="utf-8"))["items"]
    sizes = sample["sizes"]
    per = Counter(it["stratum"] for it in sample["items"])
    weight = {s: sizes[s] / per[s] for s in per}
    strata = list(per)

    rows = []
    for it in sample["items"]:
        lab, pr = labels.get(it["id"]), preds.get(it["id"])
        if not lab or not pr or not pr["runs"][0]:
            continue
        ans = pr["runs"][0]
        rules = it["rules"]
        hybrid, outcome = jev.decide(dict(rules) if rules else None, ans, rescuable=it["stratum"] == "dropped")
        rows.append({
            "id": it["id"], "title": it["title"], "site": it["site"], "stratum": it["stratum"], "w": weight[it["stratum"]],
            "gold_ai": lab["ai"], "gold_contest": lab["contest"], "gold_cat": lab["category"],
            "draft": lab.get("draft", {}),
            "jev_ai": ans["ai"], "jev_contest": ans["contest"], "jev_cat": ans["category"], "jev_catconf": ans["categoryConf"],
            "rules_ai": bool(rules and rules["aiRelated"]), "rules_cat": rules["category"] if rules else None,
            "hybrid_keep": hybrid is not None, "hybrid_cat": hybrid["category"] if hybrid else (rules or {}).get("category"), "outcome": outcome,
            "runs": pr["runs"], "rich": pr["rich"],
        })

    def binary_task(key_gold, key_score, only=lambda r: True):
        rs = [r for r in rows if only(r) and r[key_gold] in (True, False)]
        y = lambda xs: [int(r[key_gold]) for r in xs]
        s = lambda xs: [r[key_score] for r in xs]
        w = lambda xs: [r["w"] for r in xs]
        rel = reliability(y(rs), s(rs), w(rs))
        out = {
            "n": len(rs), "positiveRate": sum(r["w"] for r in rs if r[key_gold]) / sum(r["w"] for r in rs),
            "auroc": with_ci(rs, lambda xs: auroc(y(xs), s(xs), w(xs)), strata),
            "averagePrecision": with_ci(rs, lambda xs: avg_precision(y(xs), s(xs), w(xs)), strata),
            "brier": with_ci(rs, lambda xs: brier(y(xs), s(xs), w(xs)), strata),
            "logLoss": with_ci(rs, lambda xs: log_loss(y(xs), s(xs), w(xs)), strata),
            "ece": with_ci(rs, lambda xs: ece(reliability(y(xs), s(xs), w(xs)), sum(w(xs))), strata),
            "reliability": rel,
            "at05": {k: with_ci(rs, lambda xs, k=k: cls_metrics(y(xs), [v >= 0.5 for v in s(xs)], w(xs))[k], strata)
                     for k in ("accuracy", "precision", "recall", "f1", "mcc")},
            "thresholdSweep": [dict(t=t, **cls_metrics(y(rs), [v >= t for v in s(rs)], w(rs)))
                               for t in [i / 20 for i in range(1, 20)]],
        }
        return out

    is_ai_contest = lambda r: r["gold_ai"] is True and r["gold_contest"] is True
    for r in rows:
        r["gold_aic"] = None if r["gold_ai"] is None or r["gold_contest"] is None else is_ai_contest(r)

    # System comparison on the production decision: "list this as an AI contest".
    def system(pred_key):
        rs = [r for r in rows if r["gold_aic"] is not None]
        return {k: with_ci(rs, lambda xs, k=k: cls_metrics([r["gold_aic"] for r in xs], [r[pred_key] for r in xs],
                                                             [r["w"] for r in xs])[k], strata)
                for k in ("accuracy", "precision", "recall", "f1", "mcc")}

    for r in rows:
        r["rules_keep"] = r["rules_ai"]
        r["jev_keep"] = r["jev_ai"] >= 0.5 and r["jev_contest"] >= 0.5
        r["hybrid_keep_ai"] = r["hybrid_keep"] and (r["rules_ai"] or r["outcome"] == "rescued")
    comp_rows = [r for r in rows if r["gold_aic"] is not None]
    b = sum(1 for r in comp_rows if r["hybrid_keep_ai"] == r["gold_aic"] and r["rules_keep"] != r["gold_aic"])
    c = sum(1 for r in comp_rows if r["hybrid_keep_ai"] != r["gold_aic"] and r["rules_keep"] == r["gold_aic"])

    # Per-stratum view of what each pipeline rule actually did.
    def stratum_view(s):
        rs = [r for r in rows if r["stratum"] == s and r["gold_aic"] is not None]
        return {"n": len(rs), "populationSize": sizes[s], "goldAiContestRate": sum(r["gold_aic"] for r in rs) / len(rs) if rs else None,
                "outcomes": {o: {"n": sum(1 for r in rs if r["outcome"] == o),
                                 "goldAiContest": sum(1 for r in rs if r["outcome"] == o and r["gold_aic"])}
                             for o in sorted({r["outcome"] for r in rs})}}

    # Category.
    cats = list(jev.CATEGORY_HINTS)
    # Compared on listings the rules kept, where all three systems assign a category.
    cat_rows = [r for r in rows if r["gold_cat"] and r["gold_contest"] and r["rules_cat"]]
    cat_acc = lambda key: (lambda xs: sum(r["w"] for r in xs if r[key] == r["gold_cat"]) / sum(r["w"] for r in xs) if xs else None)
    cat_conf = sorted(cat_rows, key=lambda r: -r["jev_catconf"])
    selective = []
    for cov in (0.2, 0.4, 0.6, 0.8, 1.0):
        top = cat_conf[:max(1, round(cov * len(cat_conf)))]
        selective.append({"coverage": cov, "accuracy": sum(r["jev_cat"] == r["gold_cat"] for r in top) / len(top),
                          "minConfidence": top[-1]["jev_catconf"]})
    confusion_cat = {g: dict(Counter(r["jev_cat"] for r in cat_rows if r["gold_cat"] == g)) for g in cats}

    # Robustness: repeated calls and richer state.
    rep = [r for r in rows if all(r["runs"])]
    spread = [max(a["ai"] for a in r["runs"]) - min(a["ai"] for a in r["runs"]) for r in rep]
    flips_ai = sum(1 for r in rep if len({a["ai"] >= 0.5 for a in r["runs"]}) > 1)
    flips_cat = sum(1 for r in rep if len({a["category"] for a in r["runs"]}) > 1)
    rich_rows = [dict(r, jev_ai=r["rich"]["ai"], jev_contest=r["rich"]["contest"], jev_cat=r["rich"]["category"])
                 for r in rows if r["rich"]]

    def quick(rs):
        ya = [r for r in rs if r["gold_ai"] in (True, False)]
        return {"aiAuroc": auroc([int(r["gold_ai"]) for r in ya], [r["jev_ai"] for r in ya], [r["w"] for r in ya]),
                "aiF1": cls_metrics([r["gold_ai"] for r in ya], [r["jev_ai"] >= 0.5 for r in ya], [r["w"] for r in ya])["f1"],
                "categoryAccuracy": cat_acc("jev_cat")([r for r in rs if r["gold_cat"] and r["gold_contest"] and r["rules_cat"]])}

    # Annotation agreement (Claude draft vs reviewed).
    drafted = [r for r in rows if r["draft"]]
    annotation = {
        "items": len(drafted),
        "changed": sum(1 for r in drafted if (r["draft"].get("ai"), r["draft"].get("contest"), r["draft"].get("category"))
                       != (r["gold_ai"], r["gold_contest"], r["gold_cat"])),
        "kappa": {k: cohen_kappa([r["draft"].get(k) for r in drafted], [r[g] for r in drafted])
                  for k, g in (("ai", "gold_ai"), ("contest", "gold_contest"), ("category", "gold_cat"))},
    }

    # Error analysis: the most confident mistakes.
    errors = sorted([r for r in rows if r["gold_ai"] in (True, False) and (r["jev_ai"] >= 0.5) != r["gold_ai"]],
                    key=lambda r: -abs(r["jev_ai"] - 0.5))[:15]

    ops = pred_meta["ops"]
    result = {
        "generated": date.today().isoformat(), "model": pred_meta["model"], "servedBy": ops.get("models"),
        "n": len(rows), "strata": {s: {"sampled": per[s], "population": sizes[s]} for s in strata},
        "annotation": annotation,
        "ai": binary_task("gold_ai", "jev_ai"),
        "contest": binary_task("gold_contest", "jev_contest"),
        "systems": {"rules": system("rules_keep"), "jev": system("jev_keep"), "hybrid": system("hybrid_keep_ai"),
                    "mcnemar": {"hybridRightRulesWrong": b, "rulesRightHybridWrong": c, "p": mcnemar_exact(b, c)}},
        "pipeline": {s: stratum_view(s) for s in strata},
        "category": {
            "n": len(cat_rows),
            "jev": with_ci(cat_rows, cat_acc("jev_cat"), strata),
            "rules": with_ci(cat_rows, cat_acc("rules_cat"), strata),
            "hybrid": with_ci(cat_rows, cat_acc("hybrid_cat"), strata),
            "jevMacroF1": macro_f1([r["gold_cat"] for r in cat_rows], [r["jev_cat"] for r in cat_rows], cats),
            "rulesMacroF1": macro_f1([r["gold_cat"] for r in cat_rows], [r["rules_cat"] for r in cat_rows], cats),
            "selective": selective, "confusion": confusion_cat,
        },
        "consistency": {"items": len(rep), "repeats": pred_meta["repeats"],
                        "meanAiSpread": sum(spread) / len(spread) if spread else None, "maxAiSpread": max(spread, default=None),
                        "aiDecisionFlipRate": flips_ai / len(rep) if rep else None,
                        "categoryFlipRate": flips_cat / len(rep) if rep else None},
        "ablation": {"base": quick(rows), "rich": quick(rich_rows)},
        "ops": dict(ops, costPer1kListingsUsd=round(ops["costUsd"] / max(1, ops["ok"]) * 1000, 5),
                    meanInputTokens=round(ops["inputTokens"] / max(1, ops["ok"]))),
        "errors": [{k: r[k] for k in ("id", "title", "site", "stratum", "jev_ai", "gold_ai", "jev_cat", "gold_cat")} for r in errors],
        "thresholds": {"DROP_BELOW": jev.DROP_BELOW, "RESCUE_ABOVE": jev.RESCUE_ABOVE,
                       "NOT_CONTEST_BELOW": jev.NOT_CONTEST_BELOW, "CATEGORY_CONFIDENCE": jev.CATEGORY_CONFIDENCE},
    }
    (HERE / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    a = result["ai"]
    print(f"n={len(rows)}  ai AUROC={a['auroc']['value']:.3f} ECE={a['ece']['value']:.3f} F1@0.5={a['at05']['f1']['value']:.3f}")
    for k in ("rules", "jev", "hybrid"):
        print(f"  {k:6} F1={result['systems'][k]['f1']['value']:.3f} P={result['systems'][k]['precision']['value']} R={result['systems'][k]['recall']['value']}")


if __name__ == "__main__":
    main()
