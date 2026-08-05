#!/usr/bin/env python3
"""summarize_run.py — condense one cap-evolve run dir into a portable summary.

Usage:
    summarize_run.py <run_dir> [--bench BENCH] [--agent MODEL] [--optimizer MODEL]

Reads a cap-evolve run directory (contains baseline.json / final.json / events.jsonl
/ rollouts/) and writes two portable summaries next to those files:

  SUMMARY.md    — one-page human-readable, matches docs/RESULTS.md section style
  summary.json  — machine-readable, matches site/benchmarks.fixture.json schema=1

Idempotent; safe to rerun on the same dir. Defaults extract MODEL/AGENT from the
associated capevolve.yaml + adapter, but CLI flags override.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys
from pathlib import Path


def _load(path: Path, default=None):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _iter_events(events_jsonl: Path):
    if not events_jsonl.is_file():
        return
    for line in events_jsonl.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except Exception:
            continue


def summarize(run_dir: Path, bench: str, agent_model: str, optimizer_model: str) -> dict:
    """Extract the canonical fields from one run dir."""
    baseline = _load(run_dir / "baseline.json", {}) or {}
    final = _load(run_dir / "final.json", {}) or {}
    state = _load(run_dir / "state.json", {}) or {}
    events = list(_iter_events(run_dir / "events.jsonl"))

    # final.json wraps results per-split (e.g. {"test": {reward, per_task, ...}}).
    # The finalize EVENT (in events.jsonl) has flat top-level test_reward/test_delta.
    # Prefer `finalize_patched` if present (manual splice supersedes the original).
    final_test_block = (final or {}).get("test") or {}
    final_headline = {}
    for e in events:
        if e.get("kind") == "finalize":
            final_headline = e
    for e in events:
        if e.get("kind") == "finalize_patched":
            final_headline = e  # overrides finalize when present

    # Build a per-iteration timeline from evaluate + step events. For optimization
    # runs, the HEADLINE metrics should reflect the BEST candidate — not the seed.
    per_iter_val = {}       # candidate_id -> {reward, stderr}
    steps: list[dict] = []
    for e in events:
        if e.get("kind") == "evaluate" and e.get("split") == "val":
            per_iter_val[e.get("tag") or "seed"] = {
                "reward": e.get("reward"),
                "stderr": e.get("stderr"),
                "seconds": e.get("seconds"),
            }
        elif e.get("kind") == "step":
            steps.append({
                "candidate": e.get("candidate"),
                "parent": e.get("parent"),
                "parent_val": e.get("parent_val"),
                "val": e.get("val"),
                "accepted": e.get("accept"),
                "reason": e.get("reason"),
                "optimizer_seconds": e.get("optimizer_seconds"),
                "runner_seconds": e.get("runner_seconds"),
                "optimizer_usd": e.get("opt_cost_usd"),
                "optimizer_tokens": e.get("opt_tokens"),
            })

    best_id = final_headline.get("best_id") or state.get("best_id") or "seed"

    # For OPTIMIZATION runs, prefer the best candidate's per-task rollouts if we have them;
    # otherwise (baseline-only runs) fall back to baseline.json's per_task.
    import glob
    per_task = baseline.get("val", {}).get("per_task") or []
    if best_id != "seed":
        # Re-derive per-task list from rollouts/val/*__<best_id>__t0.json
        rollout_files = sorted(glob.glob(str(run_dir / "rollouts" / "val" / f"*__{best_id}__t*.json")))
        if rollout_files:
            per_task = []
            for f in rollout_files:
                try:
                    d = json.loads(Path(f).read_text())
                except Exception:
                    continue
                score = d.get("score") or {}
                rollout = d.get("rollout") or {}
                per_task.append({
                    "task_id": d.get("input"),
                    "reward": score.get("reward"),
                    "feedback": score.get("feedback"),
                    "raw": {"errored_trials": 1 if rollout.get("error") else 0, "n_trials": 1},
                })

    val_block = per_iter_val.get(best_id) or baseline.get("val") or {}

    # Aggregate per-task stats
    passed, partial, errored, failed = [], [], [], []
    for t in per_task:
        tid = t.get("task_id")
        r = t.get("reward")
        errs = t.get("raw", {}).get("errored_trials", 0)
        if errs and errs > 0:
            errored.append(tid)
        elif r is None:
            errored.append(tid)  # treat missing as error
        elif r >= 1.0:
            passed.append(tid)
        elif r > 0:
            partial.append({"task_id": tid, "reward": r})
        else:
            failed.append(tid)

    # Timing from events
    ts_first = ts_last = None
    val_seconds = test_seconds = None
    for e in events:
        t = e.get("t")
        if t:
            ts_first = ts_first or t
            ts_last = t
        if e.get("kind") == "evaluate":
            if e.get("split") == "val":
                val_seconds = e.get("seconds")
            elif e.get("split") == "test":
                test_seconds = e.get("seconds")

    wall_sec = int(ts_last - ts_first) if (ts_first and ts_last) else None

    # Config knobs (read from capevolve.yaml if reachable)
    project_yaml = run_dir.parent / "project" / "capevolve.yaml"
    num_trials = max_iterations = split_kind = None
    if project_yaml.is_file():
        for line in project_yaml.read_text().splitlines():
            s = line.strip()
            if s.startswith("num_trials:"):
                num_trials = int(s.split(":", 1)[1].split("#", 1)[0].strip())
            elif s.startswith("max_iterations:"):
                max_iterations = int(s.split(":", 1)[1].split("#", 1)[0].strip())

    # Split kind (fit vs held-out) inferred from split_ids.json
    split_ids_file = run_dir.parent / "project" / "split_ids.json"
    if split_ids_file.is_file():
        d = _load(split_ids_file, {}) or {}
        train, val, test = d.get("train", []), d.get("val", []), d.get("test", [])
        if set(train) == set(val) == set(test):
            split_kind = "fit-metric (train==val==test, no holdout)"
        elif set(val) & set(test):
            split_kind = f"partial holdout (val {len(val)}, test {len(test)})"
        else:
            split_kind = f"held-out (train={len(train)}, val={len(val)}, test={len(test)})"

    # Baseline (seed) val — always the reused/measured seed val
    baseline_val = per_iter_val.get("seed") or (baseline.get("val") or {})
    return {
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "bench": bench,
        "agent_model": agent_model,
        "optimizer_model": optimizer_model,
        "config": {
            "n_tasks": len(per_task),
            "num_trials": num_trials,
            "max_iterations": max_iterations,
            "split_kind": split_kind,
        },
        "val": {
            "reward": val_block.get("reward"),
            "stderr": val_block.get("stderr"),
            "pass_at_k": val_block.get("pass_at_k"),
            "n_tasks": len(per_task),
        },
        "baseline_val": {
            "reward": baseline_val.get("reward"),
            "stderr": baseline_val.get("stderr"),
        },
        "steps": steps,
        "final": {
            "best_id": final_headline.get("best_id") or state.get("best_id") or "seed",
            "test_reward": final_headline.get("test_reward") or final_test_block.get("reward"),
            "test_baseline_reward": final_headline.get("test_baseline_reward"),
            "test_delta": final_headline.get("test_delta", 0.0),
            # actual iterations from state.json (config value is the *cap*, not the count)
            "iterations": state.get("iters") or state.get("iterations") or 0,
        },
        "counts": {
            "passed": len(passed),
            "partial": len(partial),
            "errored": len(errored),
            "failed": len(failed),
        },
        "passed": sorted(passed),
        "partial": sorted(partial, key=lambda x: -x["reward"]),
        "errored": sorted(errored),
        "timing": {
            "val_seconds": val_seconds,
            "test_seconds": test_seconds,
            "wall_seconds": wall_sec,
        },
    }


def to_markdown(summary: dict) -> str:
    """Render SUMMARY.md — matches the docs/RESULTS.md section style."""
    s = summary
    c = s["config"]
    v = s["val"]
    f = s["final"]
    cnt = s["counts"]

    def fmt_sec(x):
        return f"{int(x//60)}m {int(x%60)}s" if x else "—"

    def fmt_reward(x):
        return f"{x:.4f}" if isinstance(x, (int, float)) else "—"

    reward_pct = f"{v['reward']*100:.1f}%" if v["reward"] is not None else "—"
    pass_k1 = (v.get("pass_at_k") or {}).get("1")
    pass_k1_pct = f"{pass_k1*100:.1f}%" if pass_k1 is not None else "—"

    baseline_val = s.get("baseline_val") or {}
    steps = s.get("steps") or []
    n_iter = len(steps)
    n_accepted = sum(1 for st in steps if st.get("accepted"))
    best_id = f["best_id"]

    lines = [
        f"# Run summary — `{s['run_id']}`",
        "",
        f"- **Benchmark:** `{s['bench']}`",
        f"- **Agent under test:** `{s['agent_model']}`",
        f"- **Optimizer:** `{s['optimizer_model']}`",
        f"- **Tasks / trials:** {c['n_tasks']} tasks · {c['num_trials'] or '?'} trials",
        f"- **Iterations (actual / cap):** {n_iter} / {c['max_iterations'] or 0}  ·  {n_accepted} accepted",
        f"- **Split discipline:** {c['split_kind'] or '?'}",
        f"- **Best candidate:** `{best_id}`",
        "",
        "## Headline",
        "",
        f"| | baseline (seed) | best (`{best_id}`) |",
        "|---|---|---|",
        f"| val_reward (mean) | {fmt_reward(baseline_val.get('reward'))} ± {fmt_reward(baseline_val.get('stderr'))} | **{fmt_reward(v['reward'])} ± {fmt_reward(v.get('stderr'))}** ({reward_pct}) |",
        f"| pass_at_1 (fully passing) | — | **{cnt['passed']}/{c['n_tasks']}** ({pass_k1_pct}) |",
        f"| test_reward | {fmt_reward(f.get('test_baseline_reward'))} | **{fmt_reward(f.get('test_reward'))}** |",
        f"| test_delta (best − baseline) |  | **{fmt_reward(f.get('test_delta'))}** |",
        f"| val wall-clock |  | {fmt_sec(s['timing']['val_seconds'])} |",
        f"| test wall-clock |  | {fmt_sec(s['timing']['test_seconds'])} |",
        f"| total wall-clock |  | {fmt_sec(s['timing']['wall_seconds'])} |",
        "",
    ]

    if steps:
        lines += [
            "## Iterations",
            "",
            "| iter | candidate | parent | val | Δ vs parent | accepted? |",
            "|---|---|---|---|---|---|",
        ]
        for i, st in enumerate(steps, 1):
            pv = st.get("parent_val")
            vv = st.get("val")
            delta = f"{(vv - pv):+.4f}" if pv is not None and vv is not None else "—"
            accept_glyph = "✓" if st.get("accepted") else "✗"
            lines.append(
                f"| {i} | `{st.get('candidate')}` | `{st.get('parent')}` | "
                f"{fmt_reward(vv)} | {delta} | {accept_glyph} |"
            )
        lines.append("")

    if s["passed"]:
        lines += ["## Passing tasks", "", *[f"- ✓ `{t}`" for t in s["passed"]], ""]
    if s["partial"]:
        lines += ["## Partial credit", "", "| task | reward |", "|---|---|"]
        for p in s["partial"]:
            lines.append(f"| `{p['task_id']}` | {p['reward']:.3f} |")
        lines.append("")
    if s["errored"]:
        lines += ["## Errored tasks (infra, not skill defect)", ""]
        lines += [f"- ⚠ `{t}`" for t in s["errored"]]
        lines.append("")

    # Emit RELATIVE artifact hints, not absolute paths — this file may end up
    # on a public detail page (e.g. via a `summary_url` field on a
    # benchmark-history record) and a hard-coded /Users/... path would leak
    # local layout and fail relative-link checks in CI (lychee, etc.).
    run_name = Path(s["run_dir"]).name
    lines += [
        "## Artifacts",
        "",
        f"Local run — artifacts live on the recording host under `.capevolve/{run_name}/`",
        "(gitignored, per-run). See the run dir for:",
        "",
        "- `baseline.json` — full per-task rewards",
        "- `final.json` — headline numbers",
        "- `events.jsonl` — event timeline (including any manual splice records)",
        "- `PATCH_NOTE.md` — human-readable splice documentation (when applicable)",
        f"- `rollouts/val/*.json` — per-rollout JSONs (agent transcript + CTRF)",
        "- `rollouts/test/*.json` — finalize per-rollout JSONs",
        "- `dashboard.html` — static snapshot of the run's dashboard",
        "",
    ]

    return "\n".join(lines)


def to_fixture_json(summary: dict) -> dict:
    """Render summary.json in benchmarks.fixture.json schema=1."""
    s = summary
    v = s["val"]; f = s["final"]; c = s["config"]
    return {
        "schema": 1,
        "run_id": s["run_id"],
        "run_url": None,
        "bench": s["bench"],
        "tier": "local",
        "event": "local",
        "source": "local (manual)",
        "pr": None,
        "branch": None,
        "sha": None,
        "date": dt.datetime.utcnow().isoformat() + "Z",
        "iterations": len(s.get("steps") or []),  # actual iterations completed (accept+reject)
        "max_iterations": c["max_iterations"],    # config cap
        "num_trials": c["num_trials"],
        "n_tasks": c["n_tasks"],
        "split_kind": c["split_kind"],
        "agent_model": s["agent_model"],
        "optimizer_model": s["optimizer_model"],
        "conclusion": "success" if v["reward"] is not None else "failure",
        "suite": {
            "reward_base": (s.get("baseline_val") or {}).get("reward"),
            "reward_opt": v["reward"],  # best candidate val (was: test_reward)
            "n": c["n_tasks"],
            "optimizer_usd": None,
            "eval_usd": None,
        },
        "counts": s["counts"],
        "timing_seconds": s["timing"],
        "passed_tasks": s["passed"],
        "partial_tasks": s["partial"],
        "errored_tasks": s["errored"],
        "steps": s.get("steps") or [],
        "baseline_val": s.get("baseline_val"),
    }


def main() -> int:
    p = argparse.ArgumentParser(prog="summarize_run.py")
    p.add_argument("run_dir")
    p.add_argument("--bench", default="skillsbench")
    p.add_argument("--agent", default=None, help="agent-under-test model id")
    p.add_argument("--optimizer", default=None, help="optimizer model id")
    args = p.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        print(f"error: {run_dir} is not a directory", file=sys.stderr)
        return 2

    # Defaults from adapter + capevolve.yaml if not overridden
    agent = args.agent or os.environ.get("SKILLSBENCH_MODEL", "?")
    optimizer = args.optimizer
    if optimizer is None:
        y = run_dir.parent / "project" / "capevolve.yaml"
        if y.is_file():
            for line in y.read_text().splitlines():
                if line.strip().startswith("optimizer_model:"):
                    optimizer = line.split(":", 1)[1].split("#", 1)[0].strip()
                    break
        optimizer = optimizer or "?"

    summary = summarize(run_dir, bench=args.bench, agent_model=agent, optimizer_model=optimizer)

    md_path = run_dir / "SUMMARY.md"
    js_path = run_dir / "summary.json"
    md_path.write_text(to_markdown(summary))
    js_path.write_text(json.dumps(to_fixture_json(summary), indent=2))
    print(f"wrote {md_path}")
    print(f"wrote {js_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
