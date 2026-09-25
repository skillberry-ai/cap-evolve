"""A blank-`trials` dispatch must produce a run that can actually finish.

`NUM_TRIALS` defaulted to 10 for every non-smoke tier. On the whole-set tiers that is a run
the `bench` job cannot complete inside its own `timeout-minutes`, and it contradicts the cost
model both tiers' READMEs publish (which quote `trials=1`):

    full           91·10 + 10·91·10 + 2·639·10 = 22,790 rollouts   (~167 h at the measured rate)
    full_verified  40·10 + 10·40·10 + 2·280·10 = 10,000 rollouts   (~73 h)

against `timeout-minutes: 1440`. Measured throughput anchor: 2.28 rollouts/min on run
35861572021 (spreadsheetbench smoke, CONCURRENCY=4, ~2 concurrent evals).

`trials=1` is not a loss of rigour: the dominant noise term is TASK COUNT, not trials. That
run measured val SE 0.158 on 10 tasks × 3 trials; 40 tasks × 1 projects to ≈0.079 and the
280-task sealed split to ≈0.030. Replication is `grow.py`'s job, bought only for candidates
that look promising.

WHY THE EXPRESSIONS ARE EVALUATED RATHER THAN PATTERN-MATCHED
    GitHub's `&&`/`||` short-circuit on truthiness, and for the string operands these inputs
    carry the semantics are identical to Python's: `''` is falsy, `'0'` is TRUTHY (only the
    NUMBER 0 is falsy). So the workflow expression can be translated one-for-one and evaluated,
    which tests the behaviour per tier instead of the spelling.
"""

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"
SB = REPO / "ci" / "benchmarks" / "spreadsheetbench"

# Tiers that evaluate a benchmark's whole (or whole verified) task set.
WHOLE_SET_TIERS = ("full", "full_verified")
ALL_TIERS = ("smoke", "pilot", "full", "full_verified")

# A blank dispatch of a whole-set tier must stay inside a budget a single job can finish.
# Derived from `timeout-minutes: 1440` and the 2.28 rollouts/min anchor above, with margin:
# 1440 min × 2.28 ≈ 3,280 rollouts is the hard ceiling, so cap the DEFAULT well under it.
MAX_DEFAULT_ROLLOUTS = 2500


def _env_expr(key: str) -> str:
    """The workflow's `env:` expression for one key, verbatim (see test_benchmarks_agent_optimize)."""
    for ln in WORKFLOW.read_text(encoding="utf-8").splitlines():
        if ln.strip().startswith(f"{key}:") and "${{" in ln:
            return ln.split(":", 1)[1].strip()
    raise AssertionError(f"no env expression for {key} in {WORKFLOW}")


def _input_default(name: str) -> str:
    """The declared `default:` of a workflow_dispatch input."""
    src = WORKFLOW.read_text(encoding="utf-8")
    block = src.split(f"\n      {name}:\n", 1)
    assert len(block) == 2, f"no workflow_dispatch input named {name}"
    m = re.search(r'^\s+default:\s*"?([^"\n]*)"?\s*$', block[1], re.M)
    assert m, f"input {name} declares no default"
    return m.group(1)


def _evaluate(expr: str, *, tier: str, inputs: dict[str, str]) -> str:
    """Evaluate a GitHub `${{ ... }}` env expression for one tier + dispatch payload."""
    body = expr.strip()
    assert body.startswith("${{") and body.endswith("}}"), body
    py = body[3:-2]
    # github.event.inputs.X / inputs.X -> the dispatch value (declared default when blank)
    py = re.sub(r"(?:github\.event\.)?inputs\.([a-z_]+)",
                lambda m: repr(inputs.get(m.group(1), "")), py)
    py = py.replace("matrix.tier", repr(tier))
    py = py.replace("&&", " and ").replace("||", " or ").replace("==", "==")
    value = eval(py, {"__builtins__": {}}, {})  # noqa: S307 - fixed, repo-owned expression
    return "" if value is False else str(value)


def _blank(tier: str, key: str) -> str:
    """What `key` resolves to for a dispatch that sets nothing (all inputs at their defaults)."""
    inputs = {n: _input_default(n) for n in ("trials", "iterations")}
    return _evaluate(_env_expr(key), tier=tier, inputs=inputs)


# --- the defaults -------------------------------------------------------------------------


@pytest.mark.parametrize("tier", WHOLE_SET_TIERS)
def test_a_blank_dispatch_on_a_whole_set_tier_gets_one_trial(tier):
    """The bug: these resolved to 10, which no job can finish."""
    assert _blank(tier, "NUM_TRIALS") == "1", (
        f"tier {tier} defaults to {_blank(tier, 'NUM_TRIALS')} trials; at that setting the run "
        "cannot finish inside timeout-minutes (see this module's docstring)"
    )


def test_smoke_still_defaults_to_three():
    """Smoke is the tier the algorithm itself is iterated on — 1 trial cannot separate signal
    from noise on a 10-task binary tier, which is why blank has never meant 1 there."""
    assert _blank("smoke", "NUM_TRIALS") == "3"


def test_a_tier_sized_for_measurement_keeps_ten():
    """`pilot` exists to measure cost on a 50-task val split; 10 trials is right there."""
    assert _blank("pilot", "NUM_TRIALS") == "10"


