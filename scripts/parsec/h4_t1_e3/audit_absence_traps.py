#!/usr/bin/env python3
"""Find trials where an ABSENCE trap failed while the agent behaved correctly.

Several h4 tasks test whether the agent honestly reports that something is not
there: `cloud-055-azure-subscription-not-found`, `platform-039-catalog-miss-...`.
Their required assertions carry ids like `subscription-not-found` or
`catalog-miss`.

When the simulator answers such a lookup with an invented record instead of an
error, the agent faithfully reports what it was handed, the absence assertion is
missed, and the trial scores a plausible partial credit. Tool calls still score
1.0 -- the agent asked exactly the right question. Nothing in the harness flags
this, and it is the inverse of a capability failure: the more honest the agent,
the worse it looks.

Observed on the Oct-06 drop, same call and byte-identical seed as Oct-04:

    e1  query_azure_pools(get_subscription, 'pool-01-999')
        -> {"error": "Subscription 'pool-01-999' not found"}        reward 1.00
    e3  same call
        -> {"subscription_name": "pool-01-999", "subscription_id": ...,
            "tenant_id": "72f988bf-...", "status": "Succeeded"}     reward 0.65

So this reports, per arm and task: trials that missed an absence assertion while
scoring full marks on tool calls. A high count with tool_calls == 1.0 means the
arm's data is biased against exactly the tasks worth the most.
"""
from __future__ import annotations
import glob, json, os, re, sys

#: Assertion ids that encode "report that this is absent".
ABSENCE = re.compile(r"not[-_]?found|miss\b|missing|absent|no[-_]|unavailable|"
                     r"not[-_]?enriched|not[-_]?requested|empty", re.I)
ARMS = ("h4_t1_e1", "h4_t1_e2", "h4_t1_e3")


def trial_rows(prefix: str):
    for base in sorted(glob.glob(f".capevolve/{prefix}_*")):
        if not os.path.isdir(base):
            continue
        task = os.path.basename(base)[len(prefix) + 1:]
        for run in sorted(glob.glob(base + "/run_*")):
            if not os.path.exists(run + "/baseline.json"):
                continue
            for f in sorted(glob.glob(run + "/rollouts/val/*.json")):
                try:
                    ro = (json.load(open(f)).get("rollout") or {})
                except (ValueError, OSError):
                    continue
                md = ro.get("metadata") or {}
                td = md.get("trial_dir") or ""
                rew = detail = None
                for p in glob.glob(td + "/*/*/verifier/reward.json"):
                    try: rew = json.load(open(p))
                    except (ValueError, OSError): pass
                for p in glob.glob(td + "/*/*/verifier/reward-detail.json"):
                    try: detail = json.load(open(p))
                    except (ValueError, OSError): pass
                if rew and detail:
                    yield task, os.path.basename(f).split("__")[-1][:7], rew, detail


def main() -> int:
    print("Trials that missed an ABSENCE assertion despite perfect tool calls.")
    print("A simulator that invents a record for something absent produces these;")
    print("the agent asked the right question and reported what it was given.\n")
    hdr = f"{'arm':<5}{'task':<44}{'trials':>8}{'hit':>6}{'mean reward':>13}"
    print(hdr); print("-" * len(hdr))
    totals = {}
    for a in ARMS:
        per = {}
        for task, tag, rew, detail in trial_rows(a):
            an = detail.get("answer") or {}
            missed = [m.get("id", "") for m in (an.get("required_missed") or [])]
            absent_missed = [m for m in missed if ABSENCE.search(m or "")]
            tc = rew.get("tool_calls")
            d = per.setdefault(task, {"n": 0, "hit": 0, "r": []})
            d["n"] += 1
            d["r"].append(rew.get("reward"))
            # the signature: absence assertion missed AND the investigation was perfect
            if absent_missed and tc == 1.0:
                d["hit"] += 1
                d.setdefault("ids", set()).update(absent_missed)
        for task, d in sorted(per.items()):
            if d["hit"]:
                rs = [x for x in d["r"] if x is not None]
                m = sum(rs) / len(rs) if rs else float("nan")
                print(f"{a[-2:]:<5}{task[:44]:<44}{d['n']:>8}{d['hit']:>6}{m:>13.3f}")
                print(f"     missed: {', '.join(sorted(d.get('ids', [])))}")
        totals[a] = sum(d["hit"] for d in per.values())
    print("-" * len(hdr))
    for a in ARMS:
        print(f"  {a[-2:]}: {totals.get(a, 0)} trials lost an absence trap this way")
    print("\n  A count that rises between arms on identical seeds is a simulator")
    print("  change, not an agent change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
