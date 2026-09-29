"""The tau2 blackbox leg: one VANILLA benchmark, two legs, tailoring applied from outside.

Replaces test_ci_tau2_custom_arms.py. That file guarded a pair of arms that installed a FORKED
tau2 from skillberry-benchmarks; both legs now install the same public sierra-research checkout
and everything proxy-specific lives in examples/tau2_airline/adapters/tau2_tailoring.py. The
four checks in it that were never arm-specific are carried over at the bottom.
"""

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RUN_SUITE = (REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh").read_text(encoding="utf-8")
CI_SETUP = (REPO / "ci" / "benchmarks" / "lib" / "ci_setup.sh").read_text(encoding="utf-8")
BENCH_WF = (REPO / ".github" / "workflows" / "benchmarks.yml").read_text(encoding="utf-8")
ITEST_WF = (REPO / ".github" / "workflows" / "integration-tests.yml").read_text(encoding="utf-8")
TIERS = ("smoke", "integration", "full")
ARM_DIR = REPO / "examples" / "tau2_airline" / "blackbox"


def _leg_case(text: str, token: str) -> str:
    """The body of one `case` branch, so an assertion cannot leak into a neighbouring leg."""
    start = text.index(f"  {token})")
    end = text.index("\n    ;;\n", start) + len("\n    ;;\n")
    return text[start:end]


def _code(text: str) -> str:
    """Shell with comment-only lines dropped. These assertions are about what the script DOES;
    the words `skillberry-benchmarks` and `[voice]` legitimately appear in comments explaining
    why neither is installed any more."""
    return "\n".join(l for l in text.split("\n") if not l.strip().startswith("#"))


# --- the fork is gone -------------------------------------------------------------------

def test_no_leg_installs_a_forked_tau2():
    """The whole point of the change: one PUBLIC benchmark, unmodified, for both legs."""
    code = _code(CI_SETUP)
    assert "skillberry-benchmarks" not in code
    assert "[skillberry]" not in code
    assert "sierra-research/tau2-bench" in code


def test_the_deleted_arm_layout_is_fully_gone():
    assert not (REPO / "examples" / "tau2_custom").exists()
    assert not (REPO / "ci" / "benchmarks" / "tau2_custom").exists()
    assert not (REPO / "core" / "tests" / "test_ci_tau2_custom_arms.py").exists()
    for text in (RUN_SUITE, CI_SETUP, BENCH_WF, ITEST_WF):
        assert "tau2_custom_direct" not in text
        assert "tau2_custom_blackbox" not in text


def test_websockets_is_installed_because_tau2_cannot_import_without_it():
    """tau2's data_model imports its voice stack unconditionally but ships websockets only in
    the [voice] extra, so a base install cannot even `import tau2`. Installing all of [voice]
    would drag in livekit/boto3/google-cloud-aiplatform."""
    code = _code(CI_SETUP)
    assert "websockets>=13.0" in code
    assert "[voice]" not in code


def test_both_tau2_legs_share_one_venv():
    """The per-arm venv existed only because a forked and a public tau2 share a package name."""
    assert "venv-tau2-custom" not in CI_SETUP
    assert 'VENV="$CACHE/venv"' in CI_SETUP


def test_the_resolved_benchmark_commit_is_recorded():
    """A published number that cannot name its benchmark commit cannot be compared to another."""
    assert "TAU2_BENCH_SHA" in CI_SETUP
    assert "rev-parse HEAD" in CI_SETUP


# --- the leg is dispatchable ------------------------------------------------------------

def test_the_leg_is_offered_and_planned():
    assert "tau2_blackbox" in BENCH_WF
    assert '"tau2_blackbox"' in BENCH_WF          # in the planner's BENCHES list
    assert "tau2_blackbox" in ITEST_WF


def test_the_arm_is_selected_by_the_intervention_input_not_a_picker_token():
    """`benchmark: tau2` + `intervention: blackbox`, as before this change — the arm token is not
    offered in the benchmark picker. What changed is the RESOLUTION: generic
    (`<bench>_blackbox`) instead of a per-benchmark ARM_OF table."""
    assert "INTERVENTION_SEL" in BENCH_WF
    assert "ARM_OF" not in BENCH_WF, "the per-benchmark arm table is replaced by a generic rule"
    assert '_blackbox"' in BENCH_WF or "_blackbox'" in BENCH_WF
    # The picker offers benchmarks, not arms.
    opts = next(l for l in BENCH_WF.split("\n") if "options: [tau2," in l)
    assert "tau2_blackbox" not in opts, "the arm is reached via intervention, not the picker"


def test_blackbox_on_a_benchmark_with_no_arm_selects_nothing():
    """Deliberately the SAME outcome as before this was generalized: only tau2 ships an arm, so
    any other benchmark + blackbox resolves to a leg that does not exist. A silent fallback to
    direct would run the wrong delivery and record it as the requested one."""
    assert 'f"{bench_sel}_blackbox"' in BENCH_WF
    for bench in ("swebench", "skillsbench", "spreadsheetbench", "rfe-creator"):
        assert not (REPO / "ci" / "benchmarks" / f"{bench}_blackbox").exists()


def test_no_nested_tier_path_transform_remains():
    """tau2_custom/<arm>/<tier>/ needed the same transform in three places. Flat now."""
    assert 'BENCH_DIR="tau2_custom/' not in RUN_SUITE
    assert "tau2_custom/" not in BENCH_WF
    sync = (REPO / "ci" / "benchmarks" / "lib" / "sync_models.py").read_text(encoding="utf-8")
    assert '"*/*/*/tasks.json"' not in sync


@pytest.mark.parametrize("tier", TIERS)
def test_every_tier_ships_a_task_list(tier):
    p = REPO / "ci" / "benchmarks" / "tau2_blackbox" / tier / "tasks.json"
    rows = json.loads(p.read_text(encoding="utf-8"))
    assert rows and all("id" in r for r in rows)


@pytest.mark.parametrize("tier", TIERS)
def test_the_leg_runs_the_SAME_ids_as_the_vanilla_leg(tier):
    """Comparability is the only reason this leg exists; differing ids would void it."""
    def ids(bench):
        p = REPO / "ci" / "benchmarks" / bench / tier / "tasks.json"
        return [str(r["id"]) for r in json.loads(p.read_text(encoding="utf-8"))]
    assert ids("tau2_blackbox") == ids("tau2")


@pytest.mark.parametrize("tier", TIERS)
def test_the_recorded_agent_is_a_gateway_model_not_the_proxy_sentinel(tier):
    """The sentinel is a ROUTE, never a model anyone can dispatch — recording it would make the
    published row claim a model that does not exist."""
    p = REPO / "ci" / "benchmarks" / "tau2_blackbox" / tier / "tasks.json"
    agents = {r.get("agent") for r in json.loads(p.read_text(encoding="utf-8"))}
    assert "ibm/skillberry-local" not in agents
    assert agents == {"aws/gpt-oss-120b"}


# --- what the leg wires up --------------------------------------------------------------

def test_the_leg_sources_the_example_not_a_template_copy():
    case = _leg_case(RUN_SUITE, "tau2_blackbox")
    assert "examples/tau2_airline" in case
    assert "$TPL/" not in case
    for name in ("adapter.py", "gateway.py", "tau2_tailoring.py"):
        assert name in case


def test_the_leg_deploys_the_blackbox_seed_not_the_direct_one():
    case = _leg_case(RUN_SUITE, "tau2_blackbox")
    assert "$ARM_DIR/seed_capability" in case
    assert (ARM_DIR / "seed_capability" / "my_skill" / "SKILL.md").exists()
    assert (ARM_DIR / "seed_capability" / "primitive_tools" / "functions.py").exists()


def test_the_leg_lands_its_own_optimizer_instructions():
    case = _leg_case(RUN_SUITE, "tau2_blackbox")
    assert "optimizer/INSTRUCTIONS.md" in case
    assert "OPT_INSTRUCTIONS=" in case
    assert (ARM_DIR / "optimizer" / "INSTRUCTIONS.md").exists()


def test_the_extra_yaml_declares_the_delivery_and_seals_the_substrate():
    case = _leg_case(RUN_SUITE, "tau2_blackbox")
    for key in ("intervention: blackbox", "skill_name: my_skill",
                "protected_paths:", "runner_repo_path:"):
        assert key in case
    assert "primitive_tools/*" in case and "my_skill/SKILL.md" in case


def test_the_leg_uses_the_sentinel_and_a_low_concurrency():
    case = _leg_case(RUN_SUITE, "tau2_blackbox")
    assert 'TAU2_AGENT_MODEL:-ibm/skillberry-local' in case
    assert "TAU2_MAX_CONCURRENCY:-4" in case, \
        "every agent call funnels through ONE proxy and ONE store process"
    assert "SPA_MODEL_NAME" in case, "what the proxy calls upstream must be set explicitly"


def test_the_leg_starts_the_environment_service_and_probes_a_route_it_serves():
    case = _code(_leg_case(RUN_SUITE, "tau2_blackbox"))
    assert "EnvironmentManager" in case
    assert "/health" not in case, "this FastAPI app serves no /health; probing it never succeeds"
    assert "/docs" in case


def test_the_leg_starts_the_store_before_the_proxy():
    case = _leg_case(RUN_SUITE, "tau2_blackbox")
    assert case.index("start_store") < case.index("start_spa"), \
        "the proxy binds its skill at start, so the store must be healthy first"


def test_the_leg_tears_its_stack_down():
    case = _leg_case(RUN_SUITE, "tau2_blackbox")
    assert "trap _blackbox_teardown EXIT" in case
    assert "stop_all()" in case
    assert "pkill -f" in case, "stop_all does not own tau2's environment service"


def test_the_leg_reads_service_logs_and_never_writes_them():
    case = _leg_case(RUN_SUITE, "tau2_blackbox")
    assert "tail -c" in case
    assert ': > "$_log"' not in case, "truncating a log whose fd a live service holds fights its owner"


def test_only_the_blackbox_leg_provisions_the_stack():
    assert 'if [ "$BENCH" = "tau2_blackbox" ]' in CI_SETUP
    assert "provision()" in CI_SETUP
    code = _code(CI_SETUP)
    for started in ("start_store", "start_spa"):
        assert started not in code, "starting a service belongs to the run, not provisioning"


def test_native_sims_are_on_for_both_tau2_legs():
    assert "tau2|tau2_blackbox) _NATIVE_SIMS_DEFAULT=1 ;;" in RUN_SUITE


# --- carried over from test_ci_tau2_custom_arms.py (never arm-specific) -----------------

def test_comments_in_unquoted_heredocs_are_plain_text():
    """In an UNQUOTED heredoc, `$x` expands and a backtick starts a command substitution — so a
    comment containing either is executed, not documentation."""
    bad = []
    for m in re.finditer(r"<<(?!-?')(\w+)\n(.*?)\n\1\n", RUN_SUITE, re.S):
        for line in m.group(2).split("\n"):
            st = line.strip()
            if st.startswith("#") and ("`" in st or "$" in st):
                bad.append(st)
    assert not bad, f"expanding text in an unquoted-heredoc comment: {bad}"


def test_the_spec_template_carries_the_per_bench_extra_keys():
    assert "${EXTRA_YAML:-}" in RUN_SUITE
    assert 'optimizer_instructions_file: "${OPT_INSTRUCTIONS:-}"' in RUN_SUITE


def test_the_integration_workflow_still_defaults_to_tau2():
    assert "default: tau2" in ITEST_WF
    for m in re.finditer(r"inputs\.bench[^}]*}}", ITEST_WF):
        assert "|| 'tau2'" in m.group(0), f"undefaulted inputs.bench: {m.group(0)}"
