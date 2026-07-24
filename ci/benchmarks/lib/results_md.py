#!/usr/bin/env python3
"""Assemble RESULTS.md from the 2x measurement (measure/run{1,2}/<bench>/metrics.jsonl).

  results_md.py <measure_dir> <out_md>

Per task, shows baseline vs optimized reward, latency (both runs), and cost — the
recorded baseline metrics the CI compares against.
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


def fnum(v, unit=""):
    if v is None:
        return "—"
    return (f"${v:.4f}" if unit == "$" else f"{v:.2f}{unit}")


def main(argv):
    measure, out = Path(argv[1]), Path(argv[2])
    runs = load_runs(measure)
    lines = [
        "# Benchmark suite — baseline metrics (2× measurement)",
        "",
        (
            "Agent `aws/gpt-oss-120b` · optimizer Claude Code `claude-opus-4-8` · 1 iteration · "
            "baselines frozen & reused (baseline agent never re-run in CI). Measured twice on "
            "skillberry-1 (self-hosted, IBM VPC). All tasks are **hard** (baseline reward 0; no "
            "natural 0→1 flip exists at this budget — see README). Latency is wall-time and "
            "host-dependent; cost/tokens are host-independent (tau2/skillsbench runners report 0)."
        ),
        "",
        "| bench | task | reward base→opt | latency base (s) | latency opt r1/r2 (s) | runner cost base→opt | optimizer $ r1/r2 |",
        "|---|---|:--:|---|---|---|---|",
    ]
    for (bench, task) in sorted(runs):
        r1 = runs[(bench, task)].get("run1", {})
        r2 = runs[(bench, task)].get("run2", {})
        base_reward = r1.get("reward_baseline")
        opt_reward = f"{fnum(r1.get('reward_opt'))}/{fnum(r2.get('reward_opt'))}"
        lat_base = fnum(r1.get("latency_baseline_s"))
        lat_opt = f"{fnum(r1.get('latency_opt_s'))}/{fnum(r2.get('latency_opt_s'))}"
        cost = f"{fnum(r1.get('cost_baseline_usd'),'$')}→{fnum(r1.get('cost_opt_runner_usd'),'$')}"
        opt_usd = f"{fnum(r1.get('optimizer_usd'),'$')}/{fnum(r2.get('optimizer_usd'),'$')}"
        lines.append(
            f"| {bench} | `{task}` | {fnum(base_reward)}→{opt_reward} | {lat_base} | {lat_opt} | {cost} | {opt_usd} |"
        )
    lines.append("")
    lines.append("`reward base→opt` = frozen baseline reward → optimized test reward (run1/run2). "
                 "A stable `0→0/0` is the expected hard-task signal; the CI gates on non-regression.")
    out.write_text("\n".join(lines) + "\n")
    print(out.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
