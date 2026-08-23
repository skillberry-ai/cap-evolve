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
