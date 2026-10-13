#!/usr/bin/env python3
"""Build results/v5/v5_b1_e1/results.json from the vendored, frozen
results/v5/v5_b1_e1/source_v5_b1_e1.json (the intake worktree's own
collect.py output) plus task_set_10-12.txt.

v5_b1_e1 is the v5 BASELINE arm: the original, unmodified parsec skill
(verified byte-identical to parsec commit 28e2c40 and to this branch's
artifacts/v4/seed/), zero-shot, 5 trials/task, no optimization, across all
136 v5 tasks. Structurally this is v4_t4_e1/e2's shape (one eval per task),
not v4_t_e1's (seed/candidate/best/final) -- so this ledger carries no
optimization fields.

Two things it records that no earlier arm's ledger did, because this arm's
job is to characterise the benchmark rather than to beat it:

* **task_set** -- v5 pools two independently authored 68-task drops
  (v5_2026-10-10 and v5_2026-10-12). Task ids do not collide. Keeping the
  provenance per task is what lets a reader check the pooled mean is not an
  artefact of mixing two different difficulties (it is not: permutation
  p = 0.62, see summary.md).

* **per-task variability** (`variable`, `spread`, `sd`) -- 68% of these
  tasks return a different reward across identical repeated trials. A mean
  alone hides that, and the implied noise floor (~0.25 per task at n=5)
  governs how any later optimizer arm must be gated. Derived here once
  rather than recomputed per consumer.

Usage: python3 scripts/build_v5_b1_results_json.py [--check]
  --check   exit 1 if regenerating would change results.json, instead of writing it.
"""
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARM_DIR = ROOT / "results" / "v5" / "v5_b1_e1"
SOURCE_JSON = ARM_DIR / "source_v5_b1_e1.json"
SET_1012 = ARM_DIR / "task_set_10-12.txt"
RESULTS_JSON = ARM_DIR / "results.json"

TOTAL_TASKS = 136
CATEGORIES = ("cloud", "cost", "icinga", "platform")


def category_of(task_id):
    for c in CATEGORIES:
        if task_id.startswith(c + "-"):
            return c
    raise ValueError(f"unrecognized category prefix for task id {task_id!r}")


def build_task_ledger(source_tasks, new_ids):
    ledger = []
    for t in sorted(source_tasks, key=lambda x: x["task_id"]):
        tid = t["task_id"]
        trials = t.get("trial_rewards") or []
        ledger.append({
            "task": tid,
            "category": category_of(tid),
            "task_set": "10-12" if tid in new_ids else "10-10",
            "status": t["status"],
            "reward": t["reward"],
            "stderr": t.get("stderr"),
            "trial_rewards": trials,
            "errored_trials": t.get("errored_trials", 0),
            "valid_trials": t.get("valid_trials"),
            "n_trials": t.get("n_trials"),
            # Variability, derived once here. `variable` is the plain
            # question "did identical trials disagree at all".
            "variable": len(set(trials)) > 1,
            "trial_min": min(trials) if trials else None,
            "trial_max": max(trials) if trials else None,
            "spread": round(max(trials) - min(trials), 6) if trials else None,
            "sd": round(statistics.pstdev(trials), 6) if len(trials) > 1 else 0.0,
            "cost_usd": t.get("cost_usd"),
            "tokens": t.get("tokens"),
            "seconds": t.get("seconds"),
            "headroom": "saturated" if t["reward"] >= 0.95 else "ok",
            "report": f"reports/v5/v5_b1_e1/{tid}.md",
        })
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
        "n_saturated": sum(1 for x in rw if x >= 1.0),
        "n_unsaturated": len(uns),
        "unsaturated_mean": round(statistics.fmean(uns), 6) if uns else None,
        "n_zero": sum(1 for x in rw if x == 0.0),
        "n_variable": len(var),
        "pct_variable": round(100 * len(var) / len(rows), 2) if rows else None,
        "n_deterministic": len(rows) - len(var),
        "mean_spread_variable_only": round(statistics.fmean(r["spread"] for r in var), 6) if var else None,
        "mean_sd_variable_only": round(statistics.fmean(r["sd"] for r in var), 6) if var else None,
        "mean_sd_all": round(statistics.fmean(r["sd"] for r in rows), 6),
        "cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 4),
        "tokens": sum(r["tokens"] or 0 for r in rows),
        "seconds": round(sum(r["seconds"] or 0 for r in rows), 2),
    }


