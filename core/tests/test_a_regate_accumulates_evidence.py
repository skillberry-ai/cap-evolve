"""Re-gating an iteration destroyed the very control readings its own table cited.

``round.py`` is careful about this in two places and inconsistent in the third:

* ``control_tag`` is per-ITERATION, and its docstring says why — "a fixed ``ctl_null`` tag makes
  each round's control OVERWRITE the previous round's on disk — destroying the one measurement
  that proves what zero change looked like at that point in the run. The noise floor is
  evidence."
* the round TABLE gets a ``.r<n>`` suffix on a same-iteration re-run rather than overwriting,
  "since a re-gate is usually being COMPARED with the first one".
* the control ROLLOUTS get neither. So the one operation ``round.py`` explicitly supports —
  re-gating the same iteration — preserves the summary and deletes the measurements it
  summarises, because rollouts are ``<task>__<tag>__t{k}.json`` for ``k in range(n_trials)`` and
  the second attempt writes the same ``ctl_null_i<N>`` / ``ctl_null_i<N>r1`` tags.

Measured on smoke spreadsheetbench run 33046360451, where the driver was told by an inconclusive
verdict to "re-run with more trials" and did exactly that:

    ctl_null_i1     0.4967  ->  0.5067   (replaced)
    ctl_null_i1r1   0.4800  ->  0.4367   (replaced)

200 of the run's 900 metric calls — about $2 and an hour of wall clock — bought no new evidence:
they swapped two readings for two other readings. The round's replicate spread went from 0.0167
to 0.0700, so the bar the candidate had to clear grew 4.2x, and ``round_i1.json`` was left citing
an ``evidence_bar`` of 0.0167 derived from two numbers that no longer exist anywhere on disk. Its
own re-gate table disagrees with it and only the second is reproducible.

Pooling is the whole point. Four byte-identical replicates of the same parent in the same round
are four samples of the same null — which is precisely the extra evidence a re-gate is run to
buy — so the second attempt should report the null over all four, not over its own two.
"""

from __future__ import annotations

import json


import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def _load_round():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ao_round_regate", SCRIPTS / "round.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


class _Spent:
    def __init__(self, iterations):
        self.iterations = iterations


class _RD:
    """Just enough RunDir for ``control_tag``."""
    def __init__(self, root, iterations=1):
        self.root = Path(root)
        self.spent = _Spent(iterations)


def test_a_regate_does_not_reuse_the_first_attempts_control_tags(tmp_path):
    rnd = _load_round()
    work = tmp_path / "work"
    work.mkdir()
    rd = _RD(tmp_path, iterations=1)

    first = rnd.control_tag(rd)
    # The first attempt's table on disk is what marks the iteration as already gated once.
    (work / "round_i1.json").write_text("{}", encoding="utf-8")
    second = rnd.control_tag(rd)

    assert first != second, (
        f"a re-gate of iteration 1 reuses the control tag {first!r}, so its rollouts "
        "(<task>__<tag>__t{k}.json) overwrite the first attempt's — the re-gate deletes the "
        "measurements its own first table cites")
    assert first in second or "i1" in second, (
        f"the re-gate's control tag {second!r} must still name the iteration it belongs to")


def test_the_control_tag_still_changes_between_iterations(tmp_path):
    """Control: the per-iteration property the existing docstring argues for must survive."""
    rnd = _load_round()
    (tmp_path / "work").mkdir()
    assert rnd.control_tag(_RD(tmp_path, 1)) != rnd.control_tag(_RD(tmp_path, 2))


