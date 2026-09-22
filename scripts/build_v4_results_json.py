#!/usr/bin/env python3
"""Build results/v4/results.json from the frozen source_parsec34.json snapshot
plus the C/G arm scaffold from
docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md.

Usage: python3 scripts/build_v4_results_json.py [--check]
  --check   exit 1 if regenerating would change results.json, instead of writing it.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_JSON = ROOT / "results" / "v4" / "source_parsec34.json"
COST_TIME_SOURCE = ROOT / "results" / "v4" / "cost_time" / "v4_t2_e1_results_table.md"
RESULTS_JSON = ROOT / "results" / "v4" / "results.json"
SPEC = "docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md"

COST_TIME_FIELDS = (
    "t2_cost_usd", "t2_tokens", "t2_time_s",
    "t2_eval_cost_usd", "t2_eval_tokens", "t2_eval_s",
    "t2_opt_cost_usd", "t2_opt_tokens", "t2_opt_s",
)

ARMS = [
    {"arm_id": "T1", "section": "task", "name": "seed", "mode": "zs",
     "status": "done", "source": "v4_t1_e1",
     "description": "native bundle, zero-shot, all 34 tasks"},
    {"arm_id": "T2", "section": "task", "name": "tbt", "mode": "opt",
     "status": "done_by_design", "source": "v4_t2_e1",
     "description": "independent optimizer run per task, 21 of 34 tasks "
                     "(the other 13 already scored 1.0 on the seed -- spec Sec.3)"},
    {"arm_id": "C1", "section": "category", "name": "seed", "mode": "zs",
     "status": "done", "source": "derived from T1",
     "description": "native bundle, zero-shot, scored per category"},
    {"arm_id": "C2", "section": "category", "name": "joint", "mode": "opt",
     "status": "not_run", "source": None,
     "description": "one optimizer run per category, scoring all of that "
                     "category's tasks together"},
    {"arm_id": "C3", "section": "category", "name": "merge", "mode": "zs",
     "status": "not_run", "source": None,
     "description": "per category, union of that category's T2 bundles, "
                     "zero-shot, evaluated on all of that category's tasks "
                     "including the already-perfect ones (spec Sec.3)"},
    {"arm_id": "C4", "section": "category", "name": "merge-joint", "mode": "opt",
     "status": "not_run", "source": None,
     "description": "C3's union, continued optimization jointly on that category"},
    {"arm_id": "G1", "section": "global", "name": "seed", "mode": "zs",
     "status": "done", "source": "derived from T1",
     "description": "native bundle, zero-shot, all 34 tasks (= T1)"},
    {"arm_id": "G2", "section": "global", "name": "joint", "mode": "opt",
     "status": "not_run", "source": None,
     "description": "one optimizer run scoring all 34 tasks together"},
    {"arm_id": "G3", "section": "global", "name": "merge", "mode": "zs",
     "status": "not_run", "source": None,
     "description": "union of all 21 T2 bundles, evaluated zero-shot on all "
                     "34 tasks, including the 13 already-perfect ones (spec Sec.3)"},
    {"arm_id": "G4", "section": "global", "name": "merge-joint", "mode": "opt",
     "status": "not_run", "source": None,
     "description": "G3's union, continued optimization jointly on all 34 tasks"},
]

NOT_RUN_NOTE_MERGE = (
    f"Design only, per {SPEC} Sec.2. No job has been submitted for this arm. "
    f"Merge strategy for the shared 8-file bundle is an open question -- see "
    f"{SPEC} Sec.4."
)
NOT_RUN_NOTE_JOINT = (
    f"Design only, per {SPEC} Sec.2. No job has been submitted for this arm."
)


def load_source():
    return json.loads(SOURCE_JSON.read_text())


def _pipe_row_cells(line):
    """Split one markdown pipe-table row into stripped cell strings."""
    parts = line.strip().split("|")
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _find_header(lines, must_contain):
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and all(col in line for col in must_contain):
            return i
    raise ValueError(f"no pipe-table header found containing {must_contain}")


def _parse_pipe_table(lines, header_idx):
    """Parse the pipe table whose header is lines[header_idx] (row after it
    is the '---' separator). Returns the list of data rows (each a list of
    cell strings)."""
    rows = []
    i = header_idx + 2
    while i < len(lines) and lines[i].strip().startswith("|"):
        rows.append(_pipe_row_cells(lines[i]))
        i += 1
    return rows


def _num(s):
    return float(s.replace(",", ""))


def parse_cost_time_source():
    """Parse results/v4/cost_time/v4_t2_e1_results_table.md's Summary and
    Per-iteration detail tables into per-task cost/token/time totals.

    Returns {task_id: {t2_cost_usd, t2_tokens, t2_time_s, t2_eval_cost_usd,
                        t2_eval_tokens, t2_eval_s, t2_opt_cost_usd,
                        t2_opt_tokens, t2_opt_s}} for the 21 tasks T2 ran on.

    Cross-checks that each task's eval+opt sums (from the detail table)
    reproduce that task's own Cost($)/Tokens totals (from the Summary
    table) -- the two tables are two views of the same run, and this
    catches a future edit that breaks that identity.
    """
    lines = COST_TIME_SOURCE.read_text().splitlines()

    summary_header = _find_header(lines, ["Task", "Cost($)", "Tokens"])
    summary_by_task = {}
    for row in _parse_pipe_table(lines, summary_header):
        summary_by_task[row[1]] = {"cost_usd": _num(row[10]), "tokens": int(_num(row[11]))}

    detail_header = _find_header(lines, ["Task", "Stage", "Eval $", "Opt $"])
    totals_by_task = {}
    for row in _parse_pipe_table(lines, detail_header):
        task = row[1]
        t = totals_by_task.setdefault(task, {
            "eval_cost_usd": 0.0, "eval_tokens": 0, "eval_s": 0.0,
            "opt_cost_usd": 0.0, "opt_tokens": 0, "opt_s": 0.0,
        })
        t["eval_cost_usd"] += _num(row[6])
        t["eval_tokens"] += int(_num(row[7]))
        t["eval_s"] += _num(row[8])
        t["opt_cost_usd"] += _num(row[9])
        t["opt_tokens"] += int(_num(row[10]))
        t["opt_s"] += _num(row[11])

    assert set(totals_by_task) == set(summary_by_task), (
        f"Summary/detail task sets disagree: "
        f"{set(summary_by_task) ^ set(totals_by_task)}"
    )

    out = {}
    for task, t in totals_by_task.items():
        cost_usd = t["eval_cost_usd"] + t["opt_cost_usd"]
        tokens = t["eval_tokens"] + t["opt_tokens"]
        summary = summary_by_task[task]
        assert abs(cost_usd - summary["cost_usd"]) < 0.01, (
            f"{task}: eval+opt cost {cost_usd:.4f} != Summary Cost($) {summary['cost_usd']:.4f}"
        )
        assert tokens == summary["tokens"], (
            f"{task}: eval+opt tokens {tokens} != Summary Tokens {summary['tokens']}"
        )
        out[task] = {
            "t2_cost_usd": round(cost_usd, 4),
            "t2_tokens": tokens,
            "t2_time_s": round(t["eval_s"] + t["opt_s"], 1),
            "t2_eval_cost_usd": round(t["eval_cost_usd"], 4),
            "t2_eval_tokens": t["eval_tokens"],
            "t2_eval_s": round(t["eval_s"], 1),
            "t2_opt_cost_usd": round(t["opt_cost_usd"], 4),
            "t2_opt_tokens": t["opt_tokens"],
            "t2_opt_s": round(t["opt_s"], 1),
        }
    return out


def build_task_ledger(source, cost_time):
    rows = []
    for row in source["tasks"]:
        row = dict(row)
        row["report"] = f"reports/task-by-task/v4-{row['task']}.md"
        ct = cost_time.get(row["task"])
        for key in COST_TIME_FIELDS:
            row[key] = ct[key] if ct else None
        rows.append(row)
    return rows


def build_cost_time_section(task_ledger):
    """Tranche-segmented cost/time totals across the 21 T2-optimized tasks.

    Kept split by tranche, never pooled into one number -- same convention
    as sections.task.summaries (spec Sec.0)."""
    by_tranche = {}
    for row in task_ledger:
        if row.get("t2_cost_usd") is None:
            continue
        t = by_tranche.setdefault(row["tranche"], {
            "n_tasks": 0, "cost_usd": 0.0, "tokens": 0, "time_s": 0.0,
            "eval_cost_usd": 0.0, "opt_cost_usd": 0.0,
        })
        t["n_tasks"] += 1
        t["cost_usd"] += row["t2_cost_usd"]
        t["tokens"] += row["t2_tokens"]
        t["time_s"] += row["t2_time_s"]
        t["eval_cost_usd"] += row["t2_eval_cost_usd"]
        t["opt_cost_usd"] += row["t2_opt_cost_usd"]
    for t in by_tranche.values():
        for k in ("cost_usd", "eval_cost_usd", "opt_cost_usd", "time_s"):
            t[k] = round(t[k], 4)
    return {
        "note": (
            "T2-optimized tasks only (21 of 34); tranches are kept separate and "
            "must never be pooled into one number -- see spec Sec.0 and "
            "results/v4/summary.md's aggregate caution."
        ),
        "by_tranche": by_tranche,
    }


def mean(vals):
    vals = [v for v in vals if v is not None]
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


def build_category_rows(task_ledger):
    by_cat = {}
    for row in task_ledger:
        by_cat.setdefault(row["category"], []).append(row)

    out = []
    for cat, rows in sorted(by_cat.items()):
        jb_mean, jb_n = mean(r["jb_reward"] for r in rows)
        seed_mean, seed_n = mean(r["our_baseline"] for r in rows)
        out.append({
            "category": cat,
            "n_tasks": len(rows),
            "C1_seed": {"source": "derived from T1", "jb_reward_mean": jb_mean,
                        "our_baseline_mean": seed_mean, "n": seed_n},
            "C2_joint": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_JOINT},
            "C3_merge": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_MERGE},
            "C4_merge_joint": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_MERGE},
        })
    return out


def build_global_row(task_ledger):
    jb_mean, jb_n = mean(r["jb_reward"] for r in task_ledger)
    seed_mean, seed_n = mean(r["our_baseline"] for r in task_ledger)
    return {
        "n_tasks": len(task_ledger),
        "G1_seed": {"source": "derived from T1", "jb_reward_mean": jb_mean,
                    "our_baseline_mean": seed_mean, "n": seed_n},
        "G2_joint": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_JOINT},
        "G3_merge": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_MERGE},
        "G4_merge_joint": {"status": "not_run", "scores": None, "note": NOT_RUN_NOTE_MERGE},
    }


def build_results(source):
    cost_time = parse_cost_time_source()
    task_ledger = build_task_ledger(source, cost_time)
    n_optimized = sum(1 for r in task_ledger if r["status"] == "optimized")
    n_cost = sum(1 for r in task_ledger if r.get("t2_cost_usd") is not None)
    assert n_cost == n_optimized, (
        f"cost/time source covers {n_cost} tasks but n_optimized={n_optimized} "
        f"-- {COST_TIME_SOURCE} and {SOURCE_JSON} disagree on which tasks T2 ran on"
    )
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "scripts/build_v4_results_json.py",
        "benchmark": "parsec",
        "target": "parsec multi-agent bundle (orchestrator.md + 6 domain agents + "
                  "shared_context.md; capabilities: [system-prompt])",
        "spec": SPEC,
        "total_tasks": len(task_ledger),
        "n_optimized": n_optimized,
        "arms": ARMS,
        "task_ledger": task_ledger,
        "sections": {
            "task": {
                "summaries": source["summaries"],
                "cost_time": build_cost_time_section(task_ledger),
            },
            "category": {"rows": build_category_rows(task_ledger)},
            "global": {"row": build_global_row(task_ledger)},
        },
        "provenance": {
            "source_parsec34_results": "results/v4/source_parsec34.json",
            "source_parsec34_generator": "parsec-intake_v4/scripts/build_parsec34_heatmap.py",
            "cost_time_source": "results/v4/cost_time/v4_t2_e1_results_table.md",
            "spec": SPEC,
            "note": (
                "task_ledger rows are the frozen source's 34 task rows verbatim, "
                "plus a 'report' pointer and the t2_* cost/time fields parsed from "
                "cost_time_source (null for the 13 tasks T2 never targeted). "
                "category/global C1/G1 rows are computed here from T1's "
                "our_baseline column, not from a new job (spec Sec.2). C2-C4/G2-G4 "
                "are not_run (spec Sec.2); see spec Sec.3 for why T2 covers only "
                "21/34 tasks and Sec.4 for the open merge-strategy question."
            ),
        },
    }


def main():
    check_only = "--check" in sys.argv
    source = load_source()
    assert len(source["tasks"]) == 34, f"expected 34 source tasks, got {len(source['tasks'])}"

    new_results = build_results(source)
    new_text = json.dumps(new_results, indent=2) + "\n"

    if RESULTS_JSON.exists():
        old_stable = {k: v for k, v in json.loads(RESULTS_JSON.read_text()).items()
                      if k != "generated_at"}
        new_stable = {k: v for k, v in new_results.items() if k != "generated_at"}
        if old_stable == new_stable:
            print(f"{RESULTS_JSON} already up to date.")
            return 0

    if check_only:
        print(f"{RESULTS_JSON} is STALE relative to source_parsec34.json.", file=sys.stderr)
        return 1

    RESULTS_JSON.write_text(new_text)
    print(f"Wrote {RESULTS_JSON} ({new_results['total_tasks']} tasks, "
          f"{new_results['n_optimized']} optimized).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
