"""Issue #404 item 2: the optimizer must be told when a run is ending.

``_augment_instructions`` threads the run's remaining iteration/spend budget into
the per-iteration prompt, with an explicit stronger nudge once this is likely the
last iteration -- so optional accumulators (META_INSIGHTS.md, FRAMEWORK_IMPROVEMENTS.md)
get a real signal instead of losing out to the required PROCESS.md every time.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

from cap_evolve import Budget, RunDir, harness  # noqa: E402


def test_last_iteration_gets_a_strong_nudge(tmp_path):
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="low", budget=Budget(max_iterations=2))
    run_dir.update_spent(iterations=1)  # one done -> this is iteration 2/2, the last one

    workdir = tmp_path / "work"
    workdir.mkdir()
    augmented = harness._augment_instructions("BASE INSTRUCTIONS", workdir, run_dir)

    assert "iteration 2/2" in augmented
    assert "LAST ITERATION" in augmented
    assert "META_INSIGHTS.md" in augmented and "FRAMEWORK_IMPROVEMENTS.md" in augmented
    assert "BASE INSTRUCTIONS" in augmented


def test_early_iteration_gets_a_plain_status_no_false_urgency(tmp_path):
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="early", budget=Budget(max_iterations=20))

    workdir = tmp_path / "work"
    workdir.mkdir()
    augmented = harness._augment_instructions("BASE INSTRUCTIONS", workdir, run_dir)

    assert "iteration 1/20 (19 after this one)" in augmented
    assert "LAST ITERATION" not in augmented


def test_near_usd_ceiling_also_triggers_the_last_iteration_nudge(tmp_path):
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="usd",
                             budget=Budget(max_iterations=20, max_usd=10.0))
    run_dir.update_spent(usd=9.0)  # 90% of max_usd spent, well under max_iterations

    workdir = tmp_path / "work"
    workdir.mkdir()
    augmented = harness._augment_instructions("BASE INSTRUCTIONS", workdir, run_dir)

    assert "LAST ITERATION" in augmented
    assert "$9.00/$10.00 spent (90%)" in augmented


if __name__ == "__main__":
    import tempfile
    for fn in (test_last_iteration_gets_a_strong_nudge,
               test_early_iteration_gets_a_plain_status_no_false_urgency,
               test_near_usd_ceiling_also_triggers_the_last_iteration_nudge):
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"ok: {fn.__name__}")
    print("all ok")
