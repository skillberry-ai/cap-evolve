"""The documented `cap-evolve` CLI surface is real: every command, flag and --help.

Docs are the agent-facing API: `orchestrate` and the algorithm SKILL.mds tell an agent
to run these exact command lines. A subcommand that does not exist turns a documented
instruction into an exit-2 crash — and #203 found five algorithm SKILL.mds instructing
`cap-evolve finalize` at the SEAL step, i.e. after the whole budget is spent.

Shared file with #198, which adds the phase-`scripts/run.py` scanner (documented flags
and enumerated values vs the real argparse) to it. The two halves are additive: this
one covers the `cap-evolve` front door, #198's covers the phase scripts behind it.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(REPO / "core")}


def _run(*args):
    return subprocess.run([sys.executable, "-m", "cap_evolve.cli", *args],
                          capture_output=True, text=True, cwd=REPO, env=ENV)


# ---------------------------------------------------------------- #137: cap-evolve
# The other half of the surface: `cap-evolve <subcommand>` in docs. #203 found five
# algorithm SKILL.mds telling an agent to run `cap-evolve finalize`, which exits 2 at
# the SEAL step — after the whole budget is spent. Rather than a prose allowlist, this
# accepts anything the CLI itself resolves: a real subcommand, or a phase name whose
# error message hands back the runnable script path.
_CE = re.compile(r"`cap-evolve ([a-z][a-z0-9-]*)")
# "There is no `cap-evolve status` command" is documentation OF the absence, not an
# instruction to run it — the one shape that must not be flagged.
_DENIES = re.compile(r"\b(no|not|never|does ?n[o']t|doesn't|non-existent)\b", re.I)


def _documented_subcommands():
    """Every `cap-evolve <word>` a doc actually instructs, as (doc, word) pairs."""
    docs = [p for p in REPO.glob("**/*.md")
            if "node_modules" not in p.parts and ".git" not in p.parts
            and "specs" not in p.parts and "plans" not in p.parts]
    for doc in [*docs, *(REPO / "site").glob("*.html")]:
        for line in doc.read_text(errors="replace").splitlines():
            for word in _CE.findall(line):
                if not _DENIES.search(line):
                    yield doc, word


def _cli():
    sys.path.insert(0, str(REPO / "core"))
    from cap_evolve import cli
    return cli


def test_every_subcommand_renders_help():
    """`cap-evolve <cmd> --help` works for every command in COMMANDS (#137).

    Asserts the contract a NEW subcommand must meet — exit 0 and a `cap-evolve <cmd>`
    usage line, i.e. the parser's `prog` is right — and nothing beyond it. Requiring an
    `examples:` epilog here would fail whenever a parallel branch registers a command
    (#116's `tail`, #121's `doctor`), which is a merge tax, not a bug: examples are
    checked below only for the commands this PR authored.
    """
    cli = _cli()
    for name in cli.COMMANDS:
        out = _run(name, "--help")
        assert out.returncode == 0, f"`cap-evolve {name} --help` exited {out.returncode}:\n{out.stderr}"
        assert f"usage: cap-evolve {name}" in out.stdout, (
            f"`cap-evolve {name} --help` has no `cap-evolve {name}` usage line — the "
            f"parser's prog= is probably wrong:\n{out.stdout[:400]}")


def test_help_carries_examples():
    """The commands #137 documented keep their worked examples (#137)."""
    for name in ("version", "splits", "check", "run", "estimate", "dashboard"):
        out = _run(name, "--help")
        assert "examples:" in out.stdout, f"`cap-evolve {name} --help` lost its examples"


def test_top_level_help_lists_exactly_the_real_commands():
    """The usage line is generated from COMMANDS, so it cannot drift (#137)."""
    cli = _cli()
    usage = cli._usage()
    assert "{" + "|".join(cli.COMMANDS) + "}" in usage
    for name in cli.COMMANDS:
        assert f"\n  {name}" in usage, f"{name} missing from the command listing"


def test_documented_cap_evolve_subcommands_resolve():
    """No doc instructs a `cap-evolve <word>` the CLI can't act on (#203/#137).

    A word is fine when it is a real subcommand, OR a phase-skill name the CLI's
    unknown-command handler redirects by name, OR ordinary English prose ("cap-evolve
    runs the loop") — prose is filtered by requiring the line to look like a command.
    """
    cli = _cli()
    ok = set(cli.COMMANDS) | set(cli._PHASE_SCRIPTS) | {"help"}
    seen, findings = 0, []
    for doc, word in _documented_subcommands():
        seen += 1
        if word not in ok:
            findings.append(f"{doc.relative_to(REPO)}: `cap-evolve {word}` is not a command")
    assert seen > 50, f"scanner found only {seen} invocations — regex likely broke"
    assert not findings, ("documented cap-evolve subcommands that do not exist:\n"
                         + "\n".join(sorted(set(findings))))


def test_unknown_subcommand_suggests_and_exits_nonzero():
    """Typos get a suggestion; phase names get the real script path (#137)."""
    cli = _cli()
    assert "check" in cli._did_you_mean("chekc")
    assert "run" in cli._did_you_mean("runn")
    # A phase name is redirected to the runnable script, not "did you mean".
    msg = cli._did_you_mean("finalize")
    assert "phases/finalize/scripts/run.py" in msg and "did you mean" not in msg
    out = _run("chekc")
    assert out.returncode == 2, f"unknown command exited {out.returncode}, want 2"
    assert "did you mean: check" in out.stderr
    assert out.stdout == "", f"unknown command polluted stdout: {out.stdout!r}"


def test_run_rejects_negative_budget():
    """A negative cap is a typo, not 'unlimited' (0 is) — exit 2, spend nothing (#137)."""
    out = _run("run", "--max-usd", "-5")
    assert out.returncode == 2
    assert "--max-usd must be >= 0" in out.stderr


def test_cli_survives_an_ascii_stdout():
    """Reports carry →/Δ/✓; an ascii stream must not kill the process (#137)."""
    out = subprocess.run([sys.executable, "-m", "cap_evolve.cli", "--help"],
                         capture_output=True, text=True, cwd=REPO,
                         env={**ENV, "PYTHONIOENCODING": "ascii", "LC_ALL": "C", "LANG": "C"})
    assert out.returncode == 0, f"ascii stdout crashed --help:\n{out.stderr}"
    assert "commands:" in out.stdout


def test_run_stdout_is_a_single_json_object(tmp_path):
    """`cap-evolve run > out.json | json.loads` — the machine-readable contract (#137).

    Scripts parse `cap-evolve run`'s stdout. Before this, the dashboard-launch status
    was ALSO printed there, so stdout held two concatenated objects and json.loads
    raised "Extra data". Human/progress output belongs on stderr (#116's convention);
    this drives the real zero-API toy_calc run and parses stdout to keep it that way.
    """
    import json
    import shutil

    ex = REPO / "examples" / "toy_calc"
    (tmp_path / ".capevolve/project/adapters").mkdir(parents=True)
    shutil.copy(ex / "adapter.py", tmp_path / ".capevolve/project/adapters/adapter.py")
    shutil.copytree(ex / "capability", tmp_path / "seed_capability")
    shutil.copy(REPO / "templates/project/capevolve.yaml",
                tmp_path / ".capevolve/project/capevolve.yaml")
    out = subprocess.run(
        [sys.executable, "-m", "cap_evolve.cli", "run",
         "--spec", str(tmp_path / ".capevolve/project/capevolve.yaml"),
         "--project", str(tmp_path / ".capevolve/project"), "--run-ts", "t"],
        capture_output=True, text=True, cwd=REPO,
        env={**ENV, "CAPEVOLVE_CORE": str(REPO / "core"),
             "CAPEVOLVE_SKILLS_DIR": str(REPO / "skills"),
             "CAPEVOLVE_TOY_DATA": str(ex),
             "CAPEVOLVE_MOCK_SCRIPT": str(ex / "mock_script.json")})
    assert out.returncode == 0, f"run failed:\n{out.stdout}\n{out.stderr}"
    report = json.loads(out.stdout)      # the whole point: no "Extra data"
    assert report["test_reward"] is not None and "run_dir" in report
