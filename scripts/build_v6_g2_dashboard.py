#!/usr/bin/env python3
"""Regenerate the `const DATA = {...}` block in ui/dashboard_v6_g2_e1.html from
results/v6/v6_g2_e1/results.json, so the dashboard's numbers are never hand-typed
twice — every figure on the page traces back to the one generated ledger.

Usage: python3 scripts/build_v6_g2_dashboard.py [--check]
  --check   exit 1 if regenerating would change dashboard_v6_g2_e1.html, instead of writing it.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS_JSON = ROOT / "results" / "v6" / "v6_g2_e1" / "results.json"
DASHBOARD_HTML = ROOT / "ui" / "dashboard_v6_g2_e1.html"

DATA_RE = re.compile(r"^const DATA = (\{.*?\});$", re.MULTILINE)


def build_data(results):
    iterations = []
    for it in results["iterations_detail"]:
        iterations.append({
            "iter": it["iteration"],
            "cand": it["candidate"],
            "parent": it["parent"],
            "f_delta": it["f_screen_delta"],
            "f_z": it["f_screen_z"],
            "c_decision": it["c_decision"],
            "c_val": it["c_val"],
            "broke": len(it["broke"]),
            "fixed": len(it["fixed"]),
            "opt_usd": it["optimizer_usd"],
        })

    cat_summary = results["category_summary"]
    test_by_cat = []
    for cat in ("cloud", "cost", "icinga", "platform"):
        s = cat_summary[cat]
        test_by_cat.append({
            "cat": cat, "n": s["n_tasks"],
            "seed": s["seed_mean"], "cand": s["champion_mean"], "delta": s["delta"],
        })

    task_ledger = results["task_ledger"]
    improved = sum(1 for t in task_ledger if t["delta_vs_seed"] is not None and t["delta_vs_seed"] > 0.05)
    regressed = sum(1 for t in task_ledger if t["delta_vs_seed"] is not None and t["delta_vs_seed"] < -0.05)
    same = len(task_ledger) - improved - regressed

    test_tasks = [{
        "task": t["task"], "cat": t["category"],
        "seed": t["seed"], "cand": t["champion"], "delta": t["delta_vs_seed"],
    } for t in task_ledger]

    # seed_f/seed_c are the run's own full-split measurements (not in results.json's
    # per-iteration view, which only ever carries the 12-task rung screen) -- pulled from
    # the first iteration's parent context in source/events.jsonl's "step" events
    # (parent_val for cand_0001 == seed's full F mean; the C-split full re-confirmation is
    # logged separately as an "internal_estimate" style figure). Hardcoded here from the
    # same two source numbers summary.md cites, since results.json's iterations_detail
    # intentionally does not carry them (they aren't a per-candidate field).
    seed_f = 0.8300
    seed_c = 0.8213

    return {
        "seed_f": seed_f,
        "seed_c": seed_c,
        "seed_test": results["test_baseline_reward"],
        "iterations": iterations,
        "test": {
            "best_id": results["best_id"],
            "champion_reward": results["test_reward"],
            "seed_reward": results["test_baseline_reward"],
            "delta": results["test_delta"],
            "n_tasks": results["test_n_tasks"],
            "n_trials": results["test_n_trials"],
        },
        "test_by_cat": test_by_cat,
        "test_counts": {"improved": improved, "regressed": regressed, "same": same},
        "cost": {
            "total_eval_usd": results["spent"]["eval_usd"],
            "total_opt_usd": results["spent"]["optimizer_usd"],
            "total_usd": results["spent"]["total_usd"],
            "runner_seconds": round(results["spent"]["runner_seconds"]),
            "optimizer_seconds": round(results["spent"]["optimizer_seconds"]),
            "iterations": results["spent"]["iterations"],
        },
        "test_tasks": test_tasks,
    }


def main():
    check_only = "--check" in sys.argv
    results = json.loads(RESULTS_JSON.read_text())
    data = build_data(results)
    new_data_line = "const DATA = " + json.dumps(data, sort_keys=False) + ";"

    html = DASHBOARD_HTML.read_text()
    m = DATA_RE.search(html)
    if not m:
        print("ERROR: could not find 'const DATA = {...};' in dashboard_v6_g2_e1.html", file=sys.stderr)
        return 2

    new_html = html[:m.start()] + new_data_line + html[m.end():]

    if new_html == html:
        print(f"{DASHBOARD_HTML} is up to date")
        return 0
    if check_only:
        print(f"ERROR: {DASHBOARD_HTML} is stale (would change on regeneration)", file=sys.stderr)
        return 1

    DASHBOARD_HTML.write_text(new_html)
    print(f"wrote {DASHBOARD_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
