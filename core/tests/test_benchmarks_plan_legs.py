"""The planner's leg selection, exercised as the real embedded script.

Adding the `pilot` tier must not change which legs any existing dispatch or label produces.
`run_suite.sh` already no-ops on a missing `tasks.json`, but *emitting* a leg claims a slot on
the single serialized self-hosted runner just to warn and exit — the exact waste this planner
was introduced to remove. So the planner now filters tiers a benchmark hasn't populated, and
these tests pin both halves: existing selections are unchanged, and `pilot` reaches only the
benchmark that ships it.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"


def _plan_script() -> str:
    """Lift the planner's python heredoc verbatim out of the workflow."""
    src = WORKFLOW.read_text(encoding="utf-8")
    start = src.index("python3 - <<'PY' >> \"$GITHUB_OUTPUT\"")
    body = src[src.index("\n", start) + 1:]
    end = body.index("\n          PY")
    block = body[:end]
    # strip the workflow's 10-space YAML indentation
    script = "\n".join(ln[10:] if ln.startswith(" " * 10) else ln for ln in block.splitlines())
    assert "TIERS" in script and "legs.append" in script, "planner script not found"
    return script


def _run_plan(*, event, tier_sel=None, bench_sel=None, labels=None):
    env = dict(os.environ, EVENT=event)
    if tier_sel is not None:
        env["TIER_SEL"] = tier_sel
    if bench_sel is not None:
        env["BENCH_SEL"] = bench_sel
    env["LABELS"] = json.dumps(labels or [])
    proc = subprocess.run([sys.executable, "-c", _plan_script()], capture_output=True,
                          text=True, cwd=str(REPO), env=env)
    assert proc.returncode == 0, proc.stderr
    m = re.search(r"^matrix=(.*)$", proc.stdout, re.M)
    assert m, proc.stdout
    return [(leg["tier"], leg["bench"]) for leg in json.loads(m.group(1))]


ALL_BENCHES = ["tau2", "swebench", "skillsbench", "spreadsheetbench"]


# ---- adding `pilot` must not disturb existing selections ---------------------

@pytest.mark.parametrize("tier", ["smoke", "full"])
def test_single_tier_dispatch_unchanged(tier):
    legs = _run_plan(event="workflow_dispatch", tier_sel=tier, bench_sel="all")
    assert sorted(legs) == sorted((tier, b) for b in ALL_BENCHES)


def test_tier_all_does_not_sweep_in_the_pilot():
    """`tier=all` must stay exactly what it was: smoke+full for every benchmark.

    pilot is a measurement rig whose rewards are not comparable, and the aggregate job
    publishes every leg to benchmark-history — so "all" must not pick it up.
    """
    legs = _run_plan(event="workflow_dispatch", tier_sel="all", bench_sel="all")
    assert [b for t, b in legs if t == "pilot"] == [], "pilot leaked into tier=all"
    assert sorted(legs) == sorted((t, b) for t in ("smoke", "full") for b in ALL_BENCHES)


def test_pilot_runs_only_when_named_explicitly():
    legs = _run_plan(event="workflow_dispatch", tier_sel="pilot", bench_sel="all")
    assert sorted(legs) == [("pilot", "spreadsheetbench"), ("pilot", "swebench")]


def test_single_bench_dispatch_unchanged():
    legs = _run_plan(event="workflow_dispatch", tier_sel="smoke", bench_sel="tau2")
    assert legs == [("smoke", "tau2")]


def test_default_dispatch_is_still_smoke_everywhere():
    legs = _run_plan(event="workflow_dispatch")
    assert sorted(legs) == sorted(("smoke", b) for b in ALL_BENCHES)


# ---- pull_request labels ----------------------------------------------------

def test_tier_label_unchanged():
    legs = _run_plan(event="pull_request", labels=["benchmark-smoke"])
    assert sorted(legs) == sorted(("smoke", b) for b in ALL_BENCHES)


def test_per_bench_label_unchanged():
    legs = _run_plan(event="pull_request", labels=["benchmark-full-spreadsheetbench"])
    assert legs == [("full", "spreadsheetbench")]


