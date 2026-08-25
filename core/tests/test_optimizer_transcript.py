"""``run-optimizer --transcript`` — the run's own record of what the agent did.

Run 32814848187 spent four hours doing nothing measurable (its 900 metric calls account for
every evaluation in ``events.jsonl``, and none fall in the gap), and the only trace kept of
the agent's own actions was an 800-char ``stdout_tail``. So "what was it blocked on" could be
narrowed to "something that ran into the 4-hour Bash ceiling" and no further — the next
identical stall would have been equally undiagnosable.

``--output-format json`` cannot fix that: it returns ONE result object with the final text and
the totals, never the turns. The registry therefore carries a separate ``transcript_flag``
(``--output-format stream-json --verbose``, verified against Claude Code 2.1.241) used only
when a transcript is asked for, whose last line is the same result object — so cost and stop
parsing are unchanged and the deterministic per-iteration path is untouched.

What is pinned here: the transcript lands, the streaming flag REPLACES ``json_flag`` rather
than joining it (two ``--output-format`` flags is an error), cost/stop still parse out of a
streamed run, and secret values never reach the file.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN_OPT = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"


def _fake_registry(tmp: Path, *, transcript_flag: str | None) -> Path:
    """A registry whose one row is a python script we control, plus a fake CLI."""
    cli = tmp / "fakecli.py"
    cli.write_text(
        "import json, sys\n"
        "streaming = '--output-format' in sys.argv and 'stream-json' in sys.argv\n"
        "assert sys.argv.count('--output-format') <= 1, f'duplicate flag: {sys.argv}'\n"
        "if streaming:\n"
        "    print(json.dumps({'type': 'system', 'subtype': 'init'}))\n"
        "    print(json.dumps({'type': 'assistant', 'message': 'editing'}))\n"
        "    print(json.dumps({'type': 'tool_use', 'name': 'Bash',\n"
        "                      'input': {'command': 'echo $ANTHROPIC_AUTH_TOKEN'}}))\n"
        "    print(json.dumps({'type': 'tool_result', 'content': 'sk-secret-value-1234567890'}))\n"
        "print(json.dumps({'type': 'result', 'subtype': 'success', 'num_turns': 42,\n"
        "                  'stop_reason': 'end_turn', 'terminal_reason': 'end_turn',\n"
        "                  'is_error': False, 'total_cost_usd': 1.25,\n"
        "                  'usage': {'input_tokens': 100, 'output_tokens': 20}}))\n",
        encoding="utf-8")
    row = [
        "faker:",
        f'  command_template: "{sys.executable} {cli} --prompt {{prompt}}"',
        '  env_keys: "ANTHROPIC_AUTH_TOKEN"',
        '  install_url: ""',
        '  auth_notes: ""',
        '  json_flag: "--output-format json"',
        '  budget_flag: ""',
        '  usd_budget_flag: ""',
        '  offline: "false"',
    ]
    if transcript_flag:
        row.append(f'  transcript_flag: "{transcript_flag}"')
    reg = tmp / "registry.yaml"
    reg.write_text("\n".join(row) + "\n", encoding="utf-8")
    return reg


def _run(tmp: Path, *, transcript: Path | None, transcript_flag="--output-format stream-json "
                                                                "--verbose", secret="") -> dict:
    reg = _fake_registry(tmp, transcript_flag=transcript_flag)
    workdir = tmp / "wd"; workdir.mkdir(exist_ok=True)
    prompt = tmp / "INSTRUCTIONS.md"; prompt.write_text("edit something", encoding="utf-8")
    argv = [sys.executable, str(RUN_OPT), "--name", "faker", "--json",
            "--workdir", str(workdir), "--prompt", str(prompt)]
    if transcript:
        argv += ["--transcript", str(transcript)]
    env = dict(os.environ, CAPEVOLVE_OPTIMIZER_REGISTRY=str(reg),
               CAPEVOLVE_CORE=str(REPO / "core"))
    if secret:
        env["ANTHROPIC_AUTH_TOKEN"] = secret
    p = subprocess.run(argv, capture_output=True, text=True, env=env)
    assert p.returncode == 0, f"rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    return json.loads(p.stdout)


def test_the_full_transcript_is_persisted_not_just_an_800_char_tail(tmp_path):
    dest = tmp_path / "host" / "transcript.jsonl"
    out = _run(tmp_path, transcript=dest)

    assert dest.is_file(), f"--transcript wrote nothing to {dest}: {out}"
    assert out["transcript"]["path"] == str(dest), out
    lines = [json.loads(x) for x in dest.read_text(encoding="utf-8").splitlines() if x.strip()]
    kinds = [x.get("type") for x in lines]
    assert "tool_use" in kinds, (
        "the transcript holds no tool calls, so it still cannot show what a stalled agent was "
        f"doing: {kinds}")
    assert kinds[-1] == "result", f"the result object must remain the last line: {kinds}"
    # Parent dirs are created: the host points this at $R/host/, which need not exist yet.
    assert out["transcript"]["lines"] >= 5, out["transcript"]


def test_the_streaming_flag_replaces_json_flag_rather_than_joining_it(tmp_path):
    """Two --output-format flags is an error, so this must substitute, not append.

    The fake CLI asserts on it, so an append would surface as a non-zero exit here.
    """
    out = _run(tmp_path, transcript=tmp_path / "t.jsonl")
    assert out["returncode"] == 0, out
    # And the streamed shape really was requested (the fake only emits turns when it is).
    body = (tmp_path / "t.jsonl").read_text(encoding="utf-8")
    assert '"type": "assistant"' in body, f"the CLI was not asked for the stream: {body[:300]}"


def test_cost_and_stop_still_parse_from_a_STREAMED_run(tmp_path):
    """The whole point of reusing the result object: nothing downstream changes.

    host.py books spend from `cost.total_cost_usd` and diagnoses from `stop`; if either went
    missing under streaming, the transcript would have been bought with the run's accounting.
    """
    out = _run(tmp_path, transcript=tmp_path / "t.jsonl")

    assert out["cost"]["total_cost_usd"] == 1.25, out["cost"]
    assert out["cost"]["tokens"] == 120, out["cost"]
    stop = out["stop"]
    assert stop["subtype"] == "success" and stop["num_turns"] == 42, stop
    assert stop["stop_reason"] == "end_turn", stop
    assert stop["terminal_reason"] == "end_turn", (
        f"terminal_reason names the terminating condition outright and is dropped: {stop}")


def test_a_row_with_no_transcript_flag_still_records_what_it_printed(tmp_path):
    """Graceful for every other CLI: --transcript must not require a streaming mode."""
    dest = tmp_path / "t.jsonl"
    out = _run(tmp_path, transcript=dest, transcript_flag=None)

    assert dest.is_file(), f"a row without transcript_flag lost its transcript: {out}"
    body = dest.read_text(encoding="utf-8")
    assert '"type": "result"' in body, body
    assert '"type": "assistant"' not in body, (
        "no transcript_flag means no stream was requested; inventing one would pass a flag "
        f"the CLI may not support: {body[:200]}")


def test_secret_values_never_reach_the_transcript(tmp_path):
    """A transcript records tool results verbatim, and the run dir is a CI artifact.

    One `env` the agent happened to run would otherwise publish the gateway token. The fake CLI
    echoes a secret-shaped value in a tool result precisely to prove the scrub runs.
    """
    dest = tmp_path / "t.jsonl"
    out = _run(tmp_path, transcript=dest, secret="sk-secret-value-1234567890")

    body = dest.read_text(encoding="utf-8")
    assert "sk-secret-value-1234567890" not in body, (
        f"the auth token was written to the transcript verbatim: {body[:400]}")
    assert "ANTHROPIC_AUTH_TOKEN" in body, (
        f"the redaction should leave a marker so the reader knows what was removed: {body[:400]}")
    assert out["transcript"].get("error") is None, out


def test_the_claude_code_row_declares_a_transcript_flag():
    """The row the host actually uses, and the streamed shape verified on CLI 2.1.241."""
    sys.path.insert(0, str(RUN_OPT.parent))
    import run as run_optimizer  # noqa: PLC0415

    row = run_optimizer.load_registry()["claude-code"]
    flag = str(row.get("transcript_flag", ""))
    assert "stream-json" in flag, f"claude-code cannot produce a real transcript: {row}"
    assert "--verbose" in flag, (
        f"headless stream-json requires --verbose or the CLI refuses the combination: {flag}")


# --- the transcript has to survive INTO the artifact -------------------------

RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"


def _host_publish_block() -> str:
    """The host-record copy block, lifted verbatim out of run_suite.sh."""
    src = RUN_SUITE.read_text(encoding="utf-8")
    start = src.index("# The agent's own record, into the dir that actually gets uploaded")
    return src[start:src.index('cat "$OUT/report.md"', start)]


def test_the_transcript_reaches_the_uploaded_artifact_not_just_the_run_dir(tmp_path):
    """Writing it to the run dir is not enough, and the gap is silent.

    The artifact path is `$OUT/**`; the run dir lives under `suite_<tier>_<bench>_proj/`. Run-dir
    files reach the artifact only through the UI export, which caps EVERY file at 256 KiB and
    keeps `raw[:_MAX_FILE_BYTES]` — the FIRST chunk. Measured: one turn of stream-json with no
    tool results is already 17 KB, so a multi-round transcript is megabytes and the cap would
    keep only its opening — while the part that shows where a run stalled is the END. That is
    the precise evidence the transcript was added to capture, so it must bypass the export.

    Executed as real bash, like the algorithm-selection block: what breaks here is shell
    behaviour, not text.
    """
    run_dir = tmp_path / "run"; (run_dir / "host").mkdir(parents=True)
    out = tmp_path / "out"; out.mkdir()
    # Bigger than the export's 256 KiB cap, so a truncating path is visibly wrong.
    big = "\n".join(json.dumps({"type": "assistant", "i": i, "pad": "x" * 400})
                    for i in range(2000))
    (run_dir / "host" / "transcript.jsonl").write_text(big, encoding="utf-8")
    (run_dir / "host" / "driver_prompt.md").write_text("# briefing", encoding="utf-8")

    script = f'RUN_DIR={run_dir}\nOUT={out}\n' + _host_publish_block()
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert p.returncode == 0, f"{p.stdout}\n{p.stderr}"

    gz = out / "host" / "transcript.jsonl.gz"
    assert gz.is_file(), f"the transcript never reached $OUT: {list((out).rglob('*'))}"
    assert (out / "host" / "driver_prompt.md").is_file(), "the briefing stopped being published"

    import gzip  # noqa: PLC0415
    body = gzip.decompress(gz.read_bytes()).decode("utf-8")
    assert body == big, "the published transcript is not byte-identical to the run's"
    assert len(body) > 256 * 1024, "the fixture no longer exceeds the cap it exists to defeat"
    # And the whole point of gzipping: full fidelity for a fraction of the artifact.
    assert gz.stat().st_size < len(big) / 4, (
        f"gzip bought nothing: {gz.stat().st_size} vs {len(big)} raw")


def test_publishing_the_host_record_is_skipped_cleanly_when_there_is_none(tmp_path):
    """Every deterministic-path run has no host/ dir; the block must not fail the suite."""
    run_dir = tmp_path / "run"; run_dir.mkdir()
    out = tmp_path / "out"; out.mkdir()
    script = f'RUN_DIR={run_dir}\nOUT={out}\n' + _host_publish_block()
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert p.returncode == 0, f"a run with no host/ dir broke the publish step: {p.stderr}"
    assert not (out / "host").exists(), f"an empty host/ dir was published: {out}"