def noise_floor(rows):
    """What the observed stochasticity bounds. n=5 trials per task."""
    sd = statistics.fmean(r["sd"] for r in rows)
    task_se = sd / math.sqrt(5)
    suite_sd = statistics.stdev([r["reward"] for r in rows])
    return {
        "mean_per_task_trial_sd": round(sd, 6),
        "se_of_a_5_trial_task_mean": round(task_se, 6),
        "ci95_halfwidth_per_task": round(1.96 * task_se, 6),
        "min_detectable_per_task_delta": round(2 * 1.96 * task_se, 6),
        "se_of_suite_mean": round(suite_sd / math.sqrt(len(rows)), 6),
        "note": (
            "A per-task improvement smaller than min_detectable_per_task_delta "
            "cannot be distinguished from run-to-run noise at 5 trials, so a "
            "hill-climb gate that accepts on any per-task gain will accept "
            "noise. The suite mean is far better resolved (se_of_suite_mean), "
            "so pooled movement of ~3x that is meaningful. Gate on suite "
            "movement, or raise trials for the gate."
        ),
    }


def build_results(source, new_ids):
    tasks = source["tasks"]
    assert len(tasks) == TOTAL_TASKS, f"expected {TOTAL_TASKS} tasks, got {len(tasks)}"
    assert all(t["status"] == "ok" for t in tasks), "a task is not status=='ok'"
    assert all((t.get("errored_trials") or 0) == 0 for t in tasks), \
        "a task has errored trials -- re-run it rather than vendoring it"

    ledger = build_task_ledger(tasks, new_ids)
    assert {r["task"] for r in ledger} == {t["task_id"] for t in tasks}
    n_1012 = sum(1 for r in ledger if r["task_set"] == "10-12")
    assert n_1012 == 68, f"expected 68 tasks from the 10-12 drop, got {n_1012}"

    by_set = {s: [r for r in ledger if r["task_set"] == s] for s in ("10-10", "10-12")}
    by_cat = {c: [r for r in ledger if r["category"] == c] for c in CATEGORIES}

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
            "noise_floor": noise_floor(ledger),
        },
        "provenance": {
            "source_results": "results/v5/v5_b1_e1/source_v5_b1_e1.json",
            "source_generator": (
                "parsec-intake_v5 worktree, scripts/parsec/v5/collect.py "
                "(gitignored there -- vendored here as a frozen snapshot)"
            ),
            "task_set_membership": "results/v5/v5_b1_e1/task_set_10-12.txt",
            "skill_under_test": (
                "artifacts/v5/seed/ -- verified byte-identical (8/8 files) to parsec "
                "commit 28e2c40's config/prompts/ via a fresh clone of the parsec "
                "reference repo, and byte-identical to this branch's own "
                "artifacts/v4/seed/. This is the real original skill."
            ),
            "discarded_predecessor": (
                "An earlier run of this same sweep (v5_t1_e1, 68 tasks) was discarded: "
                "its skill was byte-identical (8/8 prompt files) to "
                "artifacts/v4/v4_g_e1/rejected/cand_0001 -- a candidate produced by v4's "
                "GLOBAL optimizer arm, left installed in the live parsec clone's working "
                "tree (parsec git HEAD still read 28e2c40) and inherited when the v5 "
                "benchmark tree was built from that clone. It was never a baseline. On the "
                "68 tasks shared with this arm it inflated the mean by +0.151 "
                "(0.7372 -> 0.8885)."
            ),
            "no_optimizer_stage": (
                "v5_b1_e1 is a zero-shot sweep -- there is no seed/candidate/best/final "
                "lineage here, unlike v4_t_e1 and v4_g_e1."
            ),
        },
    }


def main():
    check_only = "--check" in sys.argv
    source = json.loads(SOURCE_JSON.read_text())
    new_ids = set(SET_1012.read_text().split())
    new_results = build_results(source, new_ids)

    old = json.loads(RESULTS_JSON.read_text()) if RESULTS_JSON.exists() else None

    def strip_ts(d):
        return {k: v for k, v in d.items() if k != "generated_at"}

    if old is not None and strip_ts(old) == strip_ts(new_results):
        print("results/v5/v5_b1_e1/results.json already up to date.")
        return 0
    if check_only:
        print("results/v5/v5_b1_e1/results.json is STALE relative to source_v5_b1_e1.json.",
              file=sys.stderr)
        return 1

    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(new_results, indent=2) + "\n")
    print(f"Wrote results/v5/v5_b1_e1/results.json ({len(new_results['task_ledger'])} tasks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
