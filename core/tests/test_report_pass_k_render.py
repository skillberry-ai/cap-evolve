"""report.md renders exactly the ks that were MEASURED — no invented, no dropped.

Issue #112 is about never printing a statistic that wasn't computed. A hardcoded
`for k in (1, 2)` re-introduced that defect from the other direction: with a
non-default `ks` (gepa.py already passes one) it dropped a real pass^3 and
fabricated a `pass^2=N/A` nobody requested.
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


def _run_report(tmp_path, pass_k):
    """Write a minimal run dir with the given pass_k dict, run report, return report.md."""
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget())
    (rd.root / "final.json").write_text(
        json.dumps({"test": {"reward": 0.9, "pass_k": pass_k}, "best_id": "cand_0001"}),
        encoding="utf-8")

    scripts = REPO / "skills" / "phases" / "report" / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("report_run_test", scripts / "run.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            assert mod.main(["--run-dir", str(rd.root), "--no-dashboard"]) == 0
    finally:
        sys.path.remove(str(scripts))
    return (rd.root / "report.md").read_text()


def test_nondefault_ks_renders_measured_k3_and_never_invents_k2(tmp_path):
    md = _run_report(tmp_path, {"1": 0.9, "3": 0.4})
    assert "pass^3=0.400" in md, md          # measured — must be shown
    assert "pass^2" not in md, md            # never requested — must NOT be invented
    assert "pass^1=0.900" in md, md


def test_single_trial_renders_only_k1(tmp_path):
    md = _run_report(tmp_path, {"1": 1.0})
    assert "pass^1=1.000" in md, md
    assert "pass^2" not in md, md            # was 'pass^2=N/A' under the hardcoded range


def test_legacy_scalar_pass_k_still_renders(tmp_path):
    # report/scripts/check.py writes this shape.
    md = _run_report(tmp_path, 0.7)
    assert "pass^1=0.700" in md, md
