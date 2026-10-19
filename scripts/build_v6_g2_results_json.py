#!/usr/bin/env python3
"""Build results/v6/v6_g2_e1/results.json from the vendored, frozen source files
under results/v6/v6_g2_e1/source/ (events.jsonl, final.json, state.json, splits.json,
process/<cand>_PROCESS.md).

v6_g2_e1 is a hill-climb run over a shared 8-file multi-agent bundle (orchestrator +
6 domain agents + shared_context), with THREE splits that have no v4/v5 analogue:

- F (feedback, 67 tasks): the optimizer's own visible signal. Screened by a random
  12-task rung per iteration -- never the whole split -- so there is no per-task F
  ledger, only a per-iteration paired delta.
- C (confirm, 67 tasks): hidden from the optimizer; the ONLY split the accept/reject
  gate reads. Scored via a group-sequential test at increasing sample sizes
  (n=16/33/67/133/200 cumulative) -- the task ids are deliberately never exposed to
  preserve the hidden-split guarantee, so (same as F) there is no per-task C ledger,
  only the per-iteration decision + aggregate val.
- test (66 tasks): sealed, scored exactly ONCE after the run's final champion was
  fixed by iteration 5's acceptance. This is the only split with a full per-task
  ledger (final.json's "test"/"test_baseline" per_task arrays), and the only number
  in this arm comparable to v4/v5's task-level heatmaps.

So unlike v4_g_e1/v5_g2_e1's results.json (one task_ledger covering every candidate
on one shared split), this script emits TWO ledgers:
  - "iterations": one row per iteration (F screen delta/z, C decision, broke/fixed
    counts from LEDGER.md, optimizer cost) -- the only cross-iteration view available.
  - "task_ledger": one row per TEST task, seed vs. the final champion only (no
    per-candidate columns, because only the champion and seed were ever scored on
    test -- scoring an intermediate candidate on test would burn the one-time seal).

Usage: python3 scripts/build_v6_g2_results_json.py [--check]
  --check   exit 1 if regenerating would change results.json, instead of writing it.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARM_DIR = ROOT / "results" / "v6" / "v6_g2_e1"
SOURCE_DIR = ARM_DIR / "source"
EVENTS_JSONL = SOURCE_DIR / "events.jsonl"
FINAL_JSON = SOURCE_DIR / "final.json"
STATE_JSON = SOURCE_DIR / "state.json"
RESULTS_JSON = ARM_DIR / "results.json"

CATEGORIES = ("cloud", "cost", "icinga", "platform")

# From the run's LEDGER.md (results/v6/v6_g2_e1/source/LEDGER.md), the framework's
# own factual record -- broke/fixed counts only, re-derived here programmatically
# from events.jsonl's "promotion"/"step" events rather than re-typed by hand.


def category_of(task_id: str) -> str:
    for c in CATEGORIES:
        if task_id.startswith(c + "-"):
            return c
    raise ValueError(f"unrecognized category prefix for task id {task_id!r}")


def load_events():
    events = []
    for line in EVENTS_JSONL.read_text().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def build_iterations(events):
    """One row per iteration: F-screen rung-1 result + C-split decision, pulled
    from the run's own 'promotion'/'step' events (not re-typed from LEDGER.md)."""
    rows = []
    iter_no = 0
    by_round = {}
    for e in events:
        if e.get("kind") == "promotion":
            rnd = e.get("round")
            by_round.setdefault(rnd, {})["promotion"] = e
        elif e.get("kind") == "step":
            rnd = None
            # step events don't carry round directly; match by candidate+order
            by_round.setdefault(e.get("candidate"), {})["step"] = e

    # Walk promotion events in file order, pairing each with the step event for the
    # same candidate (steps are logged immediately after their promotion).
    cand_order = []
    promo_by_cand = {}
    step_by_cand = {}
    for e in events:
        if e.get("kind") == "promotion":
            cand = e.get("candidate")
            if cand not in promo_by_cand:
                cand_order.append(cand)
            promo_by_cand[cand] = e
        elif e.get("kind") == "step":
            step_by_cand[e.get("candidate")] = e

    for i, cand in enumerate(cand_order, start=1):
        promo = promo_by_cand[cand]
        step = step_by_cand.get(cand, {})
        rung1 = promo.get("rung1", {})
        stage = promo.get("stage")
        bit = promo.get("bit")
        if stage == "rung_kill":
            c_decision = "killed_rung1"
            c_val = None
        elif bit == "accept":
            c_decision = "accept"
            c_val = step.get("val")
        else:
            c_decision = "reject"
            c_val = step.get("val")
        rows.append({
            "iteration": i,
            "candidate": cand,
            "parent": step.get("parent"),
            "f_screen_delta": round(rung1.get("mean", 0.0), 6) if rung1 else None,
            "f_screen_z": round(rung1.get("z", 0.0), 4) if rung1 else None,
            "f_screen_n": rung1.get("n"),
            "c_decision": c_decision,
            "c_val": round(c_val, 6) if c_val is not None else None,
            "broke": step.get("broke", []),
            "fixed": step.get("fixed", []),
            "optimizer_usd": round(step.get("opt_cost_usd", 0.0), 6),
            "optimizer_tokens": step.get("opt_tokens", 0),
        })
    return rows


