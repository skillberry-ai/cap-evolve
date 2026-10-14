#!/usr/bin/env python3
"""Build results/v5/v5_b1_e1/results.json from the vendored, frozen
results/v5/v5_b1_e1/source_v5_b1_e1.json plus task_set_10-12.txt and this
branch's own v4 ledger (results/v4/v4_t_e1/results.json).

v5_b1_e1 is the v5 BASELINE arm: the original, unmodified parsec skill
(verified byte-identical to parsec commit 28e2c40 and to artifacts/v4/seed/),
zero-shot, 5 trials/task, no optimization, across all 136 v5 tasks.

The source is the intake worktree's collect.py output AFTER a per-trial audit
of all 680 trials (harbor result.json, verifier detail, agent transcript). The
audit exists because cap-evolve counts only exceptions it catches itself: a
harbor AgentTimeoutError -- in this run always a gateway hang before the
agent's first tool call -- was scored 0.0 with errored_trials 0. Dead trials
are excluded and counted as errored; a task carrying any carries an
`audit_note` and must still have >= MIN_VALID_TRIALS valid ones.

Recorded per task beyond the raw scores, because this arm's job is to
characterise the benchmark rather than beat it:

* task_set -- which 68-task drop (10-10 / 10-12) the task came from.
* origin   -- its lineage: v4-34 (same task as v4's original set, contracts
  unchanged), h4-rewritten (shares an h4 id but instruction, contract, seeds
  and verifier were all rewritten, so h4's numbers do NOT carry over),
  renamed-content-changed, or new.
* per-task variability (variable / spread / sd).
* for v4-34 tasks, v4's own ORIGINAL-skill baselines (v4_t1_e1 "our_baseline",
  n=3, and JB's baseline-v2, n=1). Not v4_t4_e*: those are the merged bundle
  of 21 optimized skills, not a baseline.

Usage: python3 scripts/build_v5_b1_results_json.py [--check]
  --check   exit 1 if regenerating would change results.json, instead of writing it.
"""
import json
import math
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARM_DIR = ROOT / "results" / "v5" / "v5_b1_e1"
SOURCE_JSON = ARM_DIR / "source_v5_b1_e1.json"
SET_1012 = ARM_DIR / "task_set_10-12.txt"
V4_LEDGER = ROOT / "results" / "v4" / "v4_t_e1" / "results.json"
RESULTS_JSON = ARM_DIR / "results.json"

TOTAL_TASKS = 136
MIN_VALID_TRIALS = 4
CATEGORIES = ("cloud", "cost", "icinga", "platform")
PERMUTATIONS = 20000
PERMUTATION_SEED = 0  # fixed, so --check is stable

# Tasks whose v5 id matches an h4_2026_10_06 task. All 21 were rewritten going
# into v5 (every instruction, every contract, the seeds and verify.py), so
# they are listed to be labelled -- not to be compared with h4's numbers.
H4_DERIVED = {
    "platform-062-provisioning-job-trace", "cost-064-reservation-release-active-job-check",
    "cloud-055-azure-subscription-not-found", "cloud-057-cloudtrail-select-only-refusal",
    "cloud-058-malformed-account-id", "cloud-059-blank-owner-email-fallback",
    "cost-051-gcp-net-of-credits", "cost-053-capacity-dropped-reservations",
    "cost-054-monitor-no-dashboard-link", "icinga-045-hosts-search-filter",
    "icinga-046-services-search-cross-host", "icinga-047-downtime-similar-host-names",
    "icinga-048-comment-service-vs-host-scope", "platform-036-secret-redacted-not-absent",
    "platform-037-ocpv-healthy-vm-degraded-machineset",
    "platform-038-anarchy-subject-guid-cross-cluster",
    "platform-040-workshop-cross-cluster-name-search",
    "platform-041-resource-pool-unfiltered-list", "platform-042-deployment-via-resource-claim",
    "platform-043-multiworkshop-asset-failure", "platform-044-search-catalog-env-type",
}
# Kept a v4/h4 task NUMBER but got different content.
RENAMED_CONTENT_CHANGED = {"cloud-060-marketplace-cost-not-in-usd", "cost-050-partial-account-coverage"}


