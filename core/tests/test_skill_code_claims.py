"""Pin the code facts the four merged skill PRs (#368/#369/#373/#380) ASSERT.

A skill that describes behavior the code does not have is the exact failure mode
those PRs were written to remove — and three of them came straight back when #386
and #350 restructured the code afterwards. These tests are the mechanical half of
"the skill and the code cannot drift silently": each one fails the day the code
changes, so whoever changes it is told which SKILL.md sentence is now a lie.

Deliberately NOT a doc linter. Each test pins ONE behavior a skill states in
plain language, and names the sentence it is pinning.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

CORE = str(Path(__file__).resolve().parents[1])
if CORE not in sys.path:
    sys.path.insert(0, CORE)

from cap_evolve import tool_surface  # noqa: E402
from cap_evolve.types import NON_CAPABILITY_DIRS, NON_CAPABILITY_FILES  # noqa: E402

SKILLS = Path(__file__).resolve().parents[2] / "skills"


# ---- #373 / #352: the policy path ----------------------------------------

def test_load_policy_reads_the_capability_dir_not_inputs(tmp_path):
    """`mcp-tool/SKILL.md`: "the effective policy is `policy.json` **in the
    capability dir** (not `inputs/policy.json`)". Seven doc surfaces used to claim
    `inputs/`, so a policy written as documented was silently ignored (#352)."""
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs" / "policy.json").write_text(json.dumps({"allow": ["schema"]}))
    default = {"allow": ["description"]}
    assert tool_surface.load_policy(tmp_path, default)["allow"] == ["description"], \
        "inputs/policy.json must NOT be read — no doc surface may promise it"

    (tmp_path / "policy.json").write_text(json.dumps({"allow": ["schema"]}))
    assert tool_surface.load_policy(tmp_path, default)["allow"] == ["schema"]


def test_load_policy_docstrings_name_the_path_it_actually_reads():
    """The loader's own docstrings are the most authoritative surface there is; both used to
    name `inputs/policy.json` while the code read `<capability_dir>/policy.json` (#352).

    Naming the wrong path is fine when it is being ruled OUT — what must never happen again
    is a docstring that presents `inputs/policy.json` as the file the loader reads.
    """
    for where, text in (("load_policy docstring", tool_surface.load_policy.__doc__),
                        ("module docstring", tool_surface.__doc__)):
        flat = " ".join((text or "").split())
        assert "<capability_dir>/policy.json" in flat, \
            f"{where} does not name <capability_dir>/policy.json, the path load_policy reads"
        if "inputs/policy.json" in flat:
            assert ("NOT ``inputs/policy.json``" in flat or "silently ignored" in flat), \
                f"{where} names inputs/policy.json without ruling it out"


# ---- #373: apply() filters the LABEL, not the effect ---------------------

def test_apply_does_not_refuse_a_schema_rewrite_smuggled_through_params(tmp_path):
    """`mcp-tool/SKILL.md`: "a `params` value is shallow-merged into `parameters`, so a
    value containing `properties`, `type`, `required`, or `enum` rewrites the wire
    schema and is *not* refused" (#372). If apply() ever starts refusing this, that
    sentence must change from a warning into a description of a guard."""
    (tmp_path / "tools.json").write_text(json.dumps({"tools": [
        {"name": "t", "description": "d",
         "parameters": {"type": "object", "properties": {"n": {"type": "integer"}}},
         "examples": []}]}))
    policy = {"allow": ["description", "params", "examples", "add", "remove"]}
    report = tool_surface.apply(tmp_path, policy, [
        {"tool": "t", "kind": "params",
         "value": {"type": "array", "required": ["x"], "properties": {}}}])
    assert report["refused"] == [], "apply() gained a guard the SKILL.md says it lacks"
    params = json.loads((tmp_path / "tools.json").read_text())["tools"][0]["parameters"]
    assert params["type"] == "array" and params["required"] == ["x"], \
        "the wire schema was NOT rewritten — SKILL.md's warning is now wrong"

    report = tool_surface.apply(tmp_path, policy, [
        {"tool": "u", "kind": "add",
         "value": {"name": "u", "description": "d", "parameters": {}, "code": "x"}}])
    assert report["refused"] == []
    added = [t for t in json.loads((tmp_path / "tools.json").read_text())["tools"]
             if t["name"] == "u"][0]
    assert "code" in added, "an `add` no longer carries a `code` key through unrefused"


def test_validate_does_not_consult_the_policy():
    """`mcp-tool/SKILL.md`: "`validate()` will not catch either — it checks
    well-formedness only ... and reports `ok: true` on a schema-rewritten artifact"."""
    assert "load_policy" not in inspect.getsource(tool_surface.validate)


# ---- #369: what gepa's component list excludes ---------------------------

def test_optimizer_read_context_is_never_an_editable_component():
    """`gepa/SKILL.md` no longer claims round-robin can burn an iteration on
    `.claude/`/`CLAUDE.md`: #386 added the injected read-context to the exclusions,
    which is what makes that claim false. If it is removed again, restore the gap."""
    for name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "REFLECTION.md", "FOCUS.md"):
        assert name in NON_CAPABILITY_FILES, f"{name} is an editable gepa component again"
    for name in (".claude", ".agents", "guidance", "trajectories", "prior_iterations"):
        assert name in NON_CAPABILITY_DIRS, f"{name}/ is an editable gepa component again"


