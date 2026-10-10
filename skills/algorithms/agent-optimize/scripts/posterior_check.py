"""posterior_check — print the paired-posterior read-out of every candidate in a run dir.

For each tag in the evidence ledger (eval_index.jsonl) other than the parent: P(D > 0.02), mean D,
the decision the sequential rule would take, and trial counts. Read-only, advisory.

  python posterior_check.py --run-dir <run> [--parent <tag>] [--split val] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

from cap_evolve import RunDir, eval_index, posterior


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--parent", default=None, help="parent tag (default: the run's best_id)")
    ap.add_argument("--split", default="val")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rd = RunDir.open(Path(a.run_dir))
    parent = a.parent or rd.best_id()
    if not parent:
        print("no parent: pass --parent", file=sys.stderr)
        return 2
    ph = eval_index.cap_hash(rd.candidate_dir(parent))
    tags = sorted({r["tag"] for r in eval_index.rows(rd) if r["split"] == a.split})
    out = {}
    for t in tags:
        if t == parent or eval_index.cap_hash(rd.candidate_dir(t)) == ph:
            continue  # the parent and its byte-identical copies are the baseline, not candidates
        out[t] = posterior.summarize(rd, t, parent, a.split)
    if a.json:
        print(json.dumps({"parent": parent, "candidates": out}, indent=2))
        return 0
    print(f"parent={parent} split={a.split}")
    for t, v in out.items():
        if v is None:
            print(f"  {t:20s} no evidence")
        else:
            print(f"  {t:20s} p_beat={v['p_beat']:.2f} dmean={v['d_mean']:+.3f} "
                  f"n={v['n_cand']}/{v['n_parent']} -> {v['decision'] or 'continue'}"
                  + (f" canary={v['canary_tasks']}" if v["canary_tasks"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
