"""The human CLI surface: home screen, help, doctor, init, diff — plus the two
contracts that must not bend for any of them.

1. **stdout belongs to machines.** Chrome goes to stderr; only a command's actual
   payload (JSON, or the diff itself) reaches stdout.
2. **``--spec`` belongs to ``--project``.** A spec resolved relative to the cwd let
   ``cap-evolve run --project OTHER`` optimize a different project's capability while
   looking perfectly healthy — including, because the foreign spec said
   ``orchestration_mode: deterministic``, spawning a paid optimizer subprocess that
   should never have started.
"""

import io
import json
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _run(*argv):
    """(rc, stdout, stderr) for one ``cap-evolve`` invocation, in-process."""
    from cap_evolve import cli
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main(list(argv))
    return rc, out.getvalue(), err.getvalue()


# ---- home screen / help -----------------------------------------------------

def test_no_args_prints_the_home_screen_to_stderr():
    rc, out, err = _run()
    assert rc == 0
    assert out == ""                        # stdout stays clean for machines
    assert "cap-evolve" in err and "Golden path" in err
    assert "cap-evolve init" in err and "cap-evolve run --tui" in err
    assert not _ANSI.search(err)            # captured stream is not a TTY


def test_help_for_a_command_lists_runnable_examples():
    rc, out, err = _run("help", "diff")
    assert rc == 0 and out == ""
    assert "cap-evolve diff --best" in err
    assert "usage" in err


def test_help_index_and_dash_h_agree():
    _, _, a = _run("help")
    _, _, b = _run("--help")
    assert a == b
    assert "inspect" in a and "set up" in a


def test_unknown_command_exits_2_and_shows_the_command_index():
    rc, out, err = _run("frobnicate")
    assert rc == 2 and out == ""
    assert "unknown command: frobnicate" in err
    assert "diff" in err and "doctor" in err


def test_every_command_answers_help_with_exit_0():
    from cap_evolve import branding
    for name in branding.COMMANDS:
        try:
            rc, _out, err = _run(name, "--help")
        except SystemExit as e:             # argparse-backed subcommands
            assert e.code == 0, name
            continue
        assert rc == 0, name
        assert err.strip(), name


def test_argparse_subcommands_show_examples_in_their_help():
    """``--help`` on a real subcommand carries the same examples as the catalog."""
    from cap_evolve import cli
    for name in ("run", "watch", "diff", "replay", "tail", "estimate", "dashboard"):
        out = io.StringIO()
        try:
            with redirect_stdout(out):
                cli.main([name, "--help"])
        except SystemExit as e:
            assert e.code == 0, name
        text = out.getvalue()
        assert "examples:" in text, name
        assert cli._epilog(name).splitlines()[1].strip() in text, name


def test_version_stays_machine_readable():
    rc, out, _err = _run("version")
    assert rc == 0 and json.loads(out)["cap-evolve"]
    rc, out, _err = _run("--version")
    assert rc == 0 and json.loads(out)["cap-evolve"]


def test_algorithms_json_is_machine_readable():
    rc, out, _err = _run("algorithms", "--json")
    assert rc == 0
    assert "gepa" in json.loads(out)


# ---- the --spec / --project regression -------------------------------------

def _project(root: Path, name: str, mode: str) -> Path:
    proj = root / name / "project"
    proj.mkdir(parents=True)
    (proj / "capevolve.yaml").write_text(
        "algorithm_skill: hill-climb              # comment survives\n"
        f"orchestration_mode: {mode}\n"
        "optimizer_skill: mock\n"
        "capability_path: seed_capability\n"
        "max_iterations: 3\n", encoding="utf-8")
    return proj


def test_spec_defaults_relative_to_project_not_the_cwd(tmp_path, monkeypatch):
    """The exact bug: a decoy spec at the cwd default must never be read.

    A foreign spec does not merely point at the wrong files — it carries the wrong
    ``orchestration_mode``, which decides whether a paid optimizer subprocess is
    spawned at all. So this is checked on the resolver AND through ``--plan-only``.
    """
    from cap_evolve import cli

    decoy = _project(tmp_path, ".capevolve", "deterministic")
    real = _project(tmp_path, ".capevolve-agentopt", "agent")
    monkeypatch.chdir(tmp_path)

    path, err = cli._resolve_spec(None, str(real))
    assert err is None
    assert path == (real / "capevolve.yaml").resolve()
    assert path != (decoy / "capevolve.yaml").resolve()

    rc, out, _err = _run("run", "--project", str(real), "--dashboard", "off",
                         "--plan-only")
    assert rc == 0
    plan = json.loads(out)
    assert plan["spec_path"] == str((real / "capevolve.yaml").resolve())
    assert plan["orchestration_mode"] == "agent"       # NOT the decoy's deterministic
    assert "<handoff" in " ".join(plan["sequence"])    # so no optimizer is spawned


