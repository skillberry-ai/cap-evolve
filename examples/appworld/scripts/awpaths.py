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
# The cap-evolve arm's run: runs/<name>/.capevolve/run_<name> (scripts/launch_cape_hc.sh uses the dir name).
CAPE_NAME = os.environ.get("AW_CAPE_RUN", "cape_hc_s0")
CAPE_RUN = RUNS / CAPE_NAME / ".capevolve" / f"run_{CAPE_NAME}"
OPT_TRANSCRIPTS = RUNS / "optimizer_transcripts"
EXAMPLE = Path(__file__).resolve().parents[1]
REPO = EXAMPLE.parents[1]
# ALTK-Evolve needs Python >= 3.12, so it lives in its own venv (README: Setup).
ALTK_PYTHON = os.environ.get("AW_ALTK_PYTHON", str(REPO / ".venv" / "bin" / "python"))
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
