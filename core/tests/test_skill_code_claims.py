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
