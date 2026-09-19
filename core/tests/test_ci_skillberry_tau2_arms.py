"""The two skillberry_benchmarks_tau2_airline DELIVERY ARMS as CI benchmark legs.

`skillberry_tau2_direct` and `skillberry_tau2_spa` run the SAME 50 tau2 airline tasks by two
different delivery routes: in the runner's own process, and through the Skillberry Store +
Proxy-Agent. What makes them worth having in CI is that the two numbers are comparable to each
other — so the things worth pinning are the ones that would silently break that comparison, or
that would silently degrade a leg into measuring something other than what it claims.

Everything here is static analysis of the committed wiring: no gateway, no runner, no spend.
"""

import json
import re
from pathlib import Path

import pytest

from cap_evolve.specfile import read_yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github/workflows/benchmarks.yml"
RUN_SUITE = REPO / "ci/benchmarks/lib/run_suite.sh"
CI_SETUP = REPO / "ci/benchmarks/lib/ci_setup.sh"
ARMS = ("skillberry_tau2_direct", "skillberry_tau2_spa")
TIERS = ("smoke", "integration", "full")


def _arm_case() -> str:
    """The run_suite.sh case body shared by both arms."""
    sh = RUN_SUITE.read_text(encoding="utf-8")
    head = "  skillberry_tau2_direct|skillberry_tau2_spa)"
    assert head in sh, "the arms' case block is gone from run_suite.sh"
    return sh.split(head, 1)[1].split("\n  swebench)", 1)[0]


# ---- the picker and the planner must agree ----------------------------------------

def test_both_arms_are_dispatchable_and_planned():
    """A bench in the picker but not in BENCHES is unselectable; the reverse is worse — it
    runs under `benchmark=all` with no way to run it alone."""
    wf = WORKFLOW.read_text(encoding="utf-8")
    options = re.search(r"options: \[all, tau2,(.*?)\]", wf, re.S).group(1)
    benches = re.search(r"BENCHES = \[(.*?)\]", wf, re.S).group(1)
    assert "tau2-custom" in options, "the picker must offer tau2-custom"
    for arm in ARMS:
        assert arm not in options, f"{arm} is an internal leg, not a picker option"
        assert arm in benches, f"{arm} missing from the planner's BENCHES"


def test_the_intervention_input_offers_exactly_the_spec_values():
    """The input feeds the spec key of the same name, so its values must be core's."""
    wf = WORKFLOW.read_text(encoding="utf-8")
    block = wf.split("      intervention:", 1)[1].split("      tier:", 1)[0]
    assert "options: [direct, spa]" in block
    assert "default: direct" in block, "every other benchmark runs direct"


def test_the_dispatch_form_stays_within_githubs_input_ceiling():
    """GitHub allows 25. An earlier note in this repo said 10, which is why the arm used to be
    packed into the benchmark token."""
    wf = WORKFLOW.read_text(encoding="utf-8")
    inputs_block = wf.split("    inputs:", 1)[1].split("  pull_request:", 1)[0]
    names = re.findall(r"^      ([a-z_]+):$", inputs_block, re.M)
    assert len(names) <= 25, f"{len(names)} dispatch inputs: {names}"


def test_tau2_custom_resolves_to_an_arm_through_the_intervention_input():
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert 'INTERVENTION_SEL: ${{ github.event.inputs.intervention' in wf, "planner needs it"
    assert '"direct": "skillberry_tau2_direct", "spa": "skillberry_tau2_spa"' in wf
    assert 'bench_sel = ARM_OF.get(intervention, ARM_OF["direct"])' in wf


# ---- the tier task lists ---------------------------------------------------------

@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("tier", TIERS)
def test_every_tier_ships_a_task_list(arm, tier):
    """A tier with no tasks.json is not an error — `plan` silently drops the leg. So a missing
    file means "this tier quietly does not exist", which is exactly the failure to catch here."""
    p = REPO / "ci/benchmarks" / arm / tier / "tasks.json"
    assert p.is_file(), f"{p} missing — the {tier} leg would never be created"
    rows = json.loads(p.read_text(encoding="utf-8"))
    assert rows and all(r.get("id") for r in rows)


@pytest.mark.parametrize("tier", TIERS)
def test_the_two_arms_run_identical_task_ids(tier):
    """The whole point of two arms is a like-for-like comparison. Different task ids would make
    the two rewards incomparable for a reason that has nothing to do with delivery."""
    ids = {arm: [r["id"] for r in json.loads(
        (REPO / "ci/benchmarks" / arm / tier / "tasks.json").read_text(encoding="utf-8"))]
        for arm in ARMS}
    assert ids[ARMS[0]] == ids[ARMS[1]], f"{tier}: arms disagree on task ids"