def build_test_ledger(final_data):
    best_by_task = {t["task_id"]: t for t in final_data["test"]["per_task"]}
    base_by_task = {t["task_id"]: t for t in final_data["test_baseline"]["per_task"]}
    ledger = []
    for tid in sorted(best_by_task):
        b = best_by_task[tid]
        s = base_by_task.get(tid, {})
        best_reward = b.get("reward")
        seed_reward = s.get("reward")
        ledger.append({
            "task": tid,
            "category": category_of(tid),
            "seed": round(seed_reward, 6) if seed_reward is not None else None,
            "seed_n": s.get("n"),
            "champion": round(best_reward, 6) if best_reward is not None else None,
            "champion_n": b.get("n"),
            "delta_vs_seed": round(best_reward - seed_reward, 6)
                             if best_reward is not None and seed_reward is not None else None,
        })
    return ledger


def build_category_summary(task_ledger):
    by_cat = {}
    for row in task_ledger:
        if row["seed"] is None or row["champion"] is None:
            continue
        by_cat.setdefault(row["category"], []).append(row)
    summaries = {}
    for cat, rows in sorted(by_cat.items()):
        n = len(rows)
        seed_mean = sum(r["seed"] for r in rows) / n
        champ_mean = sum(r["champion"] for r in rows) / n
        summaries[cat] = {
            "n_tasks": n,
            "seed_mean": round(seed_mean, 6),
            "champion_mean": round(champ_mean, 6),
            "delta": round(champ_mean - seed_mean, 6),
        }
    all_rows = [r for r in task_ledger if r["seed"] is not None and r["champion"] is not None]
    n = len(all_rows)
    seed_mean = sum(r["seed"] for r in all_rows) / n
    champ_mean = sum(r["champion"] for r in all_rows) / n
    summaries["overall"] = {
        "n_tasks": n,
        "seed_mean": round(seed_mean, 6),
        "champion_mean": round(champ_mean, 6),
        "delta": round(champ_mean - seed_mean, 6),
    }
    return summaries


def main():
    check = "--check" in sys.argv
    events = load_events()
    final_data = json.loads(FINAL_JSON.read_text())
    state_data = json.loads(STATE_JSON.read_text())

    iterations = build_iterations(events)
    task_ledger = build_test_ledger(final_data)
    category_summary = build_category_summary(task_ledger)

    if len(task_ledger) != 66:
        print(f"ERROR: expected 66 test tasks, got {len(task_ledger)}", file=sys.stderr)
        return 2
    if len(iterations) != 6:
        print(f"ERROR: expected 6 iterations, got {len(iterations)}", file=sys.stderr)
        return 2

    accepted = [r["candidate"] for r in iterations if r["c_decision"] == "accept"]
    if accepted[-1] != final_data["best_id"]:
        print(f"ERROR: last accepted candidate {accepted[-1]!r} != "
              f"final.json best_id {final_data['best_id']!r}", file=sys.stderr)
        return 2

    payload = {
        "run": "v6_g2_e1",
        "best_id": final_data["best_id"],
        "test_reward": round(final_data["test"]["reward"], 6),
        "test_baseline_reward": round(final_data["test_baseline"]["reward"], 6),
        "test_delta": final_data["test_delta"],
        "test_n_tasks": final_data["test"]["n_tasks"],
        "test_n_trials": 10,
        "spent": {
            "iterations": state_data["spent"]["iterations"],
            "eval_usd": round(state_data["spent"]["usd"], 2),
            "optimizer_usd": round(state_data["spent"]["optimizer_usd"], 2),
            "total_usd": round(state_data["spent"]["usd"] + state_data["spent"]["optimizer_usd"], 2),
            "runner_seconds": state_data["spent"]["runner_seconds"],
            "optimizer_seconds": state_data["spent"]["optimizer_seconds"],
        },
        "iterations_detail": iterations,
        "category_summary": category_summary,
        "task_ledger": task_ledger,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reconstructed_after_crash": final_data.get("reconstruction_note") is not None,
    }

    new_text = json.dumps(payload, indent=2, sort_keys=False) + "\n"

    if RESULTS_JSON.exists():
        old_text = RESULTS_JSON.read_text()
        # generated_at is expected to drift between runs; strip it before comparing.
        old_cmp = re.sub(r'"generated_at": "[^"]*"', '"generated_at": ""', old_text)
        new_cmp = re.sub(r'"generated_at": "[^"]*"', '"generated_at": ""', new_text)
        if old_cmp == new_cmp:
            print(f"{RESULTS_JSON} is up to date")
            return 0
        if check:
            print(f"ERROR: {RESULTS_JSON} is stale (would change on regeneration)", file=sys.stderr)
            return 1

    RESULTS_JSON.write_text(new_text)
    print(f"wrote {RESULTS_JSON} ({len(task_ledger)} test tasks, {len(iterations)} iterations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
