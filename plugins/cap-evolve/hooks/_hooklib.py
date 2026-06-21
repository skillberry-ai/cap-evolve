"""Shared, deterministic helpers for the cap-evolve honesty hooks.

These scripts embody the honesty rules in CORE-OWNED code, never in editable
skill markdown: an optimizer agent that can rewrite its own instructions still
cannot edit the sealed test split or declare an iteration "done" while the gate
is red, because the harness (Claude Code) runs these scripts, not the model.

Design rules for every hook here:
  * **Deterministic** — same stdin payload always yields the same decision.
  * **No-op gracefully** when not inside a CapEvolve run dir (exit 0): the hooks
    ship in a general-purpose plugin, so they must be silent on unrelated repos.
  * **Fail open on hook-internal errors** (exit 0 with a note on stderr): a bug
    in a hook must never wedge an unrelated Claude Code session. The honesty
    invariants are *also* enforced inside ``cap_evolve`` itself (splits seal,
    val-only gate); the hooks are a fast, early, model-visible guardrail, not the
    only line of defense.

stdin payload (Claude Code hook contract): JSON with at least ``cwd``,
``hook_event_name``, and for tool hooks ``tool_name`` / ``tool_input``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def read_payload() -> dict:
    """Parse the hook JSON from stdin; return {} on empty/garbage (fail-open)."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def hook_cwd(payload: dict) -> Path:
    """The directory Claude Code reports for the session."""
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return Path(cwd)


def find_run_dir(start: Path) -> Path | None:
    """Locate the active CapEvolve run dir, or None if we are not inside a run.

    Precedence:
      1. ``$CAPEVOLVE_RUN_DIR`` (set by the orchestrator while a run is live).
      2. The newest ``.capevolve/run_*`` (or legacy ``.agentcapo/run_*``) with a
         ``splits.json`` found walking up from ``start``.

    Returns None when nothing matches — the caller then no-ops (exit 0).
    """
    env = os.environ.get("CAPEVOLVE_RUN_DIR")
    if env:
        p = Path(env)
        if (p / "splits.json").exists() or (p / "state.json").exists():
            return p

    here = Path(start).resolve()
    candidates: list[Path] = []
    for parent in [here, *here.parents]:
        for base_name in (".capevolve", ".agentcapo"):
            base = parent / base_name
            if base.is_dir():
                runs = sorted(
                    (r for r in base.glob("run_*")
                     if (r / "splits.json").exists() or (r / "state.json").exists()),
                    key=lambda r: r.name,
                )
                candidates.extend(runs)
        if candidates:
            # newest run under the nearest base wins
            return candidates[-1]
    return None


def project_dir_for(run_dir: Path) -> Path | None:
    """The ``.capevolve/project`` (or ``.agentcapo/project``) sibling of a run dir."""
    base = run_dir.parent  # .capevolve/ or .agentcapo/
    for name in ("project",):
        proj = base / name
        if (proj / "adapters" / "adapter.py").exists():
            return proj
    return None


def load_sealed_test_ids(run_dir: Path) -> list[str]:
    """The held-out test ids from ``splits.json`` (empty list if unreadable)."""
    sp = run_dir / "splits.json"
    if not sp.exists():
        return []
    try:
        d = json.loads(sp.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [str(x) for x in (d.get("test") or [])]


def emit_block(reason: str) -> "int":
    """Print the reason to stderr and return exit code 2 (Claude Code: block + feed
    stderr back to the model)."""
    print(reason, file=sys.stderr)
    return 2


def core_importable() -> bool:
    """Best-effort: make ``cap_evolve`` importable from the repo or $CAPEVOLVE_CORE."""
    try:
        import cap_evolve  # noqa: F401
        return True
    except Exception:
        pass
    cand = os.environ.get("CAPEVOLVE_CORE")
    roots = [cand] if cand else []
    here = Path(__file__).resolve()
    for parent in here.parents:
        roots.append(str(parent / "core"))
    for r in roots:
        if r and (Path(r) / "cap_evolve" / "__init__.py").exists():
            sys.path.insert(0, r)
            try:
                import cap_evolve  # noqa: F401
                return True
            except Exception:
                continue
    return False
