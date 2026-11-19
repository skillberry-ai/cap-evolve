"""Shared paths and official-split helpers for the AppWorld example (README)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

EVAL = Path(os.environ.get("AW_EVAL", "/tmp/aw_eval"))
APPWORLD_REPO = EVAL / "appworld"
ROOT_FULL = EVAL / "root_full"
ROOT_OPT = EVAL / "root_opt"
RUNS = EVAL / "runs"
PROGRESS = EVAL / "progress"
MANIFEST = RUNS / "manifest.json"
# The cap-evolve arm's runs: CAPE_BASE/run_<YYYYMMDD_HHMMSS>, one per scripts/launch_cape_hc.sh launch.
# AW_CAPE_RUN names the search run the final window and the analysis use (its timestamp, e.g.
# 20261118_171500); unset, the newest run in CAPE_BASE.
CAPE_BASE = Path(os.environ.get("AW_CAPE_BASE", str(EVAL / ".capevolve")))


def _newest_run_name() -> str:
    runs = sorted(CAPE_BASE.glob("run_*"), key=lambda p: p.stat().st_mtime) if CAPE_BASE.is_dir() else []
    return runs[-1].name[len("run_"):] if runs else ""


CAPE_NAME = os.environ.get("AW_CAPE_RUN") or _newest_run_name()
CAPE_RUN = CAPE_BASE / f"run_{CAPE_NAME}"
OPT_TRANSCRIPTS = RUNS / "optimizer_transcripts"
# The final window's dir (runs/<AW_FINAL>); a re-run uses a new one so an earlier window stays intact.
FINAL = RUNS / os.environ.get("AW_FINAL", "final")
EXAMPLE = Path(__file__).resolve().parents[1]
REPO = EXAMPLE.parents[3]
# KEY=VALUE file with the agent-model key (never exported; each episode worker reads it).
SECRETS_FILE = os.environ.get("AW_SECRETS_FILE", str(REPO / ".env"))

SPLITS = ("train", "dev", "test_normal", "test_challenge")
EXPECTED_COUNTS = {"train": 90, "dev": 57, "test_normal": 168, "test_challenge": 417}


def read_split(name: str, root: Path = ROOT_FULL) -> list[str]:
    """The ids of an official split, in file order (same parse as appworld.task.load_task_ids)."""
    return [line.strip() for line in (root / "data" / "datasets" / f"{name}.txt").read_text().splitlines()
            if line.strip()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_tree(root: Path) -> str:
    """Hash of every file's relative path and content under ``root`` (sorted)."""
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(b"\0")
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def update_manifest(**fields) -> dict:
    RUNS.mkdir(parents=True, exist_ok=True)
    data = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    data.update(fields)
    MANIFEST.write_text(json.dumps(data, indent=2, sort_keys=True))
    return data
