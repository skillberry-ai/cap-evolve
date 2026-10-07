#!/usr/bin/env python3
"""Gather an h4 eval sweep's per-task results into one results.json + summary.md.

Each job in a sweep writes its own
``results/h4_<suite>/<task>/run/baseline.json``; nothing merges them, which is
what this does. It is the piece the skillsbench task-by-task sweeps never had —
there, per-job output was read and transcribed by hand, and
``skillsbench-history`` twice caught numbers that had drifted from their source
that way.

Two distinctions it preserves, because collapsing either produces a number that
looks fine and is wrong:

* **An errored trial is not a zero.** ``per_task[].raw`` carries ``errored``,
  ``errored_trials`` and ``valid_trials``. Infra failures (a gateway timeout, a
  simulator that never activated) land as ``reward: 0.0`` alongside genuine
  zeros, and they do not distribute evenly across what you are comparing — in
  v1 one outage window silently voided 16 of 60 trials in the headline cell,
  and in v2 8 of 90 baseline trials errored against 0 of 90 champion trials.
  Any task with ``errored_trials > 0`` is reported, and excluded from the
  headline mean unless --include-errored.

* **A missing task is not a scored task.** A task in the suite manifest with no
  ``baseline.json`` is listed as missing, never averaged over as if absent by
  choice. ``n_scored`` vs ``n_tasks`` is reported for the same reason.

It also flags the known cost-metering gap (cap-evolve#562): a task whose
``cost_usd`` is exactly 0.0 while ``seconds`` is large did not run free, it ran
unmetered — so the cost total is a floor, and this says so rather than
presenting it as complete.

Usage:
    python3 scripts/parsec/h4/collect.py --suite-id base01
    python3 scripts/parsec/h4/collect.py --suite-id base01 --source h4-base01-rerun
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def read_task_result(baseline_path: Path, task_id: str) -> dict | None:
    """One task's row, or None when baseline.json is unreadable/not about it."""
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"task_id": task_id, "status": "unreadable", "error": str(e)}

    val = data.get("val") or {}
    per_task = val.get("per_task") or []
    # Each h4 project pins split_ids to one task, so val.per_task should hold
    # exactly that task. Match by id rather than taking [0]: a project scaffolded
    # against the wrong split would otherwise be silently attributed here.
    entry = next((t for t in per_task if t.get("task_id") == task_id), None)
    if entry is None:
        return {
            "task_id": task_id,
            "status": "mismatched",
            "error": (f"baseline.json scored {[t.get('task_id') for t in per_task]}, "
                      f"not {task_id} — check this project's split_ids.json"),
        }

    raw = entry.get("raw") or {}
    errored_trials = int(raw.get("errored_trials") or 0)
    seconds = val.get("seconds")
    cost = val.get("cost_usd")
    return {
        "task_id": task_id,
        "status": "errored" if errored_trials else "ok",
        "reward": entry.get("reward"),
        "stderr": entry.get("stderr"),
        "n": entry.get("n"),
        "trial_rewards": entry.get("trial_rewards"),
        "errored_trials": errored_trials,
        "valid_trials": raw.get("valid_trials"),
        "n_trials": raw.get("n_trials"),
        "metrics": entry.get("metrics"),
        # cost/tokens/seconds are recorded at the val level, which for a
        # single-task project is this task's own spend.
        "cost_usd": cost,
        "tokens": val.get("tokens"),
        "seconds": seconds,
        "unmetered": bool(cost == 0 and (seconds or 0) > 60),
        "feedback": entry.get("feedback"),
    }


def collect(suite_id: str, *, repo_root: Path = REPO_ROOT) -> dict:
    results_root = repo_root / "results" / f"h4_{suite_id}"
    manifest = repo_root / ".capevolve" / f"h4_{suite_id}.tasks"

    if manifest.is_file():
        expected = [t.strip() for t in manifest.read_text().splitlines() if t.strip()]
    else:
        # No manifest (hand-driven sweep): fall back to whatever ran.
        expected = sorted(p.name for p in results_root.iterdir()
                          if p.is_dir() and not p.name.startswith("_")) \
            if results_root.is_dir() else []

    rows: list[dict] = []
    missing: list[str] = []
    for task_id in expected:
        baseline = results_root / task_id / "run" / "baseline.json"
        if not baseline.is_file():
            missing.append(task_id)
            continue
        row = read_task_result(baseline, task_id)
        if row is not None:
            rows.append(row)

    scored = [r for r in rows if r["status"] == "ok" and r.get("reward") is not None]
    errored = [r for r in rows if r["status"] == "errored"]
    broken = [r for r in rows if r["status"] in ("unreadable", "mismatched")]

    def _mean(xs: list[float]) -> float | None:
        return statistics.fmean(xs) if xs else None

    clean_rewards = [float(r["reward"]) for r in scored]
    with_errored = clean_rewards + [float(r["reward"]) for r in errored
                                    if r.get("reward") is not None]

    costs = [float(r["cost_usd"]) for r in rows if r.get("cost_usd") is not None]
    secs = [float(r["seconds"]) for r in rows if r.get("seconds") is not None]
    toks = [int(r["tokens"]) for r in rows if r.get("tokens") is not None]

    return {
        "suite_id": suite_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_expected": len(expected),
        "n_scored_clean": len(scored),
        "n_with_errored_trials": len(errored),
        "n_broken": len(broken),
        "n_missing": len(missing),
        "missing": missing,
        "mean_reward_clean": _mean(clean_rewards),
        "mean_reward_including_errored": _mean(with_errored),
        "total_cost_usd": sum(costs) if costs else None,
        "total_tokens": sum(toks) if toks else None,
        # Under fan-out these differ by the width of the sweep: billed cost adds
        # up across lanes, but elapsed time is the slowest lane, not the sum.
        "serial_seconds": sum(secs) if secs else None,
        "slowest_task_seconds": max(secs) if secs else None,
        "n_unmetered": sum(1 for r in rows if r.get("unmetered")),
        "tasks": rows,
    }


