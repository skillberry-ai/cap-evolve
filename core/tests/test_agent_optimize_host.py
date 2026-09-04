"""``host.py`` — the headless host that lets a NON-INTERACTIVE caller drive agent mode.

agent-optimize's loop is prose in SKILL.md, executed by a conversational agent. CI has no
conversational agent, so before this script the algorithm was simply unavailable there:
``cap-evolve run`` prints a handoff and returns, and nothing drives the loop.

``host.py`` closes that gap without duplicating anything: it renders the driver briefing
from the spec + handoff and delegates the actual CLI invocation to the existing
``optimizers/run-optimizer`` runner (registry rows, model/budget flag mapping, cost
capture, CLI-present hard fail). What is tested here is everything that does NOT need a
model:

  * the briefing carries the handoff facts and the loop's own commands (a briefing that
    omits ``measure.py`` produces a run with no sealed number — the failure mode that
    makes an unattended run worthless);
  * an unknown host agent is refused BEFORE any spend;
  * ``--seal-only`` seals a run the agent left unfinalized, so a host that dies mid-loop
    still yields an honest result rather than a run dir CI reads as "crashed";
  * the Bash-tool timeout is raised — at the 10-minute default ceiling every full-val
    eval on a real benchmark is killed mid-flight and reads as a broken runner.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "skills" / "algorithms" / "agent-optimize"
HOST = SKILL / "scripts" / "host.py"


def _env() -> dict:
    return dict(os.environ, CAPEVOLVE_CORE=str(REPO / "core"),
                CAPEVOLVE_SKILLS_DIR=str(REPO / "skills"))


def _host(*argv: str, expect_rc: int = 0) -> dict:
    p = subprocess.run([sys.executable, str(HOST), *argv],
                       capture_output=True, text=True, env=_env())
    assert p.returncode == expect_rc, (
        f"host.py rc={p.returncode} (expected {expect_rc})\n"
        f"stdout: {p.stdout[:2000]}\nstderr: {p.stderr[:2000]}")
    try:
        return json.loads(p.stdout)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"host.py did not emit JSON: {p.stdout[:500]}") from exc


def _project(tmp: Path, *, n: int = 20, stop: str = "") -> Path:
    """A real project dir the subprocess can load — same shape the skill's check uses."""
    project = tmp / "project"
    (project / "adapters").mkdir(parents=True, exist_ok=True)
    (project / "adapters" / "adapter.py").write_text(
        "from cap_evolve.skillcheck import SyntheticAdapter\n\n\n"
        "class Adapter(SyntheticAdapter):\n"
        f"    def __init__(self):\n        super().__init__(n={n})\n",
        encoding="utf-8")
    stop = stop or "reach val mean >= 0.9, or stop after $5 or 30 minutes"
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ngate_mode: paired\ngate_k_se: 1.0\n"
        "capabilities: [system-prompt]\ncapability_path: seed_capability\n"
        f'stop_condition: "{stop}"\n',
        encoding="utf-8")
    return project


def _run_dir(tmp: Path, *, n: int = 20):
    """A baselined run dir — exactly what the agent-mode handoff points at."""
    from cap_evolve import Budget, RunDir, harness
    from cap_evolve.skillcheck import SyntheticAdapter, seed_capability_dir

    adapter = SyntheticAdapter(n=n)
    seed = seed_capability_dir(tmp, level=3)
    run_dir = RunDir.create(tmp / ".capevolve", ts="host", budget=Budget(max_iterations=5))
    harness.ensure_splits(adapter, run_dir, seed=0)
    harness.baseline(adapter, seed, run_dir=run_dir)
    return run_dir


def test_host_script_exists_and_is_documented_where_it_belongs():
    """Documented for operators, NOT inside the agent's per-trigger context.

    SKILL.md is what the hosted agent re-reads on every trigger, and it is capped at ~5000
    tokens with about 150 characters of headroom. host.py is not part of the loop the agent
    executes — the host invokes the agent, never the other way round — so spending that
    budget on it would push out guidance the agent does need. The skill's own scripts/
    already sets this precedent: `linkcheck.py` and `abstract.py` are likewise absent from
    SKILL.md, while every genuine loop helper is named there.

    So the contract is: host.py carries its own reasoning in its docstring, and the
    operator-facing docs explain when to reach for it.
    """
    assert HOST.is_file(), "skills/algorithms/agent-optimize/scripts/host.py is missing"

    skill_body = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[-1]
    assert len(skill_body) // 4 <= 5000, (
        "SKILL.md is over the repo's 5000-token body budget — whatever was added to it "
        "belongs in references/ or the operator docs")

    agent_orch = (REPO / "docs" / "AGENT_ORCHESTRATION.md").read_text(encoding="utf-8")
    assert "host.py" in agent_orch, (
        "agent mode's own doc never mentions the headless host, so nobody looking for "
        "'how do I run this unattended' will find it")

    bench_readme = (REPO / "ci" / "benchmarks" / "README.md").read_text(encoding="utf-8")
    assert "agent-optimize" in bench_readme, (
        "the benchmarks README does not document the agent-optimize dispatch option")

    doc = HOST.read_text(encoding="utf-8")
    assert "run-optimizer" in doc, (
        "host.py must say that it delegates the CLI invocation rather than shelling agents "
        "itself — otherwise the next reader adds a second copy of that logic")


def test_prompt_only_renders_the_briefing_without_shelling_an_agent(tmp_path):
    """--prompt-only is the offline seam: render the briefing, spend nothing."""
    project = _project(tmp_path, stop="reach val mean >= 0.75, or stop after $3")
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--prompt-only")

    assert out["prompt_only"] is True
    assert out.get("returncode") is None, "a --prompt-only run must not invoke the agent"

    prompt_path = Path(out["prompt_path"])
    assert prompt_path.is_file(), "the briefing was not written to disk"
    assert prompt_path.parent == run_dir.root / "host", (
        "the briefing belongs in the run dir, so an audit of the run can read what the "
        f"host actually asked for; got {prompt_path}")
    body = prompt_path.read_text(encoding="utf-8")

    # The handoff facts. Absolute paths: the host's cwd and the agent's cwd need not agree.
    assert str(run_dir.root) in body
    assert str(project) in body
    assert str(REPO / "skills") in body

    # The spec values the loop's own gate needs, restated so the agent does not guess.
    assert "reach val mean >= 0.75" in body, "the stop_condition was not handed over"
    assert "1.0" in body and "num_trials" in body

    # The loop's commands. measure.py is the load-bearing one: no seal, no result.
    for helper in ("spend.py", "gate_check.py", "commit.py", "measure.py"):
        assert helper in body, f"the briefing never names {helper}"

    # Unattended means unattended — a briefing that invites questions stalls in CI.
    assert "do not ask" in body.lower()


