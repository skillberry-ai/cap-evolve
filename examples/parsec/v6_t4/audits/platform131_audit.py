#!/usr/bin/env python3
"""Audit of platform-131 on the sealed test (Global cand_0005 vs Seed), from recorded trials only.

Prints, for each arm: per-trial reward, the tool-call sequence (flagging whether `cluster` was passed
to list_anarchy_subjects), the unmatched expected calls and missed answer facts from each trial's
verifier output, and then rescores the recorded trajectories with the task's own verify.py under
counterfactual contracts:
  A  list_anarchy_subjects does not require `cluster`
  B  A, and list_deployments is not required
  C  tool calls not scored (answer only)
  D  "both components" accepted as the component-count fact
  F  B and D
The paired test delta is then recomputed with platform-131's change substituted.

Usage:  python3 platform131_audit.py
"""
import copy
import glob
import importlib.util
import json
import random
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as C  # noqa: E402

T = "platform-131-deployment-first-resource-blind-spot"
TESTS = C.TASKS / f"bench-v6-{T}" / "tests"
spec = importlib.util.spec_from_file_location("verify131", TESTS / "verify.py")
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
EXP = json.loads((TESTS / "expected.json").read_text())
ROLL = C.G2_RUN / "rollouts" / "test"


def load(pattern):
    rows = []
    for f in sorted(glob.glob(str(ROLL / f"{T}__{pattern}__t*.json")), key=lambda x: int(re.search(r"__t(\d+)", x).group(1))):
        r = json.loads(Path(f).read_text())
        td = r["rollout"]["metadata"]["trial_dir"]
        calls, final = [], ""
        for kind, b in C.trial_messages(td):
            if kind == "tool_use":
                calls.append((b["name"], b["input"]))
            elif kind == "result":
                final = b
        detail = C.find_one(td, "reward-detail.json")
        rows.append({"reward": r["score"]["reward"], "calls": calls, "final": final,
                     "detail": json.loads(detail.read_text()) if detail else {}})
    return rows


def sequence(calls):
    out = []
    for name, a in calls:
        s = a.get("action") or name
        out.append(s + ("[cluster]" if a.get("cluster") else "") + (f"({a['guid']})" if a.get("guid") else ""))
    return " > ".join(out)


def contract(drop_cluster=False, drop_listdep=False, answer_only=False, both=False):
    e = copy.deepcopy(EXP)
    ex = e["tool_calls"]["expected"]
    if drop_cluster:
        for x in ex:
            if x["args"].get("action") == "list_anarchy_subjects":
                x["args"].pop("cluster")
    if drop_listdep:
        e["tool_calls"]["expected"] = [x for x in ex if x["args"].get("action") != "list_deployments"]
    if answer_only:
        e["weights"] = {"tool_calls": 0.0, "answer": 1.0}
    if both:
        e["answer"]["counts"][0]["extra_any_of"] = ["both components", "both subjects", "both parts"]
    return e


def score(row, e):
    ts, _ = V.score_tool_calls(row["calls"], e["tool_calls"])
    as_, _ = V.score_answer(row["final"], e["answer"])
    w = e["weights"]
    return w["tool_calls"] * ts + w["answer"] * as_


def test_means(pattern):
    out = {}
    for t in C.splits()["test"]:
        v = []
        for f in glob.glob(str(ROLL / f"{t}__{pattern}__t*.json")):
            r = json.loads(Path(f).read_text())
            if not (r.get("rollout") or {}).get("error"):
                v.append(r["score"]["reward"])
        out[t] = st.fmean(v)
    return out


if __name__ == "__main__":
    seed, glob_ = load("FINAL_seed"), load("FINAL")
    for label, rows in (("Seed", seed), ("Global cand_0005", glob_)):
        print(f"== {label}: mean {st.fmean(r['reward'] for r in rows):.4f}")
        for i, r in enumerate(rows):
            d = r["detail"]
            um = [c["args"].get("action") for c in (d.get("tool_calls") or {}).get("unmatched_expected", [])]
            miss = [x["id"] for x in (d.get("answer") or {}).get("counts_missed", [])]
            opened = any(n == "query_aap2" for n, _ in r["calls"])
            print(f"  t{i} r={r['reward']:.2f} job-opened={opened!s:5} unmatched={um} count-missed={miss}\n      {sequence(r['calls'])}")
    cases = {"as graded": contract(), "A. identifier-only lookup accepted": contract(drop_cluster=True),
             "B. A + list_deployments optional": contract(drop_cluster=True, drop_listdep=True),
             "C. tool calls not scored": contract(answer_only=True), "D. 'both components' accepted": contract(both=True),
             "F. B + D": contract(drop_cluster=True, drop_listdep=True, both=True)}
    print("\n== Counterfactual contracts (recorded trajectories rescored with the task's verify.py)")
    S, G = test_means("FINAL_seed"), test_means("FINAL")
    for name, e in cases.items():
        s, g = st.fmean(score(r, e) for r in seed), st.fmean(score(r, e) for r in glob_)
        S2, G2 = dict(S), dict(G)
        S2[T], G2[T] = s, g
        d = [G2[t] - S2[t] for t in S2]
        rng = random.Random(0)
        bs = sorted(st.fmean(rng.choices(d, k=len(d))) for _ in range(10000))
        print(f"  {name:38s} Seed {s:.3f} Global {g:.3f} delta {g - s:+.3f} | test-mean delta {st.fmean(d):+.4f} CI [{bs[250]:+.4f}, {bs[9750]:+.4f}]")
