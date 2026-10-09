#!/usr/bin/env python3
"""Aggregate an h4 arm's per-task baseline evals into one table.

Reads every .capevolve/<prefix>_<task>/run_*/baseline.json (latest run per
task) plus that run's rollouts, and prints a per-task table with the n=5 mean,
stderr, the tool_calls/answer split, each task's OWN reward weights (they vary
per task in this set -- 061 is 0.35/0.65 where the v4 tasks were 0.3/0.7), and
whether any trial tripped a forbidden-tool violation (which zeroes the whole
tool_calls component rather than costing partial credit).

Usage: python3 scripts/h4_t1_e1/collect_results.py [--prefix h4_t1_e1] [--json out.json]
"""
from __future__ import annotations
import argparse, glob, json, os, statistics, sys

GEORGE = {  # reviewed_result, n=1, from h4_2026_10_04/results.html
 "platform-035-aap2-cross-controller-job-search":1.000,"platform-036-secret-redacted-not-absent":1.000,
 "platform-037-ocpv-healthy-vm-degraded-machineset":1.000,"platform-038-anarchy-subject-guid-cross-cluster":1.000,
 "platform-039-catalog-miss-pr-fallback":1.000,"platform-040-workshop-cross-cluster-name-search":1.000,
 "platform-041-resource-pool-unfiltered-list":1.000,"platform-042-deployment-via-resource-claim":1.000,
 "platform-043-multiworkshop-asset-failure":1.000,"platform-044-search-catalog-env-type":1.000,
 "icinga-045-hosts-search-filter":1.000,"icinga-046-services-search-cross-host":0.700,
 "icinga-047-downtime-similar-host-names":1.000,"icinga-048-comment-service-vs-host-scope":1.000,
 "icinga-049-downtime-already-expired":0.850,"cost-050-org-wide-aggregate-doubling":0.825,
 "cost-051-gcp-net-of-credits":1.000,"cost-052-azure-empty-cache-no-filter":0.467,
 "cost-053-capacity-dropped-reservations":1.000,"cost-054-monitor-no-dashboard-link":0.700,
 "cloud-055-azure-subscription-not-found":1.000,"cloud-056-gcp-delete-in-progress-not-requested":0.767,
 "cloud-057-cloudtrail-select-only-refusal":0.467,"cloud-058-malformed-account-id":0.700,
 "cloud-059-blank-owner-email-fallback":0.700,"cloud-060-marketplace-usd-not-enriched":0.350,
 "061-capacity-manager-unused-cost-owner-lookup":0.650,"062-provisioning-job-trace":0.650,
 "063-babylon-namespace-missing-for-account":0.300,"064-reservation-release-active-job-check":0.325,
}

def load(prefix: str) -> list[dict]:
    rows = []
    for base in sorted(glob.glob(f".capevolve/{prefix}_*")):
        if not os.path.isdir(base):
            continue
        task = os.path.basename(base)[len(prefix) + 1:]
        runs = sorted(glob.glob(base + "/run_*"))
        run = next((r for r in reversed(runs) if os.path.exists(r + "/baseline.json")), None)
        if run is None:
            continue
        val = json.load(open(run + "/baseline.json"))["val"]
        trials, weights, forbidden, unmatched = [], None, 0, set()
        for f in sorted(glob.glob(run + "/rollouts/val/*.json")):
            ro = json.load(open(f))["rollout"]
            rj = ro["metadata"]["trial_result"].get("reward_json") or {}
            if isinstance(rj, str):
                try: rj = json.loads(rj)
                except Exception: rj = {}
            trials.append(rj)
            td = ro["metadata"].get("trial_dir") or ""
            for p in glob.glob(td + "/*/*/verifier/reward-detail.json"):
                try: d = json.load(open(p))
                except Exception: continue
                weights = weights or d.get("weights")
                tc = d.get("tool_calls") or {}
                if tc.get("forbidden_violations"): forbidden += 1
                for e in tc.get("unmatched_expected") or []:
                    unmatched.add(e.get("name") if isinstance(e, dict) else str(e))
        rw = [t.get("reward") for t in trials if t.get("reward") is not None]
        avg = lambda k: (statistics.mean([t[k] for t in trials if t.get(k) is not None])
                         if any(t.get(k) is not None for t in trials) else None)
        rows.append(dict(task=task, n=len(rw), mean=statistics.mean(rw) if rw else None,
            stderr=(statistics.stdev(rw)/len(rw)**0.5) if len(rw) > 1 else 0.0,
            tools=avg("tool_calls"), answer=avg("answer"),
            weights=weights, forbidden_trials=forbidden,
            unmatched=sorted(x for x in unmatched if x),
            cost=val.get("cost_usd") or 0, tokens=val.get("tokens") or 0,
            trials=rw, george=GEORGE.get(task)))
    return rows

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="h4_t1_e3")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    rows = load(a.prefix)
    if not rows:
        print(f"no completed tasks found for prefix {a.prefix}", file=sys.stderr); return 1
    print(f"{a.prefix}: {len(rows)} of 30 tasks complete\n")
    hdr = f"{'task':<48}{'n':>2}{'mean':>8}{'stderr':>8}{'tools':>7}{'answer':>8}{'wts':>10}{'fbd':>4}{'George':>8}{'delta':>8}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        w = r["weights"] or {}
        wts = f"{w.get('tool_calls','?')}/{w.get('answer','?')}"
        g = r["george"]; d = (r["mean"] - g) if (g is not None and r["mean"] is not None) else None
        print(f"{r['task'][:48]:<48}{r['n']:>2}{r['mean']:>8.3f}{r['stderr']:>8.3f}"
              f"{(r['tools'] if r['tools'] is not None else float('nan')):>7.2f}"
              f"{(r['answer'] if r['answer'] is not None else float('nan')):>8.2f}"
              f"{wts:>10}{r['forbidden_trials']:>4}"
              f"{(f'{g:.3f}' if g is not None else '-'):>8}{(f'{d:+.3f}' if d is not None else '-'):>8}")
    ms = [r["mean"] for r in rows if r["mean"] is not None]
    gs = [r["george"] for r in rows if r["george"] is not None and r["mean"] is not None]
    print("-" * len(hdr))
    print(f"{'MEAN (' + str(len(ms)) + ' tasks done)':<48}{'':>2}{statistics.mean(ms):>8.3f}")
    if gs: print(f"{'  George, same tasks':<48}{'':>2}{statistics.mean(gs):>8.3f}   delta {statistics.mean(ms)-statistics.mean(gs):+.3f}")
    print(f"\ncost so far ${sum(r['cost'] for r in rows):.2f} · {sum(r['tokens'] for r in rows):,} tokens")
    nf = sum(1 for r in rows if r["forbidden_trials"])
    if nf: print(f"tasks with forbidden-tool violations: {nf}")
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1); print(f"wrote {a.json}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
