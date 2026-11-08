#!/usr/bin/env python3
"""For named tasks still short of N valid trials in their current run: pool
every valid (error-free) trial from EVERY attempt on disk for that task --
the current run plus every ``.dead-<timestamp>`` run left behind by a
move-aside-and-resubmit cycle -- audit each one individually, and if the pool
has >= N valid trials, randomly sample exactly N and report their mean. If
the pool has fewer than N, use all of them (no failure declared) with a note
saying so.

This is the generalized form of a technique first used ad hoc for
``v5_g2_e1``: 4 tasks there never produced 5 clean trials in any SINGLE run
across repeated resubmission (recurring gateway hangs), but had plenty of
individually-clean trials once every attempt was pooled together. The
insight that made this acceptable: a trial's validity is a property of that
one trial (did harbor raise, did the agent's final transcript event report
is_error), not of which run batch it happened to land in -- so trials from
different attempts are not "contaminated" by being pooled, as long as each
one is still audited on its own terms.

Harness context (see ../../h4/README.md or docs/plans/*parsec* for the full
story): re-evaluating a cap-evolve tag ALWAYS overwrites t0..t{n-1}, it never
appends to reach a higher count. Moving a short-trial run dir aside to
``run_<task>.dead-<timestamp>`` before resubmitting (rather than just
resubmitting in place) is what preserves its trials for this script to find
later -- deleting or overwriting a dead-short run instead would make its
otherwise-valid trials unrecoverable.

Depends on this directory's audit_trials.py-shaped audit logic (duplicated
here in miniature as audit_trial(), rather than imported, because it reads
per-trial rollout JSON files directly instead of audit_trials.py's "scan
every run under a prefix" shape).

Usage:
    python3 examples/parsec/v5/audit/pool_valid_trials.py \
        --capevolve-dir .capevolve --prefix v5_g2_e1 --n 5 \
        platform-034-rate-limit-not-an-outage platform-111-recycled-sandbox-swallowed-teardown
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import sys
from pathlib import Path


def final_event(trial_dir: str) -> dict | None:
    """The agent's last `result` event, or None if it never wrote one. Same
    glob shape as audit_trials.py's final_event()."""
    pats = (f"{trial_dir}/*/*/agent/*.jsonl", f"{trial_dir}/*/*/agent.jsonl",
            f"{trial_dir}/*/*/*/agent*.jsonl")
    out = None
    for pat in pats:
        for p in glob.glob(pat):
            for line in open(p, errors="replace"):
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("type") == "result":
                    out = ev
    return out


def audit_trial(rollout_path: str) -> dict:
    """Read one rollout JSON and report whether it is clean, its reward, and
    its cost/tokens/seconds -- so a pooled task's cost accounting reflects
    the exact trials it ends up using, not whichever run happened to be live.
    """
    d = json.loads(open(rollout_path).read())
    rollout = d.get("rollout") or {}
    score = d.get("score") or {}
    md = rollout.get("metadata") or {}
    reward = score.get("reward")
    cost = rollout.get("cost_usd") or 0.0
    tokens = rollout.get("tokens") or 0
    win = md.get("parsec_usage_window") or {}
    seconds = 0.0
    if win.get("start") and win.get("end"):
        from datetime import datetime
        seconds = (datetime.fromisoformat(win["end"])
                   - datetime.fromisoformat(win["start"])).total_seconds()

    problems = []
    if rollout.get("error"):
        problems.append("harbor_exception")
    ev = final_event(md.get("trial_dir") or "")
    if ev is None:
        problems.append("no_result_event")
    elif not (ev.get("subtype") == "success" and not ev.get("is_error")):
        problems.append(f"final_is_error:{ev.get('subtype')}")

    return {
        "problems": problems,
        "reward": reward,
        "cost_usd": cost,
        "tokens": tokens,
        "seconds": seconds,
    }


def all_run_dirs_for(capevolve_dir: Path, prefix: str, task: str) -> list[Path]:
    """Every attempt's run dir for this task: the live one plus every
    .dead-<timestamp> one, oldest first."""
    base = capevolve_dir / f"{prefix}_{task}"
    dirs = sorted(glob.glob(str(base / f"run_{task}*")))
    return [Path(d) for d in dirs]


def pool_valid_trials(capevolve_dir: Path, prefix: str, task: str) -> list[tuple]:
    pool = []  # list of (audit_dict, source_dir_name, rollout_filename)
    for rd in all_run_dirs_for(capevolve_dir, prefix, task):
        for rp in sorted(glob.glob(str(rd / "rollouts" / "val" / "*.json"))):
            a = audit_trial(rp)
            if not a["problems"]:
                pool.append((a, rd.name, os.path.basename(rp)))
    return pool


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tasks", nargs="+", help="task ids to pool")
    parser.add_argument("--capevolve-dir", default=".capevolve")
    parser.add_argument("--prefix", required=True,
                        help="suite prefix, e.g. v5_g2_e1 (matches .capevolve/<prefix>_<task>/)")
    parser.add_argument("--n", type=int, default=5, help="trials to sample when the pool is large enough")
    parser.add_argument("--seed", type=int, default=20261014, help="random seed, for reproducibility")
    parser.add_argument("--out", help="write {task: {...}} JSON here instead of only printing")
    args = parser.parse_args()

    capevolve_dir = Path(args.capevolve_dir)
    rng = random.Random(args.seed)
    out = {}
    for t in args.tasks:
        pool = pool_valid_trials(capevolve_dir, args.prefix, t)
        n_total = len(pool)
        if n_total >= args.n:
            chosen = rng.sample(pool, args.n)
            status = "pooled_full"
            note = (
                f"Fewer than {args.n} valid trials in any single run. Pooled all {n_total} "
                f"individually-audited, error-free trials across every attempt on disk "
                f"(current + .dead-* runs) and randomly sampled {args.n} (seed={args.seed}) "
                f"rather than requiring {args.n} from one run."
            )
        else:
            chosen = pool
            status = "pooled_partial" if n_total else "pooled_none"
            note = (
                f"Only {n_total} valid trial(s) found across every attempt on disk for this "
                f"task, after pooling and individually auditing each one. Reporting the mean "
                f"of those {n_total} rather than declaring failure."
            )
        rewards = [a["reward"] for a, _, _ in chosen]
        out[t] = {
            "status": status,
            "n_pool_total": n_total,
            "n_used": len(chosen),
            "trial_rewards": rewards,
            "reward_mean": (sum(rewards) / len(rewards)) if rewards else None,
            "cost_usd": round(sum(a["cost_usd"] for a, _, _ in chosen), 4),
            "tokens": sum(a["tokens"] for a, _, _ in chosen),
            "seconds": round(sum(a["seconds"] for a, _, _ in chosen), 2),
            "sources_used": sorted({f"{d}/{f}" for _, d, f in chosen}),
            "note": note,
        }
        print(f"{t}: pool={n_total} used={len(chosen)} mean={out[t]['reward_mean']}  ({status})")

    if args.out:
        out_path = Path(args.out)
        existing = json.loads(out_path.read_text()) if out_path.exists() else {}
        existing.update(out)
        out_path.write_text(json.dumps(existing, indent=2))
        print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
