"""Evidence ledger: a content-hash index over rollouts, plus the subset-capable eval worker.

Rollouts stay the source of truth; ``<run>/eval_index.jsonl`` is an append-only, rebuildable view
keyed by the SHA-256 of the candidate's bytes. Re-measuring identical bytes (a revert, a "control"
copy of the parent) is then just more trials on the same hash instead of a new tag.

Row: ``{hash, split, task, trial_idx, tag, k, env_fp, window_id, reward, cost, tokens, ts}``.
``trial_idx`` is allocated here (next unused per hash/task/split); ``(tag, k)`` is the rollout the row
came from, which makes recording idempotent. Evidence pools only within an equal ``env_fp``
(env var ``CAPEVOLVE_ENV_FP``; empty by default). ``CAPEVOLVE_EVAL_LEDGER=0`` turns recording off.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LEDGER = "eval_index.jsonl"


def cap_hash(candidate_dir) -> str:
    """SHA-256 over the candidate's files (relative path + bytes), ignoring hidden/cache entries."""
    h = hashlib.sha256()
    root = Path(candidate_dir)
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root)
            if p.is_file() and not any(s.startswith(".") or s == "__pycache__" for s in rel.parts):
                h.update(str(rel).encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


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
        if r["hash"] == hash_ and r["split"] == split and r["env_fp"] == fp:
            a = acc.setdefault(r["task"], [0.0, 0])
            a[0] += r["reward"]
            a[1] += 1
    return {t: (s, n) for t, (s, n) in acc.items()}


def next_trial_idx(run_dir, hash_: str, task: str, split: str = "val", fp: str | None = None) -> int:
    """Ledger trial depth for this cell: the ``trial_offset`` a top-up must start at."""
    return counts(run_dir, hash_, split, fp).get(task, (0.0, 0))[1]


def missing(run_dir, hash_: str, task_ids, want_n: int, split: str = "val") -> dict[str, int]:
    """``{task: trials still needed}`` to bring every cell of ``hash_`` up to ``want_n``."""
    c = counts(run_dir, hash_, split)
    return {t: want_n - c.get(t, (0, 0))[1] for t in map(str, task_ids) if c.get(t, (0, 0))[1] < want_n}


def record(run_dir, candidate_dir, split: str, tag: str, task_ids, ks) -> int:
    """Index the rollouts ``<task>__<tag>__t<k>`` for the given tasks/ks. Returns rows appended.

    Errored rollouts are missing data, not zeros, so they are not indexed. Idempotent on
    ``(hash, split, tag, task, k)``.
    """
    if not enabled():
        return 0
    h, fp = cap_hash(candidate_dir), env_fp()
    have = rows(run_dir)
    seen = {(r["hash"], r["split"], r["tag"], r["task"], r["k"]) for r in have}
    depth: dict[str, int] = {}
    for r in have:
        if r["hash"] == h and r["split"] == split and r["env_fp"] == fp:
            depth[r["task"]] = depth.get(r["task"], 0) + 1
    new = []
    for tid in task_ids:
        for k in ks:
            if (h, split, tag, tid, k) in seen:
                continue
            f = Path(run_dir.rollouts) / split / f"{tid}__{tag}__t{k}.json"
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            ro, sc = d.get("rollout") or {}, d.get("score") or {}
            if ro.get("error") or (sc.get("raw") or {}).get("errored"):
                continue
            i = depth.get(tid, 0)
            depth[tid] = i + 1
            new.append({"hash": h, "split": split, "task": tid, "trial_idx": i, "tag": tag, "k": k,
                        "env_fp": fp, "window_id": 0, "reward": float(sc.get("reward") or 0.0),
                        "cost": float(ro.get("cost_usd") or 0.0), "tokens": int(ro.get("tokens") or 0),
                        "ts": time.time()})
    if new:
        with (Path(run_dir.root) / LEDGER).open("a", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(r) + "\n" for r in new))
    return len(new)


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
