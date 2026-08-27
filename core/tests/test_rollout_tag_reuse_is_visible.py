"""Re-measuring an existing tag REPLACES its rollouts, and nothing said so.

``evaluate_candidate`` writes ``<task>__<tag>__t{k}.json`` for ``k in range(n_trials)``, so a
second evaluation under a tag that already has rollouts overwrites ``t0..t9`` rather than adding
``t10..t19``. There is no trial accumulation. That is a defensible implementation choice; the
defect is that it happened **silently**, in a loop whose own guidance asks for the opposite.

Observed on smoke spreadsheetbench run 33046360451, round i1. ``round.py`` marked cand_2
``inconclusive`` (its verdict flipped between two byte-identical control replicates) and its
``reading`` field said "Re-run it with more trials before believing either answer". The agent
did exactly that — and re-measured the control under the EXISTING tag ``ctl_null_i1``, replacing
the 0.4967 reading with 0.5067. Net effect of 100 metric calls and ~30 minutes: still two
distinct replicates rather than three, and the replicate spread WIDENED from 0.0167 to 0.0267,
raising the bar the candidate had to clear. Nothing in the event stream, the state or the
dashboard marked the replacement; in the event stream it is indistinguishable from progress.

A warning, not a refusal: re-evaluating an existing tag is legitimate on ``--resume`` (a run
picks its champion's val score back up) and the harness must not break that. What it must not do
is let a measurement be destroyed without a record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _mk(tmp_path):
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=12)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=5))
    harness.ensure_splits(adapter, run_dir, seed=0)
    return adapter, seed, run_dir


def _events(run_dir, kind: str) -> list[dict]:
    out = []
    p = Path(run_dir.events_path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("kind") == kind:
            out.append(ev)
    return out


def test_reusing_a_tag_records_that_a_measurement_was_replaced(tmp_path):
    from cap_evolve import harness

    adapter, seed, run_dir = _mk(tmp_path)
    first = harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                                       n_trials=2, tag="ctl_null_i1")
    assert not _events(run_dir, "rollout_overwrite_warning"), (
        "a FIRST evaluation under a fresh tag overwrote nothing and must not warn")

    harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                               n_trials=2, tag="ctl_null_i1")

    warns = _events(run_dir, "rollout_overwrite_warning")
    assert len(warns) == 1, (
        "re-measuring an existing tag replaced its rollouts and left no record: "
        f"{[e.get('kind') for e in _events(run_dir, 'rollout_overwrite_warning')]}")
    w = warns[0]
    assert w.get("tag") == "ctl_null_i1" and w.get("split") == "val"
    assert w.get("prior_reward") == pytest.approx(first.reward), (
        "the warning must name the reading that was destroyed, which is the only place it "
        f"survives once the files are gone: {w}")
    assert w.get("prior_trials") == 2, f"the replaced trial count is not recorded: {w}"


def test_a_fresh_tag_never_warns_however_many_siblings_exist(tmp_path):
    """The fix must not cry wolf: distinct tags are the NORMAL case (every candidate and every
    control replicate gets its own), and a warning on those would train readers to ignore it."""
    from cap_evolve import harness

    adapter, seed, run_dir = _mk(tmp_path)
    for tag in ("ctl_null_i1", "ctl_null_i1r1", "ctl_null_i1r2", "cand_2"):
        harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                                   n_trials=1, tag=tag)

    assert not _events(run_dir, "rollout_overwrite_warning"), (
        "four distinct tags overwrote nothing, so nothing should have warned")


def test_the_replaced_reading_is_recoverable_from_the_warning_alone(tmp_path):
    """Why ``prior_reward`` and not just a "you overwrote this" flag: once ``t0..t9`` are gone
    the old number exists nowhere else unless a round table happened to capture it. On run
    33046360451 the 0.4967 replicate survived only because ``round_i1.json`` had already been
    written — had the agent re-measured before gating, the reading would have been lost."""
    from cap_evolve import harness

    adapter, seed, run_dir = _mk(tmp_path)
    r1 = harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                                    n_trials=2, tag="ctl")
    harness.evaluate_candidate(adapter, seed, run_dir=run_dir, split="val",
                               n_trials=2, tag="ctl")
    r3 = harness.split_result_from_rollouts(run_dir, "ctl", "val")

    w = _events(run_dir, "rollout_overwrite_warning")[0]
    assert w["prior_reward"] == pytest.approx(r1.reward)
    # On disk, only the newest measurement survives — which is exactly the problem.
    assert harness.split_result_from_rollouts(run_dir, "ctl", "val").reward == \
        pytest.approx(r3.reward)
