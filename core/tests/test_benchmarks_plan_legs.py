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


def _run_plan_full(*, event, tier_sel=None, bench_sel=None, labels=None, intervention=None,
                   expect_failure=False):
    """Like _run_plan but also returns (legs, stderr, returncode).

    Pass expect_failure=True for cases where a bare benchmark-* label is expected to cause
    sys.exit(1) — without it the helper asserts returncode==0 as a safety net.
    """
    env = dict(os.environ, EVENT=event)
    if tier_sel is not None:
        env["TIER_SEL"] = tier_sel
    if bench_sel is not None:
        env["BENCH_SEL"] = bench_sel
    if intervention is not None:
        env["INTERVENTION_SEL"] = intervention
    env["LABELS"] = json.dumps(labels or [])
    proc = subprocess.run([sys.executable, "-c", _plan_script()], capture_output=True,
                          text=True, cwd=str(REPO), env=env)
    if not expect_failure:
        assert proc.returncode == 0, proc.stderr
    # matrix= line is only written when the script reaches the print() after sys.exit check
    m = re.search(r"^matrix=(.*)$", proc.stdout, re.M)
    legs = [(leg["tier"], leg["bench"]) for leg in json.loads(m.group(1))] if m else []
    return legs, proc.stderr, proc.returncode


def _run_plan(*, event, tier_sel=None, bench_sel=None, labels=None, intervention=None):
    legs, _, _ = _run_plan_full(event=event, tier_sel=tier_sel, bench_sel=bench_sel,
                                labels=labels, intervention=intervention)
    return legs


# The two tau2_custom_* entries are the tau2 airline benchmark's DELIVERY ARMS (direct =
# in-process, blackbox = Store + Proxy-Agent), not two more benchmarks. They are listed here because
# the planner treats them as ordinary benches: each populates smoke/integration/full, so every
# per-bench assertion below holds for them unchanged.
ALL_BENCHES = ["tau2", "swebench", "skillsbench", "spreadsheetbench", "rfe-creator",
               "tau2_custom_direct", "tau2_custom_blackbox"]


# ---- per-bench dispatch selects exactly that bench ---------------------------

@pytest.mark.parametrize("tier", ["smoke", "full"])
@pytest.mark.parametrize("bench", ALL_BENCHES)
def test_single_bench_and_tier_dispatch(tier, bench):
    """Each bench dispatched individually returns exactly that one leg."""
    legs = _run_plan(event="workflow_dispatch", tier_sel=tier, bench_sel=bench)
    assert legs == [(tier, bench)], f"bench_sel={bench!r} tier_sel={tier!r} -> {legs}"


def test_all_is_not_a_valid_bench_sel():
    """`all` is no longer a valid bench_sel. It selects nothing, and selecting nothing is a
    FAILURE — a stale saved dispatch still naming `all` must not report green."""
    legs, stderr, rc = _run_plan_full(event="workflow_dispatch", tier_sel="smoke",
                                      bench_sel="all", expect_failure=True)
    assert legs == [], f"bench_sel='all' should produce no legs, got {legs}"
    assert rc == 1 and "::error::" in stderr


def test_a_dispatch_for_an_unpopulated_tier_fails_the_step():
    """The path `all` used to mask, and the one that matters most now that dispatch is the only
    route to the benches with no per-bench label: tau2 ships no pilot tier, so this selects
    nothing. Zero legs skips the `bench` job, so without a non-zero exit the whole workflow
    reports success having measured nothing."""
    legs, stderr, rc = _run_plan_full(event="workflow_dispatch", tier_sel="pilot",
                                      bench_sel="tau2", expect_failure=True)
    assert legs == []
    assert rc == 1, "a dispatch that selects nothing must fail, not report green"
    assert "::error::" in stderr
    assert "pilot" in stderr and "tau2" in stderr, "the annotation must name the selection"


