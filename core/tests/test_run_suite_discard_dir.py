"""The kept-run swap must not be blocked by files our account cannot delete.

Run 36466624841 finished but could not replace the kept spreadsheetbench slot: four output dirs in
the old slot were owned by the sandbox container's uid, `rm -rf` of the slot stopped partway, and
the `&&` before the `mv` skipped the swap, leaving the old slot half-deleted. `_discard_dir` renames
the path away first (needs write access only on the parent), so the path is always freed.
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"


def _function() -> str:
    src = RUN_SUITE.read_text(encoding="utf-8")
    start = src.index("_discard_dir() {")
    return src[start:src.index("\n}\n", start) + 3]


def _run(script: str, env_path: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", "set -uo pipefail\n" + _function() + script],
                          capture_output=True, text=True, env={**os.environ, "PATH": env_path})


@pytest.mark.skipif(os.geteuid() == 0, reason="root can delete anything; the case cannot be built")
def test_an_undeletable_subtree_does_not_keep_the_path_occupied(tmp_path):
    slot = tmp_path / "slot"
    locked = slot / "outputs" / "run_tag"
    locked.mkdir(parents=True)
    (locked / "1_x_output.xlsx").write_bytes(b"PK")
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)  # like the container-owned dir: we cannot unlink in it
    (slot / "latest.json").write_text("{}")
    try:
        # A docker that fails, so the fallback delete fails too — the path must still be freed.
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        (fake_bin / "docker").write_text("#!/bin/sh\nexit 1\n")
        (fake_bin / "docker").chmod(0o755)
        proc = _run(f'_discard_dir "{slot}" && mkdir "{slot}" && echo SWAPPED',
                    f"{fake_bin}:/usr/bin:/bin")
        assert proc.returncode == 0, proc.stderr
        assert "SWAPPED" in proc.stdout
        assert slot.is_dir() and not any(slot.iterdir()), "the path was not freed for the new slot"
        assert "could not fully delete" in proc.stderr
    finally:
        for p in tmp_path.rglob("*"):
            if p.is_dir():
                p.chmod(0o755)


def test_a_missing_path_is_a_no_op(tmp_path):
    proc = _run(f'_discard_dir "{tmp_path / "absent"}" && echo OK', os.environ["PATH"])
    assert proc.returncode == 0 and "OK" in proc.stdout


def test_a_plain_directory_is_deleted(tmp_path):
    d = tmp_path / "plain"
    (d / "a").mkdir(parents=True)
    proc = _run(f'_discard_dir "{d}" && echo OK', os.environ["PATH"])
    assert proc.returncode == 0 and "OK" in proc.stdout
    assert not any(tmp_path.iterdir())


def test_every_delete_of_a_container_touched_dir_goes_through_it():
    src = RUN_SUITE.read_text(encoding="utf-8")
    assert 'rm -rf "$SB_LATEST_DIR"' not in src and 'rm -rf "$STAGE"' not in src
    assert 'rm -rf "${SB_DATA:?}/outputs"' not in src
    assert '_discard_dir "$SB_LATEST_DIR" && mv "$STAGE" "$SB_LATEST_DIR"' in src
