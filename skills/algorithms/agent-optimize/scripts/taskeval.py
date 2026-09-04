"""Evaluate ONE candidate on a NAMED SUBSET of tasks, with traces. The per-task gradient.

Why this exists. A full-val gate round costs ``val_n * n_trials`` rollouts and returns one bit
per candidate — accept or reject. One task at ``n_trials`` costs ``n_trials`` rollouts and
returns the same bit about the failure that actually exists. At 30 tasks x 10 trials that is
300 rollouts per learning step versus 10, and the defect lives in the task, not in the mean.

The cost is overfitting, and it is real: an edit tuned on one task can break another. That is
what ``--canary`` is for (tasks measured 1.0 at baseline, evaluated in the same call), and why
nothing measured here is evidence until the merged artifact clears a full-val gate against
``ctl_null``. A per-task rate is a TRAINING number — the optimiser tuned on it.

    python taskeval.py --project <dir> <candidate_dir> 7,17 --n 10 \
        --canary 0,3,12 --canary-n 3 --traces /tmp/tr.json [--split val] [--conc 40]

Prints per-task pass RATE (k/n), the distinct failure feedback strings, and with --traces every
agent tool call per failing trial, so the next edit is aimed at an observed decision rather than
a guess. For an UNSTABLE task, diff a failing trial against a passing one: the divergence point
is the ambiguity.
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path


def component_rates(score, rollout) -> dict:
    """Per-component sub-scores for one rollout, WITHOUT knowing the benchmark.

    Why this is not just ``metadata["<domain>_reward_info"]``: a binary task reward collapses
    "got the database right but missed a required confirmation" and "did nothing" into the same
    0.0, and the per-component means are what separate them. That signal is worth having on every
    benchmark, so the lookup has to be generic.

    Resolution order, first hit wins:
      1. ``Score.raw`` — the adapter's own structured payload, checked under the conventional
         breakdown keys. This is the documented place for it.
      2. ``Score.metrics`` — a list of ``{"name": ..., "value": ...}`` entries.
      3. ``Rollout.metadata`` — any dict-valued key ending in ``_reward_info`` or ``_score_info``
         that itself carries a breakdown. This is the escape hatch for adapters that stash the
         runner's native structure without mapping it, and it is why no benchmark name appears here.

    Returns ``{}`` when nothing is exposed, which is a normal answer, not an error: a scorer with
    one scalar reward has no components and per-task rates remain fully usable without them.
    """
    BREAKDOWN_KEYS = ("reward_breakdown", "component_rates", "components", "breakdown", "subscores")

    def _numeric(d):
        return {str(k): float(v) for k, v in d.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)}

    raw = getattr(score, "raw", None) or {}
    if isinstance(raw, dict):
        for key in BREAKDOWN_KEYS:
            got = raw.get(key)
            if isinstance(got, dict) and _numeric(got):
                return _numeric(got)

    metrics = getattr(score, "metrics", None) or []
    named = {str(m.get("name")): float(m.get("value"))
             for m in metrics
             if isinstance(m, dict) and m.get("name") is not None
             and isinstance(m.get("value"), (int, float)) and not isinstance(m.get("value"), bool)}
    if named:
        return named

    meta = getattr(rollout, "metadata", None) or {}
    if isinstance(meta, dict):
        for k, v in meta.items():
            if not (isinstance(k, str) and (k.endswith("_reward_info") or k.endswith("_score_info"))):
                continue
            if not isinstance(v, dict):
                continue
            for key in BREAKDOWN_KEYS:
                got = v.get(key)
                if isinstance(got, dict) and _numeric(got):
                    return _numeric(got)
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate_dir")
    ap.add_argument("tasks", help="comma-separated task ids to optimise")
    ap.add_argument("--project", required=True, help="cap-evolve project dir (holds adapters/)")
    ap.add_argument("--split", default="val")
    ap.add_argument("--n", type=int, default=10, help="trials per target task")
    ap.add_argument("--canary", default="", help="comma-separated ids measured 1.0 at baseline")
    ap.add_argument("--canary-n", type=int, default=3)
    ap.add_argument("--conc", type=int, default=0,
                    help="rollout concurrency, if >0. Exported as CAPEVOLVE_MAX_CONCURRENCY (the "
                         "canonical name every adapter should read) AND as any extra names given "
                         "by --conc-env, for runners whose knob predates that convention.")
    ap.add_argument("--conc-env", default="",
                    help="comma-separated EXTRA env var names to set to --conc, e.g. "
                         "the runner's own knob. The canonical CAPEVOLVE_MAX_CONCURRENCY is always "
                         "set, so this is only needed for an adapter that does not read it yet.")
    ap.add_argument("--traces", default="", help="write per-trial agent tool calls here")
    ap.add_argument("--json", dest="json_out", default="")
    ap.add_argument("--run-dir", default="",
                    help="charge these rollouts to the run's budget ledger (strongly advised: "
                         "a fan-out of K optimisers x M iterations is the bulk of a round's "
                         "real spend, and a budget that cannot see it is not a budget)")
    args = ap.parse_args()

    proj = Path(args.project).resolve()
    sys.path.insert(0, str(proj / "adapters"))
    if args.conc > 0:
        # The concurrency knob is named per RUNNER, so the skill cannot hardcode one benchmark's
        # variable and still be general. Canonical name always; extra aliases on request.
        os.environ["CAPEVOLVE_MAX_CONCURRENCY"] = str(args.conc)
        for name in [n.strip() for n in args.conc_env.split(",") if n.strip()]:
            os.environ[name] = str(args.conc)

    from cap_evolve.check import load_adapter

    adapter = load_adapter(proj)
    cand = Path(args.candidate_dir).resolve()

    want = [t.strip() for t in args.tasks.split(",") if t.strip()]
    canary = [t.strip() for t in args.canary.split(",") if t.strip()]
    by_id = {t.id: t for t in adapter.tasks(args.split)}
    missing = [t for t in want + canary if t not in by_id]
    if missing:
        print(f"unknown task ids in split {args.split!r}: {missing}", file=sys.stderr)
        return 2
    if not canary:
        print("WARNING: no --canary. A per-task edit that breaks a working task will not be "
              "visible until the full-val gate.", file=sys.stderr)

    groups = [(want, args.n, "target")]
    if canary:
        groups.append((canary, args.canary_n, "canary"))

    rates: dict[str, list[float]] = defaultdict(list)
    role: dict[str, str] = {}
    fb: dict[str, list[str]] = defaultdict(list)
    traces: list[dict] = []
    infra: dict[str, int] = defaultdict(int)
    comps: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list))
    t0 = time.time()

    # `adapter.live(cand)` is the documented contract `run_target`'s docstring points to
    # ("ctx is whatever live() yielded (default: the candidate dir Path)") — NOT
    # `adapter.materialize(cand)`, whose default implementation writes `edits` (there are
    # none here) and returns None. Calling it directly silently made `ctx` None for every
    # adapter using the standard materialize/live split, so every rollout below raised
    # inside run_trials_pool and was counted as an infra drop rather than scored — the
    # reason this script, like integrate.py which calls it, was measured (#434/#438) to
    # have never actually produced a per-task result on a real run.
    with adapter.live(cand) as ctx:
        for ids, n, kind in groups:
            tasks = [by_id[i] for i in ids]
            for i in ids:
                role[i] = kind
            out = adapter.run_trials(tasks, ctx, n_trials=n, base_seed=0)
            for tid, rolls in sorted(out.items()):
                for k, roll in enumerate(rolls or []):
                    if roll is None or getattr(roll, "error", None):
                        infra[tid] += 1          # missing data, NOT a zero
                        continue
                    s = adapter.score(by_id[tid], roll)
                    rates[tid].append(float(s.reward))
                    for comp, v in component_rates(s, roll).items():
                        comps[tid][comp].append(v)
                    if s.reward < 1.0:
                        if s.feedback:
                            fb[tid].append(s.feedback)
                        if args.traces:
                            traces.append({
                                "task": tid, "trial": k, "reward": s.reward,
                                "feedback": s.feedback,
                                "tool_calls": [
                                    {"name": c.get("name"), "arguments": c.get("arguments")}
                                    for c in (getattr(roll, "tool_calls", None) or [])
                                ],
                                "trace": [
                                    {"role": m.get("role"),
                                     "content": str(m.get("content") or "")[:900]}
                                    for m in (getattr(roll, "trace", None) or [])
                                ],
                            })

    per_task = {
        tid: {
            "role": role[tid],
            "rate": round(sum(v) / len(v), 3) if v else None,
            "trials": len(v),
            "infra_dropped": infra.get(tid, 0),
            # Partial credit, when the scorer exposes any (see component_rates). A BINARY task
            # reward collapses "satisfied most of the contract" and "did nothing" into the same
            # 0.0; per-component means separate them, which is the difference between one
            # actionable number and thirty useless ones. Empty when the scorer has no components.
            "component_rates": {c: round(sum(v) / len(v), 3)
                                for c, v in sorted(comps[tid].items()) if v},
            "distinct_feedback": sorted({f for f in fb[tid]})[:4],
        }
        for tid, v in sorted(rates.items(), key=lambda kv: (role[kv[0]], kv[0]))
    }
    tgt = [v["rate"] for v in per_task.values() if v["role"] == "target" and v["rate"] is not None]
    can = [v["rate"] for v in per_task.values() if v["role"] == "canary" and v["rate"] is not None]
    result = {
        "candidate": str(cand),
        "wall_seconds": round(time.time() - t0, 1),
        "target_mean": round(sum(tgt) / len(tgt), 3) if tgt else None,
        "canary_mean": round(sum(can) / len(can), 3) if can else None,
        "reminder": "target_mean is a TRAINING number; only the full-val gate is evidence",
        "per_task": per_task,
    }
    if args.traces:
        Path(args.traces).write_text(json.dumps(traces, indent=2))
        result["traces_written"] = f"{args.traces} ({len(traces)} failing trials)"
    charged = sum(len(v) for v in rates.values()) + sum(infra.values())
    result["rollouts_spent"] = charged
    if args.run_dir:
        from cap_evolve import RunDir

        rd = RunDir.open(Path(args.run_dir))
        rd.update_spent(metric_calls=charged)
        result["charged_to_budget"] = str(Path(args.run_dir))
    else:
        result["charged_to_budget"] = None
        print(f"NOTE: {charged} rollouts NOT charged to any budget (no --run-dir)",
              file=sys.stderr)

    text = json.dumps(result, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
