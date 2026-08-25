"""The benchmarks suite can run `agent-optimize`, not only the hill-climb variants.

Three things had to change and each is pinned here:

  1. **run_suite.sh's algorithm selection.** It hardcoded `algorithm_skill: hill-climb`,
     so agent-optimize was unreachable — and selecting it without
     `orchestration_mode: agent` is refused outright by the algorithm itself. The block is
     executed as real bash (same approach as test_run_suite_split_hook.py) rather than
     grepped, because the thing that breaks is shell behaviour, not text.
  2. **Back-compat.** The dispatch input was renamed `algorithm_focus` -> `algorithm`, but
     committed `overrides.env` files and hand-run operators still export ALGORITHM_FOCUS.
     A silent change of focus would quietly alter what a published number means.
  3. **The CI report still renders.** metrics.py builds its iteration timeline from `step`
     events, which agent mode only produces because `commit.py` books each decision through
     `harness.record_iteration`. That coupling is load-bearing and untested, so it is
     pinned here: without it an agent-mode run reports zero iterations and an empty
     timeline while still exiting 0.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"
sys.path.insert(0, str(REPO / "ci" / "benchmarks" / "lib"))

MARK_START = "# ---- algorithm selection"
MARK_END = "# ---- end algorithm selection"


def _algorithm_block() -> str:
    """Lift the algorithm-selection block verbatim out of run_suite.sh."""
    src = RUN_SUITE.read_text(encoding="utf-8")
    start = src.index(MARK_START)
    end = src.index(MARK_END, start)
    return src[start:end]


def _select(**env: str) -> dict:
    """Run the real block with the given environment; return the variables it set."""
    script = _algorithm_block() + (
        '\nprintf "%s\\n%s\\n%s\\n%s\\n" '
        '"$ALGO_SKILL" "$ALGO_FOCUS" "$ORCH_MODE" "$STOP_CONDITION"\n')
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", **env})
    assert p.returncode == 0, f"block failed: {p.stderr}"
    skill, focus, mode, stop = (p.stdout.split("\n") + ["", "", "", ""])[:4]
    return {"skill": skill, "focus": focus, "mode": mode, "stop": stop,
            "stderr": p.stderr}


# --------------------------------------------------------------------------- 1


@pytest.mark.parametrize("value,focus", [
    ("hill-climb-all", "all"),
    ("hill-climb-cyclic", "cyclic"),
    ("hill-climb-hardest-first", "hardest-first"),
])
def test_hill_climb_variants_stay_deterministic(value, focus):
    got = _select(ALGORITHM=value)
    assert got["skill"] == "hill-climb"
    assert got["focus"] == focus
    assert got["mode"] == "deterministic", (
        "a hill-climb dispatch must not be switched into agent mode")
    assert got["stop"] == "", (
        "stop_condition is agent-mode's stopping rule; a deterministic run is bounded by "
        "max_iterations and must not carry one")


def test_default_is_the_previous_behaviour():
    """No ALGORITHM set at all == what every existing dispatch already did."""
    got = _select()
    assert (got["skill"], got["focus"], got["mode"]) == ("hill-climb", "all", "deterministic")


def test_agent_optimize_selects_agent_mode():
    got = _select(ALGORITHM="agent-optimize")
    assert got["skill"] == "agent-optimize"
    assert got["mode"] == "agent", (
        "agent-optimize refuses a deterministic invocation — selecting it without "
        "orchestration_mode: agent would fail the run outright")
    assert got["focus"] == "", "focus is a hill-climb concept and must not be emitted"
    assert got["stop"], "agent mode without a stop_condition has no stopping rule"


def test_agent_optimize_stop_condition_is_derived_from_the_dispatch_inputs():
    """The same inputs must bound both algorithms, or the two are not comparable."""
    got = _select(ALGORITHM="agent-optimize", ITERATIONS="7",
                  OPTIMIZER_USD_PER_ITER="4.0", GATE_K_SE="0.2")
    stop = got["stop"]
    assert "7" in stop, f"ITERATIONS did not reach the stop_condition: {stop}"
    assert "28" in stop, (
        "the USD ceiling should be the per-iteration cap x iterations (4.0 x 7 = 28), "
        f"since the whole loop is one process: {stop}")
    assert "finalize" in stop or "measure" in stop, (
        f"the stop_condition must require a seal — no finalize, no result: {stop}")


def test_rejections_are_not_a_stopping_condition():
    """The clause that ended a run exactly where the algorithm prescribes escalation.

    The derived stop_condition used to say "stop when two consecutive rounds are rejected".
    SKILL.md says the opposite: "after two rejected rounds, read the candidate's TRACE before
    writing a third" — a reject usually means the edit FORM was wrong, not that the search is
    done. On smoke run 32701056043 the agent rejected two prose candidates and stopped, never
    reaching the round where it would have tried a code-level guard, which its own reject note
    ("require calculate tool for all money") had already identified as the right form.

    Rounds and spend bound a run. Rejections bound nothing.
    """
    got = _select(ALGORITHM="agent-optimize", ITERATIONS="5")
    stop = got["stop"].lower()

    assert "two consecutive" not in stop, (
        f"rejections are still a stopping condition: {got['stop']}")
    assert "do not stop early merely because rounds were rejected" in stop, (
        f"the stop_condition does not say that a rejection is not a reason to stop: "
        f"{got['stop']}")
    assert "change the edit form" in stop or "change the edit" in stop, (
        f"the stop_condition does not point at escalation as the response to a reject: "
        f"{got['stop']}")
    # The real ceilings must survive.
    assert "5" in stop and "spend.py" in stop


MARK_HOST_START = "# ---- agent mode: drive the handed-off loop"
MARK_HOST_END = "# ---- metrics + report"


def _host_budget(**env: str) -> dict:
    """Run the agent-mode host-invocation block and report the budget it computes."""
    src = RUN_SUITE.read_text(encoding="utf-8")
    block = src[src.index(MARK_HOST_START):src.index(MARK_HOST_END)]
    # Stub the host call itself: this test is about the arithmetic, not the subprocess.
    block = block.replace('"$PY" "$REPO/skills/algorithms/agent-optimize/scripts/host.py" \\',
                          'echo HOSTCALL \\')
    script = ('ORCH_MODE=agent\nITER="${ITERATIONS:-3}"\nPY=python3\nREPO=.\nBENCH=tau2\n'
              'RUN_DIR=/tmp/x\nPROJ=/tmp/y\nOPTIMIZER_MODEL=m\n' + block +
              '\nprintf "TURNS=%s\\nUSD=%s\\n" "$HOST_TURNS" "${HOST_USD_ARGS[*]-}"\n')
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", **env})
    assert p.returncode == 0, f"block failed: {p.stderr}"
    out = {}
    for ln in p.stdout.splitlines():
        if "=" in ln and ln.split("=", 1)[0] in ("TURNS", "USD"):
            k, v = ln.split("=", 1)
            out[k] = v.strip()
    return out


def test_agent_mode_gets_its_own_turn_allowance_not_the_per_iteration_one():
    """80 turns/iteration is a DETERMINISTIC-path unit and starves the agent loop.

    There, one optimizer invocation means "propose one edit and stop" — the harness does the
    diagnosis, evaluation and gating. In agent mode the same allowance must also cover Phase 0
    reading, diagnose, null-control replicates, round.py orchestration, gate_check and
    commit.py, per round.

    Measured on run 32733635494: 240 turns (80 x 3) bought 1.9 rounds. The agent stopped on
    error_max_turns having evaluated a candidate at val 0.530 — the best of the run — and never
    reached the commit.py that would have booked it. So the run reported 1 of 3 rounds and
    discarded its best result.
    """
    got = _host_budget(ITERATIONS="3", OPTIMIZER_MAX_TURNS="80")
    turns = int(got["TURNS"])

    assert turns > 240, (
        f"agent mode still gets the per-iteration allowance ({turns}) — the budget that was "
        "measured to buy 1.9 of 3 rounds")
    # Per round it must clear the ~126 turns/round that run actually consumed, with the
    # non-round work (Phase 0, the seal) paid for on top.
    assert turns / 3 >= 150, (
        f"{turns} turns over 3 rounds is {turns / 3:.0f}/round; the measured requirement is "
        "~126/round before Phase 0 and finalize")


def test_a_raised_optimizer_max_turns_is_still_honoured():
    """The dispatch input must remain the operator's lever, not be clamped by the floor."""
    low = int(_host_budget(ITERATIONS="3", OPTIMIZER_MAX_TURNS="80")["TURNS"])
    high = int(_host_budget(ITERATIONS="3", OPTIMIZER_MAX_TURNS="400")["TURNS"])
    assert high > low, (
        f"raising optimizer_max_turns 80 -> 400 did not raise the host budget ({low} -> {high})")


