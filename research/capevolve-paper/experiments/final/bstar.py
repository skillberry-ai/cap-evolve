#!/usr/bin/env python3
"""bstar.py: matched budget B* per suite from rollout COUNTERS only (decisions.md 2026-10-11 11:15, CHECKPOINT_PROTOCOL.txt 2).

    B* = floor_50( min over every Tier 1 (main) seed of every Tier 1 (main) arm of its counted-rollout total ), at least 200.

Counter source = analysis/scripts/collect_metrics.counted_rollouts (the same function that produced configs_by_arm.json), in
order: <run>/rollout_counter.json:total|rollouts, <run>/logs/rollout_counter.json:total, .capevolve/run_*/state.json
spent.metric_calls, eval_opt.json, global_counter.json.  No score, reward or candidate file is read.

A seed below the floor is reported as `incomplete` (analysis plan 5A: its arm leaves the matched family, no selective seeding);
B* is still floored at 200 for the others.  "Tier 1-cheap" arms (suite A: trace2skill, ace, mipro) do not bind B*; their
counters are listed and `bstar_if_cheap_bind` is given for information.

    bstar.py --suite A [--fake 50] [--out DIR]
Writes bstar_<suite>.json (or bstar_<suite>.FAKE<n>.json with --fake: dry runs only, never frozen).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fe_common as C  # noqa: E402


NONBINDING = ("native_finish", "guard_stop")     # N* rule + token-guard addendum: neither binds; count disclosed


def floor_step(n, step=C.BSTAR_STEP, floor=C.BSTAR_FLOOR):
    return max(floor, (int(n) // step) * step)


def compute(suite):
    cm = C.collect_metrics()
    spec = C.SUITES[suite]
    rows = []
    for tier, arms in (("main", spec["main"]), ("cheap", spec["cheap"]), ("control", spec["controls"]), ("exploratory", spec.get("exploratory", []))):
        for arm in arms:
            for seed in C.SEEDS:
                rd = C.run_dir(suite, arm, seed)
                if not rd.exists():
                    rows.append({"arm": arm, "seed": seed, "tier": tier, "run_dir": str(rd), "counter": None, "source": "no_run_dir"})
                    continue
                n, src = cm.counted_rollouts(rd)
                st, ev = C.native_status(rd)
                rows.append({"arm": arm, "seed": seed, "tier": tier, "run_dir": str(rd), "counter": n, "source": src, "native_status": st, "native_evidence": ev})
    main = [r for r in rows if r["tier"] == "main"]
    known_all = [r for r in main if r["counter"] is not None]
    # N* rule: a primary seed that terminated NATIVELY before the cutoff does not bind; crashes and infra stops do
    known = [r for r in known_all if r.get("native_status") not in NONBINDING] or known_all
    unknown = [r for r in main if r["counter"] is None]
    out = {"suite": suite, "generated_utc": C.now_utc(), "rule": "floor_50(min counted rollouts over all main-tier seeds), floor 200",
           "cutoff_utc": C.CUTOFF_UTC, "runs": rows, "main_arms": spec["main"], "cheap_arms": spec["cheap"]}
    if not known:
        out.update(bstar=None, error="no counters")
        return out
    lo = min(known, key=lambda r: (r["counter"], r["arm"], r["seed"]))
    out["natively_finished"] = {"%s/s%d" % (r["arm"], r["seed"]): {"count": r["counter"], "evidence": r["native_evidence"], "stop_kind": r["native_status"]} for r in known_all if r.get("native_status") in NONBINDING}
    out["crashed"] = ["%s/s%d" % (r["arm"], r["seed"]) for r in known_all if r.get("native_status") == "crashed"]
    out["min_main_counter"] = lo["counter"]
    out["binding_run"] = "%s/s%d" % (lo["arm"], lo["seed"])
    out["bstar_raw"] = lo["counter"]
    out["bstar"] = floor_step(lo["counter"])
    out["floored_to_200"] = lo["counter"] < C.BSTAR_FLOOR
    out["incomplete_seeds"] = ["%s/s%d" % (r["arm"], r["seed"]) for r in known_all if r["counter"] < C.BSTAR_FLOOR and r.get("native_status") not in NONBINDING] + \
                              ["%s/s%d" % (r["arm"], r["seed"]) for r in unknown]
    cheap = [r for r in rows if r["tier"] == "cheap" and r["counter"] is not None]
    if cheap:
        out["bstar_if_cheap_bind"] = floor_step(min([lo["counter"]] + [r["counter"] for r in cheap]))
    per_arm = {}
    for r in main:
        if r["counter"] is not None:
            per_arm.setdefault(r["arm"], []).append(r["counter"])
    out["min_counter_by_arm"] = {a: min(v) for a, v in per_arm.items()}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, choices=sorted(C.SUITES))
    ap.add_argument("--fake", type=int, default=None, help="dry-run only: override B* (written to a separate FAKE file)")
    ap.add_argument("--out", default=str(C.MANIFESTS))
    a = ap.parse_args(argv)
    res = compute(a.suite)
    if a.fake is not None:
        res["bstar_computed"] = res.get("bstar")
        res["bstar"] = a.fake
        res["FAKE"] = True
        name = "bstar_%s.FAKE%d.json" % (a.suite, a.fake)
    else:
        name = "bstar_%s.json" % a.suite
    C.write_json_atomic(Path(a.out) / name, res)
    print("suite %s: B*=%s (raw min %s at %s); incomplete=%s -> %s" % (
        a.suite, res.get("bstar"), res.get("min_main_counter"), res.get("binding_run"), res.get("incomplete_seeds"), Path(a.out) / name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