def test_smoke_matches_the_plain_tau2_leg():
    """Sharing tau2/smoke's ids makes tau2 / direct / spa three readings of one sample rather
    than three different samples. Deliberate; change it and say so."""
    def ids(bench):
        return [r["id"] for r in json.loads(
            (REPO / "ci/benchmarks" / bench / "smoke/tasks.json").read_text(encoding="utf-8"))]
    assert ids(ARMS[0]) == ids("tau2")


@pytest.mark.parametrize("arm", ARMS)
def test_the_recorded_agent_is_a_gateway_model_not_the_spa_sentinel(arm):
    """`ibm/skillberry-local` is not a model the gateway serves — it is the signal to route the
    turn through the Proxy-Agent, which then calls a real model. Recording it as a tier's
    `agent` would make sync_models.py report an unserved agent on every scheduled pass."""
    for tier in TIERS:
        rows = json.loads((REPO / "ci/benchmarks" / arm / tier / "tasks.json").read_text())
        agents = {r.get("agent") for r in rows}
        assert "ibm/skillberry-local" not in agents
        assert agents == {"aws/gpt-oss-120b"}, agents


# ---- run_suite.sh wiring ---------------------------------------------------------

def test_the_adapter_is_sourced_from_the_example_not_duplicated_into_templates():
    """A copy under templates/adapters/ would duplicate ~700 lines per arm and be free to drift
    from the example a reviewer actually reads."""
    case = _arm_case()
    assert "examples/skillberry_benchmarks_tau2_airline/$ARM" in case
    assert "$TPL/" not in case, "the arms must not source an adapter from templates/adapters/"
    for tpl in (REPO / "templates/adapters").iterdir():
        assert "skillberry" not in tpl.name.lower(), (
            f"{tpl.name} duplicates an arm's adapter into templates/ — source it from "
            "examples/skillberry_benchmarks_tau2_airline/<arm>/ instead")


def test_both_arms_land_their_own_optimizer_instructions():
    """The generic template names policy.md and tools.py. The direct arm has no policy surface
    and the spa arm's artifact is a skill package, so the shared text sends the optimizer
    looking for files that do not exist."""
    case = _arm_case()
    assert 'cp "$ARM_DIR/optimizer/INSTRUCTIONS.md" "$PROJ/optimizer/"' in case
    assert 'OPT_INSTRUCTIONS="$PROJ/optimizer/INSTRUCTIONS.md"' in case
    for arm in ARMS:
        d = REPO / "examples/skillberry_benchmarks_tau2_airline" / arm.split("_")[-1]
        assert (d / "optimizer/INSTRUCTIONS.md").is_file(), f"{d} ships no INSTRUCTIONS.md"


def test_comments_in_unquoted_heredocs_are_plain_text():
    """A '#' line inside a heredoc is still SHELL TEXT when the delimiter is unquoted.

    Both hazards were introduced here and both misfired on a real invocation:
      * backticks — writing the key names in markdown style made bash try to EXECUTE them, so
        an arm run printed "intervention: command not found" six times. The spec came out
        correct, so nothing failed loudly; it just looked like a broken script.
      * a dollar sign — a literal $VAR in the explanatory comment dereferenced a name that does
        not exist and tripped `set -u`, which DID abort the run.

    Prose belongs in comments ABOVE the heredoc, where the shell never reads it.
    """
    lines = RUN_SUITE.read_text(encoding="utf-8").splitlines()
    offenders, i = [], 0
    while i < len(lines):
        m = re.search(r"<<-?([A-Za-z_][A-Za-z0-9_]*)\s*$", lines[i])
        if not m:                       # quoted delimiters (<<'PY') expand nothing: skip them
            i += 1
            continue
        word = m.group(1)
        i += 1
        while i < len(lines) and lines[i].strip() != word:
            ln = lines[i]
            if ln.lstrip().startswith("#"):
                for ch, why in (("`", "runs a command"), ("$", "dereferences a name")):
                    if ch in ln:
                        offenders.append((i + 1, word, ch, why, ln.strip()[:70]))
            elif "`" in ln:
                offenders.append((i + 1, word, "`", "runs a command", ln.strip()[:70]))
            i += 1
    assert not offenders, (
        "shell-active character inside an unquoted heredoc:\n"
        + "\n".join(f"  line {n} (<<{w}): {c!r} {why} — {t}" for n, w, c, why, t in offenders))