def test_more_rounds_buy_more_turns():
    three = int(_host_budget(ITERATIONS="3", OPTIMIZER_MAX_TURNS="80")["TURNS"])
    ten = int(_host_budget(ITERATIONS="10", OPTIMIZER_MAX_TURNS="80")["TURNS"])
    assert ten > three, f"the turn budget does not scale with the round count ({three}, {ten})"


def test_unlimited_optimizer_budget_yields_no_dollar_ceiling():
    """0 means unlimited everywhere else in this workflow; keep that meaning."""
    got = _select(ALGORITHM="agent-optimize", ITERATIONS="10", OPTIMIZER_USD_PER_ITER="0")
    assert "$0" not in got["stop"], (
        f"a 0 (unlimited) cap must not become a $0 ceiling: {got['stop']}")


def test_unknown_algorithm_fails_loudly():
    script = _algorithm_block()
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "ALGORITHM": "gepa-typo"})
    assert p.returncode != 0, (
        "an unrecognised algorithm must abort — silently falling back to hill-climb "
        "publishes a number under the wrong algorithm's name")
    assert "gepa-typo" in (p.stderr + p.stdout)


def _yaml_block() -> str:
    """Lift the spec-rendering block too — it turns those variables into capevolve.yaml."""
    src = RUN_SUITE.read_text(encoding="utf-8")
    start = src.index("# The algorithm block above chose the skill")
    end = src.index('BASE="$REPO/ci/benchmarks/$BENCH/$TIER"', start)
    return src[start:end]