# ---- #380: the gap skillopt's SKILL.md documents (#371) ------------------

def test_skillopt_minibatch_focus_is_still_empty_by_construction():
    """`skillopt/SKILL.md` § Known gaps: train mini-batch ids filter the parent's **val**
    rows, so the focus summary classifies ZERO tasks and the failure index is empty (#371).

    This test FAILS the day #371 is fixed — on purpose. The gap is documented in the
    skill, so the fix must delete that paragraph in the same change.

    Asserts the PROPERTY (nothing classified, no failure index), not the sentence: an
    earlier version pinned the literal "of 0 tasks" and #391 reworded the summary to
    "of 0 focused task(s) of N on val" while the gap stayed exactly as real. A tripwire
    that fires on rewording is a false alarm, which is worse than none.
    """
    from cap_evolve import harness
    from cap_evolve.loop import SplitResult

    val = SplitResult.from_dict({
        "split": "val", "reward": 0.5, "stderr": 0.0,
        "per_task": [{"task_id": "v1", "reward": 0.0, "feedback": "boom"},
                     {"task_id": "v2", "reward": 1.0, "feedback": ""}]})
    # train ids, against a val result — exactly what skillopt hands ctx.instructions().
    rendered = harness._focus_instructions(val, ["t1", "t2"], "mini-batch of 2 train tasks, L=4",
                                           algorithm="skillopt")
    summary = next(ln for ln in rendered.splitlines() if ln.startswith("Focus:"))
    assert "0 solid / 0 flaky / 0 failing" in summary, (
        "the mini-batch focus block classifies tasks now — #371 looks fixed, so remove the "
        f"'mini-batch never reaches the optimizer' gap from skillopt/SKILL.md. Got: {summary}")
    assert "boom" not in rendered, (
        "a val task's feedback reached a train-focused prompt — #371 looks fixed; update "
        "skillopt/SKILL.md")


# ---- #368: the reference pointer must not promise a missing rule ---------

def test_agent_optimize_reference_pointers_are_not_empty_promises():
    """`agent-optimize/SKILL.md` names the sign test as living in
    `references/measured-lessons.md`. #368 moved the section but dropped the rule."""
    # Both files are hard-wrapped, so any multi-word phrase can straddle a newline; and the
    # reference emphasises rules in caps, so compare case-insensitively.
    body = " ".join((SKILLS / "algorithms/agent-optimize/SKILL.md")
                    .read_text(encoding="utf-8").lower().split())
    lessons = " ".join((SKILLS / "algorithms/agent-optimize/references/measured-lessons.md")
                       .read_text(encoding="utf-8").lower().split())
    if "sign test" in body:
        assert "sign test" in lessons, \
            "SKILL.md points at measured-lessons.md for the sign test; it is not there"


