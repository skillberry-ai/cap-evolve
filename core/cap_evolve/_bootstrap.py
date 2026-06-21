"""Path resolution shared by every skill ``run.py`` / ``check.py``.

Skill scripts run as loose files (a host copies ``skills/`` somewhere and invokes
``python .../scripts/run.py``), so they need to locate the ``cap_evolve`` package
before they can ``import`` it. The logic used to be copy-pasted into 25
``scripts/_bootstrap.py`` files; it now lives here, once, and each skill ships a
2-line shim that finds *this* module and re-exports ``ensure_core``.

Resolution order (first hit wins):
  1. ``cap_evolve`` already importable (pip-installed ``cap-evolve-core``);
  2. ``$CAPEVOLVE_CORE`` pointing at the ``core/`` dir;
  3. walk up from ``start`` looking for a sibling ``core/cap_evolve``;
  4. walk up looking for any ``cap_evolve`` package on disk.

Host-agnostic: a host that pip-installed the core just works; a host that only
cloned the repo still finds it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _add(path: Path) -> bool:
    """Put ``path`` on ``sys.path`` if it contains the ``cap_evolve`` package."""
    if (path / "cap_evolve" / "__init__.py").exists():
        p = str(path)
        if p not in sys.path:
            sys.path.insert(0, p)
        return True
    return False


def ensure_core(start: Path | str | None = None) -> None:
    """Make ``import cap_evolve`` succeed from a loose skill script.

    ``start`` is the file whose location anchors the upward walk (a caller passes
    its own ``__file__``); defaults to this module's own path, which still works
    because the real module lives inside the package we are looking for.
    """
    try:
        import cap_evolve  # noqa: F401
        return
    except Exception:
        pass

    env = os.environ.get("CAPEVOLVE_CORE")
    if env and _add(Path(env)):
        return

    here = Path(start).resolve() if start else Path(__file__).resolve()
    for parent in here.parents:
        if _add(parent / "core"):
            return
        if _add(parent):
            return

    raise ImportError(
        "cap_evolve not found. Install it (`pip install ./core`) or set "
        "CAPEVOLVE_CORE to the repo's core/ directory."
    )


# Importing this module from *inside* the package means cap_evolve is already
# importable; calling ensure_core() here is a cheap no-op that keeps the
# "import _bootstrap runs ensure_core" contract identical to the old shim.
ensure_core()
