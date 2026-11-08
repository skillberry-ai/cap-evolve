#!/usr/bin/env python3
"""Infrastructure audit of the sealed-test comparison (Global cand_0005 vs Seed), recorded trials only.

For every trial: harness-errored or valid, and which error signatures its tool results contain:
  mock_internal    "Internal error generating mock response"  (an HTTP/agent error wrapped by the simulator;
                   in the control-batch outage the body was an OpenShift "Application is not available" page)
  app_unavail      "Application is not available"             (the outage page itself)
  timeout          "did not respond within 240s ... never answered"  (a simulator timeout)
  not_modelled     "is not modelled by the simulator"         (an unsupported tool; simulator-specific)
Then recomputes the paired test delta (by task, bootstrap 95% CI) after excluding flagged trials, or tasks.

"Confirmed" here means mock_internal or app_unavail. Timeouts and not_modelled are reported separately:
they are simulator behaviour, present in both arms at similar rates, and the harness does not mark them
invalid. See the printed table for the sensitivity of the headline to each rule.

Usage:  python3 test_infra_audit.py
"""
import collections
import glob
import json
import random
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

SIG = {"mock_internal": "Internal error generating mock response", "app_unavail": "Application is not available",
       "timeout": "never answered", "not_modelled": "is not modelled by the simula"}
ROLL = C.G2_RUN / "rollouts" / "test"
TEST = C.splits()["test"]


def scan(tag):
    rows = []
    for f in glob.glob(str(ROLL / f"*__{tag}__t*.json")):
        r = json.loads(Path(f).read_text())
        ro = r["rollout"]
        td = (ro.get("metadata") or {}).get("trial_dir")
        rec = {"task": Path(f).name.split("__")[0], "reward": r["score"]["reward"], "harness_err": bool(ro.get("error")),
               "flags": collections.Counter(), "readable": False}
        if td and Path(td).exists() and C.find_one(td, "agent.jsonl"):
            rec["readable"] = True
            for kind, b in C.trial_messages(td):
                if kind == "tool_result":
                    c = b.get("content")
                    c = c if isinstance(c, str) else json.dumps(c)
                    for k, s in SIG.items():
                        rec["flags"][k] += s in c
        rows.append(rec)
    return rows


def boot(x):
    rng = random.Random(0)
    bs = sorted(st.fmean(rng.choices(x, k=len(x))) for _ in range(10000))
    return bs[250], bs[9750]


def delta(data, bad, mode):
    arms, flagged = {}, {}
    for a, rows in data.items():
        per, fl = collections.defaultdict(list), set()
        for r in rows:
            if r["harness_err"]:
                continue
            if bad(r):
                fl.add(r["task"])
                if mode == "trial":
                    continue
            per[r["task"]].append(r["reward"])
        arms[a], flagged[a] = per, fl
    tasks = [t for t in TEST if arms["seed"].get(t) and arms["g"].get(t)]
    if mode == "task":
        tasks = [t for t in tasks if t not in flagged["seed"] | flagged["g"]]
    d = [st.fmean(arms["g"][t]) - st.fmean(arms["seed"][t]) for t in tasks]
    lo, hi = boot(d)
    return (len(tasks), st.fmean(st.fmean(arms["seed"][t]) for t in tasks), st.fmean(st.fmean(arms["g"][t]) for t in tasks),
            st.fmean(d), st.stdev(d) / len(d) ** .5 if len(d) > 1 else 0.0, lo, hi)


if __name__ == "__main__":
    data = {"seed": scan("FINAL_seed"), "g": scan("FINAL")}
    print("== Trial counts and error signatures (trials containing the signature)")
    for a, name in (("seed", "Seed"), ("g", "cand_0005")):
        rows = data[a]
        valid = [r for r in rows if not r["harness_err"]]
        print(f"{name:10s} trials {len(rows)}  harness-errored {len(rows) - len(valid)}  valid {len(valid)}  unreadable dirs {sum(not r['readable'] for r in rows)}")
        for k in SIG:
            n = sum(1 for r in valid if r["flags"][k])
            print(f"           {k:14s} {n:4d} valid trials ({100 * n / len(valid):.1f}%)")
    print("\n== Paired test delta under exclusion rules (Seed, cand_0005, delta, SE, bootstrap 95% CI)")
    rules = {"as published": lambda r: False,
             "confirmed (mock_internal / app_unavail)": lambda r: r["flags"]["mock_internal"] or r["flags"]["app_unavail"],
             "confirmed + timeouts": lambda r: r["flags"]["mock_internal"] or r["flags"]["app_unavail"] or r["flags"]["timeout"],
             "confirmed + timeouts + not_modelled": lambda r: any(r["flags"][k] for k in SIG)}
    for mode in ("trial", "task"):
        print(f"-- exclude by {mode}")
        for name, bad in rules.items():
            n, s, g, d, se, lo, hi = delta(data, bad, mode)
            print(f"   {name:42s} tasks {n:2d}  Seed {s:.4f}  G {g:.4f}  delta {d:+.4f}  se {se:.4f}  CI [{lo:+.4f}, {hi:+.4f}]")
