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


def _infra_dominated(agg: dict) -> bool:
    """True if this eval's reward≈0 is due to INFRASTRUCTURE errors, not capability.

    Mirrors the core's ``_is_infra_ignore``: a task counts as infra only when a
    MAJORITY of its trials errored AND its mean reward ≈ 0 (a partly-passing task is
    controllable and protected). The eval is infra-DOMINATED when a majority of its
    tasks are infra — e.g. a gateway 429 budget_exceeded kills every rollout, so the
    whole eval reads 0.000. Distinguishing this from a real regression keeps a billing
    outage from looking like a capability drop in the report.
    """
    per = agg.get("per_task") or []
    if not per:
        return False
    eps = 1e-9
    infra = 0
    for pt in per:
        raw = pt.get("raw") or {}
        if not raw.get("errored"):
            continue
        if float(pt.get("reward", 0) or 0) > eps:
            continue  # partially passed → controllable, not infra
        et, nt = raw.get("errored_trials"), (raw.get("n_trials") or pt.get("n"))
        if et is not None and nt:
            if int(et) * 2 > int(nt):
                infra += 1
        else:
            infra += 1  # no per-trial counts: any-trial-errored + mean≈0
    return infra > 0 and infra * 2 >= len(per)


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

    # Infra-error detection: a gateway outage (e.g. 429 budget_exceeded) makes every
    # rollout die with INFRASTRUCTURE_ERROR and the eval read 0.000 — NOT a real
    # regression. Flag it so the table/rollup can exclude it instead of counting it.
    opt_infra = _infra_dominated(test)
    baseline_infra = _infra_dominated(bval)

    def _d(a, b):
        return round(a - b, 6) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None

    return {
        "bench": bench,
        "task": task,
        "reward_baseline": reward_baseline,
        "reward_opt": reward_opt,
        "reward_delta": None if (opt_infra or baseline_infra) else _d(reward_opt, reward_baseline),
        # a flip only counts on real evals — never credit/penalize an infra-errored one
        "flipped": bool(reward_baseline == 0 and (reward_opt or 0) > 0
                        and not opt_infra and not baseline_infra),
        "opt_infra": opt_infra,
        "baseline_infra": baseline_infra,
        "latency_baseline_s": latency_baseline_s,
        "latency_opt_s": latency_opt_s,
        "cost_baseline_usd": cost_baseline_usd,
        "cost_opt_runner_usd": cost_opt_runner_usd,
        # total RUNNER (evaluation) spend across ALL rollouts (baseline + every
        # optimize iteration + finalize) — the cost of running the benchmark itself,
        # distinct from the optimizer's own spend. 0 when the runner/gateway does not
        # surface usage (tau2/skillsbench via the gateway); non-zero for swebench (litellm).
        "eval_usd": spent.get("usd"),
        "eval_tokens": spent.get("runner_tokens"),
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
        infra = r.get("opt_infra") or r.get("baseline_infra")
        if infra:
            # Gateway/infra outage — reward≈0 is noise, not a result. Say so explicitly.
            reward = f"{_fmt(r['reward_baseline'])} → ⚠️ infra-error"
            flip = "⚠️"
        else:
            reward = f"{_fmt(r['reward_baseline'])} → {_fmt(r['reward_opt'])}"
            flip = "✅" if r.get("flipped") else ("—" if (r.get("reward_opt") or 0) == 0 else "")
        lat = f"{_fmt(r['latency_baseline_s'])} → {_fmt(r['latency_opt_s'])}"
        cost = f"{_fmt(r['cost_baseline_usd'],'$')} → {_fmt(r['cost_opt_runner_usd'],'$')}"
        out.append(
            f"| {r['bench']} | `{r['task']}` | {reward} | {flip} | {lat} | {cost} | "
            f"{_fmt(r['optimizer_usd'],'$')} | {_fmt(r['iterations'])} |"
        )
    # suite rollup — EXCLUDE infra-errored evals from the mean + flip counts so a
    # gateway outage can't masquerade as a regression (or a win).
    real = [r for r in rows if not (r.get("opt_infra") or r.get("baseline_infra"))]
    infra_n = len(rows) - len(real)
    rew_b = [r['reward_baseline'] for r in real if isinstance(r['reward_baseline'], (int, float))]
    rew_o = [r['reward_opt'] for r in real if isinstance(r['reward_opt'], (int, float))]
    flips = sum(1 for r in real if r.get("flipped"))
    opt_usd = sum(r['optimizer_usd'] or 0 for r in rows)
    if rew_b and rew_o:
        out.append("")
        suffix = f" · {infra_n} infra-errored (excluded)" if infra_n else ""
        out.append(f"**Suite:** mean reward {sum(rew_b)/len(rew_b):.3f} → "
                   f"{sum(rew_o)/len(rew_o):.3f} · flips {flips}/{len(real)} · "
                   f"optimizer ${opt_usd:.4f}{suffix}")
    elif infra_n:
        out.append("")
        out.append(f"**Suite:** ⚠️ all {infra_n} eval(s) infra-errored (gateway/runtime "
                   "outage) — no valid optimized result. Check the model gateway (budget/429).")
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