def test_unrelated_label_selects_nothing():
    assert _run_plan(event="pull_request", labels=["documentation"]) == []


def test_pilot_label_reaches_only_the_benchmarks_that_ship_it():
    legs = _run_plan(event="pull_request", labels=["benchmark-pilot"])
    assert sorted(legs) == [("pilot", "spreadsheetbench"), ("pilot", "swebench")]


def test_pilot_label_for_an_unpopulated_bench_selects_nothing():
    assert _run_plan(event="pull_request", labels=["benchmark-pilot-tau2"]) == []


# ---- the pilot tier itself --------------------------------------------------

def test_which_benches_ship_a_pilot_tier():
    """Pinned deliberately: if another benchmark adds one, the assertions above need
    revisiting too, because `tier=pilot` and the `benchmark-pilot` label fan out over
    exactly the benches that ship the tier.

    swebench gained one when the harbor switch made a 250-task full run a multi-day,
    four-figure proposition: 50 stratified tasks (every repo represented, proportions
    tracking full) validate the per-trial cost and runtime at 10x smoke's scale before
    anyone commits to full.

    parsec ships one too, and it is the exception that proves the rule: it ships
    `pilot/tasks.json` so the tier is runnable *locally* (`TIER=pilot bash
    ci/benchmarks/lib/run_suite.sh parsec`), but it is deliberately absent from
    `benchmarks.yml`'s `BENCHES`, so the planner never enumerates it and the
    `benchmark-pilot` / `tier=pilot` fan-out assertions above are unaffected — see
    `test_pilot_label_reaches_only_the_benchmarks_that_ship_it`, which still lists two
    benches. It stays out of CI because neither its task trees (internal Red Hat) nor
    its kaegis simulators (`github.ibm.com/kaegis/simulation-harness`) exist outside
    IBM/RH; revisit both this list and the fan-out assertions if that ever changes and
    parsec becomes CI-dispatchable.
    """
    shipped = sorted(p.parent.parent.name
                     for p in (REPO / "ci" / "benchmarks").glob("*/pilot/tasks.json"))
    assert shipped == ["parsec", "spreadsheetbench", "swebench"], shipped


# ---- the missing-checkout regression (run 30682558719) -----------------------

def _run_plan_in(cwd, *, event, tier_sel=None, bench_sel=None, labels=None):
    env = dict(os.environ, EVENT=event, LABELS=json.dumps(labels or []))
    if tier_sel is not None:
        env["TIER_SEL"] = tier_sel
    if bench_sel is not None:
        env["BENCH_SEL"] = bench_sel
    proc = subprocess.run([sys.executable, "-c", _plan_script()], capture_output=True,
                          text=True, cwd=str(cwd), env=env)
    assert proc.returncode == 0, proc.stderr
    legs = json.loads(re.search(r"^matrix=(.*)$", proc.stdout, re.M).group(1))
    return [(l["tier"], l["bench"]) for l in legs], proc.stderr


def test_planner_fails_open_without_a_checked_out_tree(tmp_path):
    """The bug: the plan job had no checkout, so the tasks.json filter matched NOTHING and a
    dispatch selected zero legs while still reporting success. Filtering must only apply when
    there is a tree to inspect."""
    legs, err = _run_plan_in(tmp_path, event="workflow_dispatch", tier_sel="smoke", bench_sel="all")
    assert sorted(legs) == sorted(("smoke", b) for b in ALL_BENCHES), (
        f"planner selected {legs} with no checkout — it must fall back to unfiltered selection"
    )
    assert "filter disabled" in err


def test_plan_job_checks_out_the_repo():
    """The filter is only meaningful with a tree, so the job must provide one."""
    src = WORKFLOW.read_text(encoding="utf-8")
    plan = src[src.index("\n  plan:"):src.index("\n  bench:")]
    assert "actions/checkout" in plan, (
        "plan job reads ci/benchmarks/**/tasks.json but does not check out the repository"
    )