def _rendered_spec(**env: str) -> dict:
    """Run selection + rendering, then parse the emitted YAML the way core does."""
    from cap_evolve.specfile import read_yaml

    script = _algorithm_block() + _yaml_block() + '\nprintf "%s\\n" "$ALGO_YAML"\n'
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "PY": sys.executable, **env})
    assert p.returncode == 0, f"render failed: {p.stderr}"
    return read_yaml(p.stdout) or {}


def test_the_agent_mode_spec_it_writes_is_valid_yaml():
    """The stop_condition is a paragraph containing ':' and '$'.

    Interpolated raw it produces a spec that either fails to parse or — far worse — parses
    with the prose silently truncated at the first colon, leaving the agent with a stopping
    rule nobody wrote. Hence json.dumps; hence this test parses the real output.
    """
    spec = _rendered_spec(ALGORITHM="agent-optimize", ITERATIONS="4",
                          OPTIMIZER_USD_PER_ITER="2.5", GATE_K_SE="0.2", NUM_TRIALS="3")

    assert spec.get("algorithm_skill") == "agent-optimize"
    assert spec.get("orchestration_mode") == "agent"
    assert "algorithm_focus" not in spec

    stop = spec.get("stop_condition") or ""
    # Round-trip intact: the whole paragraph, not a fragment ending at a colon.
    assert stop.endswith("a run with no finalize has no result."), (
        f"the stop_condition was truncated in the emitted YAML: {stop!r}")
    assert "$10.00" in stop, f"2.5 x 4 rounds should give a $10.00 ceiling: {stop!r}"
    assert "gate_k_se=0.2" in stop and "3 trial(s)" in stop


