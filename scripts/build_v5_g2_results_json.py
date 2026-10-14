#!/usr/bin/env python3
"""Build results/v5/v5_g2_e1/results.json from the vendored, frozen
results/v5/v5_g2_e1/source_v5_g2_e1.json plus task_set_10-12.txt and this
branch's own v5 baseline ledger (results/v5/v5_b1_e1/results.json).

v5_g2_e1 asks whether v4's accepted G2 optimizer candidate (`cand_0004`,
`artifacts/v4/v4_g_e1/best`, verified byte-identical to the GitHub-hosted
copy) helps on the full 136-task v5 benchmark, with no further optimization:
same harness settings as v5_b1_e1 (5 trials/task, same model, same per-task
budgets), same tasks, same skill shape (orchestrator + 6 domain agents +
shared_context) -- the only variable is which bundle of those 8 files is
installed.

The source is the intake worktree's collect.py output after a per-trial
audit of all 680 trials, same rule as v5_b1_e1: a trial is dead if harbor
raised (AgentTimeoutError) or the agent's final transcript event is_error.
Unlike v5_b1_e1, which cleared its stragglers by re-running them to a fresh
5-trial batch, 4 tasks here never reached 5 clean trials in any single run
across repeated resubmission (recurring gateway hangs); for those, every
individually-audited, error-free trial across every attempt on disk for the
task (the live run plus every prior .dead-* run) was pooled and exactly 5
were drawn at random (fixed seed) and averaged. See source_v5_g2_e1.json's
"audit" block for exactly which tasks and how many trials were pooled.

Recorded per task, same shape as v5_b1_e1 plus the comparison that is this
arm's whole point:

* task_set / origin -- identical lineage labels to v5_b1_e1 (same 136 tasks).
* v5_b1_reward / v5_b1_n / delta_vs_v5_b1 -- v5_b1_e1's own reward on the
  same task, and the paired difference. This is the real comparison for
  this arm: v4_t1/JB (what v5_b1_e1 compares against) answer "did the
  rebuild reproduce v4", not "did the optimized skill help."

Usage: python3 scripts/build_v5_g2_results_json.py [--check]
  --check   exit 1 if regenerating would change results.json, instead of writing it.
"""
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARM_DIR = ROOT / "results" / "v5" / "v5_g2_e1"
SOURCE_JSON = ARM_DIR / "source_v5_g2_e1.json"
SET_1012 = ARM_DIR / "task_set_10-12.txt"
B1_LEDGER = ROOT / "results" / "v5" / "v5_b1_e1" / "results.json"
RESULTS_JSON = ARM_DIR / "results.json"

TOTAL_TASKS = 136
CATEGORIES = ("cloud", "cost", "icinga", "platform")
NOISE_FLOOR = 0.09  # carried over from v5_b1_e1's own measurement of this suite

# Same lineage labels as v5_b1_e1 (scripts/build_v5_b1_results_json.py) -- the
# 136 tasks and their provenance have not changed between arms.
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


def build_task_ledger(source_tasks, new_ids, v4_ids, b1_by_task):
    ledger = []
    for t in sorted(source_tasks, key=lambda x: x["task_id"]):
        tid = t["task_id"]
        trials = t.get("trial_rewards") or []
        task_set = "10-12" if tid in new_ids else "10-10"
        b1 = b1_by_task[tid]
        row = {
            "task": tid,
            "category": category_of(tid),
            "task_set": task_set,
            "origin": origin_of(tid, task_set, v4_ids),
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
            "pooled_note": t.get("pooled_note"),
            "report": f"reports/v5/v5_g2_e1/{tid}.md",
            "v5_b1_reward": b1["reward"],
            "v5_b1_n": b1["n_valid"],
            "delta_vs_v5_b1": round(t["reward"] - b1["reward"], 6),
            "move": ("flat" if abs(t["reward"] - b1["reward"]) < NOISE_FLOOR
                      else ("up" if t["reward"] > b1["reward"] else "down")),
        }
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
        "mean_sd_all": round(statistics.fmean(r["sd"] for r in rows), 6),
        "n_valid_trials": sum(r["n_valid"] for r in rows),
        "cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 4),
        "tokens": sum(r["tokens"] or 0 for r in rows),
        "seconds": round(sum(r["seconds"] or 0 for r in rows), 2),
        "v5_b1_mean": round(statistics.fmean(r["v5_b1_reward"] for r in rows), 6),
        "delta_vs_v5_b1_mean": round(statistics.fmean(r["delta_vs_v5_b1"] for r in rows), 6),
        "n_up": sum(1 for r in rows if r["move"] == "up"),
        "n_down": sum(1 for r in rows if r["move"] == "down"),
        "n_flat": sum(1 for r in rows if r["move"] == "flat"),
    }


def comparison_v5_b1(rows):
    d = [r["delta_vs_v5_b1"] for r in rows]
    return {
        "n_tasks": len(rows),
        "v5_b1_mean": round(statistics.fmean(r["v5_b1_reward"] for r in rows), 6),
        "v5_g2_mean": round(statistics.fmean(r["reward"] for r in rows), 6),
        "paired_delta_mean": round(statistics.fmean(d), 6),
        "paired_delta_sd": round(statistics.stdev(d), 6),
        "paired_delta_se": round(statistics.stdev(d) / math.sqrt(len(d)), 6),
        "noise_floor": NOISE_FLOOR,
        "n_up_beyond_noise": sum(1 for x in d if x > NOISE_FLOOR),
        "n_down_beyond_noise": sum(1 for x in d if x < -NOISE_FLOOR),
        "n_flat": sum(1 for x in d if abs(x) <= NOISE_FLOOR),
        "note": (
            "cand_0004 is v4's accepted G2-arm champion (artifacts/v4/v4_g_e1/best), reused "
            "as-is -- no further optimization was run for v5. Same tasks, same harness settings, "
            "same model as v5_b1_e1; the only variable is which 8-file bundle was installed. "
            "No group here (overall or by origin) clears the ~0.09 per-task noise floor measured "
            "in v5_b1_e1 -- read this as no significant change at the aggregate level, despite "
            "real task-level movement (see n_up_beyond_noise / n_down_beyond_noise)."
        ),
    }