def test_the_briefing_enumerates_every_editable_file_not_just_the_capability_names(tmp_path):
    """Naming capabilities is not enough — name the FILES, or only the prompt gets edited.

    Measured on tau2 smoke run 32649063850: the spec declared
    `capabilities: [system-prompt, tools]`, and both candidates the agent produced touched
    only `policy/policy.md`. `tools/tools.py` and `reference/data_model.py` were in the
    candidate dir, writable, and never opened. `capabilities` gates which capability
    `validate()` runs, not what may be written, so nothing was blocking the agent; it simply
    had no reason to know the other files were fair game.

    This repo already paid for that lesson once — see the "NAME THE ARTIFACTS" note in
    run_suite.sh's spreadsheetbench arm, where an optimizer handed two editable files
    reported "all in prompt.md" and left the second surface inert. The briefing must
    therefore list the real files, so the fix is generic rather than per-benchmark.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    # A multi-file capability, like tau2's: a prompt AND code, plus a nested reference.
    seed = run_dir.root / "candidates" / "seed"
    (seed / "tools").mkdir(parents=True, exist_ok=True)
    (seed / "tools" / "tools.py").write_text("def get_details():\n    ...\n", encoding="utf-8")
    (seed / "reference").mkdir(parents=True, exist_ok=True)
    (seed / "reference" / "data_model.py").write_text("SCHEMA = {}\n", encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")

    assert "tools/tools.py" in body, (
        "the briefing does not name the editable tool code, so an agent reasonably edits "
        "only the obvious prompt file")
    assert "reference/data_model.py" in body, (
        "nested files under the capability are editable too and must be listed")

    # And it must say so, not merely list paths: a bare file list reads as inventory.
    low = body.lower()
    assert "only the prompt" in low or "only the obvious" in low, (
        "the briefing lists the files but never says that touching only the prompt leaves "
        f"the rest of the surface unexercised: {body}")


def test_two_rejections_escalate_the_form_rather_than_ending_the_run(tmp_path):
    """Measured: the agent chose prose twice, was rejected twice, and stopped.

    Its own reject notes named the surface each time ("System-prompt surface") and round 1's
    note — "require calculate tool for all money" — is precisely the case where SKILL.md says
    code beats prose: the agent HAS the criterion and violates it. The prescribed third round
    was a guard in the tool code. It never happened.

    So the briefing states this as a precondition on the round, not as encouragement: after two
    rejects, the same surface-and-form is off the table.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    seed = run_dir.root / "candidates" / "seed"
    (seed / "policy").mkdir(parents=True, exist_ok=True)
    (seed / "policy" / "policy.md").write_text("Be helpful.\n", encoding="utf-8")
    (seed / "tools").mkdir(parents=True, exist_ok=True)
    (seed / "tools" / "tools.py").write_text("def calculate():\n    ...\n", encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")
    low = body.lower()

    assert "may not reuse the surface" in low, (
        "the briefing does not forbid a third round on the same surface and form")
    assert "not a reason to stop" in low, (
        "the briefing does not say that two rejections are not a reason to stop")
    # With code in the surface, the escalation must name the code form specifically —
    # a generic "try something else" is what produced three prose candidates.
    assert "guard in the code" in low, (
        f"the escalation never names the code form for a capability that owns tool code: {body}")


def test_the_briefing_does_not_invent_files_for_a_prompt_only_capability(tmp_path):
    """A single-file capability must not be described as if it had more surface.

    Overcorrecting is its own failure: telling an agent to "also edit the tool code" when
    there is none sends it hunting for code to change, which is exactly how a prompt-only
    run once ended up editing adapter.py (see run_suite.sh's spreadsheetbench note).
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    seed = run_dir.root / "candidates" / "seed"
    for extra in seed.rglob("*"):
        if extra.is_file() and extra.name != "prompt.md":
            extra.unlink()
    (seed / "prompt.md").write_text("You are a helpful agent.\n", encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")

    assert "prompt.md" in body
    assert "tools.py" not in body, (
        "the briefing named tool code for a capability that has none — that sends the agent "
        "looking for code outside its capability to edit")


def test_the_hosted_agent_gets_the_same_optimizer_context_as_every_other_algorithm(tmp_path):
    """The structural reason a hosted run edited only prose — and the fix.

    `harness.OptimizerContext` exists so "an algorithm cannot silently run on a thinner
    prompt than its siblings": it stages the declared capability skills as `./guidance/<cap>/`
    AND natively where the agent auto-discovers them, plus the diagnose method, the
    capability_sources, and the agent's own features reference. Every deterministic algorithm
    calls `inject()`.

    The host did not, and `test_optimizer_context_parity.py` says so in its own docstring:
    agent-optimize "declares none of the context flags and drives its own loop… an algorithm
    absent from [ALGORITHMS] is NOT covered — it can still run blind while this file stays
    green." It ran blind. Two consecutive CI runs edited only the prompt file across 4 of 4
    candidates, having been handed no guidance whatsoever on how to edit tool code — naming
    the files in prose did not change that, because the missing thing was never the file list.
    """
    project = _project(tmp_path)
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ngate_mode: paired\ngate_k_se: 1.0\n"
        "capabilities: [system-prompt, tools]\ncapability_path: seed_capability\n"
        'stop_condition: "at most 2 rounds; seal with measure.py"\n',
        encoding="utf-8")
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")

    workdir = Path(out["workdir"])
    assert out["context"]["staged"] is True, (
        f"the optimizer context was not staged for the hosted agent: {out['context']}")

    # Both declared capabilities, as readable guidance AND natively discoverable.
    for cap in ("system-prompt", "tools"):
        assert (workdir / "guidance" / cap / "SKILL.md").is_file(), (
            f"no ./guidance/{cap}/ — the agent has no guidance on editing this surface")
        assert (workdir / ".claude" / "skills" / cap / "SKILL.md").is_file(), (
            f"{cap} not placed where claude-code natively discovers skills")

    # The failure-clustering method the loop's step 1 depends on.
    assert (workdir / "guidance" / "diagnose" / "SKILL.md").is_file(), (
        "no ./guidance/diagnose/ — the agent is told to read clusters with no method for it")

    # And the briefing must point at what was staged, or it goes unread.
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")
    assert "guidance/" in body, "the briefing never points at the staged guidance"

    # Staging writes an always-on CLAUDE.md whose first instruction is "read
    # ./INSTRUCTIONS.md FIRST" — written for the deterministic optimizer, which has one.
    # Agent mode passes its briefing as the prompt, so without this the agent's always-on
    # context opens by pointing at a file that does not exist.
    instructions = workdir / "INSTRUCTIONS.md"
    assert instructions.is_file(), (
        "the staged CLAUDE.md points at ./INSTRUCTIONS.md and nothing wrote one")
    assert instructions.read_text(encoding="utf-8") == body, (
        "INSTRUCTIONS.md and the run-dir briefing differ — two versions of the brief means "
        "no way to tell which one the agent followed")

    # seed_framework_memory builds LEDGER.md/RUNMAP.md/prior_iterations for this loop too —
    # the briefing must say so, not claim they're deterministic-loop-only and absent here.
    assert "LEDGER.md" in body and "real here too" in body, (
        "the briefing must tell the agent LEDGER.md/RUNMAP.md/prior_iterations are real and "
        "populated in agent mode, not a deterministic-loop-only artifact it should ignore")
    assert "will not exist here" not in body, (
        "the briefing still tells the agent these files won't exist, contradicting "
        "seed_framework_memory which builds them for real")


def test_the_briefing_carries_the_same_measured_blocks_the_deterministic_prompt_does(tmp_path):
    """Prompt-content parity, from the shared seam rather than re-authored here.

    The host used to hand-roll thinner equivalents of two blocks the deterministic path has
    always had, and the measured consequence was an optimizer that only ever edited prose:

      * `harness._CAP_EDIT_SPACE["tools"]` — "HIGHEST-LEVERAGE EDIT: WRITE A NEW CODE-BEARING
        TOOL … a deterministic tool can't be 'forgotten' the way a prompt rule can".
      * the target-reader block — "when the reader is weaker than you, prefer explicit rules,
        worked examples, and code enforcement over terse prose".

    Both now come from `OptimizerContext`, so the two paths cannot drift. Asserted against
    harness's own strings, not against a copy pasted into this test.
    """
    from cap_evolve import harness

    project = _project(tmp_path)
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ngate_mode: paired\ngate_k_se: 1.0\n"
        "capabilities: [system-prompt, tools]\ncapability_path: seed_capability\n"
        "target_model: aws/gpt-oss-120b\n"
        'stop_condition: "at most 2 rounds; seal with measure.py"\n', encoding="utf-8")
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")

    # The capability brief, verbatim from the shared source.
    expected = harness.OptimizerContext(capabilities=("system-prompt", "tools")).capability_brief()
    assert expected.strip() and expected.strip() in body, (
        "the briefing does not carry harness's capability brief — the block that names tool "
        "code as the highest-leverage surface")
    assert "CODE-BEARING TOOL" in body, (
        "the measured 'write a code-bearing tool' guidance did not reach the agent")

    # The reader block, for a weak target model.
    assert "THE READER" in body and "aws/gpt-oss-120b" in body, (
        "the briefing never tells the agent who consumes the capability at runtime, so it "
        "cannot know the reader is weaker than itself")


def test_a_context_staging_failure_is_loud_not_silently_off(tmp_path):
    """Silent-off is the failure mode this repo warns about everywhere.

    A run whose guidance never got staged looks exactly like one where it did — the agent
    just quietly optimizes less surface, which is the defect that produced this fix. So a
    staging failure must be reported in the host's own output rather than swallowed.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    # Break adapter import: inject() needs the adapter for the trajectories copy.
    (project / "adapters" / "adapter.py").write_text("raise RuntimeError('boom')\n",
                                                     encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")

    assert out["context"]["staged"] is False
    assert out["context"].get("error"), (
        f"a staging failure must say why, not just that it happened: {out['context']}")
    assert "boom" in json.dumps(out["context"]) or "RuntimeError" in json.dumps(out["context"])


def test_benchmark_specific_optimizer_instructions_reach_the_agent(tmp_path):
    """`optimizer_instructions_file` must not be silently dropped in agent mode.

    cli.py applies that key only for `algorithm_name in OPTIMIZER_CONTEXT_ALGORITHMS`
    (hill-climb / gepa / skillopt) — agent-optimize is not in that set, so a spec naming
    arm-specific instructions had them ignored entirely.

    That is not cosmetic for every benchmark. The spreadsheetbench arm writes instructions
    whose appended note states that the `{placeholders}` in its second editable file are
    LOAD-BEARING and that breaking one makes EVERY task score 0 — the agent is never told
    where to write its answer. Dropping that text in agent mode means the agent can destroy
    the run's entire signal with an edit it had no way to know was fatal.
    """
    project = _project(tmp_path)
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ngate_mode: paired\ngate_k_se: 1.0\n"
        "capabilities: [system-prompt]\ncapability_path: seed_capability\n"
        'optimizer_instructions_file: "optimizer/INSTRUCTIONS.md"\n'
        'stop_condition: "at most 2 rounds; seal with measure.py"\n',
        encoding="utf-8")
    (project / "optimizer").mkdir(exist_ok=True)
    (project / "optimizer" / "INSTRUCTIONS.md").write_text(
        "# Arm-specific rules\n\nKeep every {placeholder} in task_template.md — break one "
        "and EVERY task scores 0.\n", encoding="utf-8")
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")

    assert "{placeholder}" in body and "EVERY task scores 0" in body, (
        "the arm's own optimizer instructions never reached the briefing")
    assert out["instructions_file"], "the host did not report which instructions it used"


def test_arm_instructions_are_scoped_and_their_template_slots_stripped(tmp_path):
    """Pasting the arm's file verbatim injects a CONTRADICTING contract, and raw templating.

    That file is written for the deterministic per-iteration optimizer: it says to stop after
    editing and not to evaluate, because there the harness re-scores the candidate. In agent
    mode the agent owns the evaluation and the gate — an agent that obeyed that line would
    never gate anything. And it is a template, whose `{{SLOT}}` markers the deterministic path
    renders from per-iteration state the host does not have.

    So: slots stripped, and the precedence between the two contracts stated rather than left
    for the agent to guess.
    """
    project = _project(tmp_path)
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ncapabilities: [system-prompt]\ncapability_path: seed_capability\n"
        'optimizer_instructions_file: "optimizer/INSTRUCTIONS.md"\n'
        'stop_condition: "at most 2 rounds"\n', encoding="utf-8")
    (project / "optimizer").mkdir(exist_ok=True)
    (project / "optimizer" / "INSTRUCTIONS.md").write_text(
        "# Fix the prompt\n\n{{TARGET_READER}}\n\n{{FOCUS_SUMMARY}}\n\n"
        "Then STOP — the harness re-scores you, don't run evaluation yourself.\n"
        "Keep every {placeholder}: breaking one zeroes every task.\n", encoding="utf-8")
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")

    assert "{{" not in body, (
        f"unrendered template slot reached the agent: "
        f"{[l for l in body.splitlines() if '{{' in l]}")
    # The benchmark fact survives.
    assert "zeroes every task" in body
    # And the conflicting process half is explicitly scoped out.
    assert "does NOT apply" in body, (
        "the briefing includes instructions telling the agent not to evaluate, without saying "
        "they do not apply here — the agent would never gate a candidate")