def test_the_deterministic_spec_it_writes_is_unchanged_in_shape():
    spec = _rendered_spec(ALGORITHM="hill-climb-hardest-first")
    assert spec.get("algorithm_skill") == "hill-climb"
    assert spec.get("algorithm_focus") == "hardest-first"
    assert "orchestration_mode" not in spec, (
        "a deterministic run must not carry an orchestration_mode key at all — core's "
        "default is what every existing run used")
    assert "stop_condition" not in spec


# --------------------------------------------------------------------------- 2


@pytest.mark.parametrize("focus", ["all", "cyclic", "hardest-first"])
def test_legacy_algorithm_focus_is_still_honoured(focus):
    got = _select(ALGORITHM_FOCUS=focus)
    assert (got["skill"], got["focus"], got["mode"]) == ("hill-climb", focus, "deterministic")


def test_algorithm_wins_over_the_legacy_alias():
    got = _select(ALGORITHM="hill-climb-cyclic", ALGORITHM_FOCUS="hardest-first")
    assert got["focus"] == "cyclic", (
        "the explicit new input must win; otherwise a stale exported alias silently "
        "overrides a deliberate dispatch choice")


# --------------------------------------------------------------------------- 3


def test_agent_mode_rounds_render_in_the_ci_iteration_timeline(tmp_path):
    """metrics.py's timeline is built from `step` events, and agent mode must emit them.

    This is a coupling, not a coincidence: `commit.py` books a decision through
    `harness.record_iteration`, which writes the canonical `step` record every consumer
    reads. Nothing in the agent's own prose obliges it to — so if commit.py ever stopped
    routing through record_iteration, an agent-mode CI run would still succeed while its
    report rendered "(no iteration events found)" and its iteration count stayed 0,
    which `assert_run.py --min-iterations 1` reads as a run that never optimized.

    Executed for real (commit.py against a live run dir), because the point is the
    integration, and a hand-written events.jsonl would pin only this test's assumptions.
    """
    import metrics
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=20)
    seed = seed_capability_dir(tmp_path, level=3)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ci", budget=Budget(max_iterations=5))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)

    work = run_dir.root / "work" / "cand_1"
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir.root / "candidates" / "seed", work)

    commit = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "commit.py"
    p = subprocess.run(
        [sys.executable, str(commit), "--run-dir", str(run_dir.root),
         "--candidate-id", "cand_1", "--from-dir", str(work),
         "--decision", "accept", "--val", "0.61", "--note", "a general rule"],
        capture_output=True, text=True,
        env={**os.environ, "CAPEVOLVE_CORE": str(REPO / "core")})
    assert p.returncode == 0, f"commit.py failed: {p.stdout}\n{p.stderr}"

    rows = [r for r in metrics.iteration_rows(str(run_dir.root), best_id="cand_1")
            if r["phase"] == "iterate"]
    assert len(rows) == 1, f"an agent-mode round produced no timeline row: {rows}"
    assert rows[0]["candidate"] == "cand_1"
    assert rows[0]["accepted"] is True
    assert rows[0]["reward"] == 0.61
    assert run_dir.spent.iterations == 1, (
        "the round did not charge an iteration — assert_run.py --min-iterations 1 would "
        "fail a run that really did optimize")


# --------------------------------------------------------------------------- workflow


