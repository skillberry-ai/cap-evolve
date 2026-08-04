"""`cap-evolve quickstart` — the zero-question fast path to a runnable project (#133).

Three contracts are load-bearing and each has a test that fails if it breaks:

1. **It really runs.** The scaffolded project passes `cap-evolve check` AND completes a
   full `cap-evolve run` to a sealed test number with the offline `mock` optimizer. A
   scaffold that merely *looks* right is the failure mode this whole command exists to
   avoid, so the money test drives the real pipeline.
2. **Non-interactive, never hangs.** Piped/closed stdin uses defaults and returns; only
   an explicit TTY on both stdin and stderr may prompt. Enforced with a subprocess
   timeout, because "hangs forever" is not a value any assertion can inspect.
3. **No secret ever leaves.** Multi-shape canaries under INNOCENT env names (a key-name
   heuristic missed exactly that case earlier in this epic) must not appear in stdout,
   stderr, or any written file — not the value, not a prefix, not a length.

Plus: stdout is exactly one JSON object (#217), the spec omits `protected_paths` (#197
makes an empty list a hard error), and the val split clears #195's `MIN_VAL_TASKS` floor.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(REPO / "core"),
       "CAPEVOLVE_SKILLS_DIR": str(REPO / "skills")}

sys.path.insert(0, str(REPO / "core"))
from cap_evolve import quickstart  # noqa: E402


def _last_json_object(text: str) -> dict:
    """The final top-level JSON object in ``text``, tolerating earlier ones."""
    dec, pos, last = json.JSONDecoder(), 0, None
    while pos < len(text):
        try:
            obj, pos = dec.raw_decode(text, pos)
        except json.JSONDecodeError:
            pos += 1
            continue
        if isinstance(obj, dict):
            last = obj
    assert last is not None, f"no JSON object on stdout:\n{text[:800]}"
    return last


def _qs(*args, cwd=None, env=None, stdin=subprocess.DEVNULL, timeout=60):
    return subprocess.run([sys.executable, "-m", "cap_evolve.cli", "quickstart", *args],
                          capture_output=True, text=True, cwd=str(cwd or REPO),
                          env={**ENV, **(env or {})}, stdin=stdin, timeout=timeout)


# --------------------------------------------------------------- 1. it really runs

def test_scaffolded_project_runs_to_a_sealed_test_number(tmp_path):
    """quickstart → check → run → a sealed test number, offline and free (#133).

    The money test. Everything else about quickstart is presentation; this is whether
    the thing it wrote actually optimizes. Baseline must be 0.0 (the seed prompt is
    deliberately vague) and the sealed test 1.0 (the mock optimizer makes the output
    contract explicit), so a scaffold that produced an unoptimizable project — no
    headroom, or a broken adapter — fails here rather than in a user's terminal.
    """
    out = _qs("--yes", "--dir", str(tmp_path))
    assert out.returncode == 0, f"quickstart failed:\n{out.stdout}\n{out.stderr}"

    chk = subprocess.run([sys.executable, "-m", "cap_evolve.cli", "check",
                          str(tmp_path / ".capevolve/project")],
                         capture_output=True, text=True, cwd=str(REPO), env=ENV)
    assert chk.returncode == 0, f"scaffold is not check-green:\n{chk.stdout}"
    assert json.loads(chk.stdout)["ok"] is True

    run = subprocess.run(
        [sys.executable, "-m", "cap_evolve.cli", "run",
         "--spec", str(tmp_path / ".capevolve/project/capevolve.yaml"),
         "--project", str(tmp_path / ".capevolve/project"),
         "--run-ts", "t", "--dashboard", "off"],
        capture_output=True, text=True, cwd=str(REPO),
        env={**ENV, "CAPEVOLVE_CORE": str(REPO / "core"),
             "CAPEVOLVE_MOCK_SCRIPT": str(tmp_path / ".capevolve/mock_script.json")},
        timeout=600)
    assert run.returncode == 0, f"run failed:\n{run.stdout}\n{run.stderr}"
    # The final report is the LAST JSON object on stdout. #217 says there should be
    # exactly one, and quickstart's own stdout is asserted to be exactly one below —
    # but `cap-evolve run` is not this PR's contract to enforce, and #190's branch
    # currently prints a `{"step": "provider"}` line there too. Asserting strict
    # single-object on `run` from here would make THIS file fail on a merge order it
    # does not control; #217 owns that.
    report = _last_json_object(run.stdout)
    assert report["baseline_val"] == 0.0, report
    assert report["test_reward"] == 1.0, f"no sealed improvement: {report}"


# ------------------------------------------------- 2. non-interactive, never hangs

@pytest.mark.parametrize("argv,stdin_mode", [
    ([], subprocess.DEVNULL),      # closed stdin, no flags: must default, not block
    ([], subprocess.PIPE),         # piped stdin (garbage on it): must default, not read
    (["--yes"], subprocess.PIPE),
    (["--preset", "mock"], subprocess.PIPE),
])
def test_never_hangs_and_uses_defaults(tmp_path, argv, stdin_mode):
    """No invocation blocks on stdin; the default preset is used (#133).

    `timeout=` is the assertion: a prompt written to a pipe that nobody answers hangs
    forever, and no return-value check can catch that.
    """
    d = tmp_path / f"d{len(argv)}{stdin_mode}"
    proc = subprocess.Popen(
        [sys.executable, "-m", "cap_evolve.cli", "quickstart", *argv, "--dir", str(d)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=stdin_mode,
        text=True, cwd=str(REPO), env=ENV)
    stdout, stderr = proc.communicate(input="free\n" if stdin_mode is subprocess.PIPE else None,
                                     timeout=60)
    assert proc.returncode == 0, stderr
    # Not "free": a non-TTY stdin must be ignored entirely, not consulted.
    assert json.loads(stdout)["preset"] == quickstart.DEFAULT_PRESET


def test_interactive_requires_a_tty_on_both_streams(monkeypatch):
    """`interactive()` is false unless stdin AND stderr are real terminals (#133/#215).

    Reuses #215's capability ladder rather than sniffing isatty locally, so a
    non-terminal on either side (CI, a pipe, `2>&-`) means "defaults".
    """
    class S:
        def __init__(self, tty):
            self._tty, self.closed, self.encoding = tty, False, "utf-8"

        def isatty(self):
            return self._tty

    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    for in_tty, err_tty, want in ((True, True, True), (True, False, False),
                                  (False, True, False), (False, False, False)):
        monkeypatch.setattr(sys, "stdin", S(in_tty))
        monkeypatch.setattr(sys, "stderr", S(err_tty))
        assert quickstart.interactive() is want, (in_tty, err_tty)


# ------------------------------------------------------------------- 3. no secrets

# Deliberately INNOCENT names: a key-name heuristic caught ANTHROPIC_API_KEY and missed
# a token parked in BUILD_NUMBER earlier in this epic. Shapes: bare high-entropy, UUID,
# `ghp_`, `sk-`, and an opaque watsonx-style base64 blob.
_CANARIES = {
    "GEMINI_API_KEY": "AIzaSyCANARY9bare1high2entropy3value4here5xyzQ",
    "BUILD_NUMBER": "7f3c9a21-4b8e-4d1f-9c2a-6e5b7d8f0a13",
    "DEPLOY_TAG": "ghp_CANARYghp0123456789abcdefghijklmnopqrs",
    "REGION_HINT": "cGFzc3dvcmQ6Y2FuYXJ5d2F0c29ueDEyMzQ1Njc4OTBhYmNkZWY=",
    "TELEMETRY_ID": "sk-CANARYsk0123456789abcdefghijklmnopqrstuvwxyz",
}
_SECRET_URL = "https://gw-user:s3cr3tCANARYtoken@internal.gw.example.corp/v1"


@pytest.mark.parametrize("preset", sorted(quickstart.PRESETS))
def test_no_canary_leaks_into_output_or_files(tmp_path, preset):
    """Not a value, not a prefix, not a length — anywhere (#133/#190).

    Prefixes are checked too: a truncated secret still identifies the account, and
    slicing before redaction is how a fragment survives a shape-based rule.

    Scope note: the endpoint HOSTNAME is only confidential in *output*. An endpoint the
    user typed as `--base-url` must reach the adapter or nothing can call it, so the
    host is checked against stdout/stderr only — while the userinfo credential inside
    it must not survive anywhere, files included.
    """
    d = tmp_path / preset
    out = _qs("--yes", "--preset", preset, "--dir", str(d), "--base-url", _SECRET_URL,
              env={**_CANARIES, "OPENAI_BASE_URL": _SECRET_URL})
    # `mock` now REFUSES --base-url rather than silently dropping it, so it exits 1 and
    # writes nothing. The sweep still runs on that path: a refusal message that echoes
    # the offending flag back is a prime place to leak the URL's embedded credential.
    assert out.returncode == (1 if preset == "mock" else 0), out.stderr

    printed = {"stdout": out.stdout, "stderr": out.stderr}
    written = {str(f.relative_to(d)): f.read_text(errors="replace")
               for f in d.rglob("*") if f.is_file() and f.suffix != ".pyc"}

    findings = []
    # Credential values (and prefixes) leak NOWHERE — printed or written.
    for name, value in _CANARIES.items():
        for probe in (value, value[:16], value[:12]):
            for where, text in {**printed, **written}.items():
                if probe in text:
                    findings.append(f"{name} ({len(probe)}-char prefix) leaked into {where}")
    for probe in ("s3cr3tCANARYtoken", "gw-user"):
        for where, text in {**printed, **written}.items():
            if probe in text:
                findings.append(f"URL userinfo {probe!r} survived into {where}")
    # The hostname itself: confidential in output, legitimate in the adapter config.
    for where, text in printed.items():
        if "internal.gw.example.corp" in text:
            findings.append(f"custom endpoint hostname printed to {where} "
                            "(must render as <custom>)")
    assert not findings, "\n".join(sorted(set(findings)))


def test_credential_presence_is_reported_but_never_the_value(tmp_path):
    """PRESENCE + the env var NAME, so the user knows what to export (#133/#190).

    The complement of the leak test: over-redacting `credential_env` (the key looks
    secret to `redact`) hid the one actionable fact with no security gain.
    """
    out = _qs("--yes", "--preset", "free", "--dir", str(tmp_path),
              env={"GEMINI_API_KEY": _CANARIES["GEMINI_API_KEY"]})
    prov = json.loads(out.stdout)["provider"]
    assert prov["credential_present"] is True
    assert prov["credential_env"] in ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    assert _CANARIES["GEMINI_API_KEY"] not in json.dumps(prov)


def test_url_userinfo_is_stripped_before_anything_is_written(tmp_path):
    """`https://user:token@host/` is a credential; it dies at resolution (#190)."""
    rec = quickstart.scaffold(tmp_path, "local", base_url=_SECRET_URL)
    adapter = (tmp_path / ".capevolve/project/adapters/adapter.py").read_text()
    assert "gw-user" not in adapter and "s3cr3tCANARYtoken" not in adapter
    # The host survives (the adapter must be able to call it); the credential does not.
    assert "internal.gw.example.corp" in adapter
    assert "@" not in rec["base_url"] and rec["base_url"] == "<custom>"


# ------------------------------------------------- scaffold shape: #197, #195, #217

def test_spec_omits_protected_paths(tmp_path):
    """#197 makes `protected_paths: []` a HARD error — the scaffold must omit the key.

    quickstart patches the shipped template rather than authoring a spec, so this also
    guards against a future template change reintroducing an empty list.
    """
    quickstart.scaffold(tmp_path, "mock")
    spec = (tmp_path / ".capevolve/project/capevolve.yaml").read_text()
    for line in spec.splitlines():
        assert not line.lstrip().startswith("protected_paths:") or line.lstrip().startswith("#"), line
    from cap_evolve.specfile import read_yaml
    assert "protected_paths" not in read_yaml(spec)


def test_val_split_clears_the_min_val_floor(tmp_path):
    """#195 hard-fails a tiny val split; the seed task count must clear the floor."""
    from cap_evolve import splits as _splits
    quickstart.scaffold(tmp_path, "mock")
    rows = [json.loads(ln) for ln in
            (tmp_path / ".capevolve/project/adapters/tasks.jsonl").read_text().splitlines() if ln.strip()]
    sp = _splits.make_splits([r["id"] for r in rows], seed=0, ratios=(0.5, 0.25, 0.25))
    floor = getattr(_splits, "MIN_VAL_TASKS", 2)
    assert len(sp.val) > floor, f"val={len(sp.val)} is at/below #195's floor {floor}"


def test_stdout_is_exactly_one_json_object_and_human_output_is_on_stderr(tmp_path):
    """#217: `cap-evolve quickstart | json.loads` must not raise "Extra data"."""
    out = _qs("--yes", "--dir", str(tmp_path))
    rec = json.loads(out.stdout)                # the whole point
    assert rec["ok"] is True and rec["preset"] == "mock"
    assert "quickstart: preset" in out.stderr, "human summary must go to stderr"
    assert "quickstart: preset" not in out.stdout


def test_an_existing_project_is_not_clobbered(tmp_path):
    """Refuse by default, overwrite only with --force — and report it as JSON (#133)."""
    quickstart.scaffold(tmp_path, "mock")
    (tmp_path / ".capevolve/project/adapters/adapter.py").write_text("# mine\n")
    out = _qs("--yes", "--dir", str(tmp_path))
    assert out.returncode == 1
    assert json.loads(out.stdout)["ok"] is False
    assert (tmp_path / ".capevolve/project/adapters/adapter.py").read_text() == "# mine\n"
    assert _qs("--yes", "--force", "--dir", str(tmp_path)).returncode == 0
    assert "# mine" not in (tmp_path / ".capevolve/project/adapters/adapter.py").read_text()


def test_an_existing_mock_script_is_not_silently_overwritten(tmp_path):
    """The edit script lives OUTSIDE `.capevolve/project`, so it needs its own guard.

    It used to be replaced without a word — a hand-edited script vanishing quietly, and
    the `--force` guard never saw it because it only covered the project dir.
    """
    (tmp_path / ".capevolve").mkdir()
    junk = tmp_path / ".capevolve" / "mock_script.json"
    junk.write_text('{"edits": [], "mine": true}\n')
    out = _qs("--yes", "--dir", str(tmp_path))
    assert out.returncode == 1
    assert json.loads(out.stdout)["ok"] is False
    assert "mine" in junk.read_text(), "the existing script was clobbered"
    assert _qs("--yes", "--force", "--dir", str(tmp_path)).returncode == 0
    assert "mine" not in junk.read_text(), "--force must overwrite it"


def test_flags_that_cannot_work_with_mock_are_refused_not_ignored(tmp_path):
    """A silently-dead flag is the same defect family as a silently-no-op optimizer.

    `mock` is an offline stand-in with no endpoint and no model, so `--model`/`--base-url`
    had nowhere to land and were dropped without a word.
    """
    for flag, value in (("--model", "gpt-4o"), ("--base-url", "http://x/v1")):
        out = _qs("--yes", flag, value, "--dir", str(tmp_path / flag.strip("-")))
        assert out.returncode == 1, f"{flag} was silently accepted"
        err = json.loads(out.stdout)
        assert err["ok"] is False and flag in err["error"]
        assert "--preset local" in err["error"], "must say what to do instead"
    # ...and they DO work on a preset that has an endpoint.
    rec = quickstart.scaffold(tmp_path / "ok", "local", model="m1",
                              base_url="http://127.0.0.1:9/v1")
    assert rec["model"] == "m1"


def test_val_tasks_matches_what_make_splits_actually_produces(tmp_path):
    """The reported `val_tasks` must not be a second, drifting copy of the split math."""
    from cap_evolve import splits as _splits
    rec = quickstart.scaffold(tmp_path, "mock")
    rows = [json.loads(ln) for ln in
            (tmp_path / ".capevolve/project/adapters/tasks.jsonl").read_text().splitlines() if ln.strip()]
    sp = _splits.make_splits([r["id"] for r in rows], seed=0, ratios=(0.5, 0.25, 0.25))
    assert rec["val_tasks"] == len(sp.val)


def test_preset_default_endpoints_are_shown_not_masked(tmp_path):
    """Masking the endpoint quickstart itself chose is user-hostile and protects nothing."""
    for preset in ("local", "free"):
        rec = quickstart.scaffold(tmp_path / preset, preset)
        assert rec["base_url"] == quickstart.PRESETS[preset]["base_url"], preset
    # Anything else still masks.
    assert quickstart.safe_url("https://gw.internal.example.corp/v1") == "<custom>"


def test_force_over_a_file_gives_an_actionable_message(tmp_path):
    """`--force` on a plain file used to surface a bare `[Errno 20] Not a directory`."""
    (tmp_path / ".capevolve").mkdir()
    (tmp_path / ".capevolve" / "project").write_text("not a dir\n")
    out = _qs("--yes", "--force", "--dir", str(tmp_path))
    assert out.returncode == 1
    err = json.loads(out.stdout)["error"]
    assert "Errno" not in err, err
    assert "is a file, not a directory" in err and "remove it first" in err


def test_mock_optimizer_warns_on_stderr_when_no_script_is_found():
    """Silence that looks like success: no script means every candidate is unchanged.

    The run still exits 0 with a green `check` and a sealed number equal to the baseline,
    so the JSON `note` alone is not enough — nothing surfaces it to the reader of the
    final report. This is the shape that made the documented quickstart path wrong.
    """
    script = REPO / "skills/optimizers/run-optimizer/scripts/_mock_apply.py"
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        env = {k: v for k, v in ENV.items() if k != "CAPEVOLVE_MOCK_SCRIPT"}
        out = subprocess.run([sys.executable, str(script), "--workdir", td],
                             capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr           # still a scored no-op, not a crash
    assert json.loads(out.stdout)["applied"] == []   # stdout is still exactly one object
    assert "NO EDIT SCRIPT FOUND" in out.stderr, f"silent no-op:\n{out.stderr!r}"
    assert "CAPEVOLVE_MOCK_SCRIPT" in out.stderr, "must name the fix"


def test_unknown_preset_is_refused(tmp_path):
    """argparse rejects it at the flag; the API raises rather than silently defaulting."""
    assert _qs("--yes", "--preset", "nope", "--dir", str(tmp_path)).returncode == 2
    with pytest.raises(ValueError, match="unknown preset"):
        quickstart.scaffold(tmp_path, "nope")


def test_quickstart_is_registered_in_the_generated_command_listing():
    """It must appear in #214's docstring-driven listing with zero edits there (#133).

    #214 generates the top-level listing from COMMANDS + handler docstrings so a new
    subcommand needs one registration line. This asserts quickstart met that contract
    (and, before #214 lands, that the interim usage line is also COMMANDS-derived).
    """
    from cap_evolve import cli
    assert cli.COMMANDS["quickstart"] is cli._cmd_quickstart
    usage = cli._usage() if hasattr(cli, "_usage") else ""
    if usage:
        assert "\n  quickstart" in usage, usage
        assert "Scaffold a ready-to-run project" in usage, "docstring not picked up"
    out = subprocess.run([sys.executable, "-m", "cap_evolve.cli", "--help"],
                         capture_output=True, text=True, cwd=str(REPO), env=ENV)
    assert "quickstart" in out.stdout + out.stderr
