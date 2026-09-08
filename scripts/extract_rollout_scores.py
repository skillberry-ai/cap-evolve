#!/usr/bin/env python3
"""Distil per-task/per-candidate scores out of a cap-evolve run's `rollouts/` tree.

Why this script exists at all: the raw rollouts are the only machine-readable place a
run records *per-task* candidate scores. `events.jsonl` records split aggregates,
`history.jsonl`/`rejected.jsonl` record a val mean plus `fixed`/`broke` name lists, and
`final.json` records per-task numbers only for the sealed test split. Everything else —
"what did cand_0001 score on task 004" — lives one file per (task, candidate, trial) under
`rollouts/<split>/<task>__<tag>__t<N>.json`.

Those trees are 8–19 MB per run (they embed full agent transcripts), which is not content
this branch should carry. So this script reduces them to a small `per_task_scores.json` per
experiment, which IS committed, and which `build_results_json.py` then reads. The chain is:

    intake worktree rollouts/     (not in this branch, 40+ MB)
      -> results/<exp>/per_task_scores.json      (committed, ~10 KB, THIS script)
        -> results/results.json                 (committed, build_results_json.py)
          -> ui/heatmap.html + reports/task-by-task/*.md   (build_heatmap.py, build_task_reports.py)

Only this first hop needs the source worktrees. Everything downstream regenerates from
files inside the branch, so `--check` in the other three scripts is meaningful in CI.

Usage:
  python3 scripts/extract_rollout_scores.py                 # rewrite both per_task_scores.json
  python3 scripts/extract_rollout_scores.py --check          # exit 1 if either would change
  python3 scripts/extract_rollout_scores.py --v1-root PATH --v2-root PATH

A number here is a plain mean over that (task, tag, split)'s trial rewards, and `n` is the
trial count it was taken over. Both are kept because the two v2 runs and v1's pilot were NOT
run at the same trial count, and comparing a mean without its `n` is how the v2 baseline
instability got mistaken for signal in the first place — see results/v2/summary.md.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_V1_ROOT = Path(
    "/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v1/.capevolve"
)
DEFAULT_V2_ROOT = Path(
    "/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v2/.capevolve"
)

# Which run dirs belong to which experiment, what role each plays, and which one is the
# experiment's headline. `role` is carried through into results.json because these runs are NOT
# co-equal second opinions: v2's `run_run_20260818_161550` is an aborted iter3 whose output was
# discarded (see results/v2/summary.md, "the --run-ts bug"), and the earlier runs in both chains
# are superseded attempts kept because their seed measurements are the instability evidence.
#
# `headline` marks the run whose numbers results.json reports as the experiment's result. Exactly
# one per experiment.
V1_RUNS = [
    ("run_20260813_120630", "superseded-n1", False),
    ("run_20260813_152629", "superseded-n10-a", False),
    ("run_20260814_160930", "superseded-n10-b", False),
    ("run_20260814_214843", "headline-n30", True),
]
V2_RUNS = [
    ("run_20260816_143826", "superseded-v2.1-opt-iter1", False),
    ("run_20260816_162233", "superseded-v2.1-opt-iter2", False),
    ("run_20260816_202942", "superseded-v2.2-iter1", False),
    ("run_20260818_161550", "headline-v2.2-iter2", True),
    ("run_run_20260818_161550", "discarded-aborted-iter3", False),
]

# rollouts/<split>/<task_id>__<tag>__t<N>.json
#
# `tag` is deliberately matched loosely, because cap-evolve writes five distinct ones and each
# means something different:
#   seed        the baseline measurement on val — which may be *reused* from an earlier run
#   seed_train  the seed re-measured on train inside an iteration, at that iteration's n
#   cand_NNNN   a candidate under evaluation
#   FINAL       the sealed-test evaluation of the champion at the end of the run
# Keeping `seed` and `seed_train` distinct is load-bearing for v2: run_20260818_161550's accept
# gate compared an n=9 candidate against a *reused n=3* `seed`, while its own n=9 `seed_train`
# measured 0.087 lower. Both are real; which one you quote changes the headline delta. Don't
# collapse them, and don't average across different `n`.
ROLLOUT_RE = re.compile(r"^(?P<task>.+)__(?P<tag>[A-Za-z][A-Za-z0-9_]*)__t(?P<trial>\d+)\.json$")


def err_class(error) -> str | None:
    """A short label for a harness-level trial failure, or None if the trial really ran.

    An errored trial is written to disk with `reward: 0.0` exactly like a genuine zero, so a
    naive mean over rollout files is NOT the number cap-evolve reports: cap-evolve drops
    errored trials from the denominator (`raw.valid_trials`). v1's seed val baseline lost
    8 of 30 trials this way, which is the difference between 0.211 (all files) and 0.288
    (valid only) on task 0047. Both are recorded below so neither can be quoted by accident.
    """
    if not error:
        return None
    s = str(error)
    return s.split(":", 1)[0].strip()[:60] or "unknown"


def scan_run(run_dir: Path) -> dict:
    """-> {task: {split: {tag: {n, n_valid, n_errored, mean_valid, mean_all, trials, errors}}}}"""
    cells: dict = {}
    rollouts = run_dir / "rollouts"
    if not rollouts.is_dir():
        return cells

    for split_dir in sorted(p for p in rollouts.iterdir() if p.is_dir()):
        split = split_dir.name
        for f in sorted(split_dir.glob("*.json")):
            m = ROLLOUT_RE.match(f.name)
            if not m:
                print(f"WARNING: unparsed rollout filename {f.name}", file=sys.stderr)
                continue
            try:
                doc = json.loads(f.read_text())
            except (OSError, json.JSONDecodeError) as e:
                print(f"WARNING: unreadable rollout {f.name}: {e}", file=sys.stderr)
                continue
            score = doc.get("score") or {}
            reward = score.get("reward")
            if reward is None:
                continue
            # Trust the score block's own task_id over the filename: v2's task ids embed
            # hyphens and the filename split is only unambiguous because `__` separates
            # fields, but the id is authoritative.
            task = score.get("task_id") or m.group("task")
            ec = err_class((doc.get("rollout") or {}).get("error"))
            slot = cells.setdefault(task, {}).setdefault(split, {}).setdefault(
                m.group("tag"), {"_raw": []}
            )
            slot["_raw"].append((int(m.group("trial")), float(reward), ec))

    for splits in cells.values():
        for tags in splits.values():
            for slot in tags.values():
                rows = sorted(slot.pop("_raw"))
                valid = [r for _, r, ec in rows if ec is None]
                errors = sorted({ec for _, _, ec in rows if ec})
                slot["n"] = len(rows)
                slot["n_valid"] = len(valid)
                slot["n_errored"] = len(rows) - len(valid)
                slot["mean_valid"] = round(sum(valid) / len(valid), 6) if valid else None
                slot["mean_all"] = round(sum(r for _, r, _ in rows) / len(rows), 6) if rows else None
                slot["trials"] = [
                    (None if ec else round(r, 6)) for _, r, ec in rows
                ]
                if errors:
                    slot["errors"] = errors
    return cells


def build(exp: str, root: Path, runs: list) -> dict:
    out = {
        "experiment": exp,
        "generator": "scripts/extract_rollout_scores.py",
        "source_root": str(root),
        "runs": [],
    }
    for run_name, role, headline in runs:
        run_dir = root / run_name
        if not run_dir.is_dir():
            print(f"ERROR: missing run dir {run_dir}", file=sys.stderr)
            raise SystemExit(2)
        cells = scan_run(run_dir)
        out["runs"].append(
            {
                "run": run_name,
                "role": role,
                "headline": headline,
                "n_tasks": len(cells),
                "cells": {t: cells[t] for t in sorted(cells)},
            }
        )
    if sum(1 for r in out["runs"] if r["headline"]) != 1:
        print(f"ERROR: {exp} must have exactly one headline run", file=sys.stderr)
        raise SystemExit(2)
    return out


def emit(path: Path, data: dict, check_only: bool) -> bool:
    """-> True if the file is (or would be) changed."""
    new = json.dumps(data, indent=2) + "\n"
    old = path.read_text() if path.is_file() else None
    if new == old:
        print(f"{path.relative_to(ROOT)} already up to date.")
        return False
    if check_only:
        print(f"{path.relative_to(ROOT)} is STALE.", file=sys.stderr)
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new)
    if "runs" in data:
        n = sum(r["n_tasks"] for r in data["runs"])
        print(f"wrote {path.relative_to(ROOT)} ({len(data['runs'])} run(s), {n} task rows)")
    else:
        print(f"wrote {path.relative_to(ROOT)} ({data.get('n_tasks')} task(s))")
    return True


def one_line(path: Path, limit: int = 400) -> str | None:
    if not path.is_file():
        return None
    s = " ".join(path.read_text().split())
    return s[: limit - 1] + "…" if len(s) > limit else s


def build_tasks_v1(root: Path) -> dict:
    """Task metadata for v1: the trace-extracted `traces_parsec-aap2-<NNNN>` set.

    v1 tasks DO carry a per-task contract (`tests/expected.json`), and reading it turned out
    to matter more than expected, so three of its fields are recorded per task rather than
    assumed from the shared scoring formula:

      * `n_trajectory_ops` — how many tool calls the extracted trace demands. This ranges from
        2 to 36 across the 30 tasks, and it predicts the trajectory score almost perfectly:
        all four tasks asking for <= 4 operations scored trajectory 1.0 at baseline, and of the
        26 asking for >= 6, exactly one did. See results/v1/summary.md.
      * `n_assertions` — how many `answer_contains` strings the answer must hit. Combined with
        the baseline's `assertions` fraction this recovers the exact pass count per task
        (e.g. 0.181818 x 11 = 2 of 11), which is the only per-task detail the baseline file
        itself does not record.
      * `trajectory_match` — the match mode. It is `subset` on all 30, which is what makes the
        op-count correlation above a finding rather than a tautology: a *subset* match over 36
        operations is not 36 chances to fail, it is one long ordered containment check.

    One outright contract defect is visible here and is flagged in results.json rather than
    smoothed over: `traces_parsec-aap2-0052` has an EMPTY assertion list, and an empty list
    scores a vacuous `assertions: 1.0`. Half of that task's 0.500 baseline is "nothing was
    checked", not "everything passed".
    """
    tdir = root / "project" / "harbor-tasks-patched"
    tasks = []
    for d in sorted(p for p in tdir.iterdir() if p.is_dir()):
        exp_path = d / "tests" / "expected.json"
        contract = json.loads(exp_path.read_text()) if exp_path.is_file() else {}
        traj = contract.get("trajectory") or {}
        ops = traj.get("operations") or []
        assertions = contract.get("assertions") or []
        tasks.append(
            {
                "task": d.name,
                "prompt": one_line(d / "instruction.md"),
                "scoring": "gate * (0.5*trajectory + 0.5*assertions)",
                "weights": contract.get("weights"),
                "completion": contract.get("completion"),
                "trajectory_match": traj.get("match"),
                "n_trajectory_ops": len(ops),
                "trajectory_ops": [o.get("name") for o in ops],
                "n_assertions": len(assertions),
                "assertion_values": [a.get("value") for a in assertions],
                "assertion_kinds": sorted({a.get("kind") for a in assertions}),
            }
        )
    return {
        "experiment": "v1",
        "generator": "scripts/extract_rollout_scores.py",
        "source_task_dir": str(tdir),
        "n_tasks": len(tasks),
        "tasks": tasks,
    }


def build_tasks_v2(root: Path) -> dict:
    """Task metadata for v2: the hand-authored `bench-aap2-NNN-<slug>` set.

    v2 tasks each ship their own `tests/expected.json` contract (schema `bench/v2`) with
    PER-TASK weights, so the weights are recorded here rather than assumed. They are not
    uniform: 0.2/0.8 on six tasks, 0.5/0.5 on three, 0.6/0.4 on one. Quoting "v2 weights
    tool_calls 0.2 / answer 0.8" as if it were the schema would be wrong for four of ten.
    """
    tdir = root / "project" / "harbor-tasks-v2.1"
    tasks = []
    for d in sorted(p for p in tdir.iterdir() if p.is_dir()):
        exp_path = d / "tests" / "expected.json"
        contract = json.loads(exp_path.read_text()) if exp_path.is_file() else {}
        ans = contract.get("answer") or {}
        tc = contract.get("tool_calls") or {}
        req = ans.get("required") or []
        tasks.append(
            {
                "task": d.name,
                "prompt": one_line(d / "instruction.md"),
                "contract_schema": contract.get("schema"),
                "weights": contract.get("weights"),
                "tool_call_match": tc.get("match"),
                "n_expected_calls": len(tc.get("expected") or []),
                "required_facts": [r.get("id") for r in req],
                "derived_facts": [r.get("id") for r in req if r.get("derived")],
                "forbidden_facts": [f.get("id") for f in (ans.get("forbidden") or [])],
                "n_golden_tool_calls": len(
                    (json.loads((d / "golden.json").read_text()).get("tool_calls") or [])
                )
                if (d / "golden.json").is_file()
                else None,
            }
        )
    return {
        "experiment": "v2",
        "generator": "scripts/extract_rollout_scores.py",
        "source_task_dir": str(tdir),
        "n_tasks": len(tasks),
        "tasks": tasks,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if anything would change")
    ap.add_argument("--v1-root", type=Path, default=DEFAULT_V1_ROOT)
    ap.add_argument("--v2-root", type=Path, default=DEFAULT_V2_ROOT)
    args = ap.parse_args()

    changed = False
    changed |= emit(
        ROOT / "results" / "v1" / "per_task_scores.json",
        build("v1", args.v1_root, V1_RUNS),
        args.check,
    )
    changed |= emit(
        ROOT / "results" / "v2" / "per_task_scores.json",
        build("v2", args.v2_root, V2_RUNS),
        args.check,
    )
    changed |= emit(
        ROOT / "results" / "v1" / "tasks.json", build_tasks_v1(args.v1_root), args.check
    )
    changed |= emit(
        ROOT / "results" / "v2" / "tasks.json", build_tasks_v2(args.v2_root), args.check
    )

    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
