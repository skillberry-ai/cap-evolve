#!/usr/bin/env python3
"""Extract reward / latency / cost from a cap-evolve run dir and render a report.

The baseline columns come from the run's ``baseline.json`` — which, for an
``optimize`` run, is the *frozen* baseline copied in by ``--reuse-baseline`` (so we
report against the recorded baseline without re-running the baseline agent). The
optimized columns come from ``final.json`` (sealed test) + ``state.json`` spend.

Usage:
  metrics.py extract <run_dir> [--bench B] [--task T]      # -> one JSON object (stdout)
  metrics.py table   <metrics.jsonl>                        # -> Markdown table (stdout)

Latency is wall-time seconds of the eval; it is hardware-dependent (a local baseline
vs a self-hosted CI run are not directly comparable). Cost/tokens are hardware-independent
but some runners (tau2, skillsbench) do not surface usage, so cost may read 0 there.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def extract(run_dir: str, bench: str = "", task: str = "") -> dict:
    rd = Path(run_dir)
    baseline = _load(rd / "baseline.json")
    final = _load(rd / "final.json")
    state = _load(rd / "state.json")
    spent = state.get("spent", {})

    bval = (baseline.get("val") or {})
    reward_baseline = bval.get("reward")
    latency_baseline_s = bval.get("seconds")
    cost_baseline_usd = bval.get("cost_usd")

    test = (final.get("test") or {})
    reward_opt = test.get("reward")
    latency_opt_s = test.get("seconds")
    cost_opt_runner_usd = test.get("cost_usd")

    def _d(a, b):
        return round(a - b, 6) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None

    return {
        "bench": bench,
        "task": task,
        "reward_baseline": reward_baseline,
        "reward_opt": reward_opt,
        "reward_delta": _d(reward_opt, reward_baseline),
        "flipped": bool(reward_baseline == 0 and (reward_opt or 0) > 0),
        "latency_baseline_s": latency_baseline_s,
        "latency_opt_s": latency_opt_s,
        "cost_baseline_usd": cost_baseline_usd,
        "cost_opt_runner_usd": cost_opt_runner_usd,
        "optimizer_usd": spent.get("optimizer_usd"),
        "optimizer_tokens": spent.get("optimizer_tokens"),
        "optimizer_seconds": spent.get("optimizer_seconds"),
        "iterations": spent.get("iterations"),
        "run_dir": str(rd),
    }


def _fmt(v, unit=""):
    if v is None:
        return "—"
    if isinstance(v, float):
        return (f"{v:.3f}" if unit != "$" else f"${v:.4f}") + (unit if unit != "$" else "")
    return f"{v}{unit}"


def table(rows: list[dict]) -> str:
    hdr = ("| bench | task | reward (base→opt) | flip | latency base→opt (s) | "
           "runner cost base→opt | optimizer $ | iters |")
    sep = "|---|---|---|:--:|---|---|---|:--:|"
    out = [hdr, sep]
    for r in rows:
        reward = f"{_fmt(r['reward_baseline'])} → {_fmt(r['reward_opt'])}"
        flip = "✅" if r.get("flipped") else ("—" if (r.get("reward_opt") or 0) == 0 else "")
        lat = f"{_fmt(r['latency_baseline_s'])} → {_fmt(r['latency_opt_s'])}"
        cost = f"{_fmt(r['cost_baseline_usd'],'$')} → {_fmt(r['cost_opt_runner_usd'],'$')}"
        out.append(
            f"| {r['bench']} | `{r['task']}` | {reward} | {flip} | {lat} | {cost} | "
            f"{_fmt(r['optimizer_usd'],'$')} | {_fmt(r['iterations'])} |"
        )
    # suite rollup
    rew_b = [r['reward_baseline'] for r in rows if isinstance(r['reward_baseline'], (int, float))]
    rew_o = [r['reward_opt'] for r in rows if isinstance(r['reward_opt'], (int, float))]
    flips = sum(1 for r in rows if r.get("flipped"))
    opt_usd = sum(r['optimizer_usd'] or 0 for r in rows)
    if rew_b and rew_o:
        out.append("")
        out.append(f"**Suite:** mean reward {sum(rew_b)/len(rew_b):.3f} → "
                   f"{sum(rew_o)/len(rew_o):.3f} · flips {flips}/{len(rows)} · "
                   f"optimizer ${opt_usd:.4f}")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "extract":
        bench = task = ""
        args = argv[2:]
        rd = args[0]
        for i, a in enumerate(args):
            if a == "--bench" and i + 1 < len(args):
                bench = args[i + 1]
            if a == "--task" and i + 1 < len(args):
                task = args[i + 1]
        print(json.dumps(extract(rd, bench, task)))
        return 0
    if len(argv) >= 3 and argv[1] == "table":
        rows = [json.loads(l) for l in Path(argv[2]).read_text().splitlines() if l.strip()]
        print(table(rows))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