def test_spec_outside_the_project_is_refused_naming_both_paths(tmp_path):
    from cap_evolve import cli
    a = _project(tmp_path, "a", "deterministic")
    b = _project(tmp_path, "b", "agent")
    path, err = cli._resolve_spec(str(b / "capevolve.yaml"), str(a))
    assert path is None
    assert "outside" in err["error"]
    assert str(a.resolve()) in err["project"] and str(b.resolve()) in err["spec"]
    assert err["fix"].startswith("cap-evolve run --project")

    rc, out, err_text = _run("run", "--project", str(a), "--dashboard", "off",
                             "--spec", str(b / "capevolve.yaml"))
    assert rc == 1
    assert json.loads(out)["step"] == "spec"
    assert "→ cap-evolve run --project" in err_text     # actionable next command


def test_missing_spec_names_the_command_that_creates_it(tmp_path):
    from cap_evolve import cli
    path, err = cli._resolve_spec(None, str(tmp_path / "nothing"))
    assert path is None
    assert "no spec at" in err["error"]
    assert err["fix"].startswith("cap-evolve init")


# ---- doctor ----------------------------------------------------------------

def test_doctor_reports_a_missing_spec_with_its_fix(tmp_path):
    rc, out, err = _run("doctor", "--project", str(tmp_path / "absent"), "--json")
    assert rc == 1
    rep = json.loads(out)
    assert rep["ok"] is False
    row = rep["checks"][0]
    assert row["name"] == "spec" and row["status"] == "fail"
    assert row["fix"].startswith("cap-evolve init")
    assert err == ""


def test_doctor_human_output_shows_every_fix_as_a_command(tmp_path):
    proj = _project(tmp_path, ".capevolve", "deterministic")
    rc, out, err = _run("doctor", "--project", str(proj))
    assert rc == 1                       # no adapter → blocking
    assert out == ""
    assert "readiness check" in err
    assert "adapter" in err and "capability" in err
    # every blocking row offers a command to run next
    assert "→ " in err


def test_doctor_flags_an_agent_algorithm_in_deterministic_mode(tmp_path):
    from cap_evolve.cli import _doctor_checks
    proj = _project(tmp_path, ".capevolve", "deterministic")
    (proj / "capevolve.yaml").write_text(
        "algorithm_skill: agent-optimize\norchestration_mode: deterministic\n"
        "optimizer_skill: mock\n", encoding="utf-8")
    rows = {r["name"]: r for r in _doctor_checks(proj)}
    assert rows["algorithm"]["status"] == "fail"
    assert "agent-driven" in rows["algorithm"]["detail"]


# ---- init ------------------------------------------------------------------

def test_init_writes_a_spec_with_the_chosen_algorithm(tmp_path):
    proj = tmp_path / ".capevolve" / "project"
    rc, out, err = _run("init", "--project", str(proj), "--algorithm", "gepa",
                        "--optimizer", "mock", "--yes")
    assert rc == 0 and out == ""
    text = (proj / "capevolve.yaml").read_text(encoding="utf-8")
    assert "algorithm_skill: gepa" in text
    assert "optimizer_skill: mock" in text
    assert "orchestration_mode: deterministic" in text
    assert "cap-evolve doctor" in err          # tells you the next step
    # and the spec it wrote is the one a run would pick up
    from cap_evolve import cli
    path, e = cli._resolve_spec(None, str(proj))
    assert e is None and path == (proj / "capevolve.yaml").resolve()


def test_init_selects_agent_mode_for_an_agent_driven_algorithm(tmp_path):
    proj = tmp_path / ".capevolve" / "project"
    assert _run("init", "--project", str(proj), "--algorithm", "evograph", "--yes")[0] == 0
    text = (proj / "capevolve.yaml").read_text(encoding="utf-8")
    assert "algorithm_skill: evograph" in text
    assert "orchestration_mode: agent" in text


