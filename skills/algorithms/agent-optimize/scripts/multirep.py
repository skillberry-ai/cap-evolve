"""Combine several INDEPENDENT paired runs into one verdict, with the SE taken ACROSS runs.

One paired run cannot settle anything here. Measured on this benchmark: a byte-identical control,
re-run on the SAME seeds at temperature 0, moved 0.6467 -> 0.7267 — a paired delta of +0.0800 that
"passes" a k_se=1.0 gate. So the within-run SE (across tasks) understates the real uncertainty,
because it cannot see run-to-run nondeterminism at all.

The fix is to repeat the whole paired comparison on distinct seed blocks and take the spread of
the per-run deltas as the error. That estimator sees both sources of variance, needs no assumption
about where the noise comes from, and is the only thing that would have caught the retracted accept
before it was reported.

    python multirep.py cand1.json:ctl1.json cand2.json:ctl2.json ...
"""
import json
import math
import statistics as st
import sys
from pathlib import Path

def rates(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    return {t: r["rate"] for t, r in (d.get("per_task") or {}).items() if "rate" in r}


def main() -> int:
    pairs = [a.split(":") for a in sys.argv[1:]]
    if not pairs:
        print("usage: multirep.py cand.json:ctl.json ...", file=sys.stderr)
        return 2
    rows, deltas = [], []
    for cand, ctl in pairs:
        c, k = rates(cand), rates(ctl)
        common = sorted(set(c) & set(k))
        if not common:
            continue
        d = sum(c[t] - k[t] for t in common) / len(common)
        rows.append({"run": Path(cand).stem, "cand": round(sum(c[t] for t in common) / len(common), 4),
                     "ctl": round(sum(k[t] for t in common) / len(common), 4),
                     "paired_delta": round(d, 4), "tasks": len(common)})
        deltas.append(d)
    n = len(deltas)
    mean = sum(deltas) / n
    sd = st.stdev(deltas) if n > 1 else float("nan")
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    out = {
        "runs": rows,
        "n_runs": n,
        "mean_paired_delta": round(mean, 4),
        "sd_across_runs": None if n < 2 else round(sd, 4),
        "se_across_runs": None if n < 2 else round(se, 4),
        "t_like": None if n < 2 or se == 0 else round(mean / se, 2),
        "verdict": ("need >= 2 independent runs" if n < 2 else
                    "DEMONSTRATED (delta > 2 SE across runs)" if mean > 2 * se else
                    "NOT DEMONSTRATED at this sample size"),
        "note": ("SE here is across whole runs, so it includes run-to-run nondeterminism that a "
                 "single run's across-task SE cannot see. A byte-identical control re-run moved "
                 "0.0800 on this benchmark, which is why this estimator exists."),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
