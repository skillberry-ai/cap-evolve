"""Per-host metadata reader — ``skills/_registry/hosts.yaml`` is the single source.

Issue #143: the host list used to live in five places (``install.sh``'s ``case``,
``doctor._VERIFIED_HOST_DIRS``, and two tables in ``docs/HOST_SUPPORT.md``) and
drifted. Now ``hosts.yaml`` is the truth, this module is the only reader, and
``core/tests/test_host_parity.py`` fails when any consumer disagrees with it.

Stdlib-only on purpose: ``read_yaml`` falls back to its own tiny parser when PyYAML
is absent, so ``python3 -m cap_evolve.hosts --dest claude`` works in a bare
environment — which is what ``install.sh`` calls, before anything is pip-installed.
``core/tests/test_stdlib_only.py`` proves that under an import hook that blocks every
non-stdlib module.

CLI (used by install.sh, one call per run):
    python3 -m cap_evolve.hosts --dest <host-alias>   # expanded destination, or ""
    python3 -m cap_evolve.hosts --json                # the whole table
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .specfile import read_yaml

#: Grades a destination row may carry. ``verified`` demands an executing artifact.
STATUSES = ("verified", "docs-checked", "best-guess")


def hosts_path() -> Path | None:
    """``skills/_registry/hosts.yaml`` — next to the manifest, found the same way."""
    env = os.environ.get("CAPEVOLVE_HOSTS_FILE")
    if env and Path(env).exists():
        return Path(env)
    from .cli import _find_skills_dir
    d = _find_skills_dir()
    for cand in ([d / "_registry" / "hosts.yaml"] if d else []) + [
        p / "skills" / "_registry" / "hosts.yaml" for p in Path(__file__).resolve().parents
    ]:
        if cand.exists():
            return cand
    return None


def load_hosts() -> dict:
    p = hosts_path()
    return read_yaml(p.read_text(encoding="utf-8")) if p else {}


def _expand(dest: str) -> str:
    """Expand the literal ``$HOME`` / ``$PWD`` tokens the rows are written with.

    Written literally (not pre-expanded) so a row is byte-comparable with the path
    ``install.sh`` echoes — that string equality is what the parity guard checks.
    """
    return dest.replace("$HOME", os.path.expanduser("~")).replace("$PWD", os.getcwd())


def dest_for(alias: str) -> str | None:
    """Install destination for a ``./install.sh --host <alias>`` spelling, expanded."""
    for row in load_hosts().values():
        if alias in (row.get("aliases") or []):
            return _expand(str(row.get("dest", "")))
    return None


def status_for(alias: str) -> str | None:
    for row in load_hosts().values():
        if alias in (row.get("aliases") or []):
            return str(row.get("status", ""))
    return None


def verified_dests() -> list[str]:
    """Expanded destinations of every row — what doctor treats as a known host dir.

    Replaces doctor's hand-maintained ``_VERIFIED_HOST_DIRS`` tuple, which is how
    that list drifted from ``install.sh`` in the first place.
    """
    return [_expand(str(r.get("dest", ""))) for r in load_hosts().values() if r.get("dest")]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--json" in argv:
        print(json.dumps(load_hosts(), indent=2, sort_keys=True))
        return 0
    if "--dest" in argv:
        alias = argv[argv.index("--dest") + 1]
        d = dest_for(alias)
        print(d or "")
        return 0 if d else 1
    print("usage: python3 -m cap_evolve.hosts --dest <host> | --json", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