def test_the_table_and_the_control_tags_agree_on_which_attempt_this_is(tmp_path):
    """The table name and the control tags are the two halves of one round's identity. If they
    are derived independently they can disagree — and then a reader cannot tell which table
    summarises which rollouts, which is the failure this whole file is about."""
    rnd = _load_round()
    work = tmp_path / "work"
    work.mkdir()
    rd = _RD(tmp_path, iterations=1)

    assert rnd.round_attempt(rd) == 0
    assert rnd.table_stem(rd) == "round_i1"
    (work / "round_i1.json").write_text("{}", encoding="utf-8")
    assert rnd.round_attempt(rd) == 1
    assert rnd.table_stem(rd) == "round_i1.r1"
    assert "1" in rnd.control_tag(rd).removeprefix("ctl_null_i1")
    (work / "round_i1.r1.json").write_text("{}", encoding="utf-8")
    assert rnd.round_attempt(rd) == 2


def test_a_regate_pools_the_earlier_attempts_replicates(tmp_path):
    """A second attempt's null must be computed over EVERY byte-identical replicate of this
    iteration, not just its own two. That is the extra evidence a re-gate is run to buy, and
    without pooling the re-gate throws away half the samples it has already paid for."""
    rnd = _load_round()
    work = tmp_path / "work"
    work.mkdir()
    rd = _RD(tmp_path, iterations=1)
    (work / "round_i1.json").write_text(json.dumps({
        "control_replicates": [{"tag": "ctl_null_i1", "reward": 0.4967},
                               {"tag": "ctl_null_i1r1", "reward": 0.48}],
    }), encoding="utf-8")

    prior = rnd.prior_attempt_controls(rd)
    tags = {r["tag"] for r in prior}
    assert tags == {"ctl_null_i1", "ctl_null_i1r1"}, (
        f"the earlier attempt's replicates are not recovered, so the re-gate's null is computed "
        f"over half the samples the round has paid for: {prior}")
    assert all(r.get("from_attempt") is not None for r in prior), (
        "a pooled replicate must say which attempt it came from, or the table cannot be audited")


def test_pooling_is_absent_when_this_is_the_first_attempt(tmp_path):
    """No false positives: a first attempt has nothing to pool and must say so, not invent rows."""
    rnd = _load_round()
    (tmp_path / "work").mkdir()
    assert rnd.prior_attempt_controls(_RD(tmp_path, 1)) == []


def test_round_warns_when_it_is_re_gating_rather_than_doing_it_silently():
    """A re-gate is a legitimate and expensive operation. The table must say it is one, because
    on the live run nothing in the output distinguished "second opinion on iteration 1" from
    "iteration 1" — the operator watching the event stream saw two identical control evaluations
    and no statement that the second had replaced the first."""
    src = (SCRIPTS / "round.py").read_text(encoding="utf-8")
    assert "round_attempt" in src and "prior_attempt_controls" in src
    assert '"attempt"' in src or "'attempt'" in src, (
        "the round table never states which attempt it is")


def test_the_end_to_end_regate_keeps_both_attempts_rollouts(tmp_path):
    """The property that actually matters, checked on real rollout files rather than tag strings:
    after a re-gate, BOTH attempts' control rollouts are still on disk and readable."""
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=12)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=3))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)

    rnd = _load_round()
    (run_dir.root / "work").mkdir(parents=True, exist_ok=True)
    rd = _RD(run_dir.root, iterations=1)
    first = rnd.control_tag(rd)

    # Rollouts live at rollouts/<split>/<task>__<tag>__t<k>.json (RunDir's own docstring).
    roll = run_dir.rollouts / "val"
    roll.mkdir(parents=True, exist_ok=True)
    for k in range(3):
        (roll / f"t1__{first}__t{k}.json").write_text("{}", encoding="utf-8")
    (run_dir.root / "work" / "round_i1.json").write_text("{}", encoding="utf-8")

    second = rnd.control_tag(rd)
    assert second != first, "the re-gate would write over the first attempt's rollout files"
    # The concrete files the second attempt would write must not collide with the first's.
    firsts = {p.name for p in roll.glob(f"*__{first}__t*.json")}
    seconds = {f"t1__{second}__t{k}.json" for k in range(3)}
    assert firsts and not (firsts & seconds), (
        f"the re-gate writes the same rollout filenames as the first attempt: "
        f"{sorted(firsts & seconds)}")
