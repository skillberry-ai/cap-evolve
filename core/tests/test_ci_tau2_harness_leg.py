"""The tau2_harness CI leg: the tau2 leg plus the agent-harness capability (#1018).

The leg exists to answer one question with an A/B pair — does adding the agent-harness
capability help on tau2 airline? — so what is pinned here is what would silently break the
comparison with the plain `tau2` leg:

* the two legs run the same task ids, adapter and seed;
* the harness overlay joins the seed (and its README does not, since system-prompt reads any
  top-level .md as prompt text);
* the seed harness behaves like tau2's plain llm_agent (same tools, same system prompt);
* a candidate without harness.json still runs the plain llm_agent, so the control leg is
  unchanged;
* lessons from the test split are never loaded, and the agent factory never reads the task
  object (it holds the user simulator's hidden instructions).

The adapter checks that need tau2 itself skip when tau2 is not installed (core CI does not
install it); everything else is static analysis or runs with stub paths.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github/workflows/benchmarks.yml"
RUN_SUITE = REPO / "ci/benchmarks/lib/run_suite.sh"
CI_SETUP = REPO / "ci/benchmarks/lib/ci_setup.sh"
ADAPTER = REPO / "benchmarks/tau2/template/adapter.py"
SEED = REPO / "benchmarks/tau2/examples/airline/seed_capability"
OVERLAY = REPO / "benchmarks/tau2/examples/airline/harness_seed"
sys.path.insert(0, str(REPO / "core"))


# ---------------------------------------------------------------- wiring (static)

def test_the_leg_is_dispatchable_and_planned():
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert "options: [tau2, tau2_harness," in wf
    assert '"tau2", "tau2_harness",' in wf


@pytest.mark.parametrize("tier", ["smoke", "canary", "full", "integration"])
def test_both_legs_run_identical_task_lists(tier):
    a = json.loads((REPO / f"ci/benchmarks/tau2/{tier}/tasks.json").read_text())
    b = json.loads((REPO / f"ci/benchmarks/tau2_harness/{tier}/tasks.json").read_text())
    assert a == b, f"tau2_harness/{tier}/tasks.json drifted from tau2/{tier}/tasks.json"


def test_setup_installs_the_same_tau2_and_prints_its_commit():
    sh = CI_SETUP.read_text(encoding="utf-8")
    assert "  tau2|tau2_harness)" in sh
    assert 'tau2-bench @ $(git -C "$CACHE/tau2-bench" rev-parse HEAD' in sh


def test_native_sims_are_on_for_the_leg():
    assert "tau2|tau2_harness|tau2_sierra|tau2_sierra_blackbox) _NATIVE_SIMS_DEFAULT=1" in \
        RUN_SUITE.read_text(encoding="utf-8")


# ------------------------------------------------------ the run_suite case, executed

def _tau2_case() -> str:
    sh = RUN_SUITE.read_text(encoding="utf-8")
    head = "  tau2|tau2_harness)\n"
    start = sh.index(head)
    end = sh.index("\n    ;;\n", start)
    return sh[start:end] + "\n    ;;\n"


@pytest.mark.parametrize("bench", ["tau2", "tau2_harness"])
def test_the_case_block_builds_the_right_project(tmp_path, bench):
    proj = tmp_path / "proj"
    (proj / "adapters").mkdir(parents=True)
    script = (
        "set -euo pipefail\n"
        f'REPO="{REPO}"; TPL="$REPO/benchmarks"; PROJ="{proj}"; WORK="{tmp_path}"\n'
        'AGENT_MODEL_WIRE=m; AGENT_API_BASE=http://x; AGENT_API_KEY=k\n'
        f'BENCH="{bench}"\n'
        'case "$BENCH" in\n' + _tau2_case() + "esac\n"
        'echo "CAPS=$CAPS"; echo "OPT=${OPT_INSTRUCTIONS:-}"\n'
    )
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout
    caps = next(ln for ln in out.splitlines() if ln.startswith("CAPS=")).split("=", 1)[1]
    opt = next(ln for ln in out.splitlines() if ln.startswith("OPT=")).split("=", 1)[1]
    seed = proj / "seed_capability"
    if bench == "tau2":
        assert caps == "[system-prompt, tools]" and opt == ""
        assert not (seed / "harness.json").exists(), "the control leg must not get the overlay"
        return
    assert caps == "[system-prompt, tools, agent-harness]"
    for f in ("harness.json", "harness_policy.json", "memory/lessons.jsonl"):
        assert (seed / f).exists(), f
    assert not (seed / "README.md").exists() and not (seed / "OPTIMIZER_NOTE.md").exists()
    text = Path(opt).read_text(encoding="utf-8")
    default = (REPO / "benchmarks/_scaffold/project/optimizer/INSTRUCTIONS.md").read_text()
    assert text.startswith(default), "the leg must extend, not replace, the default instructions"
    assert "## The agent harness (this benchmark)" in text


def test_the_seed_overlay_validates_cleanly(tmp_path):
    cand = tmp_path / "c"
    shutil.copytree(SEED, cand)
    for f in ("harness.json", "harness_policy.json"):
        shutil.copy(OVERLAY / f, cand)
    shutil.copytree(OVERLAY / "memory", cand / "memory")
    from cap_evolve import harness
    os.environ.setdefault("CAPEVOLVE_SKILLS_DIR", str(REPO / "skills"))
    rep = harness._capability_validate(["system-prompt", "tools", "agent-harness"], cand)
    assert rep is not None
    assert not [p for p in rep.problems if p.startswith("agent-harness")], rep.problems
    assert not [w for w in rep.warnings if w.startswith("agent-harness")], rep.warnings


def test_the_policy_wires_exactly_what_the_adapter_reads():
    pol = json.loads((OVERLAY / "harness_policy.json").read_text())
    assert "code" not in pol["allow"], "hooks are not wired in tau2"
    adapter = _adapter()
    assert set(adapter.HARNESS_WIRED) <= set(pol["wired"])


# ------------------------------------------------------- adapter, without tau2

def _adapter():
    os.environ.setdefault("MODEL", "litellm_proxy/dummy")
    sys.path.insert(0, str(REPO / "benchmarks/_shared"))
    spec = importlib.util.spec_from_file_location("tau2_template_adapter_harness", ADAPTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_cand(tmp_path, cfg=None, lessons=()):
    cand = tmp_path / "cand"
    cand.mkdir()
    if cfg is not None:
        (cand / "harness.json").write_text(json.dumps(cfg))
    if lessons:
        (cand / "memory").mkdir()
        (cand / "memory/lessons.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lessons))
    return cand


LESSON = {"id": "confirm", "when": "before any booking change", "do": "get an explicit yes",
          "evidence": "train: 3 traces", "source_split": "train", "tags": ["change"]}


def test_no_harness_json_runs_the_plain_llm_agent(tmp_path):
    A = _adapter()
    name, steps, _args, h = A._run_settings(_write_cand(tmp_path))
    assert (name, steps, h) == ("llm_agent", 100, None)
    assert A._harness_summary(None) == {"agent": "llm_agent"}


def test_test_split_and_malformed_lessons_are_not_loaded(tmp_path):
    A = _adapter()
    cand = _write_cand(tmp_path, {"memory": {"mode": "all"}},
                       [LESSON, dict(LESSON, id="leak", source_split="test")])
    with (cand / "memory/lessons.jsonl").open("a") as fh:
        fh.write("{not json\n")
    h = A._load_harness(cand)
    assert [x["id"] for x in h["lessons"]] == ["confirm"]


def test_memory_off_loads_no_lessons_and_max_entries_caps(tmp_path):
    A = _adapter()
    two = [LESSON, dict(LESSON, id="b", do="other")]
    assert A._load_harness(_write_cand(tmp_path, {"memory": {"mode": "off"}}, two))["lessons"] == []
    other = tmp_path / "x"
    other.mkdir()
    h = A._load_harness(_write_cand(other, {"memory": {"mode": "all", "max_entries": 1}}, two))
    assert [x["id"] for x in h["lessons"]] == ["confirm"]


def test_settings_map_to_the_run_config(tmp_path):
    A = _adapter()
    pytest.importorskip("tau2")
    cand = _write_cand(tmp_path, {"loop": {"max_steps": 40}, "sampling": {"temperature": 0.3}})
    name, steps, args, _h = A._run_settings(cand)
    assert (name, steps, args.get("temperature")) == (A.HARNESS_AGENT, 40, 0.3)


def test_lessons_block_and_retrieval():
    A = _adapter()
    other = dict(LESSON, id="bags", when="the user asks about checked bags", tags=["baggage"],
                 do="look up the membership tier first")
    block = A._lessons_block([LESSON])
    assert block.startswith("<lessons>") and "When before any booking change: get an explicit yes" in block
    assert A._lessons_block([]) == ""
    got = A._retrieve_lessons([LESSON, other], "how many checked bags can I bring", 1)
    assert [x["id"] for x in got] == ["bags"]
    assert A._retrieve_lessons([LESSON, other], "anything", None) == [LESSON, other]


def test_the_factory_never_reads_the_task_object():
    src = ADAPTER.read_text(encoding="utf-8")
    body = src[src.index("def _harness_agent_factory"):src.index("def _register_harness_agent")]
    assert 'kwargs.get("task")' not in body and "kwargs['task']" not in body


# ------------------------------------------------------------ adapter, with tau2

def test_seed_harness_matches_the_plain_agent_and_think_tool_is_added(tmp_path):
    pytest.importorskip("tau2")
    A = _adapter()
    from tau2.agent.llm_agent import create_llm_agent
    from tau2.registry import registry

    plain = tmp_path / "plain"
    shutil.copytree(SEED, plain)
    cand = tmp_path / "cand"
    shutil.copytree(SEED, cand)
    for f in ("harness.json", "harness_policy.json"):
        shutil.copy(OVERLAY / f, cand)
    shutil.copytree(OVERLAY / "memory", cand / "memory")
    ad = A.Adapter()
    ad.apply(plain)
    env_plain = registry._domains["airline"]()
    ad.apply(cand)
    env_seed = registry._domains["airline"]()
    assert sorted(t.name for t in env_plain.get_tools()) == sorted(t.name for t in env_seed.get_tools())
    A._run_settings(cand)
    fac = registry.get_agent_factory(A.HARNESS_AGENT)
    seed_agent = fac(tools=env_seed.get_tools(), domain_policy=env_seed.policy, llm="x",
                     llm_args={}, task=None)
    plain_agent = create_llm_agent(env_plain.get_tools(), env_plain.policy, llm="x", llm_args={})
    assert seed_agent.system_prompt == plain_agent.system_prompt

    cfg = json.loads((cand / "harness.json").read_text())
    cfg["loop"]["think_tool"] = True
    (cand / "harness.json").write_text(json.dumps(cfg))
    ad.apply(cand)
    env = registry._domains["airline"]()
    assert "think" in {t.name for t in env.get_tools()}
