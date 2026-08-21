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
    """Minimal: put a dir containing the cap_evolve package on sys.path.

    ``CAPEVOLVE_CORE`` is honoured BEFORE any ambient import. An editable install of a
    *different* cap-evolve checkout registers a ``sys.meta_path`` finder, which outranks
    both ``sys.path`` and ``PYTHONPATH`` — so "cap_evolve imports fine" is not evidence that
    it imports the checkout you are standing in. Deferring to the ambient package here made
    an explicit override unreachable, and the symptom was a stale core silently answering
    for this one (``ModuleNotFoundError: cap_evolve.constraints`` from a checkout that
    predates that module). An explicit env var wins.
    """
    env = os.environ.get("CAPEVOLVE_CORE")
    want = Path(env).resolve() if env else None
    if want and (want / "cap_evolve" / "__init__.py").exists():
        loaded = sys.modules.get("cap_evolve")
        already = getattr(loaded, "__file__", None)
        if already and Path(already).resolve().parent.parent == want:
            return                      # right checkout already imported: touch nothing
        p = str(want)
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)
        if loaded is not None:
            # Evicting a module makes a re-import yield a DIFFERENT object, so anything
            # already holding a reference fails an `is` check. Only ever do it when the
            # loaded package really is the wrong checkout — otherwise this "fix" becomes
            # the bug (it broke two identity assertions in core/tests exactly once).
            for name in [m for m in sys.modules
                         if m == "cap_evolve" or m.startswith("cap_evolve.")]:
                sys.modules.pop(name, None)
        for finder in list(sys.meta_path):
            if "cap_evolve" in getattr(finder, "MAPPING", {}):
                sys.meta_path.remove(finder)
        return
    # A checkout's own core outranks an ambient install. Without this, a skill script run
    # from checkout X silently executed against checkout Y's cap_evolve (an editable install
    # registers a sys.meta_path finder, which outranks sys.path), and the only symptom was
    # missing modules — or, worse, a green result measured against the wrong tree.
    here = Path(__file__).resolve()
    own = next((p / "core" for p in here.parents
                if (p / "core" / "cap_evolve" / "__init__.py").exists()), None)
    if own is not None:
        os.environ.setdefault("CAPEVOLVE_CORE", str(own))
        return _seed_path()
    try:
        import cap_evolve  # noqa: F401
        return
    except Exception:
        pass
    cands = []
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