@pytest.mark.parametrize("tier", ALL_TIERS)
@pytest.mark.parametrize("asked", ["1", "3", "10"])
def test_an_explicit_trials_value_wins_on_every_tier(tier, asked):
    """Input-first precedence. A tier pin that short-circuits the dispatch input is the bug
    `test_an_explicit_iterations_dispatch_reaches_smoke` was written for; do not reintroduce it."""
    got = _evaluate(_env_expr("NUM_TRIALS"), tier=tier, inputs={"trials": asked})
    assert got == asked, f"tier {tier} overrode an explicit trials={asked} with {got}"


def test_the_input_default_stays_empty_so_blank_is_distinguishable():
    """With a non-empty default, "asked for 10" and "asked for nothing" are the same string —
    the invariant recorded in test_benchmarks_agent_optimize, and the bug in
    optimizer_usd_per_iter."""
    assert _input_default("trials") == ""


def test_the_input_description_states_the_whole_set_default():
    """An operator reading only the dispatch form must see which tiers default to 1."""
    src = WORKFLOW.read_text(encoding="utf-8")
    desc = src.split("\n      trials:\n", 1)[1].split("\n      ", 1)[0]
    assert "full_verified" in desc and "1" in desc, (
        f"the trials description does not mention the whole-set default: {desc}"
    )


# --- the default must fit the job's own timeout --------------------------------------------


def _rollouts(val: int, test: int, trials: int, iterations: int = 10) -> int:
    """Rollouts a run spends: baseline val, one val eval per iteration, then test twice.

    Matches the cost model both tier READMEs publish. `algorithm_focus: all` never evaluates
    the train split, and `finalize` scores test for the champion AND the baseline.
    """
    return val * trials + iterations * val * trials + 2 * test * trials


@pytest.mark.parametrize("tier", WHOLE_SET_TIERS)
def test_a_blank_whole_set_dispatch_stays_inside_a_finishable_budget(tier):
    split = json.loads((SB / tier / "split_ids.json").read_text(encoding="utf-8"))
    trials = int(_blank(tier, "NUM_TRIALS"))
    n = _rollouts(len(split["val"]), len(split["test"]), trials)
    assert n <= MAX_DEFAULT_ROLLOUTS, (
        f"a blank {tier} dispatch plans {n} rollouts at trials={trials}; the job's "
        f"timeout-minutes cannot absorb that (ceiling ~{MAX_DEFAULT_ROLLOUTS})"
    )


def test_the_documented_cost_model_matches_the_new_default():
    """The READMEs quote `trials=1` figures — 2,279 for full, 1,000 for full_verified. With the
    default fixed, the workflow now actually produces the configuration they describe."""
    assert _rollouts(91, 639, trials=1) == 2279
    assert _rollouts(40, 280, trials=1) == 1000


def test_the_job_timeout_is_still_the_constraint_this_default_respects():
    """Guards the premise: if the cap is raised, revisit MAX_DEFAULT_ROLLOUTS deliberately."""
    assert "timeout-minutes: 1440" in WORKFLOW.read_text(encoding="utf-8")


# --- the projection is visible at the start of the log, not at hour 24 ---------------------


def _plan_block() -> str:
    """Lift the rollout-projection block verbatim out of run_suite.sh."""
    src = RUN_SUITE.read_text(encoding="utf-8")
    start = src.index("# PLAN. Print what this dispatch will actually spend")
    return src[start:src.index("\ncat > \"$PROJ/capevolve.yaml\"", start)]


def _run_plan(tmp_path, *, val: int, test: int, trials: int, iterations: int) -> str:
    """Execute the real projection block against a temp split and report its output."""
    import subprocess
    import textwrap

    proj = tmp_path / "proj" / "inputs"
    proj.mkdir(parents=True)
    (proj / "split_ids.json").write_text(json.dumps({
        "train": [f"tr{i}" for i in range(3)],
        "val": [f"v{i}" for i in range(val)],
        "test": [f"te{i}" for i in range(test)],
    }), encoding="utf-8")
    script = textwrap.dedent(f"""
        set -euo pipefail
        PY=python3
        PROJ={tmp_path / "proj"}
        NUM_TRIALS={trials}
        ITER={iterations}
    """) + _plan_block()
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout + p.stderr


def test_run_suite_projects_the_rollout_count_before_spending_it(tmp_path):
    """An over-budget dispatch must be visible in the log, not discovered at the timeout."""
    out = _run_plan(tmp_path, val=40, test=280, trials=1, iterations=10)
    assert "1000 rollouts" in out, f"projection is wrong or missing: {out}"


def test_the_projection_reports_the_inputs_it_used(tmp_path):
    """The number is only actionable next to the knobs that produced it."""
    out = _run_plan(tmp_path, val=40, test=280, trials=1, iterations=10)
    for fragment in ("val=40", "test=280", "trials=1", "iterations=10"):
        assert fragment in out, f"projection omits {fragment}: {out}"


def test_the_projection_scales_with_trials(tmp_path):
    """Guards the arithmetic: 10 trials is 10x the rollouts, which is the whole point."""
    out = _run_plan(tmp_path, val=40, test=280, trials=10, iterations=10)
    assert "10000 rollouts" in out, out
