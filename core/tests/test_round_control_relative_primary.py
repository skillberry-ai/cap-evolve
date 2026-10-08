"""issue #684 item 6: control-relative is the PRIMARY accept/reject signal, not a secondary
cross-check — reproducing the real run's exact ambiguous scenario end to end through round.py.

Confirmed bug: measurement drift between rounds (~0.10 on a real run) is comparable in
magnitude to the real effects being chased (~0.02-0.09). The gate used to treat the candidate's
delta against the PARENT's STORED reward (which can carry drift since the parent was last
measured) as primary, with the drift-free comparison against a freshly-measured byte-identical
control kept as a secondary diagnostic — backwards, and it required a manual
``grow.py``/driver escalation to resolve the two runs that hit exactly this disagreement.

This fixture builds that disagreement on purpose, through a real ``round.py`` invocation (not a
hand-typed table): the candidate TIES against the parent's stale, stored reward, but shows a
real, significant win against the control replicates measured fresh THIS round from the SAME
parent bytes. Asserts the top-level verdict — the one ``commit.py`` reads to decide accept vs
reject — now resolves ACCEPT directly, with no grow.py growth round needed.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from test_round_requires_screen_ladder import CORE, SCRIPTS, _project, _run

N = 20


def _solved_ids(val_ids: list[str], level: int) -> set[str]:
    """Which val ids SyntheticAdapter(n=N) solves at this capability level."""
    return {t for t in val_ids if int(t[1:]) < level}


def _stage(tmp_path):
    from cap_evolve import RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir, write_val_rollout

    adapter = SyntheticAdapter(n=N)
    project = _project(tmp_path, n=N, num_trials=1)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="chk")
    val_ids = [f"t{i}" for i in range(N)]
    harness.ensure_splits(adapter, run_dir, seed=0,
                          split_ids={"train": val_ids, "val": val_ids, "test": val_ids})

    # The PARENT's real on-disk bytes: level 10 — true adapter score 10/20 = 0.5. This is what
    # a FRESH control (a byte-identical copy, measured this round) will actually read.
    PARENT_LEVEL = 10
    # The CANDIDATE's bytes: level 13 — true adapter score 13/20 = 0.65.
    CAND_LEVEL = 13
    cand_true_solved = _solved_ids(val_ids, CAND_LEVEL)

    # The PARENT's STORED reward is stale: written as if it had already measured level 13 (a
    # plausible earlier reading that has since drifted from what the SAME bytes read today).
    # Pairing this against the candidate's TRUE level-13 pattern below ties every task exactly
    # — the "reward tie against stored parent" half of the scenario.
    for t in val_ids:
        write_val_rollout(run_dir, t, tag="cur",
                          reward=1.0 if t in cand_true_solved else 0.0, feedback="fb")
    run_dir.set_best("cur")
    run_dir.snapshot("cur", seed_capability_dir(tmp_path / "parent_cap", level=PARENT_LEVEL))

    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copytree(seed_capability_dir(tmp_path / "cand_src", level=CAND_LEVEL), work / "cand_1")
    return run_dir, project, work, val_ids


_JUSTIFY = ["--single-candidate-justification",
           "control-relative-primary fixture: single candidate by design"]


def test_control_relative_primary_resolves_the_tie_vs_stored_parent_as_accept(tmp_path):
    run_dir, project, work, val_ids = _stage(tmp_path)
    p = _run([str(SCRIPTS / "round.py"), "--run-dir", str(run_dir.root),
             "--project", str(project), "--candidates", "cand_1", "--n-trials", "1",
             "--skip-screen-justification", "fixture: screen ladder not under test",
             *_JUSTIFY])
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    row = out["candidates"][0]

    # The SECONDARY diagnostic (raw vs the stored parent) is the tie this test engineered: no
    # evidence either way, exactly the ambiguity a real run hit.
    assert row["raw_vs_parent"]["verdict"] != "accept", (
        "fixture is wrong: the raw-vs-stored-parent comparison must NOT be a clean accept "
        f"on its own (row={row})")

    # The PRIMARY verdict — what commit.py actually reads — is now control-relative, and a
    # real, significant win against the freshly-measured control resolves it ACCEPT directly.
    assert row["verdict"] == "accept", (
        f"control-relative was not promoted to the primary signal: {row}")
    assert out["primary_signal"] == "control"

    # The backward-compatible field commit.py/dashboard already read agrees with the (now
    # primary) top-level verdict — no disagreement left for --reject-basis drift_control to
    # resolve, and no grow.py escalation is needed to reach this accept.
    assert row["control_relative"]["verdict"] == "accept"
    assert row["control_relative"]["gate_delta"] == row["gate_delta"]

    # No grow.py growth round was ever created for this candidate.
    assert not list((run_dir.root / "work").glob("grow_cand_1_r*.json"))