def test_the_spec_template_carries_the_per_bench_extra_keys():
    sh = RUN_SUITE.read_text(encoding="utf-8")
    assert "${EXTRA_YAML:-}" in sh, "the generated spec no longer interpolates EXTRA_YAML"
    assert 'optimizer_instructions_file: "${OPT_INSTRUCTIONS:-}"' in sh


@pytest.mark.parametrize("arm,expect", [
    ("direct", {"actions", "capability_sources", "runner_repo_path"}),
    ("spa", {"actions", "capability_sources", "intervention", "skill_name",
             "protected_paths", "runner_repo_path"}),
])
def test_each_arms_extra_yaml_parses_and_declares_its_delivery(arm, expect):
    """The extra keys are assembled as shell text, so a typo is invisible until a live run
    reads the spec. Parse each block with the reader core actually uses."""
    case = _arm_case()
    blocks = re.findall(r'EXTRA_YAML="(.*?)"\n', case, re.S)
    assert len(blocks) == 2, f"expected one EXTRA_YAML per arm, found {len(blocks)}"
    block = blocks[0 if arm == "direct" else 1]
    text = block.replace('\\"', '"').replace("$SB_DIR", "/tmp/skillberry-benchmarks")
    parsed = read_yaml(text)
    assert set(parsed) == expect, f"{arm}: parsed {sorted(parsed)}"
    assert parsed["runner_repo_path"].startswith("/"), (
        "runner_repo_path must be ABSOLUTE — the arms' committed specs use a project-relative "
        "path that resolves to nothing under ci/benchmarks/.work/")
    if arm == "spa":
        assert parsed["intervention"] == "spa"
        assert parsed["skill_name"] == "my_skill"
        assert "my_skill/SKILL.md" in parsed["protected_paths"]
        assert "primitive_tools/*" in parsed["protected_paths"]


def test_the_spa_arm_matches_the_adapters_own_concurrency():
    """The CI leg must not invent a different value from the one the arm runs with locally."""
    case = _arm_case()
    spa = case.split('if [ "$ARM" = "direct" ]', 1)[1].split("else", 1)[1]
    adapter = (REPO / "examples/skillberry_benchmarks_tau2_airline/spa/adapters/adapter.py"
               ).read_text(encoding="utf-8")
    default = re.search(r'TAU2_MAX_CONCURRENCY", "(\d+)"', adapter).group(1)
    assert f"TAU2_MAX_CONCURRENCY:-{default}" in spa, (
        f"adapter defaults to {default}; the spa leg must use the same")
    assert 'TAU2_AGENT_MODEL:-ibm/skillberry-local' in spa, "spa delivery needs the sentinel"


def test_native_sims_are_on_for_the_tau2_legs():
    """A rollout that fails before scoring is only readable from its raw trajectory. Written to the
    run dir only; not uploaded."""
    sh = RUN_SUITE.read_text(encoding="utf-8")
    assert "tau2|skillberry_tau2_*) _NATIVE_SIMS_DEFAULT=1" in sh
    assert "*)                      _NATIVE_SIMS_DEFAULT=0" in sh, "other benches stay off"
    assert 'CAPEVOLVE_NATIVE_SIMS:-$_NATIVE_SIMS_DEFAULT' in sh, "env must still win"


def test_the_arms_use_their_own_venv():
    """Both arms install tau2 from skillberry-benchmarks; the `tau2` leg installs the public
    checkout. Same package name, two sources, both editable — one venv means whichever ran last
    wins, and the loser fails with a missing domain rather than an install error."""
    setup = CI_SETUP.read_text(encoding="utf-8")
    head = setup.split("case \"$BENCH\" in", 1)[1].split("esac", 1)[0]
    assert 'skillberry_tau2_*) VENV="$CACHE/venv-skillberry-tau2"' in head, (
        "the arms must not share the venv the tau2 leg installs its own tau2 into")
    assert 'VENV="$CACHE/venv"' in head, "every other bench keeps the shared venv"


def test_the_spa_arm_sets_the_upstream_model_the_proxy_calls():
    """SPA_MODEL_NAME must be derived from AGENT_MODEL, not left unset or pinned.

    CI has no repo-root .env, and unset makes the adapter fall back to a hardcoded default — so a
    dispatched agent_model would be silently ignored by both the proxy and the report.
    """
    case = _arm_case()
    spa = case.split('if [ "$ARM" = "direct" ]', 1)[1].split("else", 1)[1]
    code = "\n".join(ln for ln in spa.splitlines() if not ln.strip().startswith("#"))
    assert "SPA_MODEL_NAME" in code, "the spa leg must set the proxy's upstream model"
    assert "openai/$AGENT_MODEL" in code, "derive it from AGENT_MODEL"
    assert "openai/*)" in code, "openai/openai/... is a 404; only prefix when absent"
    direct = case.split('if [ "$ARM" = "direct" ]', 1)[1].split("else", 1)[0]
    assert "SPA_MODEL_NAME" not in direct, "the direct arm has no proxy"