def test_tier_all_does_not_sweep_in_the_pilot():
    """`tier=all` must only sweep smoke+full — never pilot or full_verified.

    pilot is a measurement rig whose rewards are not comparable, and the aggregate job
    publishes every leg to benchmark-history — so "all" must not pick it up.
    """
    legs = _run_plan(event="workflow_dispatch", tier_sel="all", bench_sel="tau2")
    assert [b for t, b in legs if t == "pilot"] == [], "pilot leaked into tier=all"
    assert sorted(legs) == [("full", "tau2"), ("smoke", "tau2")]


def test_pilot_runs_only_when_named_explicitly():
    legs = _run_plan(event="workflow_dispatch", tier_sel="pilot", bench_sel="spreadsheetbench")
    assert legs == [("pilot", "spreadsheetbench")]


def test_single_bench_dispatch_unchanged():
    legs = _run_plan(event="workflow_dispatch", tier_sel="smoke", bench_sel="tau2")
    assert legs == [("smoke", "tau2")]


def test_default_dispatch_is_smoke_tau2():
    """The default bench is now `tau2` — a single-bench dispatch, not a fan-out."""
    legs = _run_plan(event="workflow_dispatch")
    assert legs == [("smoke", "tau2")]


# ---- tau2-custom + intervention resolves to a real, populated leg ------------

@pytest.mark.parametrize("intervention,expect", [
    ("direct", "tau2_custom_direct"),
    ("blackbox", "tau2_custom_blackbox"),
])
def test_tau2_custom_plus_intervention_selects_a_leg_whose_tasks_exist(intervention, expect):
    """Both halves, because the planner FAILS OPEN on a missing tasks.json: it prints `skip`
    and drops the leg. So renaming the leg token without moving
    ci/benchmarks/tau2_custom/<option>/ would select ZERO legs and still report success — a
    dispatch that looks green and measured nothing. Assert the leg is planned AND that the
    file the planner looked for is really there."""
    legs = _run_plan(event="workflow_dispatch", tier_sel="smoke", bench_sel="tau2-custom",
                     intervention=intervention)
    assert legs == [("smoke", expect)], f"intervention={intervention} planned {legs}"
    option = expect.removeprefix("tau2_custom_")
    tasks = REPO / "ci" / "benchmarks" / "tau2_custom" / option / "smoke" / "tasks.json"
    assert tasks.is_file(), f"the planner resolves to {tasks}, which does not exist"


def test_an_unknown_intervention_falls_back_to_direct():
    """The workflow, unlike core's `declared()`, does not refuse an unknown value — it
    silently falls back. Pinned so the fallback stays deliberate and visible."""
    legs = _run_plan(event="workflow_dispatch", tier_sel="smoke", bench_sel="tau2-custom",
                     intervention="not-a-mode")
    assert legs == [("smoke", "tau2_custom_direct")]


# ---- pull_request labels ----------------------------------------------------

def test_per_bench_label_selects_exactly_that_bench():
    """Only benchmark-<tier>-<bench> labels are accepted; bare labels have no effect."""
    legs = _run_plan(event="pull_request", labels=["benchmark-smoke-tau2"])
    assert legs == [("smoke", "tau2")]


def test_per_bench_label_unchanged():
    legs = _run_plan(event="pull_request", labels=["benchmark-full-spreadsheetbench"])
    assert legs == [("full", "spreadsheetbench")]


def test_bare_label_fails_the_step():
    """A bare benchmark-* label that matches no legs exits 1 and emits a ::error::
    annotation — so the failure is visible rather than a silent green no-op.
    An unrelated label ('documentation') produces no annotation and exits 0."""
    _, stderr, rc = _run_plan_full(event="pull_request", labels=["benchmark-smoke"],
                                   expect_failure=True)
    assert rc == 1, f"bare label must exit 1, got {rc}"
    assert "::error::" in stderr, "bare label must emit a ::error:: annotation"
    assert "benchmark-smoke-tau2" in stderr, "annotation must suggest the correct form"

    # both bare labels, not just one: they are separate labels on the repo and each is
    # applyable on its own.
    _, stderr_full, rc_full = _run_plan_full(event="pull_request", labels=["benchmark-full"],
                                             expect_failure=True)
    assert rc_full == 1 and "::error::" in stderr_full

    _, stderr_unrelated, rc_unrelated = _run_plan_full(event="pull_request",
                                                       labels=["documentation"])
    assert rc_unrelated == 0, "non-benchmark label must exit 0"
    assert "::error::" not in stderr_unrelated, "non-benchmark label must not emit annotation"