def test_init_refuses_to_clobber_an_existing_spec(tmp_path):
    proj = tmp_path / ".capevolve" / "project"
    assert _run("init", "--project", str(proj), "--yes")[0] == 0
    rc, _out, err = _run("init", "--project", str(proj), "--yes")
    assert rc == 1
    assert "already exists" in err and "--force" in err


def test_set_spec_key_preserves_comments_and_appends_missing_keys():
    from cap_evolve.cli import _set_spec_key
    src = "algorithm_skill: hill-climb   # pick one\nother: 1\n"
    out = _set_spec_key(src, "algorithm_skill", "gepa")
    assert "algorithm_skill: gepa  # pick one" in out
    assert "other: 1" in out
    assert "new_key: v" in _set_spec_key(src, "new_key", "v")
    # a commented-out line is not the key
    commented = _set_spec_key("# algorithm_skill: x\n", "algorithm_skill", "gepa")
    assert "# algorithm_skill: x" in commented          # left alone
    assert "\nalgorithm_skill: gepa" in commented       # real key appended


# ---- diff ------------------------------------------------------------------

def _run_dir(tmp_path) -> Path:
    root = tmp_path / ".capevolve" / "run_t"
    (root / "candidates" / "seed").mkdir(parents=True)
    (root / "candidates" / "c1").mkdir(parents=True)
    (root / "candidates" / "seed" / "p.txt").write_text("one\n", encoding="utf-8")
    (root / "candidates" / "c1" / "p.txt").write_text("one\ntwo\n", encoding="utf-8")
    (root / "events.jsonl").write_text(json.dumps(
        {"kind": "step", "candidate": "c1", "parent": "seed", "accept": True}) + "\n",
        encoding="utf-8")
    (root / "final.json").write_text(json.dumps({"best_id": "c1"}), encoding="utf-8")
    return root


def test_diff_puts_the_diff_on_stdout_and_the_header_on_stderr(tmp_path):
    root = _run_dir(tmp_path)
    rc, out, err = _run("diff", "c1", "--run-dir", str(root), "--no-color")
    assert rc == 0
    assert "+ two" in out.replace("+  two", "+ two")
    assert "p.txt" in out
    assert "parent seed → c1" in err        # which two snapshots: chrome
    assert not _ANSI.search(out)


def test_diff_best_compares_seed_to_the_winner(tmp_path):
    root = _run_dir(tmp_path)
    rc, out, err = _run("diff", "--best", "--run-dir", str(root), "--no-color")
    assert rc == 0 and "two" in out
    assert "seed → best" in err


def test_diff_without_a_candidate_is_exit_2_and_lists_the_candidates(tmp_path):
    root = _run_dir(tmp_path)
    rc, out, err = _run("diff", "--run-dir", str(root))
    assert rc == 2 and out == ""
    assert "name a candidate" in err
    assert "c1" in err and "seed" in err
    assert "cap-evolve diff --best" in err


def test_diff_on_a_run_without_snapshots_explains_itself(tmp_path):
    root = tmp_path / ".capevolve" / "run_t"
    root.mkdir(parents=True)
    (root / "events.jsonl").write_text("", encoding="utf-8")
    rc, _out, err = _run("diff", "ghost", "--run-dir", str(root))
    assert rc == 2
    assert "no snapshot for" in err
    assert "cap-evolve watch" in err        # what to do instead


def test_diff_stat_and_files_views(tmp_path):
    root = _run_dir(tmp_path)
    assert "1 file changed" in _run("diff", "c1", "--run-dir", str(root),
                                    "--stat", "--no-color")[1]
    assert "changed" in _run("diff", "c1", "--run-dir", str(root),
                             "--files", "--no-color")[1]


# ---- the stdout contract, end to end ---------------------------------------

def _toy_project(tmp_path: Path):
    """The zero-API toy_calc project (mock optimizer) + its env."""
    import os
    import shutil
    example = REPO / "examples" / "toy_calc"
    proj = tmp_path / ".capevolve" / "project"
    (proj / "adapters").mkdir(parents=True)
    shutil.copy(example / "adapter.py", proj / "adapters" / "adapter.py")
    shutil.copytree(example / "capability", tmp_path / "seed_capability")
    shutil.copy(REPO / "templates" / "project" / "capevolve.yaml", proj / "capevolve.yaml")
    env = dict(os.environ)
    env.update(PYTHONPATH=str(CORE), CAPEVOLVE_CORE=str(CORE),
               CAPEVOLVE_SKILLS_DIR=str(REPO / "skills"),
               CAPEVOLVE_TOY_DATA=str(example),
               CAPEVOLVE_MOCK_SCRIPT=str(example / "mock_script.json"))
    return proj, env


