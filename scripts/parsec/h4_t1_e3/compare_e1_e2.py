#!/usr/bin/env python3
"""Compare h4_t1_e2 against h4_t1_e1 for whatever e2 has finished so far.

Same bundle, same tasks, so the e1->e2 delta is harness noise, not capability.
Also shows George's n=1 reference, and our own mean-of-max, which is the
statistic comparable to his method (n=1, then rerun/rescore the failures).
"""
from __future__ import annotations
import glob, json, os, statistics as st, sys

E1_SNAPSHOT = "/tmp/h4_t1_e1_results.json"
GEORGE_INITIAL, GEORGE_REVIEWED = 0.727, 0.815


def arm(prefix):
    out = {}
    for base in sorted(glob.glob(f".capevolve/{prefix}_*")):
        if not os.path.isdir(base):
            continue
        task = os.path.basename(base)[len(prefix) + 1:]
        runs = [r for r in sorted(glob.glob(base + "/run_*")) if os.path.exists(r + "/baseline.json")]
        if not runs:
            continue
        tr = []
        for f in sorted(glob.glob(runs[-1] + "/rollouts/val/*.json")):
            rj = json.load(open(f))["rollout"]["metadata"]["trial_result"].get("reward_json") or {}
            if isinstance(rj, str):
                try: rj = json.loads(rj)
                except Exception: rj = {}
            if rj.get("reward") is not None:
                tr.append(rj["reward"])
        if tr:
            out[task] = tr
    return out


def main() -> int:
    e1s = {r["task"]: r for r in json.load(open(E1_SNAPSHOT))}
    e2 = arm("h4_t1_e2")
    if not e2:
        print("e2 has no completed tasks yet"); return 0
    done = sorted(e2)
    w = 46
    print(f"h4_t1_e1 vs h4_t1_e3 — identical T1 bundle, identical tasks — {len(done)}/30 done\n")
    hdr = f"{'task':<{w}}{'e1':>7}{'e2':>7}{'delta':>8}{'e1 trials':>22}{'e2 trials':>22}{'George':>8}"
    print(hdr); print("-" * len(hdr))
    for t in done:
        a = e1s.get(t)
        m1 = st.mean(a["trials"]) if a else float("nan")
        m2 = st.mean(e2[t])
        g = a.get("george") if a else None
        f = lambda xs: "[" + " ".join(f"{x:.2f}" for x in xs) + "]"
        print(f"{t[:w]:<{w}}{m1:>7.3f}{m2:>7.3f}{m2-m1:>+8.3f}"
              f"{f(a['trials']) if a else '-':>22}{f(e2[t]):>22}"
              f"{(f'{g:.3f}' if g is not None else '-'):>8}")
    print("-" * len(hdr))
    m1 = st.mean([st.mean(e1s[t]["trials"]) for t in done if t in e1s])
    m2 = st.mean([st.mean(e2[t]) for t in done])
    mx = st.mean([max(e2[t]) for t in done])
    gs = [e1s[t]["george"] for t in done if t in e1s and e1s[t].get("george") is not None]
    print(f"{'MEAN of completed':<{w}}{m1:>7.3f}{m2:>7.3f}{m2-m1:>+8.3f}{'':>44}{st.mean(gs):>8.3f}")
    ds = [st.mean(e2[t]) - st.mean(e1s[t]["trials"]) for t in done if t in e1s]
    moved = [t for t in done if t in e1s and abs(st.mean(e2[t]) - st.mean(e1s[t]["trials"])) > 0.001]
    print()
    print(f"  harness noise (e1->e2, same bundle): mean {st.mean(ds):+.4f}"
          + (f"  mean|delta| {st.mean([abs(d) for d in ds]):.4f}"
             f"  sd {st.stdev(ds):.4f}" if len(ds) > 1 else ""))
    print(f"  tasks that moved at all: {len(moved)}/{len(done)}")
    print(f"  our mean-of-max (George's method): {mx:.3f}   "
          f"George initial {GEORGE_INITIAL:.3f}   reviewed {GEORGE_REVIEWED:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