def test_the_env_manager_log_lives_in_tmp_and_is_rotated_by_the_shared_helper():
    """Every log this stack produces lives in /tmp, with one rotation implementation in the tree.
    tau2's env manager is not a Skillberry service, so spa_env does not launch it -- but the leg
    that starts it owns bounding its log, as the arm's own run.sh does."""
    case = _arm_case()
    assert "ENV_LOG=/tmp/env_manager.log" in case, "the env manager log must live in /tmp"
    assert "$OUT/env_manager.log" not in case, "no service log may be written into $OUT"
    assert "spa_env.rotate_if_large(" in case, (
        "rotate through the shared helper rather than reimplementing rotation here")


def test_the_env_manager_health_probe_uses_a_route_it_actually_serves():
    """The Environment Manager is a FastAPI app with NO /health route.

    Probing /health reports a healthy service as dead: the start branch's poll would burn all 60
    attempts and the leg would fail with the service running perfectly. /docs (or /) is what the
    arm's own run.sh probes, and it is what exists.
    """
    case = _arm_case()
    env_block = case.split("ENV_LOG=", 1)[1].split("# Store, then Proxy-Agent", 1)[0]
    # CODE only: the comment above the probe names /health precisely to say why it is wrong,
    # and matching that would be a false positive.
    code = "\n".join(ln for ln in env_block.splitlines() if not ln.strip().startswith("#"))
    assert "/health" not in code, "no /health route exists on this service"
    assert "/docs" in code, "probe /docs, which the app does serve"


def test_the_spa_arm_tears_its_stack_down():
    """The arm's own run.sh leaves the stack up for a human. CI has no operator, and a proxy
    still bound to the previous leg's skill is a silent wrong-candidate hazard for the next
    job on this serialized runner."""
    case = _arm_case()
    assert "trap _spa_teardown EXIT" in case
    assert "spa_env.stop_all()" in case
    assert "pkill -f" in case, "stop_all() does not own tau2's Environment Manager"


def test_the_spa_arm_reads_service_logs_and_never_writes_them():
    """Service logs belong to the services, not to this leg.

    Each rotates its own from inside the process holding the fd -- the only place a live log can
    be rotated: renaming under a writer leaves it appending to a deleted inode while the fresh
    file stays empty. So CI may only READ bounded tails into the artifacts.
    """
    case = _arm_case()
    spa = case.split('if [ "$ARM" = "direct" ]', 1)[1].split("else", 1)[1]
    assert "SPA_VENDOR_DIR" in spa, "the run must agree with ci_setup.sh on the vendor dir"
    assert ': > "$_log"' not in spa, "must not truncate a log a live service owns"
    assert "tail -c" in spa, "no bounded tail captured for the artifacts"
    # Paths come from spa_env rather than being retyped, so they cannot drift.
    for name in ("AGENT_LOG_FILE", "STORE_LOG_FILE", "AGENT_TOOLS_LOG_FILE",
                 "STORE_TOOLS_LOG_FILE"):
        assert f"spa_env.{name}" in spa, f"tail capture should source {name} from spa_env"

    setup = CI_SETUP.read_text(encoding="utf-8")
    arm_case = setup.split("  skillberry_tau2_direct|skillberry_tau2_spa)", 1)[1] \
                    .split("\n  skillsbench)", 1)[0]
    assert 'export SPA_VENDOR_DIR="$CACHE/spa-vendor"' in arm_case, (
        "the stack must be provisioned into the cache, not the checkout — actions/checkout "
        "wipes untracked files, so the default <repo>/vendor re-clones both services per run")
    assert "SPA_VENDOR_DIR=$SPA_VENDOR_DIR\" >> \"$GITHUB_ENV\"" in arm_case, (
        "SPA_VENDOR_DIR must reach the Run suite step, or the run re-provisions mid-leg")
    assert ': > "$_log"' not in arm_case, (
        "setup must not truncate service logs either — see the fd argument above")


def test_the_spa_log_paths_the_leg_captures_all_exist_in_spa_env():
    """A tail capture naming a constant spa_env does not export would silently capture nothing."""
    src = (REPO / "skills/interventions/llm-proxies/spa/scripts/spa_env.py").read_text()
    for name in ("AGENT_LOG_FILE", "STORE_LOG_FILE", "AGENT_TOOLS_LOG_FILE",
                 "STORE_TOOLS_LOG_FILE"):
        assert re.search(rf"^{name}\s*=", src, re.M), f"spa_env no longer defines {name}"