def test_workflow_exposes_the_algorithm_input_within_githubs_ten_input_cap():
    src = WORKFLOW.read_text(encoding="utf-8")
    inputs = src[src.index("  workflow_dispatch:"):src.index("  pull_request:")]
    # Top-level input keys are indented exactly 6 spaces under `inputs:`.
    names = [ln.strip().rstrip(":") for ln in inputs.splitlines()
             if len(ln) - len(ln.lstrip()) == 6 and ln.rstrip().endswith(":")
             and not ln.strip().startswith("#")]
    assert "algorithm" in names, f"no `algorithm` dispatch input: {names}"
    assert "algorithm_focus" not in names, (
        "algorithm_focus was replaced by algorithm; keeping both would exceed the cap")
    assert len(names) <= 10, (
        f"workflow_dispatch allows at most 10 inputs; this file declares {len(names)}: "
        f"{names} — GitHub rejects the whole workflow as invalid")


def test_workflow_offers_every_algorithm_the_suite_can_run():
    src = WORKFLOW.read_text(encoding="utf-8")
    block = src[src.index("      algorithm:"):]
    block = block[:block.index("\n      #") if "\n      #" in block[:2000] else 2000]
    for opt in ("hill-climb-all", "hill-climb-cyclic", "hill-climb-hardest-first",
                "agent-optimize"):
        assert opt in block, f"the algorithm input does not offer {opt}: {block[:500]}"


def test_runmeta_records_which_algorithm_produced_the_number():
    src = WORKFLOW.read_text(encoding="utf-8")
    assert '"algorithm"' in src, (
        "runmeta.json must record the algorithm — benchmark-history compares numbers "
        "across runs, and hill-climb vs agent-optimize is not a like-for-like comparison")


# --- the iterations input was unreachable on smoke ---------------------------


def _env_expr(key: str) -> str:
    """The workflow's `env:` expression for one key, verbatim."""
    src = WORKFLOW.read_text(encoding="utf-8")
    for ln in src.splitlines():
        if ln.strip().startswith(f"{key}:") and "${{" in ln:
            return ln.split(":", 1)[1].strip()
    raise AssertionError(f"no env expression for {key} in {WORKFLOW}")


def test_an_explicit_iterations_dispatch_reaches_smoke():
    """`matrix.tier == 'smoke' && '3'` came FIRST, so it short-circuited the input.

    GitHub's `||` yields the first truthy operand, so with the tier pin leading, a dispatch of
    `iterations: 10` on smoke silently produced 3 — discoverable only by reading ITERATIONS in
    the job log, after the run had already spent its budget on the wrong round count. Smoke is
    the tier the algorithm itself gets iterated on, so it is the worst one to make unreachable.

    NUM_TRIALS already had this right, including the reason its input default is `""` (with a
    non-empty default, "asked for 10" and "asked for nothing" are indistinguishable). The two
    knobs must therefore have the SAME shape: input first, tier default second.
    """
    iters, trials = _env_expr("ITERATIONS"), _env_expr("NUM_TRIALS")

    assert iters.index("inputs.iterations") < iters.index("matrix.tier"), (
        "the tier pin still precedes the dispatch input, so an explicit `iterations` on smoke "
        f"is short-circuited away: {iters}")
    # Parity with the knob that already solved this, so the next edit to either notices.
    shape = lambda e: (e.index("inputs.") < e.index("matrix.tier"),  # noqa: E731
                       "'3'" in e, "'10'" in e)
    assert shape(iters) == shape(trials), (
        f"ITERATIONS and NUM_TRIALS disagree on precedence/defaults:\n  {iters}\n  {trials}")
    # Smoke's default must survive a blank dispatch: 3, not 10.
    assert "'3'" in iters and "smoke" in iters, (
        f"smoke's 3-iteration default was dropped rather than made overridable: {iters}")


def test_the_iterations_input_defaults_to_blank_so_the_tier_default_can_win():
    """A non-empty input default re-breaks the fix, silently, for every tier."""
    src = WORKFLOW.read_text(encoding="utf-8")
    block = src[src.index("      iterations:"):src.index("      trials:")]
    assert 'default: ""' in block, (
        "the `iterations` input must default to blank so a tier default is distinguishable "
        f"from a deliberate choice — otherwise smoke silently gets the input's number: {block}")
    assert "BLANK" in block or "blank" in block, (
        f"the input description must tell the operator blank means the tier default: {block}")
