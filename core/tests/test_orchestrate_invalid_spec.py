"""orchestrate reports a broken capevolve.yaml cleanly (file name + line), not a traceback."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "orchestrate" / "orchestrate" / "scripts"


def _load_run():
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("orchestrate_run_t10", SCRIPTS / "run.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(SCRIPTS))


def test_unclosed_quote_spec_returns_1_with_file_and_line(tmp_path, capsys):
    # no importorskip: the built-in reader (no PyYAML) refuses it in strict mode too
    bad = tmp_path / "bad.yaml"
    bad.write_text('algorithm_skill: hill-climb\nmax_usd: "5\n')
    run = _load_run()
    rc = run.main(["--spec", str(bad)])
    assert rc == 1
    err = capsys.readouterr().err
    assert str(bad) in err
    assert "line" in err


def test_non_utf8_spec_returns_1_without_a_traceback(tmp_path, capsys):
    bad = tmp_path / "capevolve.yaml"
    bad.write_bytes(b"max_usd: 5\nrun_name: \xff\xfe\n")
    run = _load_run()
    rc = run.main(["--spec", str(bad)])
    assert rc == 1
    err = capsys.readouterr().err
    assert str(bad) in err and "not UTF-8" in err and "Traceback" not in err