def category_of(task_id):
    for c in CATEGORIES:
        if task_id.startswith(c + "-"):
            return c
    raise ValueError(f"unrecognized category prefix for task id {task_id!r}")


def origin_of(task_id, task_set, v4_ids):
    if task_set == "10-12":
        return "new-10-12"
    if task_id in RENAMED_CONTENT_CHANGED:
        return "renamed-content-changed"
    if task_id in v4_ids:
        return "v4-34"
    if task_id in H4_DERIVED:
        return "h4-rewritten"
    return "new-10-10"


def build_task_ledger(source_tasks, new_ids, v4):
    ledger = []
    for t in sorted(source_tasks, key=lambda x: x["task_id"]):
        tid = t["task_id"]
        trials = t.get("trial_rewards") or []
        task_set = "10-12" if tid in new_ids else "10-10"
        row = {
            "task": tid,
            "category": category_of(tid),
            "task_set": task_set,
            "origin": origin_of(tid, task_set, v4),
            "reward": t["reward"],
            "stderr": t.get("stderr"),
            "trial_rewards": trials,
            "n_valid": len(trials),
            "errored_trials": t.get("errored_trials", 0),
            "n_trials": t.get("n_trials"),
            "variable": len(set(trials)) > 1,
            "trial_min": min(trials) if trials else None,
            "trial_max": max(trials) if trials else None,
            "spread": round(max(trials) - min(trials), 6) if trials else None,
            "sd": round(statistics.pstdev(trials), 6) if len(trials) > 1 else 0.0,
            "cost_usd": t.get("cost_usd"),
            "tokens": t.get("tokens"),
            "seconds": t.get("seconds"),
            "headroom": "saturated" if t["reward"] >= 0.95 else "ok",
            "audit_note": t.get("audit_note"),
            "report": f"reports/v5/v5_b1_e1/{tid}.md",
            "v4_t1_reward": None, "v4_t1_n": None, "jb_reward": None, "jb_n": None,
            "delta_vs_v4_t1": None,
        }
        if tid in v4:
            r = v4[tid]
            row.update(v4_t1_reward=r["our_baseline"], v4_t1_n=r["our_baseline_n"],
                       jb_reward=r["jb_reward"], jb_n=r["jb_n"],
                       delta_vs_v4_t1=round(t["reward"] - r["our_baseline"], 6))
        ledger.append(row)
    return ledger


def summarize(rows):
    rw = [r["reward"] for r in rows]
    uns = [x for x in rw if x < 1.0]
    var = [r for r in rows if r["variable"]]
    return {
        "n_tasks": len(rows),
        "reward_mean": round(statistics.fmean(rw), 6),
        "reward_median": round(statistics.median(rw), 6),
        "reward_sd_across_tasks": round(statistics.stdev(rw), 6) if len(rw) > 1 else 0.0,
        "n_saturated": sum(1 for r in rows if r["trial_min"] is not None and r["trial_min"] >= 1.0),
        "n_unsaturated": len(uns),
        "unsaturated_mean": round(statistics.fmean(uns), 6) if uns else None,
        "n_zero": sum(1 for x in rw if x == 0.0),
        "n_variable": len(var),
        "pct_variable": round(100 * len(var) / len(rows), 2) if rows else None,
        "n_deterministic": len(rows) - len(var),
        "mean_spread_variable_only": round(statistics.fmean(r["spread"] for r in var), 6) if var else None,
        "mean_sd_variable_only": round(statistics.fmean(r["sd"] for r in var), 6) if var else None,
        "mean_sd_all": round(statistics.fmean(r["sd"] for r in rows), 6),
        "n_valid_trials": sum(r["n_valid"] for r in rows),
        "cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 4),
        "tokens": sum(r["tokens"] or 0 for r in rows),
        "seconds": round(sum(r["seconds"] or 0 for r in rows), 2),
    }


