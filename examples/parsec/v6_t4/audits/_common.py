"""Paths shared by the v6 audit scripts. Override with environment variables.

V6_G2_RUN     the Global run dir        (<parsec-intake_v6>/.capevolve/v6_g2_e1/run_g2_e1)
V6_G2_SEALED  its sealed counterpart     (<parsec-intake_v6>/.capevolve.sealed/run_g2_e1)
V6_TREE       the unified v6 task tree   (rhdp-parsec/v6_2026-10-16)
V6_REPO       a cap-evolve checkout, for core/cap_evolve (default: this checkout)
"""
import json
import os
from pathlib import Path

_W = "/dccstor/knewedge2/boazc/workarea/python"
G2_RUN = Path(os.environ.get("V6_G2_RUN", f"{_W}/skillberry_ai/cap-evolve-ps-worktrees/parsec-intake_v6/.capevolve/v6_g2_e1/run_g2_e1"))
G2_SEALED = Path(os.environ.get("V6_G2_SEALED", f"{_W}/skillberry_ai/cap-evolve-ps-worktrees/parsec-intake_v6/.capevolve.sealed/run_g2_e1"))
TREE = Path(os.environ.get("V6_TREE", f"{_W}/rhdp-parsec/v6_2026-10-16"))
REPO = Path(os.environ.get("V6_REPO", Path(__file__).resolve().parents[4]))
TASKS = TREE / "bench-v6-harbor-tasks"


def splits() -> dict:
    return json.loads((G2_RUN / "splits.json").read_text())


def find_one(root, name):
    return next(Path(root).rglob(name), None)


def trial_messages(trial_dir):
    """Yield (kind, payload) from a harbor trial's agent.jsonl: tool_use / tool_result / result."""
    aj = find_one(trial_dir, "agent.jsonl")
    if aj is None:
        return
    for line in aj.read_text().splitlines():
        o = json.loads(line)
        m = o.get("message") or {}
        if isinstance(m.get("content"), list):
            for b in m["content"]:
                if b.get("type") in ("tool_use", "tool_result"):
                    yield b["type"], b
        if o.get("type") == "result":
            yield "result", o.get("result") or ""
