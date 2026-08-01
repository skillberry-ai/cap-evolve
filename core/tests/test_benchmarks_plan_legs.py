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
    assert legs == [("pilot", "spreadsheetbench")]


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


def test_pilot_label_reaches_only_the_benchmark_that_ships_it():
    legs = _run_plan(event="pull_request", labels=["benchmark-pilot"])
    assert legs == [("pilot", "spreadsheetbench")]


def test_pilot_label_for_an_unpopulated_bench_selects_nothing():
    assert _run_plan(event="pull_request", labels=["benchmark-pilot-tau2"]) == []


# ---- the pilot tier itself --------------------------------------------------

def test_only_spreadsheetbench_ships_a_pilot_tier():
    """If another benchmark adds one, the assertions above need revisiting deliberately."""
    shipped = sorted(p.parent.parent.name
                     for p in (REPO / "ci" / "benchmarks").glob("*/pilot/tasks.json"))
    assert shipped == ["spreadsheetbench"], shipped
