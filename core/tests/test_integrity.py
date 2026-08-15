"""Protected-path tamper detection: a manifest an optimizer cannot talk its way past."""

import os
import stat

import pytest

from cap_evolve.integrity import (
    read_manifest,
    set_readonly,
    snapshot,
    verify,
    write_manifest,
)

PATTERNS = ["tasks/*", "*gold*", "conftest.py", "*/conftest.py"]


def _project(tmp_path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "t1.json").write_text('{"q": 1}')
    (tmp_path / "tasks" / "nested").mkdir()
    (tmp_path / "tasks" / "nested" / "t2.json").write_text('{"q": 2}')
    (tmp_path / "gold.json").write_text('{"a": 42}')
    (tmp_path / "conftest.py").write_text("# fixtures\n")
    (tmp_path / "SKILL.md").write_text("# the capability, freely editable\n")
    return tmp_path


def test_round_trip_clean_verify(tmp_path):
    root = _project(tmp_path)
    man = snapshot(root, PATTERNS)
    rep = verify(man, root)
    assert rep.ok and rep.to_dict()["modified"] == []
    # The capability itself is NOT protected — editing it must stay legal.
    (root / "SKILL.md").write_text("# improved\n")
    assert verify(man, root).ok


def test_patterns_select_expected_files(tmp_path):
    root = _project(tmp_path)
    files = snapshot(root, PATTERNS)["files"]
    assert set(files) == {"tasks/t1.json", "tasks/nested/t2.json", "gold.json", "conftest.py"}
    assert list(files) == sorted(files), "manifest ordering must be deterministic"
    assert snapshot(root, PATTERNS) == snapshot(root, PATTERNS)


def test_detect_modified_byte(tmp_path):
    root = _project(tmp_path)
    man = snapshot(root, PATTERNS)
    (root / "gold.json").write_text('{"a": 43}')
    rep = verify(man, root)
    assert not rep.ok
    assert rep.modified == ["gold.json"]
    assert "TAMPERED" in rep.reason and "0.0" in rep.reason  # discard, don't score 0


def test_detect_added_protected_file(tmp_path):
    """A shadowing conftest.py / extra gold file is an attack that is only an addition."""
    root = _project(tmp_path)
    man = snapshot(root, PATTERNS)
    (root / "tasks" / "conftest.py").write_text("# shadows the real fixtures\n")
    rep = verify(man, root)
    assert not rep.ok and rep.added == ["tasks/conftest.py"]


def test_detect_removal(tmp_path):
    root = _project(tmp_path)
    man = snapshot(root, PATTERNS)
    (root / "tasks" / "nested" / "t2.json").unlink()
    rep = verify(man, root)
    assert not rep.ok and rep.removed == ["tasks/nested/t2.json"]


def test_manifest_atomic_round_trip(tmp_path):
    root = _project(tmp_path)
    man = snapshot(root, PATTERNS)
    path = tmp_path / "out" / "protected.json"
    path.parent.mkdir()
    write_manifest(path, man)
    assert read_manifest(path) == man
    assert not list(path.parent.glob(".*tmp*")), "no dangling temp file"


def test_set_readonly_preserves_exec_bit_and_never_raises(tmp_path):
    root = _project(tmp_path)
    script = root / "tasks" / "run.sh"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(0o755)
    man = snapshot(root, PATTERNS)

    set_readonly(root, man)

    mode = script.stat().st_mode
    assert not mode & stat.S_IWUSR, "write bit must be cleared"
    assert mode & stat.S_IXUSR, "git-tracked exec bit must survive (never chmod 0o444)"
    # Missing files / chmod-hostile filesystems must not blow up the run.
    set_readonly(root, {"files": {"does/not/exist": "deadbeef"}})
    script.chmod(0o755)  # leave tmp_path removable


def test_symlink_retarget_is_modified_and_escape_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.json").write_text('{"real": "gold"}')
    (outside / "other.json").write_text('{"other": "gold"}')
    root = tmp_path / "proj"
    root.mkdir()
    (root / "tasks").mkdir()
    link = root / "tasks" / "gold_link.json"
    link.symlink_to(outside / "secret.json")

    man = snapshot(root, ["tasks/*"])
    assert list(man["files"]) == ["tasks/gold_link.json"]
    assert verify(man, root).ok

    link.unlink()
    link.symlink_to(outside / "other.json")
    assert verify(man, root).modified == ["tasks/gold_link.json"]

    # A traversal escape never lands in the manifest.
    assert all(".." not in rel for rel in snapshot(root, ["*"])["files"])


def test_large_file_chunked_hash(tmp_path):
    import hashlib

    root = tmp_path
    (root / "tasks").mkdir()
    blob = (root / "tasks" / "big.bin")
    payload = os.urandom(3 << 20)  # > one 1 MiB chunk
    blob.write_bytes(payload)
    man = snapshot(root, ["tasks/*"])
    assert man["files"]["tasks/big.bin"] == hashlib.sha256(payload).hexdigest()
    blob.write_bytes(payload[:-1] + bytes([payload[-1] ^ 0xFF]))
    assert not verify(man, root).ok


@pytest.mark.parametrize("pattern,rel,expected", [
    ("tasks/*", "tasks/a/b.json", True),
    ("*gold*", "sub/dir/test_gold.txt", True),
    ("conftest.py", "sub/conftest.py", False),  # anchored; use */conftest.py
    ("*.py", "SKILL.md", False),
])
def test_glob_semantics(tmp_path, pattern, rel, expected):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")
    assert (rel in snapshot(tmp_path, [pattern])["files"]) is expected
