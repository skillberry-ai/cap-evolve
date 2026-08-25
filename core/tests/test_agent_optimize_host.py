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

    # That same pointer names deterministic-loop artifacts this loop never builds.
    assert "LEDGER.md" in body and "will not exist here" in body, (
        "the briefing does not tell the agent that LEDGER.md/RUNMAP.md belong to the other "
        "loop, so it will hunt for files that are legitimately absent")


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
