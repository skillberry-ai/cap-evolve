"""Where ``skills/`` and ``templates/`` live — repo checkout or installed wheel.

The core is pure code, but the run needs data that ships beside it: the skill
library (``skills/``, incl. ``optimizers/registry.yaml`` and
``_registry/manifest.json``) and the project scaffolding (``templates/``). From a
clone those sit at the repo root, two levels above this file
(``<repo>/core/cap_evolve/resources.py``). From ``pip install cap-evolve`` there is
no repo, so the same trees are packaged inside the package as
``cap_evolve/_bundled/{skills,templates}``.

``resource_root()`` returns whichever one is real, so every caller can keep asking
for ``root / "skills" / ...`` unchanged. This is the hole that #193 found in
``install.sh`` (a stock install could not read ``optimizers/registry.yaml``), in
the pip shape: a wheel that ships only ``*.py`` cannot run an optimizer at all.

``$CAPEVOLVE_RESOURCE_ROOT`` overrides both — documented in
``docs/TROUBLESHOOTING.md``; it is the escape hatch for a broken install or for a stale
``~/.claude/skills`` shadowing the tree you meant to run (#208).

BUILD CONSTRAINT: ``_bundled/{skills,templates}`` are symlinks, so the packaged copy can
never drift from the repo. A checkout without symlink support (``core.symlinks=false`` —
the Windows git default) turns them into ~15-byte text files; the ``package-data`` globs
then match nothing and ``python -m build`` produces a data-free wheel that ``twine check``
still passes. ``release.yml``'s ``build`` job asserts the symlinks before building and the
data files inside the artifact after.
"""

from __future__ import annotations

import os
from pathlib import Path

_BUNDLED = Path(__file__).resolve().parent / "_bundled"
_SOURCE = Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    """Dir containing ``skills/`` and ``templates/``. Repo root, else the bundle.

    ``$CAPEVOLVE_RESOURCE_ROOT`` overrides both (a host pinning its own tree).
    Falls back to the source layout so the message a caller gets on a genuinely
    broken install names the path it expected.
    """
    env = os.environ.get("CAPEVOLVE_RESOURCE_ROOT")
    if env and (Path(env) / "skills").is_dir():
        return Path(env)
    if (_SOURCE / "skills").is_dir():
        return _SOURCE
    if (_BUNDLED / "skills").is_dir():
        return _BUNDLED
    return _SOURCE
