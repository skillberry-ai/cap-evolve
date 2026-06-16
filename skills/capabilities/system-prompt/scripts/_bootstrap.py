"""Locate ``cap_evolve`` whether the skill runs from source or installed.

Skill scripts ``import _bootstrap`` first. Resolution order:
  1. already importable (pip-installed `cap-evolve-core`) — use it;
  2. ``$CAPEVOLVE_CORE`` env var pointing at the ``core/`` dir;
  3. walk up from this file looking for a sibling ``core/cap_evolve``;
  4. walk up looking for any ``cap_evolve`` package on disk.

This keeps skills host-agnostic: a host that pip-installed the core just works;
a host that only cloned the repo still finds it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _add(path: Path) -> bool:
    p = str(path)
    if (path / "cap_evolve" / "__init__.py").exists():
        if p not in sys.path:
            sys.path.insert(0, p)
        return True
    return False


def ensure_core() -> None:
    try:
        import cap_evolve  # noqa: F401
        return
    except Exception:
        pass

    env = os.environ.get("CAPEVOLVE_CORE")
    if env and _add(Path(env)):
        return

    here = Path(__file__).resolve()
    for parent in here.parents:
        if _add(parent / "core"):
            return
        if _add(parent):
            return

    raise ImportError(
        "cap_evolve not found. Install it (`pip install ./core`) or set "
        "CAPEVOLVE_CORE to the repo's core/ directory."
    )


ensure_core()