def render_summary(agg: dict, source: str) -> str:
    def fmt(x, nd=4):
        return "--" if x is None else f"{x:.{nd}f}"

    def hrs(s):
        return "--" if s is None else f"{s / 3600:.2f}h"

    lines: list[str] = []
    lines.append(f"# h4 eval sweep — suite `{agg['suite_id']}`")
    lines.append("")
    lines.append(f"Source tag: `{source}`  ")
    lines.append(f"Generated: {agg['generated_at']}  ")
    lines.append("Generated by `scripts/parsec/h4/collect.py` from each task's "
                 "own `baseline.json` — do not hand-edit the numbers below.")
    lines.append("")
    lines.append(f"- tasks expected: **{agg['n_expected']}**")
    lines.append(f"- cleanly scored: **{agg['n_scored_clean']}**")
    lines.append(f"- with errored trials: **{agg['n_with_errored_trials']}**")
    lines.append(f"- missing (no result): **{agg['n_missing']}**")
    if agg["n_broken"]:
        lines.append(f"- unreadable/mismatched: **{agg['n_broken']}**")
    lines.append("")
    lines.append(f"**Mean reward (clean tasks only): {fmt(agg['mean_reward_clean'])}**")
    if agg["n_with_errored_trials"]:
        lines.append(f"Mean including tasks that had errored trials: "
                     f"{fmt(agg['mean_reward_including_errored'])} — the two differ "
                     f"because infra failures score as 0.0; prefer the clean figure "
                     f"and re-run the errored tasks.")
    lines.append("")
    lines.append(f"- billed cost: **${fmt(agg['total_cost_usd'], 2)}**"
                 + (f" (FLOOR — {agg['n_unmetered']} task(s) reported $0.00 against "
                    f"real wall-clock; see cap-evolve#562)" if agg["n_unmetered"] else ""))
    lines.append(f"- tokens: **{agg['total_tokens'] if agg['total_tokens'] is not None else '--'}**")
    lines.append(f"- summed task time: **{hrs(agg['serial_seconds'])}** "
                 f"(what one lane would have taken)")
    lines.append(f"- slowest single task: **{hrs(agg['slowest_task_seconds'])}** "
                 f"(the floor on a fully parallel sweep)")
    lines.append("")
    lines.append("| task | reward | stderr | trials | errored | cost($) | time(h) | status |")
    lines.append("|---|--:|--:|--:|--:|--:|--:|:--|")
    for r in sorted(agg["tasks"], key=lambda x: x["task_id"]):
        if r["status"] in ("unreadable", "mismatched"):
            lines.append(f"| `{r['task_id']}` | -- | -- | -- | -- | -- | -- | "
                         f"**{r['status']}** |")
            continue
        lines.append(
            f"| `{r['task_id']}` | {fmt(r.get('reward'))} | {fmt(r.get('stderr'))} "
            f"| {r.get('valid_trials')}/{r.get('n_trials')} | {r.get('errored_trials')} "
            f"| {fmt(r.get('cost_usd'), 2)} | {hrs(r.get('seconds')).rstrip('h')} "
            f"| {'ok' if r['status'] == 'ok' else '**errored**'} |"
        )
    if agg["missing"]:
        lines.append("")
        lines.append("## Missing")
        lines.append("")
        lines.append("No `baseline.json` for these — not scored, not zero:")
        lines.append("")
        for t in agg["missing"]:
            lines.append(f"- `{t}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite-id", required=True)
    ap.add_argument("--source", default=None,
                    help="provenance tag written into results.json (default h4-<suite>)")
    ap.add_argument("--out", default=None,
                    help="output directory (default results/h4_<suite>/)")
    ap.add_argument("--stdout", action="store_true",
                    help="print summary.md instead of writing files")
    args = ap.parse_args()

    source = args.source or f"h4-{args.suite_id}"
    agg = collect(args.suite_id)
    agg["source"] = source

    if agg["n_expected"] == 0:
        print(f"nothing found for suite {args.suite_id}: no task manifest at "
              f".capevolve/h4_{args.suite_id}.tasks and no results under "
              f"results/h4_{args.suite_id}/", file=sys.stderr)
        return 1

    summary = render_summary(agg, source)
    if args.stdout:
        print(summary)
        return 0

    out_dir = Path(args.out) if args.out else REPO_ROOT / "results" / f"h4_{args.suite_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(agg, indent=2) + "\n", encoding="utf-8")
    (out_dir / "summary.md").write_text(summary, encoding="utf-8")

    print(f"suite {args.suite_id}: {agg['n_scored_clean']} clean, "
          f"{agg['n_with_errored_trials']} errored, {agg['n_missing']} missing "
          f"of {agg['n_expected']}")
    if agg["mean_reward_clean"] is not None:
        print(f"mean reward (clean): {agg['mean_reward_clean']:.4f}")
    print(f"wrote {out_dir / 'results.json'}")
    print(f"wrote {out_dir / 'summary.md'}")
    # A sweep with holes is the normal mid-flight state, not an error, but it
    # must not be mistaken for a finished one.
    return 0 if agg["n_missing"] == 0 and agg["n_broken"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
