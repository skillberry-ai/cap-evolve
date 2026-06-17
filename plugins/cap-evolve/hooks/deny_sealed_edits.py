#!/usr/bin/env python3
"""PreToolUse(Edit|Write) — deny edits that would leak or poison the sealed test.

The held-out test split is the headline number; an optimizer that can edit the
test rollouts, the test ids in ``splits.json``, or a ``*test*gold*`` answer key
could silently inflate it. This hook is CORE-OWNED (not skill markdown), so a
model that rewrites its own instructions still cannot get past it: Claude Code
runs this script and an exit code of 2 blocks the tool call and feeds the reason
back to the model.

Blocks an ``Edit``/``Write`` whose ``tool_input.file_path`` is:
  * the run's ``splits.json`` (carries the seal + the test id list);
  * anything under ``rollouts/test/`` of the active run (the held-out rollouts);
  * a gold/answer-key file: path matches ``*test*gold*`` or ``*gold*test*``
    (case-insensitive) — the canonical answers the scorer grades against;
  * a per-task file whose stem is exactly a sealed test id under any
    ``rollouts/test``-like directory.

No-ops (exit 0) when outside a CapEvolve run dir, when the tool is not
Edit/Write, or when no file_path is present. Fails open on internal error.
"""

from __future__ import annotations

import fnmatch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _hooklib as H  # noqa: E402


def _is_gold(path_str: str) -> bool:
    low = path_str.lower()
    return fnmatch.fnmatch(low, "*test*gold*") or fnmatch.fnmatch(low, "*gold*test*")


def decide(payload: dict) -> int:
    tool = payload.get("tool_name") or ""
    if tool not in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        return 0

    tin = payload.get("tool_input") or {}
    fp = tin.get("file_path") or tin.get("path") or tin.get("notebook_path")
    if not fp:
        return 0
    target = Path(str(fp))
    tstr = str(target)

    # Gold/answer-key files are denied regardless of run-dir context: they are the
    # scorer's ground truth wherever they live.
    if _is_gold(tstr):
        return H.emit_block(
            f"cap-evolve: refusing to edit a gold/answer-key file ({tstr}). "
            "The scorer grades against gold; editing it poisons every score. "
            "Optimize the capability (skill/tool/prompt), not the answer key."
        )

    cwd = H.hook_cwd(payload)
    run_dir = H.find_run_dir(cwd)
    if run_dir is None:
        return 0  # not inside a CapEvolve run — silent
    run_dir = run_dir.resolve()

    # A relative file_path is reported relative to the session cwd (the Claude Code
    # hook contract supplies ``cwd`` for exactly this). Resolving it against the hook
    # PROCESS cwd instead would let a relative path to splits.json / rollouts/test
    # slip past every run-dir check below (it would never match the absolute run dir).
    try:
        if not target.is_absolute():
            target = (Path(cwd) / target)
        rt = target.resolve()
    except Exception:
        rt = target

    # splits.json of this run: editing it could move ids out of test or flip the seal.
    if rt == (run_dir / "splits.json").resolve():
        return H.emit_block(
            f"cap-evolve: refusing to edit {tstr} — this run's splits.json holds the "
            "sealed test partition and the seal flag. The split is frozen once, with a "
            "seed; re-partitioning would invalidate the honest test number."
        )

    # Anything under rollouts/test/ of the active run is the held-out evaluation.
    test_roll = (run_dir / "rollouts" / "test").resolve()
    try:
        rt.relative_to(test_roll)
        return H.emit_block(
            f"cap-evolve: refusing to edit {tstr} — it lives under the sealed test "
            "rollouts (rollouts/test/). Test rollouts are written once by finalize; "
            "editing them leaks/poisons the held-out set."
        )
    except ValueError:
        pass

    # A file named for a sealed test id sitting in any rollouts/test-like dir.
    sealed = set(H.load_sealed_test_ids(run_dir))
    if sealed and "test" in {p.lower() for p in rt.parts}:
        if rt.stem in sealed or any(rt.stem.startswith(tid + "__") for tid in sealed):
            return H.emit_block(
                f"cap-evolve: refusing to edit {tstr} — its name matches a sealed test "
                f"task id under a test rollout directory. Held-out test artifacts are "
                "read-only outside finalize()."
            )

    return 0


def main() -> int:
    try:
        payload = H.read_payload()
        return decide(payload)
    except Exception as e:  # fail open: never wedge an unrelated session
        print(f"cap-evolve deny_sealed_edits hook: internal error ignored: {e}",
              file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