def test_a_label_merely_containing_benchmark_does_not_fail_the_pr():
    """The trust gate is a SUBSTRING test on the joined label list, so a PR labelled
    `no-benchmark-needed` reaches the planner. It correctly selects nothing — and must exit 0.
    Keying the refusal on a prefix rather than on "did we reach here" is what prevents an
    ordinary PR being failed by a benchmark guard it never asked for."""
    legs, stderr, rc = _run_plan_full(event="pull_request", labels=["no-benchmark-needed"])
    assert legs == []
    assert rc == 0, "a PR that never asked for benchmarks must not be failed"
    assert "::error::" not in stderr


def test_unrelated_label_selects_nothing():
    assert _run_plan(event="pull_request", labels=["documentation"]) == []


def test_pilot_label_reaches_only_the_bench_named():
    """Use benchmark-pilot-<bench> — bare labels are no longer honoured."""
    legs = _run_plan(event="pull_request", labels=["benchmark-pilot-spreadsheetbench"])
    assert legs == [("pilot", "spreadsheetbench")]


def test_pilot_label_for_an_unpopulated_bench_fails_the_step():
    """benchmark-pilot-tau2 is a well-formed label but tau2 has no pilot tier — zero legs
    selected, so the step exits 1 rather than silently reporting success.

    Asserts the ANNOTATION too, not just the exit code: `legs == []` and `rc == 1` are both
    satisfied by a planner that crashed outright (a traceback exits 1 and prints no matrix=
    line), so without this the test would pass against a broken script."""
    legs, stderr, rc = _run_plan_full(event="pull_request", labels=["benchmark-pilot-tau2"],
                                      expect_failure=True)
    assert legs == []
    assert rc == 1
    assert "::error::" in stderr, "must be the deliberate refusal, not an arbitrary crash"


# ---- the pilot tier itself --------------------------------------------------

def test_which_benches_ship_a_pilot_tier():
    """Pinned deliberately: a benchmark that gains a pilot tier becomes reachable by
    `tier=pilot` and by a `benchmark-pilot-<bench>` label, and one that has none now FAILS
    such a dispatch rather than quietly selecting nothing — so this list is what decides
    which selections are legitimate.

    swebench gained one when the harbor switch made a 250-task full run a multi-day,
    four-figure proposition: 50 stratified tasks (every repo represented, proportions
    tracking full) validate the per-trial cost and runtime at 10x smoke's scale before
    anyone commits to full.

    parsec ships one too, and it is the exception that proves the rule: it ships
    `pilot/tasks.json` so the tier is runnable *locally* (`TIER=pilot bash
    ci/benchmarks/lib/run_suite.sh parsec`), but it is deliberately absent from
    `benchmarks.yml`'s `BENCHES`, so the planner never enumerates it and the
    pilot assertions above are unaffected — see
    `test_pilot_label_reaches_only_the_bench_named` and
    `test_pilot_label_for_an_unpopulated_bench_fails_the_step`. It stays out of CI because
    neither its task trees (internal Red Hat) nor its kaegis simulators exist outside
    IBM/RH; revisit this list if that ever changes and parsec becomes CI-dispatchable.
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
    there is a tree to inspect.

    Uses an explicit bench (tau2) — `all` is no longer a valid value. The property being
    tested is that a bench with no tasks.json on disk is still selected (unfiltered), not
    that every bench is selected at once.
    """
    legs, err = _run_plan_in(tmp_path, event="workflow_dispatch", tier_sel="smoke", bench_sel="tau2")
    assert legs == [("smoke", "tau2")], (
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
