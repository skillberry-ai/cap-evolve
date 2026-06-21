"""Thin shim: locate cap_evolve, then defer to cap_evolve._bootstrap.

Skill scripts ``import _bootstrap`` first. The real path-resolution logic lives
ONCE in ``cap_evolve._bootstrap`` (so it can't drift across skills); this shim
only has to find that package, which means a minimal upward walk for ``core/`` —
the single bit of bootstrapping that genuinely must run before cap_evolve is
importable. Everything else delegates.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _seed_path() -> None:
    """Minimal: put a dir containing the cap_evolve package on sys.path."""
    try:
        import cap_evolve  # noqa: F401
        return
    except Exception:
        pass
    cands = []
    env = os.environ.get("CAPEVOLVE_CORE")
    if env:
        cands.append(Path(env))
    here = Path(__file__).resolve()
    for parent in here.parents:
        cands.append(parent / "core")
        cands.append(parent)
    for c in cands:
        if (c / "cap_evolve" / "__init__.py").exists():
            p = str(c)
            if p not in sys.path:
                sys.path.insert(0, p)
            return


_seed_path()
from cap_evolve._bootstrap import ensure_core  # noqa: E402

# Anchor the upward walk at THIS skill script's location (not the core module's).
ensure_core(Path(__file__).resolve())
