"""Shared constants and helpers for the post-cutoff final-evaluation machinery (python >= 3.9, stdlib only).

Nothing here makes a model call or reads a final-set task.  Paths are overridable by environment so the dry run can
point at a scratch directory:  CAMPAIGN_SCRATCH, FINAL_EVAL_ROOT.
"""
from __future__ import annotations

import csv
import datetime as dt
import fcntl
import hashlib
import json
import os
import random
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER = HERE.parents[1]                      # research/capevolve-paper
REPO = PAPER.parents[1]
SCRATCH = Path(os.environ.get("CAMPAIGN_SCRATCH", "/home/dev/projects2/campaign-scratch"))
RUNS = SCRATCH / "runs"
FINAL_ROOT = Path(os.environ.get("FINAL_EVAL_ROOT", str(SCRATCH / "final_eval")))
MANIFESTS = HERE / "manifests"               # committed: bstar_*.json, artifacts_*.json, order hashes
ORDER_SEED = 20261013
CUTOFF_UTC = "2026-10-13T06:00:00Z"
HARD_STOP_UTC = "2026-10-14T07:00:00Z"
BSTAR_FLOOR = 200
BSTAR_STEP = 50

# --- arm registry (keys are the real_numbers.py contract keys) -------------------------------------------------------
# run directory name per (suite, arm); CapEvolve arms live under their long names in Suite A only.
SUITES = {
    "A": {
        "exp": "E10", "label": "SpreadsheetBench (Gemma-4-31B-it)",
        "main": ["hc", "ao", "gepa", "skillopt", "metaharness", "evoskill", "wikiskill"],
        "cheap": ["trace2skill", "ace", "mipro"],
        "controls": [],
        "dirname": {"hc": "hill-climb", "ao": "agent-optimize"},
        "artifact_kind": "sb_files",       # prompt.md + task_template.md
    },
    "B": {
        "exp": "E10B", "label": "tau2 retail (gpt-oss-120b)",
        "main": ["hc", "ao", "gepa", "harnesslens"],
        "cheap": [],
        "controls": ["oneshot"],
        "dirname": {"oneshot": "ctl-oneshot"},
        "artifact_kind": "tau_cap",        # policy/** + tools/**
    },
    "C": {
        "exp": "E10C", "label": "tau2 airline (gpt-oss-120b)",
        "main": ["hc", "ao", "gepa"],
        "cheap": [],
        "controls": ["oneshot"],
        "dirname": {"oneshot": "ctl-oneshot"},
        "artifact_kind": "tau_cap",
    },
}
SEEDS = [0, 1, 2]
FAMILY_FILES = {"sb_files": ["prompt.md", "task_template.md"], "tau_cap": None}   # None = policy/** tools/**


def suite_arms(suite, include_cheap=True, include_controls=True):
    s = SUITES[suite]
    return list(s["main"]) + (list(s["cheap"]) if include_cheap else []) + (list(s["controls"]) if include_controls else [])


def run_dir(suite, arm, seed):
    s = SUITES[suite]
    return RUNS / s["exp"] / s["dirname"].get(arm, arm) / ("s%d" % seed)


# --- io helpers ------------------------------------------------------------------------------------------------------
def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def jload(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return default


def jsonl(p):
    out = []
    try:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except FileNotFoundError:
        pass
    return out


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_files(root, kind):
    """Canonical artifact file list (relative paths, sorted) of an artifact directory."""
    root = Path(root)
    if kind == "sb_files":
        return [f for f in FAMILY_FILES["sb_files"] if (root / f).is_file()]
    out = []
    for sub in ("policy", "tools"):
        for p in sorted((root / sub).rglob("*")) if (root / sub).is_dir() else []:
            if p.is_file() and "__pycache__" not in p.parts:
                out.append(str(p.relative_to(root)))
    return out


def tree_hash(root, kind):
    """sha256 over (relpath NUL file-sha256 NL) of the canonical files; also the per-file map."""
    files = {f: sha256_file(Path(root) / f) for f in tree_files(root, kind)}
    h = hashlib.sha256()
    for f in sorted(files):
        h.update(("%s\0%s\n" % (f, files[f])).encode())
    return h.hexdigest(), files


def file_sha(path):
    return sha256_file(path) if Path(path).exists() else None


def write_json_atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp%d" % os.getpid())
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def append_jsonl(path, obj):
    """Append one JSON line under an exclusive lock (safe for the multi-thread orchestrator)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(obj, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def import_by_path(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def collect_metrics():
    """The campaign's metrics module (counted_rollouts, uniform_class).  Imported, never copied, so the final runner uses
    the very classifier that is frozen and published with the analysis scripts."""
    if "collect_metrics" in sys.modules:
        return sys.modules["collect_metrics"]
    return import_by_path("collect_metrics", PAPER / "analysis" / "scripts" / "collect_metrics.py")


def git_head(path=REPO):
    import subprocess
    try:
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def final_dir(suite):
    return FINAL_ROOT / suite


def cell_key(arm, seed):
    return "%s/s%d" % (arm, seed)
