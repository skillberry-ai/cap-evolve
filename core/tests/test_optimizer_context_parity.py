"""Issue #109 — GEPA and SkillOpt get the SAME optimizer context as hill-climb.

Before the fix:
  * ``gepa_loop`` bypassed ``run_step``, so its optimizer workdir had no
    ``./trajectories/``, no ``./guidance/<cap>/`` and no native-skill injection, and its
    prompt was a hand-rolled string with no capability brief / bench repo / reader block;
  * ``skillopt_loop`` had no capability/optimizer parameters at all and called
    ``_focus_instructions`` bare, so ``CAP_BRIEF`` was empty and the ``PARALLEL`` note
    always claimed a sequential optimizer;
  * ``cap-evolve run`` gated ``--capabilities / --instructions-file / --bench-repo /
    --optimizer-name / --capability-sources / --target-model / --target-profile-file``
    behind ``algorithm == "hill-climb"``, silently dropping them for the other two.

These tests assert the injected FILES, the rendered PROMPT and the CLI flag plumbing for
all three algorithms.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
MOCK_RUN = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"

sys.path.insert(0, str(CORE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def _toy_adapter():
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_ctx_parity", EXAMPLE / "adapter.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.Adapter()


def _setup(tmp_path, ts, **budget):
    from cap_evolve import Budget, RunDir, harness
    adapter = _toy_adapter()
    seed = tmp_path / f"seed_{ts}"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts=ts, budget=Budget(**budget))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    return adapter, run_dir, base


def _ctx(tmp_path):
    """The full optimizer context a real run configures, with a custom template so we
    can prove the intake-authored instructions file is honored per-algorithm."""
    from cap_evolve.optimizer_context import OptimizerContext
    tmpl = tmp_path / "INSTRUCTIONS.tmpl.md"
    tmpl.write_text(
        "CUSTOM-TEMPLATE-MARKER\n{{FOCUS_SUMMARY}}\n{{CAP_BRIEF}}\n{{ALGO_BRIEF}}\n"
        "{{BENCH_REPO}}\n{{PARALLEL_NOTE}}\n{{FAILURES}}\n{{PASSING}}\n"
        "{{EMPTY_SEED}}\n{{TARGET_READER}}\n./trajectories/\n",
        encoding="utf-8")
    src = tmp_path / "models.py"
    src.write_text("# the data model the tools import\nVERSION = 1\n", encoding="utf-8")
    return OptimizerContext(
        capabilities="system-prompt", optimizer_name="claude-code",
        instructions_file=str(tmpl), bench_repo="/tmp/somebench",
        capability_sources=str(src), project_dir=tmp_path,
        target_model="weak")


def _assert_full_context(workdir: Path):
    """Every artifact + prompt block that used to be hill-climb-only."""
    # --- injected FILES
    assert (workdir / "trajectories").is_dir(), "no ./trajectories/ injected"
    assert any((workdir / "trajectories").iterdir()), "./trajectories/ is empty"
    assert (workdir / "guidance" / "system-prompt" / "SKILL.md").exists(), \
        "capability skill not copied to ./guidance/<cap>/"
    assert (workdir / "guidance" / "diagnose" / "SKILL.md").exists(), \
        "diagnose skill not copied to ./guidance/diagnose/"
    assert (workdir / "guidance" / "sources" / "models.py").exists(), \
        "capability_sources not copied to ./guidance/sources/"
    assert (workdir / "guidance" / "optimizer" / "claude-code.md").exists(), \
        "optimizer features reference not copied"
    # native per-agent skill placement (claude-code row of the registry)
    assert (workdir / ".claude" / "skills" / "system-prompt" / "SKILL.md").exists(), \
        "native skills dir not populated"
    assert "cap-evolve:native-skills" in (workdir / "CLAUDE.md").read_text(encoding="utf-8")

    # --- rendered PROMPT
    instr = (workdir / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "{{" not in instr, "template placeholder left unrendered"
    assert "CUSTOM-TEMPLATE-MARKER" in instr, "--instructions-file template ignored"
    assert "What you are editing (the allowed edit space)" in instr, "no CAP_BRIEF"
    assert "./guidance/system-prompt/SKILL.md" in instr, "CAP_BRIEF has no capability"
    assert "/tmp/somebench" in instr, "no bench-repo pointer"
    assert "fan out" in instr.lower(), "PARALLEL note not adapted to a parallel optimizer"
    assert "./trajectories/" in instr, "no trajectories read-pointer"
    return instr


def test_hill_climb_full_context_baseline(tmp_path):
    """The reference behavior GEPA/SkillOpt must match."""
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, "hc", max_iterations=1, stall=3)
    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])
    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=optimizer, current_val=base,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb", ctx=_ctx(tmp_path))
    _assert_full_context(run_dir.root / "work" / "cand_0001")


def test_gepa_optimizer_gets_full_context(tmp_path):
    """FAILS BEFORE THE FIX: gepa_loop had no ctx param and never injected."""
    from cap_evolve import gepa, harness
    adapter, run_dir, base = _setup(tmp_path, "gp", max_iterations=1, stall=5)
    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])
    gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=optimizer, seed_val=base,
                   max_iterations=1, minibatch_size=3, max_merges=0,
                   gate_kwargs={"mode": "significant", "k_se": 1.0},
                   ctx=_ctx(tmp_path))
    instr = _assert_full_context(run_dir.root / "work" / "gepa_0001")
    # GEPA keeps its own reflective block ON TOP of the shared context
    assert "GEPA reflective optimization step" in instr
    assert (run_dir.root / "work" / "gepa_0001" / "REFLECTION.md").exists()
    assert (run_dir.root / "work" / "gepa_0001" / "FOCUS.md").exists()


def test_gepa_trajectories_scoped_to_parent_minibatch(tmp_path):
    """./trajectories/ carries the VERBATIM rollouts REFLECTION.md only summarizes."""
    from cap_evolve import gepa, harness
    adapter, run_dir, base = _setup(tmp_path, "gt", max_iterations=1, stall=5)
    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])
    gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=optimizer, seed_val=base,
                   max_iterations=1, minibatch_size=3, max_merges=0,
                   gate_kwargs={"mode": "significant", "k_se": 1.0},
                   ctx=_ctx(tmp_path))
    names = [p.name for p in (run_dir.root / "work" / "gepa_0001" / "trajectories").iterdir()]
    assert names and all("__mb_p_0000__" in n for n in names), \
        f"trajectories not scoped to the parent minibatch tag: {names}"


def test_gepa_injected_context_excluded_from_component_list_and_snapshot(tmp_path):
    """Injected read-context must not become an editable 'component', must not bust the
    eval-cache hash, and must not be snapshotted as part of the candidate."""
    from cap_evolve import gepa, harness
    from cap_evolve.cache import hash_candidate_dir
    adapter, run_dir, base = _setup(tmp_path, "gc", max_iterations=1, stall=5)
    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])
    gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=optimizer, seed_val=base,
                   max_iterations=1, minibatch_size=3, max_merges=0,
                   gate_kwargs={"mode": "significant", "k_se": 1.0},
                   ctx=_ctx(tmp_path))
    workdir = run_dir.root / "work" / "gepa_0001"
    comps = gepa._components(workdir)
    assert comps == ["prompt.txt"], f"injected context leaked into components: {comps}"
    # hash ignores the injected dirs: a bare copy of the capability hashes the same
    bare = tmp_path / "bare"
    bare.mkdir()
    shutil.copyfile(workdir / "prompt.txt", bare / "prompt.txt")
    assert hash_candidate_dir(workdir) == hash_candidate_dir(bare)
    snap = run_dir.candidate_dir("gepa_0001")
    if snap.exists():  # only if the candidate was accepted
        assert not (snap / "trajectories").exists()
        assert not (snap / "guidance").exists()


def test_skillopt_optimizer_gets_full_context(tmp_path):
    """FAILS BEFORE THE FIX: skillopt_loop had no capabilities/optimizer_name params."""
    from cap_evolve import harness, skillopt
    adapter, run_dir, base = _setup(tmp_path, "so", max_iterations=1, stall=5)
    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])
    skillopt.skillopt_loop(adapter, run_dir=run_dir, optimizer=optimizer,
                           current_val=base, epochs=1, batch_size=4,
                           gate_kwargs={"mode": "significant", "k_se": 1.0},
                           slow_update=False, ctx=_ctx(tmp_path))
    instr = _assert_full_context(run_dir.root / "work" / "so_e01s01")
    # SkillOpt keeps its textual learning rate block ON TOP of the shared context
    assert "SkillOpt step budget (textual learning rate)" in instr


def test_optimizer_context_from_args_and_flag_declaration():
    """The shared flag set parses into an equivalent context (the seam the CLI uses)."""
    import argparse
    from cap_evolve.optimizer_context import OptimizerContext

    p = argparse.ArgumentParser()
    p.add_argument("--project")
    OptimizerContext.add_arguments(p)
    args = p.parse_args([
        "--project", "/proj", "--capabilities", "system-prompt,tools",
        "--instructions-file", "/tmp/t.md", "--bench-repo", "/tmp/bench",
        "--optimizer-name", "claude-code", "--capability-sources", "a.py,b.py",
        "--target-model", "weak", "--target-profile-file", "/tmp/p.md"])
    ctx = OptimizerContext.from_args(args)
    assert ctx.capabilities == ["system-prompt", "tools"]
    assert ctx.capability_sources == ["a.py", "b.py"]
    assert ctx.optimizer_name == "claude-code"
    assert ctx.instructions_file == "/tmp/t.md"
    assert ctx.bench_repo == "/tmp/bench"
    assert ctx.target_model == "weak"
    assert ctx.target_profile_file == "/tmp/p.md"
    assert ctx.project_dir == Path("/proj")


@pytest.mark.parametrize("algorithm", ["hill-climb", "gepa", "skillopt"])
def test_every_algorithm_run_py_accepts_the_context_flags(algorithm):
    """FAILS BEFORE THE FIX for gepa/skillopt: argparse rejected the flags entirely,
    which is why cli.py gated them behind hill-climb."""
    import subprocess
    run_py = REPO / "skills" / "algorithms" / algorithm / "scripts" / "run.py"
    out = subprocess.run([sys.executable, str(run_py), "--help"],
                         capture_output=True, text=True,
                         env={**os.environ, "CAPEVOLVE_CORE": str(CORE)})
    assert out.returncode == 0, out.stderr
    for flag in ("--capabilities", "--instructions-file", "--bench-repo",
                 "--optimizer-name", "--capability-sources", "--target-model",
                 "--target-profile-file"):
        assert flag in out.stdout, f"{algorithm} run.py does not accept {flag}"


@pytest.mark.parametrize("algorithm", ["hill-climb", "gepa", "skillopt"])
def test_cli_passes_context_flags_to_every_algorithm(algorithm):
    """FAILS BEFORE THE FIX: cli.py only emitted these for hill-climb."""
    from cap_evolve import cli
    assert algorithm in cli._OPTIMIZER_CONTEXT_ALGORITHMS
    spec = {"capabilities": ["system-prompt", "tools"],
            "runner_repo_path": "/tmp/bench",
            "capability_sources": ["models.py"],
            "target_model": "weak",
            "target_profile_file": "/tmp/prof.md"}
    flags = cli._optimizer_context_flags(spec, "/proj", "claude-code")
    assert flags[flags.index("--capabilities") + 1] == "system-prompt,tools"
    assert flags[flags.index("--optimizer-name") + 1] == "claude-code"
    assert flags[flags.index("--bench-repo") + 1] == "/tmp/bench"
    assert flags[flags.index("--capability-sources") + 1] == "models.py"
    assert flags[flags.index("--target-model") + 1] == "weak"
    assert flags[flags.index("--target-profile-file") + 1] == "/tmp/prof.md"


def test_agent_driven_algorithms_are_not_sent_context_flags():
    """evograph / agent-optimize have no deterministic loop — excluded on purpose,
    not silently dropped per-flag."""
    from cap_evolve import cli
    assert "evograph" not in cli._OPTIMIZER_CONTEXT_ALGORITHMS
    assert "agent-optimize" not in cli._OPTIMIZER_CONTEXT_ALGORITHMS


# ---------------------------------------------------------------------------
# Review-round regressions (PR #199): the three blocking findings.
# ---------------------------------------------------------------------------

def test_gepa_gets_a_populated_history_channel_and_its_true_best(tmp_path):
    """BLOCKING 1: LEDGER/RUNMAP/prior_iterations were EMPTY for GEPA.

    ``_parent_map`` / ``_build_ledger`` / ``_build_runmap`` filtered ``kind == "step"``,
    but GEPA bypasses ``run_step`` and emits ``gepa_val_gate`` — so its whole
    cross-iteration memory channel stayed empty while the prompt told the optimizer to
    read it, and ``run_dir.best_id`` stayed "seed" until loop exit. #128/#129/#130 all
    read exactly this channel.
    """
    from cap_evolve import gepa, harness
    adapter, run_dir, base = _setup(tmp_path, "gh", max_iterations=2, stall=5)
    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])
    gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=optimizer, seed_val=base,
                   max_iterations=2, minibatch_size=3, max_merges=0,
                   gate_kwargs={"mode": "significant", "k_se": 1.0},
                   ctx=_ctx(tmp_path))

    # The shared kind set must include GEPA's kind, for every consumer.
    from cap_evolve.rundir import ITERATION_EVENT_KINDS
    assert "gepa_val_gate" in ITERATION_EVENT_KINDS
    evs = run_dir.iteration_events()
    assert evs, "no iteration events recognised for a GEPA run"
    assert any(e["kind"] == "gepa_val_gate" for e in evs)

    # iteration 2's workdir must SEE iteration 1.
    wd2 = run_dir.root / "work" / "gepa_0002"
    ledger = (wd2 / "LEDGER.md").read_text(encoding="utf-8")
    runmap = (wd2 / "RUNMAP.md").read_text(encoding="utf-8")
    assert "(baseline only)" not in ledger, f"LEDGER still empty for GEPA:\n{ledger}"
    assert "gepa_0001" in ledger, f"iteration 1 missing from LEDGER:\n{ledger}"
    assert "(no prior iterations yet)" not in runmap, f"RUNMAP still empty:\n{runmap}"
    assert "gepa_0001" in runmap
    prior = wd2 / "prior_iterations" / "gepa_0001"
    assert prior.is_dir() and any(prior.iterdir()), "prior_iterations/ never populated"

    # ...and must be told its TRUE best, not "seed", once an accept happened.
    assert run_dir.best_id == "gepa_0001", f"best_id is {run_dir.best_id!r}"
    assert "## Current best: gepa_0001" in ledger


def test_gepa_cache_hit_never_substitutes_another_iterations_trajectories(tmp_path):
    """BLOCKING 2: the pinned ``tag=`` fell through on a cache hit.

    A fully-cached minibatch persists no rollout files, so ``_copy_tag`` failed and the
    chain silently handed the optimizer the PREVIOUS iteration's traces (including
    ``mb_c_*`` child rollouts) while the prompt claimed they were "the SAME minibatch
    VERBATIM". A pin must be honoured or omitted loudly — never substituted.
    """
    from cap_evolve import harness
    adapter, run_dir, _ = _setup(tmp_path, "ct", max_iterations=1, stall=5)
    workdir = tmp_path / "wd"
    workdir.mkdir()
    stale = workdir / "trajectories"
    stale.mkdir()
    (stale / "a1__mb_p_0000__t0.json").write_text("{}", encoding="utf-8")

    # Pin a tag that has NO persisted rollouts (exactly the cache-hit case).
    harness._copy_step_trajectories(adapter, run_dir, workdir, "train",
                                    tag="mb_p_0007")
    assert not stale.exists(), "stale trajectories/ left in place for an unmet pin"

    kinds = [e for e in run_dir.iteration_events()]  # touch the reader too
    warn = [json_line for json_line in
            run_dir.events_path.read_text(encoding="utf-8").splitlines()
            if "optimizer_context_warning" in json_line and "mb_p_0007" in json_line]
    assert warn, "unmet trajectory pin failed SILENTLY (no warning event)"
    assert "OMITTED" in warn[0]
    assert kinds == kinds  # no-op; keeps the reader exercised without asserting count

    # ...and the prompt block must not claim a dir that isn't there.
    from cap_evolve import gepa
    with_traj = gepa._gepa_block("s", "prompt.txt", ["a1"], has_trajectories=True)
    without = gepa._gepa_block("s", "prompt.txt", ["a1"], has_trajectories=False)
    assert "SAME minibatch rollouts VERBATIM" in with_traj
    assert "SAME minibatch rollouts VERBATIM" not in without
    assert "served entirely from the eval cache" in without


def test_focus_ids_from_a_disjoint_split_do_not_empty_the_failure_index(tmp_path):
    """BLOCKING 3: SkillOpt's failure index was always "of 0 tasks".

    ``render_instructions`` got a VAL result narrowed by TRAIN ids — disjoint by
    construction — so the intersection was always empty and the optimizer was told
    there was nothing to fix. Zero overlap must fall back to the unfiltered index and
    say so, not report a confident empty one.
    """
    from cap_evolve import skillopt, harness
    from cap_evolve.optimizer_context import render_instructions
    adapter, run_dir, base = _setup(tmp_path, "fi", max_iterations=2, stall=5)

    # Unit: val result + train-shaped ids => full index, with the caveat sentence.
    train_ids = list(run_dir.read_splits().train)
    val_ids = {pt["task_id"] for pt in base.per_task}
    assert not (set(train_ids) & val_ids), "fixture splits are not disjoint"
    out = render_instructions(base, train_ids, "mb", ctx=_ctx(tmp_path))
    assert " of 0 tasks." not in out, f"failure index emptied by disjoint ids:\n{out[:400]}"
    assert "ALWAYS-failing task(s)" in out, "no failure index rendered"
    assert "different split than the scored result" in out, "silent fallback (no caveat)"

    # End to end: a real SkillOpt step's INSTRUCTIONS.md has a non-empty index.
    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])
    skillopt.skillopt_loop(adapter, run_dir=run_dir, optimizer=optimizer,
                           current_val=base, epochs=1, batch_size=2,
                           edit_budget=2,
                           gate_kwargs={"mode": "significant", "k_se": 1.0},
                           ctx=_ctx(tmp_path))
    step_dirs = sorted((run_dir.root / "work").glob("so_*"))
    assert step_dirs, "no skillopt workdir"
    instr = (step_dirs[0] / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert " of 0 tasks." not in instr, f"SkillOpt index still empty:\n{instr[:400]}"
    assert "ALWAYS-failing task(s)" in instr
    assert "No actionable failures in focus" not in instr


def test_assembled_instructions_are_globally_capped():
    """Non-blocking 7: every block was bounded, the SUM was not."""
    from cap_evolve.loop import SplitResult
    from cap_evolve.optimizer_context import MAX_INSTRUCTIONS_CHARS, render_instructions
    res = SplitResult(split="val", reward=0.0, stderr=0.0, per_task=[
        {"task_id": "a1", "reward": 0.0, "feedback": "x" * 200, "trial_rewards": [0.0]}])
    out = render_instructions(res, None, "all", extra="Z" * 200_000, max_chars=5_000)
    assert len(out) <= 5_000 + 300, len(out)
    assert "chars elided to keep this prompt under" in out
    assert MAX_INSTRUCTIONS_CHARS >= 10_000  # a normal render must never be truncated


@pytest.mark.parametrize("algo", ["hill-climb", "gepa", "skillopt"])
def test_target_profile_file_reaches_every_algorithms_prompt(tmp_path, algo):
    """Non-blocking 8: ``--target-profile-file`` was only covered by a unit test.

    Real fixture profile file, real loop, all three algorithms: the project-local brief
    must OVERRIDE the tier's built-in brief in the rendered prompt.
    """
    from cap_evolve import gepa, harness, skillopt
    from cap_evolve.optimizer_context import OptimizerContext
    prof = tmp_path / "reader.md"
    prof.write_text("FIXTURE-READER-BRIEF-199: the consuming model needs explicit rules.",
                    encoding="utf-8")
    tmpl = tmp_path / "t.md"
    tmpl.write_text("{{FOCUS_SUMMARY}}\n{{TARGET_READER}}\n{{FAILURES}}\n", encoding="utf-8")
    ctx = OptimizerContext(capabilities="system-prompt", instructions_file=str(tmpl),
                           target_model="mid", target_profile_file=str(prof),
                           project_dir=tmp_path)
    adapter, run_dir, base = _setup(tmp_path, f"tp{abs(hash(algo)) % 997}",
                                   max_iterations=1, stall=5)
    optimizer = harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])
    common = dict(run_dir=run_dir, optimizer=optimizer, ctx=ctx,
                  gate_kwargs={"mode": "significant", "k_se": 1.0})
    if algo == "hill-climb":
        harness.hill_climb_loop(adapter, current_val=base, focus="all",
                                max_iterations=1, algorithm="hill-climb", **common)
    elif algo == "gepa":
        gepa.gepa_loop(adapter, seed_val=base, max_iterations=1, minibatch_size=3,
                       max_merges=0, **common)
    else:
        skillopt.skillopt_loop(adapter, current_val=base, epochs=1, batch_size=2,
                               edit_budget=2, **common)
    instrs = [p.read_text(encoding="utf-8")
              for p in (run_dir.root / "work").glob("*/INSTRUCTIONS.md")]
    assert instrs, f"no INSTRUCTIONS.md written for {algo}"
    assert any("FIXTURE-READER-BRIEF-199" in i for i in instrs), \
        f"--target-profile-file brief never reached {algo}'s prompt"
