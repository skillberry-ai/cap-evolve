"""Locate ``agent_capo`` whether the skill runs from source or installed.

Skill scripts ``import _bootstrap`` first. Resolution order:
  1. already importable (pip-installed `AgentCapTune-core`) — use it;
  2. ``$AGENT_CAPO_CORE`` env var pointing at the ``core/`` dir;
  3. walk up from this file looking for a sibling ``core/agent_capo``;
  4. walk up looking for any ``agent_capo`` package on disk.

This keeps skills host-agnostic: a host that pip-installed the core just works;
a host that only cloned the repo still finds it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _add(path: Path) -> bool:
    p = str(path)
    if (path / "agent_capo" / "__init__.py").exists():
        if p not in sys.path:
            sys.path.insert(0, p)
        return True
    return False


def ensure_core() -> None:
    try:
        import agent_capo  # noqa: F401
        return
    except Exception:
        pass

    env = os.environ.get("AGENT_CAPO_CORE")
    if env and _add(Path(env)):
        return

    here = Path(__file__).resolve()
    for parent in here.parents:
        if _add(parent / "core"):
            return
        if _add(parent):
            return

    raise ImportError(
        "agent_capo not found. Install it (`pip install ./core`) or set "
        "AGENT_CAPO_CORE to the repo's core/ directory."
    )


ensure_core()