def test_a_named_instructions_file_that_is_missing_is_reported_not_ignored(tmp_path):
    """Issue #252's failure mode: a bad path silently yields the generic guidance."""
    project = _project(tmp_path)
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ncapabilities: [system-prompt]\ncapability_path: seed_capability\n"
        'optimizer_instructions_file: "optimizer/NOPE.md"\n'
        'stop_condition: "at most 2 rounds"\n', encoding="utf-8")
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    assert out["instructions_warning"], (
        f"a named-but-missing instructions file must be reported: {out}")
    assert "NOPE.md" in out["instructions_warning"]


def test_code_vs_prose_advice_only_appears_when_the_surface_HAS_code(tmp_path):
    """A two-prose-file capability must not be told to write a code guard.

    spreadsheetbench's capability is `prompt.md` + `task_template.md` — both prose, no tool
    code. Advice to "prefer an in-code guard" there sends the agent looking for code it does
    not own, which is how a prompt-only run once went and edited `adapter.py`.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    seed = run_dir.root / "candidates" / "seed"
    for f in list(seed.rglob("*")):
        if f.is_file():
            f.unlink()
    (seed / "prompt.md").write_text("You are an expert.\n", encoding="utf-8")
    (seed / "task_template.md").write_text("Do {instruction}.\n", encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")

    assert "task_template.md" in body, "the second prose file must still be named"
    assert "in code as a guard" not in body and "code-level" not in body, (
        f"code advice offered to a capability with no code: {body}")


def test_a_large_capability_is_summarised_without_pretending_to_be_complete(tmp_path):
    """A skill-package capability can be dozens of files; a full list would swamp the brief.

    Bounding it is fine. Bounding it silently is not — this repo's own rule is that a
    coverage cap must say what it dropped, or the reader takes the list as exhaustive.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    seed = run_dir.root / "candidates" / "seed"
    for pack in ("docx", "pptx", "xlsx"):
        d = seed / pack
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        for i in range(12):
            (d / f"ref_{i}.md").write_text("x\n", encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")

    total = sum(1 for p in seed.rglob("*") if p.is_file())
    # Just the editable-surface section: from its heading to whatever heading follows it.
    start = body.index("## Your editable surface")
    nxt = body.find("\n## ", start + 1)
    surface = body[start:nxt if nxt != -1 else len(body)]

    assert str(total) in surface, (
        f"the briefing does not state the real file count ({total}): {surface}")
    bullets = [ln for ln in surface.splitlines() if ln.startswith("- ")]
    assert len(bullets) < total, (
        f"{total} files were listed one per line; the briefing should summarise instead")
    assert "not listed" in surface or "more" in surface, (
        "a truncated listing must say files were left out, or it reads as the whole set")
    # The top-level groups must survive truncation — that is what makes it navigable.
    for pack in ("docx", "pptx", "xlsx"):
        assert pack in surface, f"group {pack} vanished from the summarised listing"


def test_the_agents_real_cost_is_booked_not_silently_zeroed(tmp_path):
    """run-optimizer nests cost under ``cost.total_cost_usd``; the host read the wrong key.

    Measured on run 32733635494: the payload carried ``cost.total_cost_usd: 8.370`` and
    68,432 tokens, and the host booked ``usd: 0.0``. Every agent-mode run therefore reported
    $0.00 optimizer spend while really spending money — and it looked exactly like the
    "unmetered gateway" case the skill warns about, so the wrong conclusion was drawn twice.

    A cost ceiling cannot bind what it cannot see: with 0.0 booked, ``max_usd`` and spend.py's
    dollar predicates are inert.
    """
    from cap_evolve import RunDir

    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    # A stub agent that emits exactly run-optimizer's real result shape.
    stub = tmp_path / "fake_run_optimizer.py"
    stub.write_text(
        "import json, sys\n"
        "print(json.dumps({'optimizer': 'claude-code', 'cli_present': True,\n"
        "                  'returncode': 0, 'auth_present': [],\n"
        "                  'cost': {'total_cost_usd': 8.37, 'tokens': 68432}}))\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub))

    assert out["usd"] == pytest.approx(8.37), (
        f"the host did not read cost.total_cost_usd from the payload: {out}")

    rd = RunDir.open(run_dir.root)
    assert rd.spent.optimizer_usd == pytest.approx(8.37), (
        "the cost never reached the run's spend ledger, so no dollar ceiling can bind it")
    events = (run_dir.root / "events.jsonl").read_text(encoding="utf-8")
    host_ev = [json.loads(ln) for ln in events.splitlines()
               if ln.strip() and json.loads(ln).get("kind") == "host"]
    assert host_ev and host_ev[-1]["usd"] == pytest.approx(8.37), (
        f"the host event under-reports the round's cost: {host_ev}")


def test_the_host_reports_why_the_agent_stopped(tmp_path):
    """The diagnosis that had to be reconstructed by hand.

    Run 32733635494's agent stopped mid-round-2 with its highest-scoring candidate
    (val 0.530) evaluated but never committed, and the host's output said only
    ``returncode: 0, timed_out: false``. Whether it ran out of turns, hit an error, or chose
    to stop was invisible; the stop reason was inferred from a truncated stdout tail.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    stub = tmp_path / "fake_run_optimizer.py"
    stub.write_text(
        "import json\n"
        "print(json.dumps({'optimizer': 'claude-code', 'cli_present': True,\n"
        "                  'returncode': 0, 'auth_present': [],\n"
        "                  'cost': {'total_cost_usd': 1.0, 'tokens': 10},\n"
        "                  'stop': {'subtype': 'error_max_turns', 'num_turns': 240,\n"
        "                           'is_error': False}}))\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub))

    assert out.get("stop_reason") == "error_max_turns", (
        f"the host does not surface the agent's stop reason: {out}")
    assert out.get("num_turns") == 240, f"turns used not reported: {out}"
    assert "turn" in json.dumps(out).lower()


def test_an_agent_that_stopped_with_rounds_left_is_called_out(tmp_path):
    """Stopping early with budget remaining is a defect, and must not read as completion.

    The run that prompted this booked 1 of 3 rounds, had a better candidate sitting
    un-committed, and still reported success. The host cannot un-spend that, but it can refuse
    to let it look finished.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    stub = tmp_path / "fake_run_optimizer.py"
    stub.write_text(
        "import json\n"
        "print(json.dumps({'optimizer': 'claude-code', 'cli_present': True,\n"
        "                  'returncode': 0, 'auth_present': [],\n"
        "                  'stop': {'subtype': 'error_max_turns', 'num_turns': 240}}))\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub))

    # Zero rounds were committed against a budget of 5 (see _run_dir).
    assert out.get("incomplete"), (
        f"an agent that booked 0 of its rounds is reported as if it finished: {out}")
    assert "0" in str(out["incomplete"]) or "round" in str(out["incomplete"]).lower()
    assert out["seal"] == "host", "the seal fallback should have been what produced a result"


def test_unknown_host_agent_is_refused_before_any_spend(tmp_path):
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "no-such-agent-cli", expect_rc=2)

    assert "no-such-agent-cli" in json.dumps(out)
    assert "registry" in json.dumps(out).lower(), (
        "the refusal should point at optimizers/registry.yaml, which is where a host "
        f"agent is actually added: {out}")
    assert not (run_dir.root / "final.json").exists(), "a refused host must not seal"


def test_seal_only_finalizes_a_run_the_agent_left_open(tmp_path):
    """The guarantee that makes an unattended run reportable.

    An agent that runs out of turns mid-loop leaves no final.json. CI then cannot tell
    "the agent stopped early" from "a step crashed", and there is no honest number at
    all. --seal-only produces one from whatever the run already established.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    assert not (run_dir.root / "final.json").exists()

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--seal-only")

    assert out["sealed"] is True, out
    assert out["seal"] == "host", (
        "a seal the host had to perform must be labelled as such, not presented as the "
        f"agent's own: {out}")
    final = run_dir.root / "final.json"
    assert final.is_file(), "--seal-only did not produce final.json"
    payload = json.loads(final.read_text(encoding="utf-8"))
    assert "test" in payload and "reward" in payload["test"]


def test_seal_only_is_idempotent_and_never_double_seals(tmp_path):
    """A second seal must not raise TestSealError out of the host.

    The host runs after an agent that may itself have sealed. Blowing up there would
    fail a run that is actually complete.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    first = _host("--run-dir", str(run_dir.root), "--project", str(project), "--seal-only")
    assert first["sealed"] is True

    second = _host("--run-dir", str(run_dir.root), "--project", str(project), "--seal-only")
    assert second["sealed"] is True
    assert second["seal"] == "agent", (
        "an already-sealed run must be reported as already sealed, not re-sealed: "
        f"{second}")


def test_bash_timeout_is_raised_far_past_the_ten_minute_default(tmp_path):
    """A full-val eval on a real benchmark runs for hours inside one Bash call.

    Claude Code caps a Bash call at BASH_MAX_TIMEOUT_MS (default 600000 = 10 min). Left
    at the default, every eval the driver launches is killed mid-flight and the whole run
    reads as a broken runner rather than a slow one.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")

    env = out["agent_env"]
    assert int(env["BASH_MAX_TIMEOUT_MS"]) >= 3_600_000, env
    assert int(env["BASH_DEFAULT_TIMEOUT_MS"]) >= 3_600_000, env
    # The docs are explicit that the effective ceiling is max(default, max) — so both
    # have to move, and the default must never exceed the max.
    assert int(env["BASH_DEFAULT_TIMEOUT_MS"]) <= int(env["BASH_MAX_TIMEOUT_MS"]), env


def test_skills_dir_and_core_reach_the_agent(tmp_path):
    """Every loop command is `python $A/<helper>.py`, which imports cap_evolve."""
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    env = out["agent_env"]
    assert env["CAPEVOLVE_SKILLS_DIR"] == str(REPO / "skills")


@pytest.mark.parametrize("missing", ["--run-dir", "--project"])
def test_required_handoff_arguments(tmp_path, missing):
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    argv = ["--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only"]
    i = argv.index(missing)
    del argv[i:i + 2]
    p = subprocess.run([sys.executable, str(HOST), *argv],
                       capture_output=True, text=True, env=_env())
    assert p.returncode != 0, f"{missing} must be required"


# --- the end_turn defect: run 32814848187 ------------------------------------
# The turn budget raised to 600 in this branch worked: that run used 78 of 600 and stopped
# on subtype=success / stop_reason=end_turn, rc=0. It had backgrounded round 2's full-val
# gate and ended its turn to await a notification, which a `claude -p` process can never
# receive — end_turn IS process exit. The gate finished 14 minutes after the agent was gone,
# with a real verdict (r2_comm_search 0.44 vs parent 0.58 -> reject) that nobody read, so
# rounds_booked stayed 1 of 3 and round 3 never started. Three holes, one per test below.


def test_the_briefing_forbids_ending_a_turn_on_outstanding_work_without_banning_delegation(
        tmp_path):
    """The rule has to be about WHERE the main loop lives, not about avoiding concurrency.

    The briefing's "Unattended" section covered only asking questions ("Do not ask any; do
    not wait for input"). Backgrounding a job and ending the turn to await a notification
    breaks neither clause, and that is exactly what happened. But the fix must not read as
    "never delegate": fanning out subagents or several evals at once is the intended way to
    use this host, and `round.py` exists to do precisely that. What is fatal is the *main
    loop* leaving the foreground — delegation is fine as long as the driving turn stays
    blocked on the result and reads it itself.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    brief = Path(out["prompt_path"]).read_text(encoding="utf-8").lower()

    assert "foreground" in brief, (
        "the briefing never tells the agent its main loop must stay in the foreground, so "
        "backgrounding the gate and ending the turn breaks no stated rule")
    assert "orphan" in brief or "exits" in brief, (
        "the briefing must state the CONSEQUENCE — ending a turn with no pending tool call "
        "ends the process and orphans its children — or the rule reads as mere style")

    # Generic, not a ban on concurrency: subagents and parallel work must stay permitted,
    # since round.py's whole point is evaluating a round's candidates at once.
    assert ("subagent" in brief or "delegat" in brief or "parallel" in brief), (
        "the rule must say delegation stays allowed; a blanket 'do everything yourself, "
        "serially' would forbid round.py's parallel evals and the subagent fan-out the "
        "claude-code registry row advertises")

    # And it must not name one tool or one mechanism — any later-reporting mechanism is
    # equally fatal, so the rule is phrased on the outcome.
    assert "notif" in brief or "wake" in brief or "report back" in brief, (
        "the rule should generalise to anything that reports back after the turn ends, "
        "not just to the one mechanism this run happened to use")


def test_an_agent_that_ENDED_ITS_TURN_is_not_told_to_raise_the_turn_budget(tmp_path):
    """Two different stop causes had one message, and it fit only the older one.

    Run 32733635494 really did die on error_max_turns, and "raise optimizer_max_turns or
    lower the round count" was the right advice. Run 32814848187 stopped at 78 of 600 turns
    on end_turn; the same sentence sent the operator to a knob that was already 7x larger
    than what the agent used. The host has the stop reason in hand and must split on it.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    stub = tmp_path / "fake_run_optimizer.py"
    stub.write_text(
        "import json\n"
        "print(json.dumps({'optimizer': 'claude-code', 'cli_present': True,\n"
        "                  'returncode': 0, 'auth_present': [],\n"
        "                  'stop': {'subtype': 'success', 'num_turns': 78,\n"
        "                           'is_error': False, 'stop_reason': 'end_turn'}}))\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub))

    assert out.get("incomplete"), f"stopping with rounds left must not read as done: {out}"
    msg = str(out["incomplete"]).lower()
    assert "optimizer_max_turns" not in msg, (
        "an agent that used 78 of its turns and ended its turn voluntarily is not "
        f"turn-starved; pointing the operator at the turn budget misdiagnoses it: {msg}")
    assert "turn" in msg and ("outstanding" in msg or "background" in msg
                              or "chose" in msg or "voluntar" in msg), (
        f"the end_turn case needs its own diagnosis, not a generic one: {msg}")
    # The inner stop_reason is the discriminator and must survive into the payload; reading
    # only `subtype` sees "success" and cannot tell this from a clean finish.
    assert "end_turn" in json.dumps(out), (
        f"the agent's stop_reason never reaches the host's output: {out}")


def test_a_turn_starved_agent_still_gets_the_turn_budget_advice(tmp_path):
    """The split must not lose the advice that was right for the original defect."""
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    stub = tmp_path / "fake_run_optimizer.py"
    stub.write_text(
        "import json\n"
        "print(json.dumps({'optimizer': 'claude-code', 'cli_present': True,\n"
        "                  'returncode': 0, 'auth_present': [],\n"
        "                  'stop': {'subtype': 'error_max_turns', 'num_turns': 240}}))\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub))

    assert "optimizer_max_turns" in str(out.get("incomplete", "")), (
        f"the turn-exhausted case lost its own advice in the split: {out}")


def test_a_round_that_was_gated_but_never_booked_is_reported(tmp_path):
    """The work was done and the verdict was on disk; only commit.py was missing.

    round2.log held `r2_comm_search reward 0.44, verdict reject` against parent r1_ops_bag.
    Nothing read it. The host's own accounting could not see it either — `spent.iterations`
    counts commit.py calls, so an un-booked round is indistinguishable from a round that was
    never attempted, and the operator is left to diff candidate dirs by hand.

    The host reports it rather than booking it: which decision a round's verdict deserves is
    the driver's judgement, and a host that booked accepts would silently move `best_id`
    after `measure.py` had already sealed against the old one.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "round2.log").write_text(json.dumps({
        "parent": {"tag": "r1_ops_bag", "reward": 0.58},
        "candidates": [{"tag": "r2_comm_search", "reward": 0.44,
                        "delta_vs_gate_ref": -0.14, "verdict": "reject", "eval_rc": 0}],
        "control": {"tag": "ctl_null_i1", "reward": 0.5, "verdict": "reject"},
    }), encoding="utf-8")

    stub = tmp_path / "fake_run_optimizer.py"
    stub.write_text(
        "import json\n"
        "print(json.dumps({'optimizer': 'claude-code', 'cli_present': True,\n"
        "                  'returncode': 0, 'auth_present': [],\n"
        "                  'stop': {'subtype': 'success', 'num_turns': 78,\n"
        "                           'stop_reason': 'end_turn'}}))\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub))

    unbooked = out.get("unbooked_rounds")
    assert unbooked, (
        "a fully-gated round with no commit.py decision is invisible in the host's "
        f"output, so the run reads as if that round never happened: {out}")
    blob = json.dumps(unbooked)
    assert "r2_comm_search" in blob, f"the candidate is not named: {blob}"
    assert "reject" in blob, f"the verdict that was computed is not carried: {blob}"
    assert "round2.log" in blob, f"the log to look in is not named: {blob}"
    assert "r2_comm_search" in str(out.get("incomplete", "")), (
        "the un-booked candidate must surface in the operator-facing warning too, not "
        f"only in a nested key nobody greps: {out.get('incomplete')}")
    # The control is round.py's noise floor, never committed by design — reporting it as
    # un-booked would cry wolf on every single round.
    assert "ctl_null" not in blob, (
        f"the null control is not a bookable candidate and must not be flagged: {blob}")


def test_a_booked_round_is_not_reported_as_unbooked(tmp_path):
    """The backstop must be silent on the healthy path, or it is noise.

    Asserted on the full host path, not ``--seal-only``: a negative assertion is only worth
    anything on the code path that also produces the positive, and the key would otherwise be
    trivially absent.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "round1.log").write_text(json.dumps({
        "parent": {"tag": "seed", "reward": 0.24},
        "candidates": [{"tag": "r1_ops_bag", "reward": 0.58, "verdict": "accept"}],
    }), encoding="utf-8")
    # What commit.py leaves behind for that candidate.
    run_dir.log_event("accept", candidate="r1_ops_bag", val=0.58)

    stub = tmp_path / "fake_run_optimizer.py"
    stub.write_text(
        "import json\n"
        "print(json.dumps({'optimizer': 'claude-code', 'cli_present': True,\n"
        "                  'returncode': 0, 'auth_present': [],\n"
        "                  'stop': {'subtype': 'success', 'num_turns': 78,\n"
        "                           'stop_reason': 'end_turn'}}))\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub))

    assert out["unbooked_rounds"] == [], (
        f"a candidate with an accept event on record was flagged as un-booked: {out}")
    assert "r1_ops_bag" not in str(out.get("incomplete", "")), (
        f"a booked candidate leaked into the warning: {out.get('incomplete')}")


def test_seal_only_also_reports_an_abandoned_round(tmp_path):
    """--seal-only is what an operator runs on a run that died; it must say what was left.

    Reporting the abandoned round only on the full host path hides it from the one reader who
    went looking for why the run is short.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    work = run_dir.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    (work / "round2.log").write_text(json.dumps({
        "parent": {"tag": "r1_ops_bag", "reward": 0.58},
        "candidates": [{"tag": "r2_comm_search", "reward": 0.44, "verdict": "reject"}],
    }), encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--seal-only")

    assert "r2_comm_search" in json.dumps(out.get("unbooked_rounds")), (
        f"--seal-only sealed the run and said nothing about the abandoned round: {out}")


# --- run 32861747778: round 1 died on the interpreter, then on concurrency ----


def test_the_agent_inherits_the_interpreter_that_can_actually_import_the_adapter(tmp_path):
    """Round 1's every eval died `ModuleNotFoundError: No module named 'tau2'`.

    The benchmark's deps live in ONE interpreter: ci_setup.sh does
    `uv pip install -p "$CAPEVOLVE_PY" -e tau2-bench`, and run_suite.sh runs `cap-evolve run`
    with it — which is why the baseline scored 0.44 while every candidate eval crashed. But
    ci_setup exports `PATH="$HOME/.local/bin:$PATH"` and never puts that venv's bin on PATH,
    while SKILL.md tells the agent to run `python "$A/round.py"`. Bare `python` therefore CANNOT
    resolve to the interpreter that works, and the run before this one only survived by luck —
    with no transcript kept, not even the luck is inspectable.

    Prose is the wrong fix here (SKILL.md's commands would all have to change and be obeyed).
    The interpreter that launched the host is by construction the right one, so put its bin dir
    first on the agent's PATH and every existing `python ...` command becomes correct.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")

    path = out["agent_env"].get("PATH", "")
    assert path, f"the agent is handed no PATH at all, so it inherits whatever CI had: {out['agent_env']}"
    want = str(Path(sys.executable).parent)
    assert path.split(os.pathsep)[0] == want, (
        f"the host's own interpreter dir is not FIRST on the agent's PATH, so bare `python` "
        f"still resolves elsewhere: want {want}, got {path.split(os.pathsep)[:3]}")

    # And named explicitly in the handoff, so the agent can be unambiguous when it wants to be.
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")
    assert sys.executable in body, (
        "the briefing never names the interpreter, so an agent that shells a different one has "
        "no way to know which is right")


def test_the_briefing_states_the_measurement_concurrency_the_gate_can_resolve(tmp_path):
    """The agent gated at --concurrency 100, which round.py itself calls unresolvable.

    SKILL.md already says "do not raise it to buy wall clock" and the agent raised it to 100
    anyway — the run's own table then carried "a verdict from this round can therefore not
    resolve an effect smaller than roughly 0.08". A number the briefing never states is a
    number the agent picks, so state it.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    body = Path(out["prompt_path"]).read_text(encoding="utf-8")

    assert "concurrency" in body.lower(), (
        "the briefing hands over trials and k_se but not the measurement concurrency, the one "
        "knob whose misuse silently widens the noise floor past the gate")


def test_an_agent_that_SEALED_the_run_itself_is_not_accused_of_abandoning_work(tmp_path):
    """My own end_turn diagnosis fired falsely on run 32871360361.

    That agent booked 4 of 10 rounds, then investigated a round-5 lever, judged the residual
    failure unfixable by the surfaces it owned, sealed test itself, wrote its report and stopped
    at 121 of 1650 turns. The host told the operator it had "stopped of its own accord with
    rounds still to spend, which is what a turn ending on outstanding work looks like … a
    backgrounded job … cannot resume a non-interactive run" — accusing it of the exact defect
    4016ed0a was written for, when the run was complete and honest.

    Two facts already in the payload disprove it: `seal == "agent"` (it finalized itself; an
    agent that died mid-turn leaves the host to seal, which is what run 32814848187 did) and
    `unbooked_rounds == []` (the backstop found no gated-but-unbooked candidate). Unspent budget
    is worth reporting, but as under-use — not as a lost loop.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    # Seal it first, so the host sees an already-sealed run: seal == "agent".
    _host("--run-dir", str(run_dir.root), "--project", str(project), "--seal-only")

    stub = tmp_path / "fake_run_optimizer.py"
    stub.write_text(
        "import json\n"
        "print(json.dumps({'optimizer': 'claude-code', 'cli_present': True,\n"
        "                  'returncode': 0, 'auth_present': [],\n"
        "                  'stop': {'subtype': 'success', 'num_turns': 121,\n"
        "                           'stop_reason': 'end_turn'}}))\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub))

    assert out["seal"] == "agent", f"fixture did not produce an agent-sealed run: {out}"
    assert out["unbooked_rounds"] == [], out
    msg = str(out.get("incomplete") or "")
    assert msg, "unspent rounds should still be reported, as under-use"
    assert "background" not in msg and "file watcher" not in msg, (
        f"the foreground-defect diagnosis fired on a run the agent sealed itself: {msg}")
    assert "may never have been committed" not in msg, (
        "unbooked_rounds is empty and the agent sealed, so nothing was lost — saying otherwise "
        f"sends the operator hunting for a candidate that does not exist: {msg}")
    assert "budget" in msg.lower() or "unspent" in msg.lower() or "under-use" in msg.lower(), (
        f"the real finding — rounds left unspent — is not stated: {msg}")


def test_an_agent_that_died_without_sealing_still_gets_the_foreground_diagnosis(tmp_path):
    """The discriminator must not disarm the diagnosis it was built for.

    Run 32814848187 ended its turn with round 2's gate still running and left the host to seal
    (`seal: "host"`). That case must keep the foreground explanation.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    stub = tmp_path / "fake_run_optimizer.py"
    stub.write_text(
        "import json\n"
        "print(json.dumps({'optimizer': 'claude-code', 'cli_present': True,\n"
        "                  'returncode': 0, 'auth_present': [],\n"
        "                  'stop': {'subtype': 'success', 'num_turns': 78,\n"
        "                           'stop_reason': 'end_turn'}}))\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub))

    assert out["seal"] == "host", f"fixture should leave the seal to the host: {out}"
    msg = str(out.get("incomplete") or "")
    assert "foreground" in msg or "background" in msg, (
        f"the foreground diagnosis was lost for the case it exists for: {msg}")


# --- review follow-ups (PR #399 review by OsherElhadad) -----------------------


def test_code_advice_fires_for_languages_beyond_the_first_handful(tmp_path):
    """`_CODE_SUFFIXES` was a 14-entry allowlist, so C/C++/C#/PHP/Swift/Kotlin got prose advice.

    The briefing offers "the form that works is a guard in the code" only when the editable
    surface actually contains code — correct, because a two-prose-file capability told to prefer
    an in-code guard goes hunting for code it does not own. But gating that on a short suffix
    list reintroduced the same silent-miss for every language not named, which is the failure
    class this PR exists to remove rather than relocate.

    Asserted on the module's set rather than through a rendered briefing, because the point is
    coverage of the vocabulary, not one file's rendering.
    """
    # Parsed statically rather than imported: host.py's `import _bootstrap` needs its own
    # scripts dir on sys.path, and this assertion is about the vocabulary, not the runtime.
    import ast  # noqa: PLC0415

    tree = ast.parse(HOST.read_text(encoding="utf-8"))
    suffixes = next(
        ast.literal_eval(n.value) for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", "") == "_CODE_SUFFIXES" for t in n.targets))

    class _M:  # tiny shim so the assertions below read the same either way
        _CODE_SUFFIXES = suffixes
    mod = _M

    for suffix in (".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php", ".swift", ".kt", ".m",
                   ".scala", ".ex", ".erl", ".hs", ".ml", ".r", ".jl", ".dart", ".zig"):
        assert suffix in mod._CODE_SUFFIXES, (
            f"{suffix} is not recognised as code, so a capability whose only code is {suffix} "
            "silently gets prose-only advice — the bug this PR fixed for .py, relocated")
    # Prose must stay prose, or the original defect comes back from the other side.
    for suffix in (".md", ".txt", ".rst"):
        assert suffix not in mod._CODE_SUFFIXES, f"{suffix} must not count as code"
    # And the list must be documented as non-exhaustive, so the next reader broadens it rather
    # than assuming absence means "deliberately prose".
    src = HOST.read_text(encoding="utf-8")
    head = src[:src.index("_CODE_SUFFIXES")]
    assert "not exhaustive" in head.lower() or "non-exhaustive" in head.lower(), (
        "the set must say it is known-good rather than complete, or its gaps read as decisions")


def test_a_capability_with_no_guidance_skill_is_reported_not_silently_skipped(tmp_path):
    """`harness._stage_context` skips a capability with no matching skill dir and still says
    `staged: True`, so some-capabilities-missing was indistinguishable from all-staged.

    The whole-staging failure was already loud (`staged: False` + a `::warning::`). The
    per-capability miss was not — and "quietly optimizing less surface" is the exact defect
    this PR was opened to fix, so leaving one half of it silent is inconsistent.

    The staged guidance list was already in the payload; what was missing was comparing it
    against what the spec asked for and saying so.
    """
    project = _project(tmp_path)
    # A capability that has no skill package anywhere under skills/.
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ngate_mode: paired\ngate_k_se: 1.0\n"
        "capabilities: [system-prompt, no-such-capability]\n"
        "capability_path: seed_capability\nstop_condition: \"stop after 1 round\"\n",
        encoding="utf-8")
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")
    ctx = out["context"]

    assert "no-such-capability" in ctx.get("capabilities", []), ctx
    assert "no-such-capability" not in ctx.get("guidance", []), (
        "fixture is wrong: the capability must genuinely have no guidance dir")
    assert ctx.get("guidance_missing") == ["no-such-capability"], (
        "a declared capability that got NO guidance is not reported, so the agent optimizes "
        f"that surface blind and the JSON looks fully staged: {ctx}")


def test_the_guidance_gap_is_warned_about_not_only_recorded(tmp_path):
    """A field nobody greps is not a report. The all-missing case already warns; match it."""
    project = _project(tmp_path)
    (project / "capevolve.yaml").write_text(
        "num_trials: 1\ngate_mode: paired\ngate_k_se: 1.0\n"
        "capabilities: [system-prompt, no-such-capability]\n"
        "capability_path: seed_capability\nstop_condition: \"stop after 1 round\"\n",
        encoding="utf-8")
    run_dir = _run_dir(tmp_path)

    stub = tmp_path / "fake_run_optimizer.py"
    stub.write_text(
        "import json\n"
        "print(json.dumps({'optimizer': 'claude-code', 'cli_present': True,\n"
        "                  'returncode': 0, 'auth_present': []}))\n",
        encoding="utf-8")
    p = subprocess.run(
        [sys.executable, str(HOST), "--run-dir", str(run_dir.root), "--project", str(project),
         "--agent", "claude-code", "--run-optimizer", str(stub)],
        capture_output=True, text=True, env=_env())

    assert "::warning::" in p.stderr and "no-such-capability" in p.stderr, (
        f"the guidance gap was recorded but never surfaced as a warning: {p.stderr[-600:]}")


def test_a_fully_staged_run_reports_no_guidance_gap(tmp_path):
    """The gap report must be silent on the healthy path, or it is noise."""
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    out = _host("--run-dir", str(run_dir.root), "--project", str(project), "--prompt-only")

    assert out["context"].get("guidance_missing") == [], (
        f"a fully-staged run reports a phantom gap: {out['context']}")


# --- #428/#430: a crash with subtype=success must not read as a clean success, and a ------
# --- transient crash gets a bounded retry rather than forfeiting the run's budget. --------


def _crash_stub(tmp_path: Path) -> Path:
    """A stub `run-optimizer` that ALWAYS reports the run_e2e_run3 crash shape.

    `subtype: "success"` in the SAME object as `is_error: true` /
    `terminal_reason: "api_error"` — exactly issue #428's evidence, so host.py's
    classification cannot be tricked by `subtype` alone.
    """
    stub = tmp_path / "fake_run_optimizer.py"
    payload = {
        "optimizer": "claude-code", "cli_present": True, "returncode": 1,
        "auth_present": [],
        "stop": {"subtype": "success", "is_error": True, "terminal_reason": "api_error",
                 "result": "API Error: Can't reach the API server (ENOTFOUND)",
                 "num_turns": 146},
    }
    stub.write_text(
        f"import json, sys\nprint(json.dumps({payload!r}))\nsys.exit(1)\n",
        encoding="utf-8")
    return stub


def _host_events(run_dir, kind: str) -> list:
    events = (run_dir.root / "events.jsonl").read_text(encoding="utf-8")
    return [json.loads(ln) for ln in events.splitlines() if ln.strip()
            and json.loads(ln).get("kind") == kind]


def test_a_crash_with_subtype_success_is_not_logged_as_clean_success(tmp_path):
    """#428: `subtype: "success"` + `is_error: true` must be classified as a crash.

    Evidence: run_e2e_run3's `events.jsonl` recorded `stop_reason: "success"` for a run
    whose CLI payload carried `is_error: true, terminal_reason: "api_error"` in the same
    object, with 3 of 10 iterations and 2000 of 8000 rollouts spent. host.py must surface
    the crash, not let `subtype` alone paper over it.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    stub = _crash_stub(tmp_path)

    # --max-retries 0 isolates the classification from #430's retry behavior.
    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub), "--max-retries", "0")

    # The raw fields must reach the host's own output, not just get absorbed into `subtype`.
    assert out.get("stop_reason") == "success", out
    host_ev = _host_events(run_dir, "host")
    assert host_ev, "no host event was logged"
    assert host_ev[-1]["is_error"] is True, (
        f"the host event never records is_error, so the crash is indistinguishable from a "
        f"clean success in the audit trail: {host_ev[-1]}")
    assert host_ev[-1]["terminal_reason"] == "api_error", host_ev[-1]

    # And the operator-facing diagnosis must name the crash, not read as voluntary/finished.
    msg = str(out.get("incomplete") or "").lower()
    assert msg, f"a crashed run with rounds left must not read as complete: {out}"
    assert "infra failure" in msg or "error termination" in msg, (
        f"the crash was not called out as its own diagnosis: {msg}")
    assert "voluntary" not in msg and "sealed the run itself" not in msg, (
        f"a crash must not be diagnosed as a voluntary/finished stop: {msg}")


def test_a_transient_crash_triggers_a_bounded_retry_and_can_recover(tmp_path):
    """#430: a DNS/network blip gets retried against the SAME run_dir, not forfeited.

    The stub crashes on its first two invocations (api_error) and succeeds on the third —
    exactly the "transient" case #430 exists for. With --max-retries 2 the host must retry
    twice and pick up the eventual success rather than sealing on the first crash.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    counter = tmp_path / "attempts.txt"
    stub = tmp_path / "fake_run_optimizer.py"
    crash_payload = {
        "optimizer": "claude-code", "cli_present": True, "returncode": 1,
        "auth_present": [],
        "stop": {"subtype": "success", "is_error": True, "terminal_reason": "api_error",
                 "num_turns": 50},
    }
    ok_payload = {
        "optimizer": "claude-code", "cli_present": True, "returncode": 0,
        "auth_present": [],
        "stop": {"subtype": "success", "is_error": False, "stop_reason": "end_turn",
                 "num_turns": 10},
    }
    stub.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        f"counter = Path(r'{counter}')\n"
        "n = int(counter.read_text()) if counter.exists() else 0\n"
        "counter.write_text(str(n + 1))\n"
        "if n < 2:\n"
        f"    print(json.dumps({crash_payload!r}))\n"
        "    sys.exit(1)\n"
        "else:\n"
        f"    print(json.dumps({ok_payload!r}))\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub), "--max-retries", "2")

    assert int(counter.read_text()) == 3, (
        "expected exactly 1 initial attempt + 2 retries (3 CLI invocations), got "
        f"{counter.read_text()}")

    retry_ev = _host_events(run_dir, "host_retry")
    assert len(retry_ev) == 2, f"expected 2 retry events, got: {retry_ev}"
    assert [e["attempt"] for e in retry_ev] == [1, 2], retry_ev
    assert all(e["terminal_reason"] == "api_error" for e in retry_ev), retry_ev

    # The FINAL attempt succeeded, so the classification must not still call it a crash.
    msg = str(out.get("incomplete") or "").lower()
    assert "infra failure" not in msg, (
        f"the run recovered on its final retry but is still diagnosed as crashed: {msg}")


def test_a_permanent_crash_exhausts_retries_and_surfaces_clearly(tmp_path):
    """#430 acceptance criteria: a bounded retry count, and the final failure is clear.

    The stub NEVER recovers — a persistently broken endpoint. The host must not retry
    forever (bounded by --max-retries) and must still report the crash plainly rather than
    quietly sealing on a "success"-shaped payload once it gives up.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)

    counter = tmp_path / "attempts.txt"
    stub = tmp_path / "fake_run_optimizer.py"
    crash_payload = {
        "optimizer": "claude-code", "cli_present": True, "returncode": 1,
        "auth_present": [],
        "stop": {"subtype": "success", "is_error": True, "terminal_reason": "api_error",
                 "num_turns": 50},
    }
    stub.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        f"counter = Path(r'{counter}')\n"
        "n = int(counter.read_text()) if counter.exists() else 0\n"
        "counter.write_text(str(n + 1))\n"
        f"print(json.dumps({crash_payload!r}))\n"
        "sys.exit(1)\n",
        encoding="utf-8")

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub), "--max-retries", "2")

    # Bounded: exactly 1 initial attempt + 2 retries, never an unbounded loop against a
    # genuinely broken endpoint.
    assert int(counter.read_text()) == 3, (
        f"expected exactly 3 CLI invocations (bounded retries), got {counter.read_text()}")

    retry_ev = _host_events(run_dir, "host_retry")
    assert len(retry_ev) == 2, f"retries were not bounded to --max-retries: {retry_ev}"

    msg = str(out.get("incomplete") or "").lower()
    assert msg, f"an exhausted-retry crash must still surface, not read as complete: {out}"
    assert "infra failure" in msg or "error termination" in msg, (
        f"the exhausted crash is not clearly diagnosed: {msg}")
    assert "2 retries" in msg or "2 retry" in msg, (
        f"the diagnosis should say how many retries were already spent: {msg}")


def test_claude_code_registry_row_structurally_disallows_monitor():
    """#431: the Monitor denial on run_e2e_run3 must not depend on luck.

    ``--allowedTools Bash`` alone denies anything not on the list only because ``-p`` has no
    human to ask — a future row change (a broader allowlist, a different permission mode)
    could silently make a persistent ``Monitor`` call succeed instead of denied. `Claude
    Code's own precedence rule is that ``--disallowedTools`` always wins over
    ``--allowedTools``, so asserting it is present (and that it survives command-building)
    is what makes the guard structural rather than an accident of what else is allowed.
    """
    from cap_evolve.specfile import read_yaml

    registry_path = REPO / "skills" / "optimizers" / "registry.yaml"
    registry = read_yaml(registry_path.read_text(encoding="utf-8"))
    template = registry["claude-code"]["command_template"]
    assert "--disallowedTools" in template and "Monitor" in template, (
        f"claude-code's command_template no longer structurally disallows Monitor: {template}")

    sys.path.insert(0, str(REPO / "skills" / "optimizers" / "run-optimizer" / "scripts"))
    import run as run_optimizer  # noqa: E402

    cmd = run_optimizer.build_command(
        template, workdir="/tmp/w", prompt="/tmp/p.md", prompt_text="do the thing",
        model="claude-sonnet-5", self_dir="/tmp")
    assert "--disallowedTools" in cmd, f"the flag was dropped during command-building: {cmd}"
    assert cmd[cmd.index("--disallowedTools") + 1] == "Monitor", (
        f"Monitor is not the value that ends up on the built command: {cmd}")


def _permission_denial_stub(tmp_path: Path, *, denials: list) -> Path:
    stub = tmp_path / "fake_run_optimizer.py"
    payload = {
        "optimizer": "claude-code", "cli_present": True, "returncode": 0,
        "auth_present": [],
        "stop": {"subtype": "success", "stop_reason": "end_turn", "num_turns": 5,
                 "permission_denials": denials},
    }
    stub.write_text(f"import json\nprint(json.dumps({payload!r}))\n", encoding="utf-8")
    return stub


def test_a_denied_persistent_monitor_call_is_flagged_as_a_near_miss(tmp_path):
    """#431's own evidence, replayed: a denied persistent ``Monitor`` must be visible in the
    run's own report, not only recoverable by hand-reading ``host/transcript.jsonl``.
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    stub = _permission_denial_stub(tmp_path, denials=[{
        "tool_name": "Monitor",
        "tool_input": {"description": "round.py progress for iteration 1 (3 candidates)",
                       "timeout_ms": 3600000, "persistent": True,
                       "command": "tail -f -n +1 /tmp/round1.log"},
    }])

    p = subprocess.run(
        [sys.executable, str(HOST), "--run-dir", str(run_dir.root), "--project", str(project),
         "--agent", "claude-code", "--run-optimizer", str(stub)],
        capture_output=True, text=True, env=_env())
    out = json.loads(p.stdout)

    misses = out.get("backgrounding_near_misses")
    assert misses and len(misses) == 1, f"the Monitor denial was not flagged: {out}"
    assert misses[0]["tool_name"] == "Monitor", misses
    assert "backgrounding" in p.stderr.lower() or "detach" in p.stderr.lower(), (
        f"no near-miss warning reached stderr: {p.stderr}")


def test_an_unrelated_permission_denial_is_not_flagged_as_a_backgrounding_attempt(tmp_path):
    """A denial with no persistent/backgrounding shape must not be misread as this anti-pattern
    — flagging every denial would bury the real signal in noise the first time an agent is
    denied something ordinary (e.g. a write outside its workdir).
    """
    project = _project(tmp_path)
    run_dir = _run_dir(tmp_path)
    stub = _permission_denial_stub(tmp_path, denials=[{
        "tool_name": "Write", "tool_input": {"file_path": "/etc/passwd", "content": "x"},
    }])

    out = _host("--run-dir", str(run_dir.root), "--project", str(project),
                "--agent", "claude-code", "--run-optimizer", str(stub))

    assert out.get("backgrounding_near_misses") == [], (
        f"an unrelated denial was misclassified as a detach attempt: {out}")
