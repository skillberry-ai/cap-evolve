"""Scoring must be able to rewrite the container-created output file.

The sandbox container runs as uid 1000 and creates `<n>_<id>_output.xlsx` at its umask, so
the file is NOT writable by the (different-uid) runner user. Scoring then needs to rewrite it:
`just_open_libreoffice` recalculates cached formula values into a /tmp tempdir and moves the
result back — cross-filesystem, so `shutil.move` falls back to `copy2`, which opens the
existing file for WRITING and fails with `[Errno 13] Permission denied`. The adapter swallowed
that, so recalculation silently never ran and every score was a floor (issue #256).

`chmod` cannot fix it — you may not chmod a file you do not own — hence the replace-with-a-copy
approach exercised here.

Note on fidelity: creating a file owned by a *different uid* needs root, so these tests use an
unwritable-mode file, which reproduces the same `EACCES`-on-open-for-write that the foreign-uid
case produces. The directory-level permissions the fix depends on (write+execute, non-sticky)
are asserted directly instead.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"


def _load_adapter_module():
    """Import the adapter template for its pure helpers.

    ``model_config.py`` sits in ``templates/adapters/`` and is copied *alongside* the adapter
    by ``run_suite.sh``, so that dir goes on the path too. litellm/pandas are imported lazily
    inside functions, so they are not needed here.
    """
    import importlib.util
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _unwritable_file(d: Path) -> Path:
    """A readable-but-not-writable file, standing in for a container-owned output."""
    p = d / "1_42_output.xlsx"
    p.write_bytes(b"PK\x03\x04original-workbook-bytes")
    os.chmod(p, 0o444)
    return p


def test_shutil_move_over_an_unwritable_file_fails_without_the_fix():
    """Pins the underlying failure the fix exists for — the cross-filesystem copy2 path."""
    d = Path(tempfile.mkdtemp())
    os.chmod(d, 0o777)
    dest = _unwritable_file(d)
    src = Path(tempfile.mkdtemp()) / "recalculated.xlsx"
    src.write_bytes(b"PK\x03\x04recalculated-bytes")
    try:
        # copy2 is what shutil.move falls back to across filesystems.
        shutil.copy2(src, dest)
    except PermissionError as e:
        assert e.errno == 13
        return
    raise AssertionError("expected PermissionError writing over an unwritable dest")


def test_reclaim_makes_the_file_writable_and_preserves_bytes():
    mod = _load_adapter_module()
    d = Path(tempfile.mkdtemp())
    os.chmod(d, 0o777)
    p = _unwritable_file(d)
    original = p.read_bytes()

    assert not os.access(p, os.W_OK)          # precondition: the failure state
    assert mod._reclaim_container_file(p) is True
    assert os.access(p, os.W_OK)              # now rewritable by us
    assert p.read_bytes() == original         # byte-identical: scoring reads the same workbook
    assert not list(d.glob("*.hostcopy"))     # no temp litter left behind


def test_reclaim_then_move_succeeds():
    """The end-to-end shape scoring needs: reclaim, then the recalc move-back works."""
    mod = _load_adapter_module()
    d = Path(tempfile.mkdtemp())
    os.chmod(d, 0o777)
    dest = _unwritable_file(d)
    src = Path(tempfile.mkdtemp()) / "recalculated.xlsx"
    src.write_bytes(b"PK\x03\x04recalculated-bytes")

    assert mod._reclaim_container_file(dest) is True
    shutil.copy2(src, dest)                   # what previously raised EACCES
    assert dest.read_bytes() == b"PK\x03\x04recalculated-bytes"


def test_reclaim_is_a_noop_when_already_writable():
    mod = _load_adapter_module()
    d = Path(tempfile.mkdtemp())
    p = d / "out.xlsx"
    p.write_bytes(b"mine")
    inode = p.stat().st_ino
    assert mod._reclaim_container_file(p) is True
    assert p.stat().st_ino == inode, "must not needlessly replace a file we already own"


def test_per_rollout_dir_is_writable_and_not_sticky():
    """The fix relies on directory permissions: replace needs w+x, and sticky would block it
    (with sticky set, only the file's owner may rename/unlink it — which is the whole problem)."""
    mod = _load_adapter_module()
    d = Path(tempfile.mkdtemp())
    per_rollout = d / "42_0_abc"
    per_rollout.mkdir()
    mod._make_container_writable(per_rollout)
    mode = per_rollout.stat().st_mode
    assert mode & 0o300 == 0o300, "need write+execute to replace files inside"
    assert not mode & 0o1000, "per-rollout dirs must NOT be sticky, or the replace is blocked"

    # The shared root IS sticky by design (concurrent rollouts must not delete each other's).
    shared = d / "outputs"
    shared.mkdir()
    mod._make_container_writable(shared, sticky=True)
    assert shared.stat().st_mode & 0o1000, "shared outputs root should stay sticky"


# ---- the failure is reported, not swallowed ------------------------------

def test_feedback_flags_a_failed_recalc_as_infrastructure():
    mod = _load_adapter_module()
    entry = {"instruction_type": "Cell-Level Manipulation", "answer_position": "H3:H5"}
    fb = mod._build_feedback(entry, [0, 0, 0], [], [1, 2, 3], True, recalc_failed=[1, 2, 3])
    assert "INFRASTRUCTURE" in fb
    assert "do not optimize against it" in fb


def test_feedback_unchanged_when_recalc_worked():
    mod = _load_adapter_module()
    entry = {"instruction_type": "Cell-Level Manipulation", "answer_position": "H3:H5"}
    fb = mod._build_feedback(entry, [1, 1, 1], [], [], True, recalc_failed=[])
    assert "INFRASTRUCTURE" not in fb
    assert "All checks passed" in fb
