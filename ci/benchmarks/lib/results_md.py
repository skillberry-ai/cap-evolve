#!/usr/bin/env python3
"""Assemble RESULTS.md from the 2x measurement (measure/run{1,2}/<bench>/{metrics,steps}.jsonl).

  results_md.py <measure_dir> <out_md>

Per task: baseline vs optimized reward only — latency/cost are never per-task in a
whole-suite optimization (every task is scored in the same eval call), so they're
reported per bench as suite-level totals (from each run's steps.jsonl) instead.
"""
from __future__ import annotations
import json, sys
from pathlib import Path


def load_runs(measure: Path):
    runs = {}
    for rd in sorted(measure.glob("run*")):
        for mj in rd.glob("*/metrics.jsonl"):
            for line in mj.read_text().splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                runs.setdefault((r["bench"], r["task"]), {})[rd.name] = r
    return runs


def load_suite_totals(measure: Path):
    """{(bench, run_name): {"optimizer_usd", "optimizer_seconds", "eval_usd", "eval_seconds"}}
    summed from each run's steps.jsonl (baseline + each iteration + finalize)."""
    totals = {}
    for rd in sorted(measure.glob("run*")):
        for sj in rd.glob("*/steps.jsonl"):
            bench = sj.parent.name
            t = {"optimizer_usd": 0.0, "optimizer_seconds": 0.0, "eval_usd": 0.0, "eval_seconds": 0.0}
            for line in sj.read_text().splitlines():
                if not line.strip():
                    continue
                s = json.loads(line)
                for k in t:
                    t[k] += s.get(k) or 0
            totals[(bench, rd.name)] = t
    return totals


def fnum(v, unit=""):
    if v is None:
        return "—"
    return (f"${v:.4f}" if unit == "$" else f"{v:.2f}{unit}")


def fduration(v):
    """Wall-time seconds as minutes+seconds (e.g. 14m48s), matching metrics.py."""
    if v is None:
        return "—"
    total = int(round(v))
    m, s = divmod(total, 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


def main(argv):
    measure, out = Path(argv[1]), Path(argv[2])
    runs = load_runs(measure)
    totals = load_suite_totals(measure)
    benches = sorted({b for (b, _t) in runs} | {b for (b, _r) in totals})
    lines = [
        "# Benchmark suite — baseline metrics (2× measurement)",
        "",
        (
            "Agent `aws/gpt-oss-120b` · optimizer Claude Code `claude-opus-4-8` · 1 iteration · "
            "baseline computed fresh each run (no reuse across runs). Measured twice on "
            "skillberry-1 (self-hosted, IBM VPC). All tasks are **hard** (baseline reward 0) — "
            "see README. Latency is wall-time and "
            "host-dependent; cost/tokens are host-independent (tau2/skillsbench runners report 0)."
        ),
        "",
        "## Per-task reward",
        "",
        "| bench | task | reward base→opt (run1/run2) |",
        "|---|---|---|",
    ]
    for (bench, task) in sorted(runs):
        r1 = runs[(bench, task)].get("run1", {})
        r2 = runs[(bench, task)].get("run2", {})
        opt_reward = f"{fnum(r1.get('reward_opt'))}/{fnum(r2.get('reward_opt'))}"
        base_reward = f"{fnum(r1.get('reward_baseline'))}/{fnum(r2.get('reward_baseline'))}"
        lines.append(f"| {bench} | `{task}` | {base_reward}→{opt_reward} |")

    lines += [
        "",
        "## Per-suite latency/cost (summed over baseline + every iteration + finalize)",
        "",
        "| bench | optimizer $ r1/r2 | optimizer time r1/r2 | eval $ r1/r2 | eval time r1/r2 |",
        "|---|---|---|---|---|",
    ]
    for bench in benches:
        t1 = totals.get((bench, "run1"), {})
        t2 = totals.get((bench, "run2"), {})
        opt_usd = f"{fnum(t1.get('optimizer_usd'),'$')}/{fnum(t2.get('optimizer_usd'),'$')}"
        opt_s = f"{fduration(t1.get('optimizer_seconds'))}/{fduration(t2.get('optimizer_seconds'))}"
        eval_usd = f"{fnum(t1.get('eval_usd'),'$')}/{fnum(t2.get('eval_usd'),'$')}"
        eval_s = f"{fduration(t1.get('eval_seconds'))}/{fduration(t2.get('eval_seconds'))}"
        lines.append(f"| {bench} | {opt_usd} | {opt_s} | {eval_usd} | {eval_s} |")

    lines.append("")
    lines.append("`reward base→opt` = this run's own freshly-computed baseline reward → optimized "
                 "test reward (run1/run2). A stable `0→0/0` is the expected hard-task signal; the "
                 "CI gates on non-regression.")
    out.write_text("\n".join(lines) + "\n")
    print(out.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
