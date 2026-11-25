"""`python -m cap_evolve splits` gives a clean one-line error (no traceback) on bad input."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[1]


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(CORE))
    return subprocess.run([sys.executable, "-m", "cap_evolve", "splits", *args],
                          capture_output=True, text=True, env=env, cwd=cwd)


@pytest.mark.parametrize("args, needle", [
    (["--ids", "@nofile.txt"], "cannot read ids file"),
    (["--ids", "a,b,c", "--ratios", "0.5,0.5"], "need exactly 3 ratios"),
    (["--ids", "a,b,c", "--ratios", "x"], "must be 3 comma-separated numbers"),
    (["--ids", "a,b", "--ratios", "0,0,0"], "must not all be zero"),
    (["--ids", "a,b", "--ratios", "1,-1,1"], "numbers >= 0"),
])
def test_bad_input_clean_error(tmp_path, args, needle):
    r = _run(*args, cwd=tmp_path)
    assert r.returncode != 0
    assert "Traceback" not in r.stderr
    assert needle in r.stderr
    assert len(r.stderr.strip().splitlines()) == 1


def test_ids_file_that_is_not_utf8_gives_a_clean_error(tmp_path):
    (tmp_path / "ids.bin").write_bytes(b"a\n\xff\xfe\n")
    r = _run("--ids", "@ids.bin", cwd=tmp_path)
    assert r.returncode == 2
    assert "Traceback" not in r.stderr
    assert "cannot read ids file" in r.stderr and "not UTF-8" in r.stderr
    assert len(r.stderr.strip().splitlines()) == 1


def test_good_call_still_works(tmp_path):
    (tmp_path / "ids.txt").write_text("a\nb\nc\nd\n", encoding="utf-8")
    r = _run("--ids", "@ids.txt", "--ratios", "2,1,1", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    assert sorted(d["train"] + d["val"] + d["test"]) == ["a", "b", "c", "d"]
    assert len(d["train"]) == 2