def test_the_direct_arm_starts_no_services():
    """Delivery in-process is the whole distinction; a direct leg that quietly needed the stack
    would not be measuring the direct path."""
    case = _arm_case()
    direct = case.split('if [ "$ARM" = "direct" ]', 1)[1].split("else", 1)[0]
    for forbidden in ("spa_env", "start_store", "EnvironmentManager", "SPA_REMOTE_ENV_URL"):
        assert forbidden not in direct, f"direct arm should not touch {forbidden}"


# ---- ci_setup.sh -----------------------------------------------------------------

def test_the_arms_install_the_pinned_skillberry_build_not_public_tau2():
    """The `tau2` leg installs sierra-research/tau2-bench, which has neither the
    `airline_skillberry` domain the spa arm needs nor the [skillberry] extra. ONE build for
    both arms is what keeps direct-vs-spa meaningful."""
    sh = CI_SETUP.read_text(encoding="utf-8")
    case = sh.split("  skillberry_tau2_direct|skillberry_tau2_spa)", 1)[1].split("\n  skillsbench)", 1)[0]
    assert "skillberry-ai/skillberry-benchmarks" in case
    assert "tau2/tau2-bench[skillberry]" in case
    # CODE only: the comment above the case deliberately names sierra-research to say why the
    # public checkout is not used here, and matching that would be a false positive.
    code = "\n".join(ln for ln in case.splitlines() if not ln.strip().startswith("#"))
    assert "sierra-research" not in code


def test_the_ci_pin_matches_the_examples_own_pin():
    """A CI number and a local `bash examples/.../run.sh` number must refer to the same
    benchmark code, or they are not comparable and nobody would know."""
    sh = CI_SETUP.read_text(encoding="utf-8")
    ci_ref = re.search(r'BENCH_REF="\$\{BENCH_REF:-([0-9a-f]{40})\}"', sh).group(1)
    for arm in ("direct", "spa"):
        setup = (REPO / "examples/skillberry_benchmarks_tau2_airline" / arm / "setup.sh"
                 ).read_text(encoding="utf-8")
        arm_ref = re.search(r'BENCH_REF="\$\{BENCH_REF:-([0-9a-f]{40})\}"', setup).group(1)
        assert arm_ref == ci_ref, f"{arm}/setup.sh pins {arm_ref}, ci_setup.sh pins {ci_ref}"


# ---- the integration workflow is how an arm's single-task tier is reachable ---------

def test_the_integration_workflow_can_select_either_arm():
    """`integration` is not a tier benchmarks.yml can dispatch (its picker offers
    smoke/pilot/full), so this workflow is the only route to the one-task tier — the cheap check
    to run on an arm before spending a curated tier."""
    wf = (REPO / ".github/workflows/integration-tests.yml").read_text(encoding="utf-8")
    options = re.search(r"options: \[(.*?)\]", wf).group(1)
    for arm in ARMS:
        assert arm in options, f"{arm} not selectable in the integration workflow"


def test_the_integration_workflow_still_defaults_to_tau2():
    """A PR-label run supplies no inputs. If the fallback ever stopped being 'tau2', the
    `integration-test` label would silently start running a different benchmark — an arm leg
    installs a different tau2 build and (for spa) starts three services, so a label run would
    stop measuring what it has always measured."""
    wf = (REPO / ".github/workflows/integration-tests.yml").read_text(encoding="utf-8")
    assert re.search(r"default: tau2", wf), "the bench input's default moved off tau2"
    # Every interpolation of the input must carry the same fallback, including the job name and
    # the artifact paths — a missing `|| 'tau2'` yields an empty path segment on a label run.
    uses = re.findall(r"\$\{\{ github\.event\.inputs\.bench[^}]*\}\}", wf)
    assert uses, "nothing reads the bench input"
    for u in uses:
        assert "|| 'tau2'" in u, f"missing tau2 fallback in {u}"


def test_only_the_spa_arm_provisions_the_skillberry_stack():
    sh = CI_SETUP.read_text(encoding="utf-8")
    case = sh.split("  skillberry_tau2_direct|skillberry_tau2_spa)", 1)[1].split("\n  skillsbench)", 1)[0]
    assert 'if [ "$BENCH" = "skillberry_tau2_spa" ]; then' in case
    assert "spa_env.provision()" in case
    # PROVISION, never start: starting during setup is the anti-pattern the intervention skill
    # calls out, and the arm's own setup.sh is careful about the same line.
    assert "start_store" not in case and "start_spa" not in case