def build_results(source, new_ids, v4_ids, b1_by_task):
    tasks = source["tasks"]
    assert len(tasks) == TOTAL_TASKS, f"expected {TOTAL_TASKS} tasks, got {len(tasks)}"
    for t in tasks:
        n_valid = len(t.get("trial_rewards") or [])
        assert t["status"] == "ok" and n_valid == 5, f"{t['task_id']}: status/trials inconsistent"
        assert t.get("errored_trials", 0) == 0, f"{t['task_id']}: unresolved errored trials"

    ledger = build_task_ledger(tasks, new_ids, v4_ids, b1_by_task)
    assert {r["task"] for r in ledger} == {t["task_id"] for t in tasks}
    assert {r["task"] for r in ledger} == set(b1_by_task), "task set must match v5_b1_e1 exactly"
    n_1012 = sum(1 for r in ledger if r["task_set"] == "10-12")
    assert n_1012 == 68, f"expected 68 tasks from the 10-12 drop, got {n_1012}"
    n_v4 = sum(1 for r in ledger if r["origin"] == "v4-34")
    assert n_v4 == 34, f"expected 34 v4-34 tasks, got {n_v4}"

    by_set = {s: [r for r in ledger if r["task_set"] == s] for s in ("10-10", "10-12")}
    by_cat = {c: [r for r in ledger if r["category"] == c] for c in CATEGORIES}
    origins = ("v4-34", "h4-rewritten", "renamed-content-changed", "new-10-10", "new-10-12")
    by_origin = {o: [r for r in ledger if r["origin"] == o] for o in origins}

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "scripts/build_v5_g2_results_json.py",
        "benchmark": "parsec",
        "arm": "v5_g2_e1",
        "target": (
            "parsec multi-agent bundle (orchestrator.md + 6 domain agents + shared_context.md; "
            "capabilities: [system-prompt]) -- v4's accepted G2 optimizer candidate (cand_0004), "
            "reused as-is on all 136 v5 tasks, 5 trials/task, no further optimization step"
        ),
        "total_tasks": TOTAL_TASKS,
        "task_ledger": ledger,
        "sections": {
            "overall": summarize(ledger),
            "by_task_set": {s: summarize(rs) for s, rs in by_set.items()},
            "by_category": {c: summarize(rs) for c, rs in by_cat.items()},
            "by_origin": {o: summarize(rs) for o, rs in by_origin.items() if rs},
            "comparison_v5_b1": comparison_v5_b1(ledger),
        },
        "provenance": {
            "source_results": "results/v5/v5_g2_e1/source_v5_g2_e1.json",
            "source_generator": (
                "parsec-intake_v5 worktree: scripts/parsec/v5/collect.py, then a per-trial "
                "audit of all 680 trials, then scripts/parsec/v5/_pool_valid_trials.py for the "
                "4 tasks that never reached 5 clean trials in one run (gitignored there -- "
                "vendored here as a frozen snapshot)"
            ),
            "audit": source.get("audit"),
            "task_set_membership": "results/v5/v5_g2_e1/task_set_10-12.txt",
            "v5_baseline": "results/v5/v5_b1_e1/results.json (task_ledger[].reward, same 136 tasks)",
            "skill_under_test": (
                "artifacts/v4/v4_g_e1/best -- cand_0004, v4's accepted G2-arm champion "
                "(best_id_overall in results/v4/v4_g_e1/results.json). Verified byte-identical "
                "to https://github.com/skillberry-ai/cap-evolve/tree/parsec-history/"
                "artifacts/v4/v4_g_e1/best via git hash-object against that ref's blobs. Not "
                "duplicated under artifacts/v5/ -- same bytes, same path, no new artifacts dir."
            ),
            "no_optimizer_stage": (
                "zero-shot reuse of an existing candidate: no seed/candidate/best/final lineage "
                "for v5 itself. Only afterwards, if this arm's result warrants it, would a v5 "
                "optimizer round run against this skill as its starting point."
            ),
        },
    }


def main():
    check_only = "--check" in sys.argv
    source = json.loads(SOURCE_JSON.read_text())
    new_ids = set(SET_1012.read_text().split())
    b1 = json.loads(B1_LEDGER.read_text())
    v4_ids = {r["task"] for r in b1["task_ledger"] if r["origin"] == "v4-34"}
    b1_by_task = {r["task"]: r for r in b1["task_ledger"]}
    new_results = build_results(source, new_ids, v4_ids, b1_by_task)

    old = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else None

    def strip_ts(d):
        return {k: v for k, v in d.items() if k != "generated_at"}

    if old is not None and strip_ts(old) == strip_ts(new_results):
        print("results/v5/v5_g2_e1/results.json already up to date.")
        return 0
    if check_only:
        print("results/v5/v5_g2_e1/results.json is STALE relative to its sources.", file=sys.stderr)
        return 1

    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(new_results, indent=2) + "\n")
    print(f"Wrote results/v5/v5_g2_e1/results.json ({len(new_results['task_ledger'])} tasks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