def set_difference(rows):
    a = [r["reward"] for r in rows if r["task_set"] == "10-10"]
    b = [r["reward"] for r in rows if r["task_set"] == "10-12"]
    obs = statistics.fmean(a) - statistics.fmean(b)
    se = math.sqrt(statistics.stdev(a) ** 2 / len(a) + statistics.stdev(b) ** 2 / len(b))
    rng = random.Random(PERMUTATION_SEED)
    pool, hits = a + b, 0
    for _ in range(PERMUTATIONS):
        rng.shuffle(pool)
        if abs(statistics.fmean(pool[:len(a)]) - statistics.fmean(pool[len(a):])) >= abs(obs):
            hits += 1
    return {
        "mean_10_10_minus_10_12": round(obs, 6),
        "se": round(se, 6),
        "t": round(obs / se, 4),
        "permutation_p_two_sided": round(hits / PERMUTATIONS, 4),
        "permutations": PERMUTATIONS,
        "seed": PERMUTATION_SEED,
        "mean_10_10_excl_h4_rewritten_minus_10_12": round(
            statistics.fmean(r["reward"] for r in rows
                             if r["task_set"] == "10-10" and r["origin"] != "h4-rewritten")
            - statistics.fmean(b), 6),
        "note": (
            "About half the gap is composition: 10-10 contains the 21 h4-rewritten tasks, "
            "which the original skill now finds easy (see by_origin); without them the gap "
            "roughly halves. The remainder is borderline. Split o5/h5 stratified by "
            "task_set and category rather than purely at random."
        ),
    }


def comparison_v4(rows):
    m = [r for r in rows if r["origin"] == "v4-34"]
    d = [r["delta_vs_v4_t1"] for r in m]

    def blk(sub):
        return {
            "n_tasks": len(sub),
            "jb_mean": round(statistics.fmean(r["jb_reward"] for r in sub), 6),
            "v4_t1_mean": round(statistics.fmean(r["v4_t1_reward"] for r in sub), 6),
            "v5_b1_mean": round(statistics.fmean(r["reward"] for r in sub), 6),
        }
    out = blk(m)
    out.update({
        "paired_delta_mean": round(statistics.fmean(d), 6),
        "paired_delta_sd": round(statistics.stdev(d), 6),
        "paired_delta_se": round(statistics.stdev(d) / math.sqrt(len(d)), 6),
        "n_abs_delta_over_0_25": sum(1 for x in d if abs(x) > 0.25),
        "note": (
            "Same task ids, same original skill, task contracts unchanged between "
            "v4_2026-09-16 and v5 (instructions 0/34 changed, contracts 1/34). v4_t1 is "
            "v4's own original-skill baseline (n=3), JB is the external baseline-v2 "
            "(n=1). This is the reproducibility check for the whole v5 rebuild."
        ),
    })
    return out


def noise_floor(rows):
    sd = statistics.fmean(r["sd"] for r in rows)
    task_se = sd / math.sqrt(5)
    suite_sd = statistics.stdev([r["reward"] for r in rows])
    return {
        "mean_per_task_trial_sd": round(sd, 6),
        "se_of_a_5_trial_task_mean": round(task_se, 6),
        "ci95_halfwidth_per_task": round(1.96 * task_se, 6),
        "min_detectable_per_task_delta": round(2 * 1.96 * task_se, 6),
        "se_of_suite_mean": round(suite_sd / math.sqrt(len(rows)), 6),
    }