# ---- #665 ws3: SKILL.md's rewritten loop must be mechanically followable -------

AO_SCRIPTS = SKILLS / "algorithms/agent-optimize/scripts"
AO_SKILL_MD = SKILLS / "algorithms/agent-optimize/SKILL.md"


def _load_script(name: str, modname: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(modname, AO_SCRIPTS / name)
    mod = importlib.util.module_from_spec(spec)
    if str(AO_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(AO_SCRIPTS))
    spec.loader.exec_module(mod)
    return mod


def test_plan_round_output_shape_matches_what_skill_md_tells_the_driver_to_read():
    """SKILL.md step 2 reads `plan_round.py`'s stdout for `slots[].{cluster_ids,affected_tasks,
    estimated_branches}` and `total_estimated_branches`, and feeds that number straight into
    `spend.py --n-siblings`. If `plan_round` ever renames or drops one of those keys, the step
    is no longer followable as written."""
    plan_round = _load_script("plan_round.py", "_ao_claims_plan_round")
    clusters = [
        {"signature": "timeout tool_a", "tasks": ["1", "2"], "score_lost": 1.2, "tag": "c1"},
        {"signature": "wrong_field tool_b", "tasks": ["3"], "score_lost": 0.3, "tag": "c2"},
    ]
    out = plan_round.plan_round(clusters, candidate_graph=None, afford=None)
    assert "slots" in out and "total_estimated_branches" in out, (
        "SKILL.md step 2 reads these two top-level keys; plan_round() no longer returns one")
    for slot in out["slots"]:
        for key in ("cluster_ids", "affected_tasks", "estimated_branches", "hypothesis_stub"):
            assert key in slot, f"SKILL.md step 2 reads slots[].{key}; a slot no longer has it"
    assert out["total_estimated_branches"] == sum(s["estimated_branches"] for s in out["slots"]), \
        "SKILL.md step 2 passes total_estimated_branches straight to spend.py --n-siblings"


def test_model_routing_roles_match_the_table_skill_md_prints():
    """SKILL.md's "Model routing" section prints a table naming exactly these seven roles
    against `resolve_model`'s own `ROLES`. A role added or renamed in the module without
    updating the table makes the table describe a role `resolve_model` doesn't accept, or
    silently omits one it does."""
    from cap_evolve.model_routing import ROLES

    body = AO_SKILL_MD.read_text(encoding="utf-8")
    for role in ROLES:
        assert f"`{role}`" in body, (
            f"model_routing.ROLES includes {role!r}; SKILL.md's Model routing table doesn't "
            "name it")


def test_gate_check_pareto_mode_is_reachable_as_skill_md_describes():
    """SKILL.md's "Pareto acceptance" section calls `gate_check.py --mode pareto` with
    `--objectives`/`--metrics-candidate`/`--metrics-current`/`--metrics-stderr-candidate`/
    `--metrics-stderr-current`. All five flags, and the mode itself, must actually exist on
    the script's parser — a prose instruction naming a flag the CLI refuses is the exact
    "capability exists, behavior doesn't" gap this rewrite exists to close."""
    gate_check = _load_script("gate_check.py", "_ao_claims_gate_check")
    assert "pareto" in gate_check.GATE_MODES, \
        "SKILL.md tells the driver to pass --mode pareto; gate_check.py does not accept it"
    parser = gate_check.build_parser()
    flags = {opt for a in parser._actions for opt in getattr(a, "option_strings", [])}
    for flag in ("--objectives", "--metrics-candidate", "--metrics-current",
                 "--metrics-stderr-candidate", "--metrics-stderr-current"):
        assert flag in flags, f"SKILL.md's Pareto acceptance section names {flag}; gate_check.py lacks it"


def test_gate_check_pareto_wiring_actually_reaches_gate_decide(tmp_path, monkeypatch):
    """Not just a CLI flag: the pareto-mode values gate_check.py parses must reach
    `cap_evolve.gate.decide`'s `objectives`/`metrics_*` kwargs, or the flags SKILL.md
    documents would be accepted and silently ignored."""
    gate_check = _load_script("gate_check.py", "_ao_claims_gate_check_wiring")
    captured = {}

    def _fake_decide(current_val, candidate_val, **kwargs):
        captured.update(kwargs)
        from cap_evolve.gate import GateDecision
        return GateDecision(accept=True, reason="stub", delta=0.0)

    monkeypatch.setattr(gate_check, "decide", _fake_decide)

    class _Res:
        reward, stderr, coverage = 0.5, 0.0, 1.0
        per_task = [{"task_id": "1", "reward": 1.0}]

    monkeypatch.setattr(gate_check.harness, "split_result_from_rollouts",
                        lambda *a, **k: _Res())
    monkeypatch.setattr(gate_check.harness, "_paired_deltas", lambda *a, **k: [])
    monkeypatch.setattr(gate_check.harness, "movement",
                        lambda *a, **k: {"broke": [], "fixed": [], "unresolved": []})
    monkeypatch.setattr(gate_check, "regressions", lambda *a, **k: [])
    monkeypatch.setattr(gate_check, "_frozen_coverage", lambda *a, **k: 1.0)

    class _FakeRunDir:
        best_id = "seed"
        def read_splits(self):
            class _S:
                def ids(self, split):
                    return []
            return _S()
        def candidate_dir(self, tag):
            return tmp_path / tag

    monkeypatch.setattr(gate_check.RunDir, "open", staticmethod(lambda p: _FakeRunDir()))

    rc = gate_check.main([
        "--run-dir", str(tmp_path), "--candidate", "cand_1", "--mode", "pareto",
        "--no-footprint",
        "--objectives", '[{"name": "reward", "direction": "maximize"}]',
        "--metrics-candidate", '{"cost": 1.0}', "--metrics-current", '{"cost": 2.0}',
        "--metrics-stderr-candidate", '{"cost": 0.1}', "--metrics-stderr-current", '{"cost": 0.1}',
    ])
    assert rc == 0
    assert captured.get("objectives") == [{"name": "reward", "direction": "maximize"}]
    assert captured.get("metrics_candidate") == {"cost": 1.0}
    assert captured.get("metrics_current") == {"cost": 2.0}
    assert captured.get("metrics_stderr_candidate") == {"cost": 0.1}
    assert captured.get("metrics_stderr_current") == {"cost": 0.1}


def test_evaluation_plan_stage_table_in_skill_md_matches_the_module_constants():
    """SKILL.md's step 5 names every stage 0-5 by its constant. If `evaluation_plan.py` ever
    renumbers or renames one, SKILL.md silently starts describing the wrong stage."""
    from cap_evolve import evaluation_plan as ep

    body = AO_SKILL_MD.read_text(encoding="utf-8")
    expected = {
        0: "STAGE_STATIC", 1: "STAGE_TARGETED_SMALL", 2: "STAGE_EXPANDED_CLUSTER",
        3: "STAGE_REGRESSION", 4: "STAGE_BROAD_PARTIAL", 5: "STAGE_FULL",
    }
    for value, const_name in expected.items():
        assert getattr(ep, const_name) == value, (
            f"evaluation_plan.{const_name} is no longer {value}; SKILL.md's stage guidance is stale")
        assert f"`{const_name}`" in body, (
            f"SKILL.md doesn't name stage {value} ({const_name}) as documented")


def test_merge_search_check_merge_compliance_is_the_function_skill_md_requires():
    """SKILL.md's "Stop & seal" section makes an unaddressed `merge_compliance_warning` a
    reportable violation, citing `measure.py`'s automatic `check_merge_compliance` call. Pin
    that the function still exists under that name and is still what `measure.py` calls."""
    merge_search = _load_script("merge_search.py", "_ao_claims_merge_search")
    assert hasattr(merge_search, "check_merge_compliance")
    measure_src = (AO_SCRIPTS / "measure.py").read_text(encoding="utf-8")
    assert "check_merge_compliance" in measure_src, (
        "SKILL.md says measure.py runs merge_search.check_merge_compliance at finalize time; "
        "measure.py no longer calls it")
