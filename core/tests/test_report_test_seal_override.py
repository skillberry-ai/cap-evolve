"""report must disclose a test-seal override instead of claiming "scored exactly once" (#799/#341)."""

import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

from cap_evolve.rundir import RunDir
from cap_evolve.splits import make_splits

REPO = Path(__file__).resolve().parents[2]


def _finalized_run(tmp_path, monkeypatch, override):
    rd = RunDir.create(tmp_path)
    rd.write_splits(make_splits([f"t{i}" for i in range(8)], seed=0))
    if override:
        (rd.rollouts / "test").mkdir(parents=True, exist_ok=True)
        (rd.rollouts / "test" / "t1__FINAL__t0.json").write_text("{}", encoding="utf-8")
        monkeypatch.setenv("CAPEVOLVE_ALLOW_TEST_RESCORE", "1")
    else:
        monkeypatch.delenv("CAPEVOLVE_ALLOW_TEST_RESCORE", raising=False)
    rd.begin_test_attempt()
    (rd.root / "final.json").write_text(
        json.dumps({"test": {"reward": 0.5}, "best_id": rd.best_id}), encoding="utf-8")
    rd.commit_test()
    return rd


def _report(rd):
    scripts = REPO / "skills" / "phases" / "report" / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("report_run_override_test", scripts / "run.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert mod.main(["--run-dir", str(rd.root), "--no-dashboard"]) == 0
    finally:
        sys.path.remove(str(scripts))
    out = buf.getvalue()
    summary = json.loads(out[out.index("{"):out.rindex("}") + 1])
    return (rd.root / "report.md").read_text(encoding="utf-8"), summary


def test_override_is_disclosed_in_report_and_summary(tmp_path, monkeypatch):
    md, summary = _report(_finalized_run(tmp_path, monkeypatch, override=True))
    assert "scored exactly once" not in md
    assert "WARNING" in md and "re-scored 1 time(s)" in md
    assert "CAPEVOLVE_ALLOW_TEST_RESCORE" not in md
    assert summary["test_rescore_override"]["used"] is True
    assert summary["test_rescore_override"]["count"] == 1


def test_normal_run_keeps_exactly_once_line(tmp_path, monkeypatch):
    md, summary = _report(_finalized_run(tmp_path, monkeypatch, override=False))
    assert "scored exactly once" in md
    assert "WARNING" not in md
    assert "test_rescore_override" not in summary