def _real_run(tmp_path, ts, *extra):
    import subprocess
    proj, env = _toy_project(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "cap_evolve.cli", "run", "--project", str(proj),
         "--run-ts", ts, "--dashboard", "off", *extra],
        capture_output=True, text=True, env=env, timeout=600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    return proc


def test_run_tui_stdout_is_byte_identical_to_plain_run(tmp_path):
    """``--tui`` is a stderr-only feature: CI parses stdout as JSON either way."""
    plain = _real_run(tmp_path / "a", "t")
    tui = _real_run(tmp_path / "b", "t", "--tui", "--diff")
    assert json.loads(plain.stdout) == json.loads(tui.stdout)
    assert plain.stdout == tui.stdout
    assert not _ANSI.search(tui.stdout)


def test_run_echoes_and_records_the_resolved_spec(tmp_path):
    """A finished run must be able to say which spec produced it."""
    proc = _real_run(tmp_path, "t")
    proj = tmp_path / ".capevolve" / "project"
    assert f"spec: {proj / 'capevolve.yaml'}" in proc.stderr
    events = (tmp_path / ".capevolve" / "run_t" / "events.jsonl").read_text(
        encoding="utf-8")
    cfg = [json.loads(ln) for ln in events.splitlines()
           if ln.strip().startswith("{") and '"run_config"' in ln]
    assert cfg, "no run_config event — the run is not self-describing"
    assert cfg[0]["spec"] == str((proj / "capevolve.yaml").resolve())
    assert cfg[0]["algorithm"] and cfg[0]["orchestration_mode"] == "deterministic"


def test_diff_works_on_a_real_run(tmp_path):
    """The headline feature, against snapshots a real run actually wrote."""
    _real_run(tmp_path, "t")
    base = tmp_path / ".capevolve"
    rc, out, err = _run("diff", "--best", "--base", str(base), "--no-color")
    assert rc == 0, err
    assert "prompt.txt" in out
    assert "+" in out
    assert not _ANSI.search(out)


# ---- check accepts the same --project flag as every other subcommand --------

def test_check_accepts_project_as_a_flag_not_just_positionally(tmp_path):
    """``Path(argv[0])`` turned ``--project X`` into the literal path ``--project``, so
    the hard gate reported "no adapter" for a project whose adapter was right there —
    a false failure on the one command that is supposed to be trustworthy."""
    proj = tmp_path / ".capevolve" / "project"
    (proj / "adapters").mkdir(parents=True)
    rc_flag, out_flag, _ = _run("check", "--project", str(proj))
    rc_pos, out_pos, _ = _run("check", str(proj))
    rc_eq, out_eq, _ = _run("check", f"--project={proj}")
    assert rc_flag == rc_pos == rc_eq
    assert out_flag == out_pos == out_eq
    # and the reported problem is about the real project, never the literal flag
    assert "--project" not in out_flag


def test_check_rejects_an_unknown_option_instead_of_pathifying_it(tmp_path):
    rc, out, err = _run("check", "--bogus")
    assert rc == 2
    assert "--bogus" in err and out == ""


def test_check_flags_a_real_project_as_passing(tmp_path):
    """The gate must actually pass on a valid adapter (the regression above made every
    invocation look broken, which would have masked a real contract failure)."""
    proj = _project(tmp_path, ".capevolve", "deterministic")
    src = REPO / "examples" / "toy_calc" / "adapter.py"
    (proj / "adapters").mkdir(parents=True, exist_ok=True)
    (proj / "adapters" / "adapter.py").write_text(src.read_text(encoding="utf-8"),
                                                  encoding="utf-8")
    import os
    os.environ["CAPEVOLVE_TOY_DATA"] = str(REPO / "examples" / "toy_calc")
    rc, out, _ = _run("check", "--project", str(proj))
    assert json.loads(out)["ok"] is True, out
    assert rc == 0