def build_results(source, new_ids, v4):
    tasks = source["tasks"]
    assert len(tasks) == TOTAL_TASKS, f"expected {TOTAL_TASKS} tasks, got {len(tasks)}"
    for t in tasks:
        n_valid = len(t.get("trial_rewards") or [])
        if t.get("errored_trials"):
            assert t.get("audit_note"), f"{t['task_id']}: errored trials without an audit_note"
            assert n_valid >= MIN_VALID_TRIALS, f"{t['task_id']}: only {n_valid} valid trials"
        else:
            assert t["status"] == "ok" and n_valid == 5, f"{t['task_id']}: status/trials inconsistent"

    ledger = build_task_ledger(tasks, new_ids, v4)
    assert {r["task"] for r in ledger} == {t["task_id"] for t in tasks}
    n_1012 = sum(1 for r in ledger if r["task_set"] == "10-12")
    assert n_1012 == 68, f"expected 68 tasks from the 10-12 drop, got {n_1012}"
    n_v4 = sum(1 for r in ledger if r["origin"] == "v4-34")
    assert n_v4 == 34, f"expected 34 v4-34 tasks, got {n_v4}"
    assert sum(1 for r in ledger if r["origin"] == "h4-rewritten") == len(H4_DERIVED)

    by_set = {s: [r for r in ledger if r["task_set"] == s] for s in ("10-10", "10-12")}
    by_cat = {c: [r for r in ledger if r["category"] == c] for c in CATEGORIES}
    origins = ("v4-34", "h4-rewritten", "renamed-content-changed", "new-10-10", "new-10-12")
    by_origin = {o: [r for r in ledger if r["origin"] == o] for o in origins}

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "scripts/build_v5_b1_results_json.py",
        "benchmark": "parsec",
        "arm": "v5_b1_e1",
        "target": (
            "parsec multi-agent bundle (orchestrator.md + 6 domain agents + "
            "shared_context.md; capabilities: [system-prompt]) -- the ORIGINAL, "
            "unmodified skill, zero-shot, 5 trials/task, no optimization step"
        ),
        "total_tasks": TOTAL_TASKS,
        "task_ledger": ledger,
        "sections": {
            "overall": summarize(ledger),
            "by_task_set": {s: summarize(rs) for s, rs in by_set.items()},
            "by_category": {c: summarize(rs) for c, rs in by_cat.items()},
            "by_origin": {o: summarize(rs) for o, rs in by_origin.items() if rs},
            "set_difference": set_difference(ledger),
            "comparison_v4": comparison_v4(ledger),
            "noise_floor": noise_floor(ledger),
        },
        "provenance": {
            "source_results": "results/v5/v5_b1_e1/source_v5_b1_e1.json",
            "source_generator": (
                "parsec-intake_v5 worktree: scripts/parsec/v5/collect.py, then a per-trial "
                "audit of all 680 trials (gitignored there -- vendored here as a frozen snapshot)"
            ),
            "audit": source.get("audit"),
            "task_set_membership": "results/v5/v5_b1_e1/task_set_10-12.txt",
            "v4_baselines": "results/v4/v4_t_e1/results.json (task_ledger[].our_baseline, jb_reward)",
            "skill_under_test": (
                "artifacts/v5/seed/ -- verified byte-identical (8/8 files) to parsec commit "
                "28e2c40's config/prompts/ via a fresh clone of the parsec reference repo, "
                "and byte-identical to this branch's own artifacts/v4/seed/."
            ),
            "discarded_predecessor": (
                "An earlier run of this sweep (v5_t1_e1, 68 tasks, PR #801) was discarded: its "
                "skill was byte-identical to artifacts/v4/v4_g_e1/rejected/cand_0001 -- a v4 "
                "GLOBAL optimizer candidate left in the live parsec clone's working tree. It "
                "was never a baseline."
            ),
            "no_optimizer_stage": "zero-shot sweep: no seed/candidate/best/final lineage.",
        },
    }


def main():
    check_only = "--check" in sys.argv
    source = json.loads(SOURCE_JSON.read_text())
    new_ids = set(SET_1012.read_text().split())
    v4 = {r["task"]: r for r in json.loads(V4_LEDGER.read_text())["task_ledger"]}
    new_results = build_results(source, new_ids, v4)

    old = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else None

    def strip_ts(d):
        return {k: v for k, v in d.items() if k != "generated_at"}

    if old is not None and strip_ts(old) == strip_ts(new_results):
        print("results/v5/v5_b1_e1/results.json already up to date.")
        return 0
    if check_only:
        print("results/v5/v5_b1_e1/results.json is STALE relative to its sources.", file=sys.stderr)
        return 1

    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(new_results, indent=2) + "\n")
    print(f"Wrote results/v5/v5_b1_e1/results.json ({len(new_results['task_ledger'])} tasks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
