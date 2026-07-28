#!/usr/bin/env python3
"""Build the suite report for a run_suite.sh run: reward (base->opt) per task, a
per-iteration latency/cost timeline, and a suite rollup — rendered as Markdown and
optionally written to metrics.jsonl / steps.jsonl.

Usage:
  metrics.py suite <run_dir> [--bench B] [--tier T] [--agent A] [--optimizer-model M]
                    [--iters N] [--jsonl PATH] [--steps-jsonl PATH]

Baseline/optimized reward comes from the run's baseline.json (val) and final.json
(test). Because run_suite.sh pins train==val==test, this is a TRAIN-FIT metric (the
same task set scored before/after), not a generalization/held-out claim.

Latency/cost are NOT meaningful per task in a whole-suite optimization (every task is
scored in the same eval call) — they're reported per SUITE ITERATION instead, read from
the run's events.jsonl (one "step" event per hill-climb iteration, plus the baseline
and finalize evaluate events). Latency is wall-time, shown as minutes+seconds; it is
hardware-dependent (a local run vs a self-hosted CI run are not directly comparable).
Cost/tokens are hardware-independent but some runners (tau2, skillsbench) do not
surface usage, so cost may read 0 there.
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


def _fmt(v, unit=""):
    if v is None:
        return "—"
    if isinstance(v, float):
        return (f"{v:.3f}" if unit != "$" else f"${v:.4f}") + (unit if unit != "$" else "")
    return f"{v}{unit}"


def _fmt_duration(v) -> str:
    """Wall-time seconds as minutes+seconds (e.g. 14m48s), or plain seconds under a minute."""
    if v is None:
        return "—"
    total = int(round(float(v)))
    m, s = divmod(total, 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


def _infra_task(pt: dict) -> bool:
    """True if this task's reward≈0 is an infrastructure error (majority trials errored
    with mean≈0), not a real capability result — so it can be flagged, not counted as 0."""
    raw = pt.get("raw") or {}
    if not raw.get("errored"):
        return False
    if float(pt.get("reward", 0) or 0) > 1e-9:
        return False
    et, nt = raw.get("errored_trials"), (raw.get("n_trials") or pt.get("n"))
    if et is not None and nt:
        return int(et) * 2 > int(nt)
    return True


def iteration_rows(run_dir: str, best_id: str | None = None) -> list[dict]:
    """Per-iteration latency/cost timeline for ONE run, built from events.jsonl.

    Phases, in the order they occur: ``baseline`` (seed val eval) -> ``iterate`` (one
    row per hill-climb "step", accepted or rejected) -> ``finalize`` (best-on-test eval)
    -> ``finalize_baseline`` (optional seed-on-test eval, only logged when the best
    candidate isn't the seed). No optimizer call happens outside "iterate" rows, so
    their optimizer_usd/optimizer_seconds are 0.0. ``best_id`` labels the ``finalize``
    row's candidate (the "evaluate" event itself only carries a fixed tag, not the
    actual candidate id — the caller already knows it from state.json).
    """
    events_path = Path(run_dir) / "events.jsonl"
    rows: list[dict] = []
    if not events_path.exists():
        return rows
    seen_baseline = False
    it = 0
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        kind = ev.get("kind")
        if kind == "evaluate" and ev.get("tag") == "seed" and ev.get("split") == "val" and not seen_baseline:
            seen_baseline = True
            rows.append({
                "phase": "baseline", "iter": None, "candidate": "seed", "accepted": None,
                "reward": ev.get("reward"),
                "optimizer_usd": 0.0, "optimizer_seconds": 0.0,
                "eval_usd": ev.get("cost_usd"), "eval_seconds": ev.get("seconds"),
            })
        elif kind == "step":
            it += 1
            rows.append({
                "phase": "iterate", "iter": it, "candidate": ev.get("candidate"),
                "accepted": ev.get("accept"), "reward": ev.get("val"),
                "optimizer_usd": round(ev.get("opt_cost_usd") or 0.0, 6),
                "optimizer_seconds": ev.get("optimizer_seconds"),
                "eval_usd": ev.get("cost_usd"), "eval_seconds": ev.get("runner_seconds"),
            })
        elif kind == "evaluate" and ev.get("tag") == "FINAL" and ev.get("split") == "test":
            rows.append({
                "phase": "finalize", "iter": None, "candidate": best_id, "accepted": None,
                "reward": ev.get("reward"),
                "optimizer_usd": 0.0, "optimizer_seconds": 0.0,
                "eval_usd": ev.get("cost_usd"), "eval_seconds": ev.get("seconds"),
            })
        elif kind == "evaluate" and ev.get("tag") == "FINAL_seed" and ev.get("split") == "test":
            rows.append({
                "phase": "finalize_baseline", "iter": None, "candidate": "seed", "accepted": None,
                "reward": ev.get("reward"),
                "optimizer_usd": 0.0, "optimizer_seconds": 0.0,
                "eval_usd": ev.get("cost_usd"), "eval_seconds": ev.get("seconds"),
            })
    return rows


def suite_report(run_dir: str, bench: str, tier: str, agent: str, iters, jsonl_path: str = "",
                  steps_jsonl_path: str = "", optimizer_model: str = "aws/claude-opus-4-8") -> str:
    """Render the per-task + per-iteration + suite-rollup report for ONE run_suite.sh
    run (all of a tier's tasks optimized together, no-holdout FIT: train==val==test).

    Per-task base→opt come from the run's per_task arrays: baseline from ``baseline.json``
    (val) and optimized from ``final.json`` (test), which — because the split is no-holdout —
    are the same task set scored before/after. This is a TRAIN-FIT metric, labelled as such.
    """
    rd = Path(run_dir)
    baseline = _load(rd / "baseline.json")
    final = _load(rd / "final.json")
    state = _load(rd / "state.json")
    spent = state.get("spent", {})
    best_id = state.get("best_id", "seed")

    bval = baseline.get("val") or {}
    ftest = final.get("test") or {}
    base_pt = {p["task_id"]: p for p in (bval.get("per_task") or [])}
    opt_pt = {p["task_id"]: p for p in (ftest.get("per_task") or [])}
    task_ids = list(base_pt) or list(opt_pt)

    rows = []
    for tid in task_ids:
        b, o = base_pt.get(tid, {}), opt_pt.get(tid, {})
        rb = b.get("reward")
        ro = o.get("reward")
        infra = _infra_task(o) or _infra_task(b)
        rows.append({
            "bench": bench, "tier": tier, "task": tid,
            "reward_baseline": rb, "reward_opt": ro,
            "reward_delta": (round(ro - rb, 6) if isinstance(rb, (int, float)) and isinstance(ro, (int, float)) and not infra else None),
            "opt_infra": infra,
            "run_dir": str(rd),
        })
    if jsonl_path:
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    steps = iteration_rows(str(rd), best_id=best_id)
    if steps_jsonl_path:
        with open(steps_jsonl_path, "w", encoding="utf-8") as f:
            for s in steps:
                f.write(json.dumps(s) + "\n")

    # ---- render: per-task reward table ----
    out = [f"## {tier.capitalize()} suite — {bench}  (train-fit, no holdout)", ""]
    out.append(f"Agent `{agent}` · optimizer Claude Code `{optimizer_model}` · {iters} iteration(s) · "
               f"**all {len(task_ids)} tasks optimized together** · `train==val==test` (FIT metric, "
               "not a generalization/held-out claim).")
    out.append("")
    out.append("| bench | task | reward (base→opt) | Δ | note |")
    out.append("|---|---|---|---|:--:|")
    real = []
    infra_n = 0
    for r in rows:
        if r["opt_infra"]:
            infra_n += 1
            out.append(f"| {bench} | `{r['task']}` | {_fmt(r['reward_baseline'])} → ⚠️ infra-error | — | ⚠️ |")
            continue
        real.append(r)
        d = r["reward_delta"]
        dtxt = (f"{d:+.3f}" if isinstance(d, (int, float)) else "—")
        note = "↓" if isinstance(d, (int, float)) and d < 0 else ""
        out.append(f"| {bench} | `{r['task']}` | {_fmt(r['reward_baseline'])} → {_fmt(r['reward_opt'])} | {dtxt} | {note} |")

    # Suite headline = the run's aggregate reward (baseline val → optimized test).
    agg_b, agg_o = bval.get("reward"), ftest.get("reward")
    accepted = "seed (no candidate beat baseline)" if best_id in ("seed", "", None) else f"`{best_id}`"
    out.append("")
    if isinstance(agg_b, (int, float)) and isinstance(agg_o, (int, float)):
        rel = f" ({(agg_o-agg_b)/agg_b*100:+.0f}% rel)" if agg_b else ""
        out.append(f"**Suite (train-fit):** mean reward {agg_b:.3f} → {agg_o:.3f} "
                   f"(Δ {agg_o-agg_b:+.3f}{rel}) · best = {accepted} · "
                   f"optimizer ${spent.get('optimizer_usd',0) or 0:.2f} over {spent.get('iterations','?')} iter(s)"
                   + (f" · {infra_n} task(s) infra-errored" if infra_n else ""))
    elif infra_n:
        out.append(f"**Suite:** ⚠️ {infra_n}/{len(rows)} tasks infra-errored (gateway/runtime) — "
                   "no valid result. Check the model gateway (budget/429).")
    else:
        out.append("**Suite:** (no aggregate reward — run may have failed; check logs.)")

    # ---- render: per-iteration latency/cost timeline ----
    out.append("")
    out.append("### Iterations")
    out.append("")
    if not steps:
        out.append("(no iteration events found — run may have failed before logging any.)")
    else:
        out.append("| phase | iter | candidate | accepted | reward | optimizer $ | optimizer time | eval $ | eval time |")
        out.append("|---|:--:|---|:--:|---|---|---|---|---|")
        opt_usd_t = opt_s_t = eval_usd_t = eval_s_t = 0.0
        for s in steps:
            acc = "—" if s["accepted"] is None else ("✅" if s["accepted"] else "❌")
            out.append(f"| {s['phase']} | {s['iter'] if s['iter'] is not None else '—'} | "
                       f"`{s['candidate']}` | {acc} | {_fmt(s['reward'])} | "
                       f"{_fmt(s['optimizer_usd'], '$')} | {_fmt_duration(s['optimizer_seconds'])} | "
                       f"{_fmt(s['eval_usd'], '$')} | {_fmt_duration(s['eval_seconds'])} |")
            opt_usd_t += s["optimizer_usd"] or 0
            opt_s_t += s["optimizer_seconds"] or 0
            eval_usd_t += s["eval_usd"] or 0
            eval_s_t += s["eval_seconds"] or 0
        out.append("")
        out.append(f"**Totals:** optimizer ${opt_usd_t:.4f} over {_fmt_duration(opt_s_t)} · "
                   f"eval ${eval_usd_t:.4f} over {_fmt_duration(eval_s_t)}")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "suite":
        args = argv[2:]
        rd = args[0]
        opt = {"bench": "", "tier": "smoke", "agent": "aws/gpt-oss-120b", "iters": "3",
               "jsonl": "", "steps-jsonl": "", "optimizer-model": "aws/claude-opus-4-8"}
        for i, a in enumerate(args):
            for k in ("bench", "tier", "agent", "iters", "jsonl", "steps-jsonl", "optimizer-model"):
                if a == f"--{k}" and i + 1 < len(args):
                    opt[k] = args[i + 1]
        print(suite_report(rd, opt["bench"], opt["tier"], opt["agent"], opt["iters"],
                           opt["jsonl"], opt["steps-jsonl"], opt["optimizer-model"]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
