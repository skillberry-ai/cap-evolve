#!/usr/bin/env python3
"""Generate `results/results.json` — the canonical ledger every other artifact derives from.

`results/results.json` is the single machine-readable source of truth for this branch. The
heatmap's `DATA` array and the auto blocks in `reports/task-by-task/*.md` are both generated
*from* it, so a number appears in exactly one place and cannot drift between views.

Inputs — all of them committed inside this branch, so `--check` is meaningful in CI:

    results/v1/tasks.json                 task ids + prompts (30 v1 tasks)
    results/v2/tasks.json                 task ids + prompts + per-task contract weights (10)
    results/v1/per_task_scores.json       per-(task, candidate, split, trial) rewards, all 4 v1 runs
    results/v2/per_task_scores.json       ditto, all 5 v2 runs
    results/v1/baseline_all_1786543049.json      the 30-task v1 baseline sweep (n=1)
    results/v2/baseline_all_1786875106.json      the 10-task v2.1 baseline sweep (n=1)
    results/v2/baseline_all_1786651164.json      the v2.0 sweep, kept as the broken-wiring control
    results/<exp>/runs/<run>/{events,splits,state,final}.json   run-level aggregates

Two things this script does that are worth knowing about:

1. **It reconciles.** Every `evaluate` event in every run carries a split-level `reward`.
   This script recomputes that number two ways from the rollout-derived per-task scores —
   once dropping harness-errored trials from the denominator (`valid`) and once keeping them
   (`all`) — and records which convention reproduced cap-evolve's own figure. That is not
   pedantry: the two conventions disagree by up to 0.077 here, and cap-evolve does not use
   the same one everywhere (see `reconciliation_conventions` in the output, and
   results/v2/summary.md). Recording the answer per cell makes the inconsistency
   machine-visible rather than a claim in prose.

2. **It refuses to invent a seed for tasks no optimizer ever saw.** 28 of v1's 30 tasks and
   0 of v2's were baselined but never entered an optimizer run. Their rows carry `baseline`
   and leave `seed`/`best`/`delta`/`final_test` null, with `status: "BASELINE_ONLY"`. A
   baseline sweep at n=1 is not a seed measurement at n=30 and must not be shown in the same
   column — that conflation is the whole subject of results/v2/summary.md.

Usage:
  python3 scripts/build_results_json.py            # write results/results.json
  python3 scripts/build_results_json.py --check     # exit 1 if it would change (CI-friendly)
  python3 scripts/build_results_json.py --verbose   # also print the reconciliation table
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
OUT = RESULTS / "results.json"

TOL = 5e-6

# Which baseline sweep is the reference baseline for each experiment, and which extra sweeps
# exist. v2 has two: the v2.0 sweep ran against unwired MCP tools and is kept only as the
# control that shows what "the harness is broken" looks like (mean 0.087), not as a result.
BASELINES = {
    "v1": {
        "reference": "baseline_all_1786543049.json",
        "others": [],
    },
    "v2": {
        "reference": "baseline_all_1786875106.json",
        "others": ["baseline_all_1786651164.json"],
    },
}

# The tools an agent could actually call when v1's 30-task baseline sweep ran
# (baseline_all_1786543049.json, 2026-08-12 16:57 local). Two kaegis simulators were up: aap2
# on :8086 and github on :8087. recipes/v1/PROJECT.md records the set verbatim under
# "Coverage of the current 2-sim setup", and separately records the `lookup_catalog_item` gap.
#
# This is in the ledger because it is the single strongest relationship in the v1 data: a task
# whose extracted trace demands any tool outside this set could not reach trajectory 1.0 no
# matter what the skill said, so half of its reward was unreachable by construction. 25 of the
# 30 tasks are in that position. See contract_shape() and results/v1/summary.md.
V1_TOOLS_AVAILABLE_AT_BASELINE = frozenset({
    "query_aap2",                # aap2 sim, :8086
    "fetch_github_file",         # github sim, :8087
    "search_github_repo",
    "search_github_code",
    "search_agnosticv_prs",
})

# The full four-simulator set the CI harness documents (adds babylon :8088 and provisions_db
# :8090). It was up by the 2026-08-14 pilot — v1's `cand_0002` matched the trajectory on 0047
# and 0048, both of which demand `lookup_catalog_item` from babylon. Recorded so the gap
# between the two measurement regimes is machine-visible: the 28 BASELINE_ONLY rows and the 2
# OPTIMIZED rows were not measured against the same tool surface, and this branch does not
# record the moment it changed.
V1_TOOLS_AVAILABLE_FOUR_SIM = V1_TOOLS_AVAILABLE_AT_BASELINE | frozenset({
    "lookup_catalog_item",       # babylon sim, :8088
    "query_babylon_catalog",
    "query_provisions_db",       # provisions_db sim, :8090
    "db_describe_table",
})

SOURCE_WORKTREES = [
    "/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v1",
    "/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v2",
]


# ---------------------------------------------------------------------------- helpers


def rd(path: Path):
    return json.loads(path.read_text())


def jsonl(path: Path):
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def r6(v):
    return None if v is None else round(v, 6)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def report_name(exp: str, task: str) -> str:
    """Report filenames are prefixed by experiment because the two task-id namespaces are
    unrelated and a flat `reports/task-by-task/` must not collide or imply kinship.
    v1: traces_parsec-aap2-0037 -> v1-aap2-0037.md
    v2: bench-aap2-003-never-started-explanation -> v2-bench-aap2-003-never-started-explanation.md
    """
    if exp == "v1":
        return "v1-aap2-" + task.rsplit("-", 1)[-1] + ".md"
    return "v2-" + task + ".md"


# ------------------------------------------------------------------- reconciliation


def split_mean(cells: dict, tasks: list[str], tag: str, split: str, key: str):
    """cap-evolve's split aggregate is the unweighted mean over tasks of each task's own
    trial mean, so reproduce it that way rather than pooling trials."""
    vals = []
    for t in tasks:
        slot = ((cells.get(t) or {}).get(split) or {}).get(tag)
        if slot is None:
            return None, 0
        vals.append(slot.get(key))
    m = mean(vals)
    return (None if m is None else round(m, 10)), len(vals)


def reconcile(run_cells: dict, splits: dict, ev: dict, superseded: bool,
              alt_splits: dict | None = None) -> dict:
    """-> {convention, reason, recomputed_valid, recomputed_all, n_tasks, n_errored_trials}

    `convention` is which denominator reproduces the event's own `reward`:
      "valid"        errored trials dropped (cap-evolve's documented `raw.valid_trials`)
      "all"          errored trials counted as 0.0
      "either"       no trial errored, so the two agree and the cell proves nothing
      "unreconciled" neither matched

    An "unreconciled" cell is never a rounding problem here; it always has a structural cause,
    and `reason` says which, because the four causes mean very different things:

      "empty-split"        the split has no tasks, so the reported reward is a mean over
                           nothing. Both Aug-18 v2 runs print a `test` reward of 0.0 this way
                           and burned 2700 s per eval doing it.
      "superseded-measurement"
                           a later `evaluate` event in the same run reused this split+tag, and
                           only the last one's rollouts survive on disk. The earlier reported
                           number is therefore real but unverifiable from what is committed.
      "reconciled-against-original-splits"
                           the current `splits.json` disagrees with what the run actually used;
                           reconciling against the preserved original succeeds. This is the
                           retroactive edit to run_20260816_202942 (`test: 10` -> `test: []`).
      "no-rollouts"        the split has tasks but no rollouts for this tag were kept.
    """
    split = ev.get("split")
    tag = ev.get("tag")
    reported = ev.get("reward")
    task_list = splits.get(split) or []
    mv, n = split_mean(run_cells, task_list, tag, split, "mean_valid")
    ma, _ = split_mean(run_cells, task_list, tag, split, "mean_all")

    def verdict(mv, ma):
        hv = mv is not None and reported is not None and abs(mv - reported) < TOL
        ha = ma is not None and reported is not None and abs(ma - reported) < TOL
        if hv and ha:
            return "either"
        if hv:
            return "valid"
        if ha:
            return "all"
        return "unreconciled"

    conv = verdict(mv, ma)
    reason = None
    used_alt = False

    if conv == "unreconciled" and not task_list and alt_splits:
        amv, an = split_mean(run_cells, alt_splits.get(split) or [], tag, split, "mean_valid")
        ama, _ = split_mean(run_cells, alt_splits.get(split) or [], tag, split, "mean_all")
        alt = verdict(amv, ama)
        if alt != "unreconciled":
            conv, mv, ma, n, used_alt = alt, amv, ama, an, True
            reason = "reconciled-against-original-splits"
            task_list = alt_splits.get(split) or []

    if conv == "unreconciled":
        if not task_list:
            reason = "empty-split"
        elif superseded:
            reason = "superseded-measurement"
        elif mv is None:
            reason = "no-rollouts"
        else:
            reason = "mismatch"

    errored = 0
    ns = set()
    for t in task_list:
        slot = ((run_cells.get(t) or {}).get(split) or {}).get(tag)
        if slot:
            errored += slot.get("n_errored", 0)
            ns.add(slot.get("n"))

    out = {
        "convention": conv,
        "recomputed_valid": r6(mv),
        "recomputed_all": r6(ma),
        "n_tasks": n,
        "n_trials": (ns.pop() if len(ns) == 1 else (sorted(x for x in ns if x) or None)),
        "n_errored_trials": errored,
    }
    if reason:
        out["reason"] = reason
    if used_alt:
        out["reconciled_against"] = "splits.json.iter1-original"
    return out


# ------------------------------------------------------------------------- per-run


def build_runs(exp: str, pts: dict) -> list[dict]:
    out = []
    for r in pts["runs"]:
        run = r["run"]
        rdir = RESULTS / exp / "runs" / run
        splits = rd(rdir / "splits.json")
        state = rd(rdir / "state.json") if (rdir / "state.json").is_file() else {}
        final = rd(rdir / "final.json") if (rdir / "final.json").is_file() else {}
        evs = jsonl(rdir / "events.jsonl")

        alt_path = rdir / "splits.json.iter1-original"
        alt_splits = rd(alt_path) if alt_path.is_file() else None

        cells = r["cells"]
        # An `evaluate` event whose (split, tag) is used again later in the same run has had
        # its rollouts overwritten on disk, so it cannot be reconciled. Work out which those
        # are up front rather than guessing after the fact.
        seen: dict = {}
        for i, ev in enumerate(evs):
            if ev.get("kind") == "evaluate":
                seen.setdefault((ev.get("split"), ev.get("tag")), []).append(i)
        last_of = {k: v[-1] for k, v in seen.items()}

        evaluations, warnings, steps = [], [], []
        baseline_reused = None
        for i, ev in enumerate(evs):
            kind = ev.get("kind")
            if kind == "evaluate":
                key = (ev.get("split"), ev.get("tag"))
                superseded = last_of.get(key) != i
                rec = reconcile(cells, splits, ev, superseded, alt_splits)
                evaluations.append(
                    {
                        "split": ev["split"],
                        "tag": ev["tag"],
                        "reward": r6(ev.get("reward")),
                        "stderr": r6(ev.get("stderr")),
                        "seconds": r6(ev.get("seconds")),
                        "reconciliation": rec,
                    }
                )
            elif kind == "step":
                steps.append(
                    {
                        "candidate": ev.get("candidate"),
                        "accept": ev.get("accept"),
                        "reason": ev.get("reason"),
                        "val": r6(ev.get("val")),
                        "parent": ev.get("parent"),
                        "parent_val": r6(ev.get("parent_val")),
                    }
                )
            elif kind in ("splits_warning", "gate_warning"):
                warnings.append({"kind": kind, "msg": ev.get("msg")})
            elif kind == "optimizer_error":
                warnings.append(
                    {"kind": kind, "candidate": ev.get("candidate"),
                     "msg": str(ev.get("error"))[:200]}
                )
            elif kind == "baseline_reused":
                baseline_reused = {
                    "prior_run_dir": ev.get("prior_run_dir"),
                    "val": r6(ev.get("val")),
                    "stderr": r6(ev.get("stderr")),
                }

        split_sizes = {k: len(v) for k, v in splits.items() if isinstance(v, list)}
        # A test split that is a subset of train/val is a fit metric, not a holdout. Flag it
        # here so nothing downstream can print it as "held out".
        tr, va, te = (set(splits.get(k) or []) for k in ("train", "val", "test"))
        if not te:
            holdout = "empty"
        elif te & (tr | va):
            holdout = "overlaps-train-or-val"
        else:
            holdout = "disjoint"

        out.append(
            {
                "experiment": exp,
                "run": run,
                "role": r["role"],
                "headline": r["headline"],
                "splits": split_sizes,
                "splits_original": (
                    {k: len(v) for k, v in alt_splits.items() if isinstance(v, list)}
                    if alt_splits
                    else None
                ),
                "test_used": splits.get("test_used"),
                "test_holdout": holdout,
                "best_id": state.get("best_id"),
                "budget": state.get("budget"),
                "spent": state.get("spent"),
                "test_reward": r6((final.get("test") or {}).get("reward")),
                "test_baseline_reward": r6((final.get("test_baseline") or {}).get("reward")),
                "test_delta": r6(final.get("test_delta")),
                "test_per_task_rows": len((final.get("test") or {}).get("per_task") or []),
                "baseline_reused": baseline_reused,
                "evaluations": evaluations,
                "steps": steps,
                "warnings": warnings,
            }
        )
    return out


# ------------------------------------------------------------------------ per-task


def cell(cells, task, split, tag, key="mean_valid"):
    slot = ((cells.get(task) or {}).get(split) or {}).get(tag)
    return None if slot is None else slot.get(key)


def cell_n(cells, task, split, tag):
    slot = ((cells.get(task) or {}).get(split) or {}).get(tag)
    return None if slot is None else slot.get("n")


def cell_err(cells, task, split, tag):
    slot = ((cells.get(task) or {}).get(split) or {}).get(tag)
    return None if slot is None else slot.get("n_errored")


def v1_subcategory(row: dict) -> str:
    """v1's reward is gate·(0.5·trajectory + 0.5·assertions). A task whose baseline
    trajectory is exactly 1.0 is one the seed skill already reproduces the golden tool
    sequence for; everything else needs a multi-tool sequence it does not get right. That
    split is the one that actually predicts baseline reward (0.730 vs 0.142 mean), so it is
    the useful subcategory — there is no hand-assigned taxonomy for these 30 tasks."""
    return "trajectory-match" if row.get("trajectory") == 1.0 else "multi-tool"


def missing_tools(meta: dict, available=V1_TOOLS_AVAILABLE_AT_BASELINE) -> list[str]:
    """Tools this v1 task's extracted trace demands that no running simulator exposed.

    `trajectory_match` is `subset` on all 30 v1 tasks: the demanded op sequence must appear in
    the transcript in order. A single demanded op that cannot be called at all therefore makes
    trajectory 1.0 unreachable for the whole task, not merely harder — the containment fails whole.
    Deduplicated and sorted, so a task demanding `lookup_catalog_item` five times lists it once.
    """
    ops = meta.get("trajectory_ops")
    if not ops:
        return []
    return sorted(set(ops) - set(available))


def v1_flags(row: dict, meta: dict) -> list[str]:
    f = []
    if row.get("completion") == 0.0:
        f.append("gate-failed-at-baseline")
    if row.get("reward") == 0.5:
        f.append("capped-at-0.5-by-50/50-weighting")
    if row.get("reward") == 1.0:
        f.append("solved-at-baseline")
    if row.get("reward") == 0.0:
        f.append("zero-at-baseline")
    if row.get("error"):
        f.append("baseline-trial-errored")
    # A contract defect, not a result: an empty assertion list scores a vacuous 1.0, so half
    # this task's reward is "nothing was checked". Flagged rather than silently averaged in.
    if meta.get("n_assertions") == 0:
        f.append("no-assertions-scores-vacuous-1.0")
    # The dominant finding in v1, and the reason the row carries it rather than only the prose:
    # under a `subset` match, one demanded tool that no running simulator exposed makes
    # trajectory 1.0 unreachable, capping the task's reward at 0.5 whatever the skill says.
    # This flag partitions the 30 tasks exactly along the observed trajectory outcome — all 5
    # tasks without it matched, all 25 with it scored 0.0 — so it is not a hypothesis about the
    # data, it is the data. Any mean over flagged rows is a measurement of the harness.
    if missing_tools(meta):
        f.append("trajectory-unreachable-tool-gap")
    # Kept as a secondary descriptor, not an explanation. The op-count correlation
    # (4/4 matched at <= 4 demanded calls, 1/26 above) is real but confounded: four of the five
    # tool-covered tasks are also the four shortest, and the fifth (0074) demands 8 calls and
    # matched anyway. Coverage predicts the outcome perfectly; length does not add to it.
    ops = meta.get("n_trajectory_ops")
    if ops is not None and ops >= 20:
        f.append("long-trace-contract")
    return f


def assertions_passed(row: dict, meta: dict):
    """Recover the exact assertion pass count: fraction x list length.

    The baseline file records only the fraction, so "2 of 11" is not in any source file — but
    it is exact, because `assertions` is by construction k/n over the task's own contract. All
    30 v1 tasks come out integral to within 1e-9; anything that did not would be a bug in this
    assumption and is returned as None rather than rounded into looking fine.
    """
    n = meta.get("n_assertions")
    a = row.get("assertions")
    if not n or a is None:
        return None
    k = a * n
    return int(round(k)) if abs(k - round(k)) < 1e-6 else None


def build_tasks(pts: dict, tasks_meta: dict, exp: str) -> list[dict]:
    head = next(r for r in pts["runs"] if r["headline"])
    cells = head["cells"]
    hrun = head["run"]
    hsplits = rd(RESULTS / exp / "runs" / hrun / "splits.json")
    hstate = rd(RESULTS / exp / "runs" / hrun / "state.json")
    hfinal = rd(RESULTS / exp / "runs" / hrun / "final.json")
    best_id = hstate.get("best_id")
    iters = (hstate.get("spent") or {}).get("iterations")
    val = set(hsplits.get("val") or [])

    ftest = {
        pt["task_id"]: pt
        for pt in ((hfinal.get("test") or {}).get("per_task") or [])
    }

    bl_file = BASELINES[exp]["reference"]
    bl = {r["task"]: r for r in rd(RESULTS / exp / bl_file)["rows"]}

    meta = {t["task"]: t for t in tasks_meta["tasks"]}

    rows = []
    for task in sorted(meta):
        m = meta[task]
        b = bl.get(task, {})
        optimized = task in val
        status = "OPTIMIZED" if optimized else "BASELINE_ONLY"

        seed = r6(cell(cells, task, "val", "seed")) if optimized else None
        seed_n = cell_n(cells, task, "val", "seed") if optimized else None
        c1 = r6(cell(cells, task, "val", "cand_0001")) if optimized else None
        c2 = r6(cell(cells, task, "val", "cand_0002")) if optimized else None
        seed_train = r6(cell(cells, task, "train", "seed_train"))
        seed_train_n = cell_n(cells, task, "train", "seed_train")
        # The `*_all` twins count harness-errored trials as 0.0 instead of dropping them. They
        # differ from the plain field ONLY where a trial errored, and they exist because
        # cap-evolve does not consistently pick one: v1's headline val/seed aggregate matches
        # the drop-errored convention, v2's headline train/seed_train matches this one. Carrying
        # both means a downstream view can label which it is showing instead of guessing.
        seed_all = r6(cell(cells, task, "val", "seed", "mean_all")) if optimized else None
        c1_all = r6(cell(cells, task, "val", "cand_0001", "mean_all")) if optimized else None
        seed_train_all = r6(cell(cells, task, "train", "seed_train", "mean_all"))

        if not optimized:
            best = best_tag = delta = None
        elif best_id == "seed":
            best, best_tag = seed, "seed"
            delta = 0.0
        else:
            best = {"cand_0001": c1, "cand_0002": c2}.get(best_id)
            best_tag = best_id
            delta = None if (best is None or seed is None) else r6(best - seed)

        ft = ftest.get(task)
        final_test = r6(ft["reward"]) if ft else None

        errored = 0
        for split, tag in (
            ("val", "seed"), ("val", "cand_0001"), ("val", "cand_0002"),
            ("train", "seed_train"), ("test", "FINAL"), ("test", "FINAL_seed"),
        ):
            e = cell_err(cells, task, split, tag)
            if e:
                errored += e

        row = {
            "experiment": exp,
            "task": task,
            "category": "aap2",
            "subcategory": (
                v1_subcategory(b) if exp == "v1"
                else task.split("-", 3)[-1]  # the slug: 003-never-started-explanation -> never-started-explanation
            ),
            "source": "trace-extracted" if exp == "v1" else "hand-authored",
            "status": status,
            "baseline": r6(b.get("reward")),
            "baseline_n": 1,
            "baseline_gate": b.get("completion"),
            "baseline_trajectory": b.get("trajectory"),
            "baseline_assertions": r6(b.get("assertions")),
            # Contract shape, copied from the task's own tests/expected.json via tasks.json.
            # These are the denominators every score above is a fraction of, and v1's numbers
            # are not interpretable without them: see results/v1/summary.md.
            "n_trajectory_ops": m.get("n_trajectory_ops"),
            "trajectory_match": m.get("trajectory_match"),
            # Which demanded ops no simulator served when the baseline sweep ran, and hence
            # whether the trajectory half of this task's reward was reachable at all. Null for
            # v2, which has no trajectory component.
            "trajectory_tools_missing_at_baseline": (
                missing_tools(m) if exp == "v1" else None
            ),
            "trajectory_reachable_at_baseline": (
                (not missing_tools(m)) if exp == "v1" else None
            ),
            "trajectory_reachable_four_sim": (
                (not missing_tools(m, V1_TOOLS_AVAILABLE_FOUR_SIM)) if exp == "v1" else None
            ),
            "n_assertions": m.get("n_assertions"),
            "baseline_assertions_passed": assertions_passed(b, m) if exp == "v1" else None,
            "n_required_facts": len(m.get("required_facts") or []) if exp == "v2" else None,
            "n_derived_facts": len(m.get("derived_facts") or []) if exp == "v2" else None,
            "n_expected_calls": m.get("n_expected_calls") if exp == "v2" else None,
            "seed": seed,
            "seed_n": seed_n,
            "seed_all": seed_all,
            "seed_train": seed_train,
            "seed_train_n": seed_train_n,
            "seed_train_all": seed_train_all,
            "cand_0001": c1,
            "cand_0001_all": c1_all,
            "cand_0002": c2,
            "best": best,
            "best_tag": best_tag,
            "delta": delta,
            "final_test": final_test,
            "iters_spent": iters if optimized else None,
            "trials_errored": errored,
            "headline_run": hrun if optimized else None,
            "flags": v1_flags(b, m) if exp == "v1" else [],
            "weights": m.get("weights"),
            "prompt": m.get("prompt"),
            "report": "reports/task-by-task/" + report_name(exp, task),
        }
        rows.append(row)
    return rows


# ---------------------------------------------------------------------- aggregates


def experiment_summary(exp: str, rows: list[dict], runs: list[dict]) -> dict:
    head = next(r for r in runs if r["headline"])
    opt = [r for r in rows if r["status"] == "OPTIMIZED"]
    bl = [r["baseline"] for r in rows if r["baseline"] is not None]
    bl_mean = mean(bl)
    var = (
        sum((x - bl_mean) ** 2 for x in bl) / (len(bl) - 1)
        if bl_mean is not None and len(bl) > 1
        else None
    )
    return {
        "experiment": exp,
        "n_tasks": len(rows),
        "n_optimized": len(opt),
        "n_baseline_only": len(rows) - len(opt),
        "baseline_file": BASELINES[exp]["reference"],
        "baseline_mean": r6(bl_mean),
        "baseline_stdev": r6(var**0.5) if var else None,
        "baseline_n_trials": 1,
        "headline_run": head["run"],
        "headline_best_id": head["best_id"],
        "headline_val_seed": r6(
            next((e["reward"] for e in head["evaluations"]
                  if e["split"] == "val" and e["tag"] == "seed"), None)
        )
        or (head.get("baseline_reused") or {}).get("val"),
        "headline_val_best": r6(
            next((e["reward"] for e in head["evaluations"]
                  if e["split"] == "val" and e["tag"] == head["best_id"]), None)
        ),
        "headline_test_reward": head["test_reward"],
        "headline_test_delta": head["test_delta"],
        "headline_test_holdout": head["test_holdout"],
        "n_runs": len(runs),
        "contract_shape": contract_shape(exp, rows),
    }


def contract_shape(exp: str, rows: list[dict]) -> dict:
    """How much of the score is explained by the contract and the harness rather than the skill.

    This lives in the ledger, not just in prose, because it carries the strongest relationship
    in the v1 data and a reader who only sees means will miss it. v1's baseline trajectory
    component is 1.0 on exactly the 5 tasks whose entire demanded op sequence was callable
    against the two simulators that were running, and 0.0 on all 25 that demand at least one
    tool no simulator exposed. Under a `subset` match one uncallable op fails the whole
    containment, so for those 25 tasks half the reward was unreachable by construction and
    their scores are a property of the harness, not of the skill.

    The op-count relationship is also recorded (4/4 matched at <= 4 demanded calls, 1/26 above)
    but it is the weaker of the two and is confounded by the first: four of the five covered
    tasks are also the four shortest. Coverage separates the outcome perfectly, 5/5 against
    0/25; length does not add anything once coverage is known.
    """
    if exp == "v2":
        # v2 has no trajectory component at all — its tool-call term is a per-call match over a
        # short expected list, and its answer term is a required/forbidden fact check. So the
        # comparable shape numbers are call counts and fact counts, not op counts.
        calls = [r["n_expected_calls"] for r in rows if r.get("n_expected_calls") is not None]
        facts = [r["n_required_facts"] for r in rows if r.get("n_required_facts") is not None]
        wsets = sorted({json.dumps(r["weights"], sort_keys=True) for r in rows if r.get("weights")})
        return {
            "n_expected_calls_min": min(calls) if calls else None,
            "n_expected_calls_max": max(calls) if calls else None,
            "n_required_facts_min": min(facts) if facts else None,
            "n_required_facts_max": max(facts) if facts else None,
            "n_derived_facts_total": sum(r.get("n_derived_facts") or 0 for r in rows),
            # Recorded because "v2 weights tool_calls 0.2 / answer 0.8" is true of only six of
            # the ten tasks; the weights are per-task, not a schema-wide constant.
            "weight_variants": [json.loads(w) for w in wsets],
            "tasks_per_weight_variant": {
                w: sum(1 for r in rows
                       if json.dumps(r.get("weights"), sort_keys=True) == w)
                for w in wsets
            },
        }

    ops = [r["n_trajectory_ops"] for r in rows if r.get("n_trajectory_ops") is not None]
    out = {
        "n_trajectory_ops_min": min(ops) if ops else None,
        "n_trajectory_ops_max": max(ops) if ops else None,
        "n_trajectory_ops_mean": r6(mean(ops)) if ops else None,
        "trajectory_match_modes": sorted({r["trajectory_match"] for r in rows
                                          if r.get("trajectory_match")}),
    }
    hit = lambda rs: sum(1 for r in rs if r.get("baseline_trajectory") == 1.0)

    # --- tool coverage: the dominant effect, reported first ---------------------------------
    reach = [r for r in rows if r.get("trajectory_reachable_at_baseline")]
    unreach = [r for r in rows if r.get("trajectory_reachable_at_baseline") is False]
    gapcount: dict[str, int] = {}
    for r in rows:
        for t in r.get("trajectory_tools_missing_at_baseline") or []:
            gapcount[t] = gapcount.get(t, 0) + 1
    out |= {
        "tools_available_at_baseline": sorted(V1_TOOLS_AVAILABLE_AT_BASELINE),
        "n_tasks_trajectory_reachable_at_baseline": len(reach),
        "n_tasks_trajectory_unreachable_at_baseline": len(unreach),
        "trajectory_hit_when_reachable": f"{hit(reach)}/{len(reach)}",
        "trajectory_hit_when_unreachable": f"{hit(unreach)}/{len(unreach)}",
        "tasks_trajectory_reachable_at_baseline": [r["task"] for r in reach],
        "missing_tool_task_counts": dict(sorted(gapcount.items(), key=lambda kv: -kv[1])),
        # What the aggregate would have to be if every unreachable task lost exactly its
        # trajectory half and nothing else: (25 x 0.5 + 5 x 1.0) / 30. The observed baseline
        # mean is far below this, so the tool gap is a ceiling on the experiment, not an
        # explanation of its result — the assertion half was also mostly failing.
        "reward_ceiling_given_tool_gap": r6((len(unreach) * 0.5 + len(reach) * 1.0) / len(rows)),
        "n_tasks_trajectory_reachable_four_sim": sum(
            1 for r in rows if r.get("trajectory_reachable_four_sim")
        ),
        "tool_coverage_note": (
            "The 30-task baseline sweep ran on 2026-08-12 against two simulators (aap2, "
            "github). 25 of 30 tasks demand at least one tool neither served, and under a "
            "`subset` trajectory match that makes trajectory 1.0 unreachable for those tasks "
            "regardless of the skill. Their baseline rewards are capped at 0.5 by construction "
            "and must not be read as skill measurements. By the 2026-08-14 pilot the babylon "
            "and provisions_db simulators were also up (cand_0002 matched the trajectory on "
            "0047 and 0048, which both demand lookup_catalog_item) — so the 28 BASELINE_ONLY "
            "rows and the 2 OPTIMIZED rows were measured against different tool surfaces, and "
            "no file in this branch records when the surface changed."
        ),
    }

    # --- op count: secondary, and confounded by the above -----------------------------------
    short = [r for r in rows if (r.get("n_trajectory_ops") or 0) <= 4]
    long_ = [r for r in rows if (r.get("n_trajectory_ops") or 0) > 4]
    out |= {
        "trajectory_hit_le_4_ops": f"{hit(short)}/{len(short)}",
        "trajectory_hit_gt_4_ops": f"{hit(long_)}/{len(long_)}",
        "trajectory_hit_gt_4_ops_which": [
            r["task"] for r in long_ if r.get("baseline_trajectory") == 1.0
        ],
        "op_count_confound_note": (
            "Secondary and confounded. Four of the five tool-covered tasks are also the four "
            "with <= 4 demanded calls, and the fifth (0074) demands 8 and matched anyway. "
            "Within the covered five, demanded length ranges 2-8 and every one matched, so op "
            "count has no residual predictive power once tool coverage is accounted for."
        ),
        "n_assertions_min": min(r["n_assertions"] for r in rows),
        "n_assertions_max": max(r["n_assertions"] for r in rows),
        "tasks_with_zero_assertions": [r["task"] for r in rows if r["n_assertions"] == 0],
        "baseline_assertions_passed_total": sum(
            r["baseline_assertions_passed"] or 0 for r in rows
        ),
        "baseline_assertions_total": sum(r["n_assertions"] for r in rows),
    }
    return out


# ----------------------------------------------------------------------------- main


def build() -> dict:
    tasks, runs, exps = [], [], []
    for exp in ("v1", "v2"):
        pts = rd(RESULTS / exp / "per_task_scores.json")
        meta = rd(RESULTS / exp / "tasks.json")
        rrows = build_runs(exp, pts)
        trows = build_tasks(pts, meta, exp)
        tasks += trows
        runs += rrows
        exps.append(experiment_summary(exp, trows, rrows))

    conv = {}
    for r in runs:
        for e in r["evaluations"]:
            c = e["reconciliation"]["convention"]
            conv[c] = conv.get(c, 0) + 1

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator": "scripts/build_results_json.py",
        "benchmark": "parsec",
        "target": "parsec aap2 sub-agent SKILL.md (capabilities: [system-prompt])",
        "total_tasks": len(tasks),
        "experiments": exps,
        "source_worktrees": SOURCE_WORKTREES,
        "reconciliation_conventions": conv,
        "reconciliation_note": (
            "Counts of how cap-evolve's own split aggregates reproduce from the per-task trial "
            "rewards. 'either' means no trial errored in that cell, so it proves nothing about "
            "the denominator. 'valid' and 'all' both occurring in the same ledger is the "
            "inconsistency described in results/v2/summary.md: v1's headline val/seed drops "
            "errored trials, v2's headline train/seed_train counts them as zeros."
        ),
        "runs": runs,
        "tasks": tasks,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    data = build()

    if args.verbose:
        print(f"{'run':28} {'split':6} {'tag':11} {'reported':>10} {'valid':>10} {'all':>10}  conv")
        for r in data["runs"]:
            for e in r["evaluations"]:
                rec = e["reconciliation"]
                print(
                    f"{r['run'][:28]:28} {e['split']:6} {e['tag']:11} "
                    f"{e['reward']!s:>10} {rec['recomputed_valid']!s:>10} "
                    f"{rec['recomputed_all']!s:>10}  {rec['convention']}"
                    + (f" [{rec['reason']}]" if rec.get("reason") else "")
                    + (f"  (+{rec['n_errored_trials']} errored)" if rec["n_errored_trials"] else "")
                )
        print()

    new = json.dumps(data, indent=2) + "\n"
    if OUT.is_file():
        old = OUT.read_text()
        # `generated_at` changes on every run; ignore it when deciding staleness so `--check`
        # tests content, not clock.
        def strip_ts(s):
            d = json.loads(s)
            d.pop("generated_at", None)
            return json.dumps(d, indent=2, sort_keys=True)

        if strip_ts(new) == strip_ts(old):
            print(f"results/results.json already up to date ({data['total_tasks']} tasks).")
            return 0

    if args.check:
        print("results/results.json is STALE.", file=sys.stderr)
        return 1

    if data["reconciliation_conventions"].get("unreconciled"):
        print(
            f"NOTE: {data['reconciliation_conventions']['unreconciled']} evaluate cell(s) did "
            "not reconcile under either convention — recorded in the output.",
            file=sys.stderr,
        )

    OUT.write_text(new)
    print(
        f"wrote results/results.json — {data['total_tasks']} tasks, "
        f"{len(data['runs'])} runs, conventions {data['reconciliation_conventions']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
