"""Ensure the stdlib-only ``cap_evolve`` core is importable.

Prefer an installed ``cap-evolve-core``; fall back to the in-repo ``core/`` dir
so tests and dev runs work from a checkout (mirrors core's own _bootstrap.py).
"""
from __future__ import annotations

import sys
from pathlib import Path


def ensure_core_on_path() -> None:
    try:
        import cap_evolve  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    # dashboard/backend/capevolve_dashboard/_bootstrap.py -> repo root is parents[3]
    core = Path(__file__).resolve().parents[3] / "core"
    if core.is_dir():
        sys.path.insert(0, str(core))


ensure_core_on_path()
