"""Evidence ledger: a content-hash index over rollouts, plus the subset-capable eval worker.

Rollouts stay the source of truth; ``<run>/eval_index.jsonl`` is an append-only, rebuildable view
keyed by ``cap_hash`` (the SHA-256 of the candidate's capability bytes). Re-measuring identical bytes (a revert, a "control"
copy of the parent) is then just more trials on the same hash instead of a new tag.

Row: ``{cap_hash, split, task, trial_idx, tag, k, env_fp, window_id, reward, cost, tokens, ts}``.
``trial_idx`` is allocated here (next unused per hash/task/split); ``(tag, k)`` is the rollout the row
came from, which makes recording idempotent. Evidence pools only within an equal ``env_fp``
(env var ``CAPEVOLVE_ENV_FP``; empty by default). ``CAPEVOLVE_EVAL_LEDGER=0`` turns recording off.
"""

from __future__ import annotations

import re
import json
import os
import sys
import time
from pathlib import Path

from .cache import hash_candidate_dir
from .rundir import _file_lock

LEDGER = "eval_index.jsonl"


def cap_hash(candidate_dir) -> str:
    """Same value as ``cache.hash_candidate_dir`` (injected memory/trajectories/dot-scratch are not
    capability). The graph node field ``capability_hash`` (run schema v2) is this exact value."""
    return hash_candidate_dir(Path(candidate_dir))


def enabled() -> bool:
    return os.environ.get("CAPEVOLVE_EVAL_LEDGER", "1") != "0"


def env_fp() -> str:
    return os.environ.get("CAPEVOLVE_ENV_FP", "")


def rows(run_dir) -> list[dict]:
    path = Path(run_dir.root) / LEDGER
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue  # a torn trailing line must not poison the ledger
    return out


def counts(run_dir, hash_: str, split: str = "val", fp: str | None = None) -> dict[str, tuple[float, int]]:
    """Per-task ``(sum_reward, n)`` pooled over every tag that shares ``hash_``."""
    fp = env_fp() if fp is None else fp
    acc: dict[str, list] = {}
    for r in rows(run_dir):
        if r["cap_hash"] == hash_ and r["split"] == split and r["env_fp"] == fp:
            a = acc.setdefault(r["task"], [0.0, 0])
            a[0] += r["reward"]
            a[1] += 1
    return {t: (s, n) for t, (s, n) in acc.items()}


def next_trial_idx(run_dir, hash_: str, task: str | None = None, split: str = "val",
                   fp: str | None = None) -> int:
    """First unused trial/seed index for this hash (``task=None``: across all its tasks), so a
    new tag's trials are fresh seeds, never a replay of seeds already in the ledger."""
    fp = env_fp() if fp is None else fp
    return max((r["trial_idx"] + 1 for r in rows(run_dir)
                if r["cap_hash"] == hash_ and r["split"] == split and r["env_fp"] == fp
                and (task is None or r["task"] == task)), default=0)


def missing(run_dir, hash_: str, task_ids, want_n: int, split: str = "val") -> dict[str, int]:
    """``{task: trials still needed}`` to bring every cell of ``hash_`` up to ``want_n``."""
    c = counts(run_dir, hash_, split)
    return {t: want_n - c.get(t, (0, 0))[1] for t in map(str, task_ids) if c.get(t, (0, 0))[1] < want_n}


_ROLLOUT = re.compile(r"^(?P<task>.+)__(?P<tag>.+)__t(?P<k>\d+)\.json$")


def record(run_dir, candidate_dir, split: str, tag: str, task_ids, ks, *, seed_base: int = 0,
           subset: bool = False) -> int:
    """Index the rollouts ``<task>__<tag>__t<k>`` for the given tasks/ks. Returns rows written.

    ``trial_idx`` of the j-th k is ``seed_base + j`` (the seed index the harness used). Errored
    rollouts are missing data, so they are not indexed; the test split is never indexed.
    Atomic under the run's file lock. Idempotent on ``(tag, split, task, k)``: re-recording a
    re-evaluated tag replaces its superseded rows (rollouts are the truth), unchanged rows stay.
    """
    if not enabled() or split == "test":
        return 0
    h, fp = cap_hash(candidate_dir), env_fp()
    path = Path(run_dir.root) / LEDGER
    with _file_lock(path.with_suffix(".lock")):
        have = rows(run_dir)
        old = {(r["tag"], r["split"], r["task"], r["k"]): r for r in have}
        new = []
        for tid in task_ids:
            for j, k in enumerate(ks):
                f = Path(run_dir.rollouts) / split / f"{tid}__{tag}__t{k}.json"
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                ro, sc = d.get("rollout") or {}, d.get("score") or {}
                if ro.get("error") or (sc.get("raw") or {}).get("errored"):
                    continue
                reward = float(sc.get("reward") or 0.0)
                prev = old.get((tag, split, tid, k))
                if prev and prev["cap_hash"] == h and prev["reward"] == reward:
                    continue
                new.append({"cap_hash": h, "split": split, "task": tid, "trial_idx": seed_base + j,
                            "tag": tag, "k": k, "env_fp": fp, "window_id": 0, "reward": reward,
                            "subset": subset, "cost": float(ro.get("cost_usd") or 0.0),
                            "tokens": int(ro.get("tokens") or 0), "ts": time.time()})
        if new:
            gone = {(r["tag"], r["split"], r["task"], r["k"]) for r in new}
            keep = [r for r in have if (r["tag"], r["split"], r["task"], r["k"]) not in gone]
            tmp = path.with_suffix(".tmp")
            tmp.write_text("".join(json.dumps(r) + "\n" for r in keep + new), encoding="utf-8")
            os.replace(tmp, path)
        return len(new)


def backfill(run_dir) -> int:
    """Rebuild the ledger from the rollouts on disk (train/val; never test)."""
    n = 0
    for split in ("train", "val"):
        d = Path(run_dir.rollouts) / split
        by_tag: dict[str, dict[str, set]] = {}
        for p in d.glob("*.json") if d.is_dir() else []:
            m = _ROLLOUT.match(p.name)
            if m:
                by_tag.setdefault(m["tag"], {}).setdefault(m["task"], set()).add(int(m["k"]))
        for tag, tasks in by_tag.items():
            cand = run_dir.candidate_dir(tag)
            for tid, ks in tasks.items():
                n += record(run_dir, cand, split, tag, [tid], sorted(ks), seed_base=min(ks))
    return n


# ---- subset-capable eval executor (extracted from agent-optimize round.py::_evaluate) ----------

_EVALUATE = Path(__file__).resolve().parents[2] / "skills" / "phases" / "evaluate" / "scripts" / "run.py"


def eval_cmd(run_dir, project, tag: str, split: str, n_trials: int, *, ids=None,
             trial_offset: int = 0, skills_dir=None) -> list[str]:
    script = (Path(skills_dir) / "phases" / "evaluate" / "scripts" / "run.py") if skills_dir else _EVALUATE
    cmd = [sys.executable, str(script), "--run-dir", str(run_dir), "--project", str(project),
           "--candidate", str(Path(run_dir) / "work" / tag), "--split", split,
           "--n-trials", str(n_trials)]
    if ids:
        cmd += ["--ids", ",".join(map(str, ids))]
    if trial_offset:
        cmd += ["--trial-offset", str(trial_offset)]
    return cmd
