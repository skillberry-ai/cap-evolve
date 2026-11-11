"""A prompt over the kernel's 128 KiB per-argument limit still reaches the optimizer, whole.

With full LLM-judge feedback (every trial's rationale, never shortened) one iteration's
INSTRUCTIONS.md reached 460 KB on a 12-task x 3-trial run. ``claude -p {prompt_text}``
put all of it in ONE argv string, Linux caps that at MAX_ARG_STRLEN = 128 KiB, and exec
failed with E2BIG before Claude Code started: iteration 1 proposed nothing and the loop
went on to score an unedited candidate.

Pinned here: a ``prompt_stdin`` row (claude-code) gets the whole prompt byte-for-byte on
stdin; a row that still inlines ``{prompt_text}`` gets a pointer to the prompt file
instead of an exec failure; and the template renderer no longer doubles the failure
index by also expanding the backtick-quoted ``{{FAILURES}}`` mention in its prose.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
RUN_OPT = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"

from cap_evolve import harness  # noqa: E402
from cap_evolve.loop import SplitResult  # noqa: E402
from cap_evolve.specfile import read_yaml  # noqa: E402

ARG_LIMIT = 128 * 1024  # Linux MAX_ARG_STRLEN
TAIL = "END-OF-PROMPT-MARKER"


def _big_prompt(tmp: Path, size: int = 3 * ARG_LIMIT) -> Path:
    body = ("judge rationale: the WHY section names no customer. " * (size // 50))[:size] + TAIL
    p = tmp / "INSTRUCTIONS.md"
    p.write_text(body, encoding="utf-8")
    assert len(body.encode("utf-8")) > ARG_LIMIT
    return p


def _run(tmp: Path, row_lines: list[str]) -> dict:
    """Run run-optimizer against a one-row registry whose CLI records what it received."""
    seen = tmp / "seen.json"
    cli = tmp / "fakecli.py"
    cli.write_text(
        "import json, sys\n"
        "stdin = '' if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()\n"
        f"json.dump({{'argv': sys.argv[1:], 'stdin': stdin}}, open({str(seen)!r}, 'w'))\n",
        encoding="utf-8")
    reg = tmp / "registry.yaml"
    reg.write_text("\n".join(["faker:", *(ln.replace("{cli}", f"{sys.executable} {cli}")
                                          for ln in row_lines),
                              '  offline: "false"']) + "\n", encoding="utf-8")
    prompt = _big_prompt(tmp)
    wd = tmp / "wd"
    wd.mkdir()
    env = dict(os.environ, CAPEVOLVE_OPTIMIZER_REGISTRY=str(reg), CAPEVOLVE_CORE=str(REPO / "core"))
    p = subprocess.run([sys.executable, str(RUN_OPT), "--name", "faker", "--workdir", str(wd),
                        "--prompt", str(prompt)], capture_output=True, text=True, env=env,
                       stdin=subprocess.DEVNULL)
    out = json.loads(p.stdout)
    assert out["returncode"] == 0, f"{out}\n{p.stderr}"
    return {"seen": json.loads(seen.read_text(encoding="utf-8")), "prompt": prompt,
            "stderr": p.stderr}


def test_a_prompt_stdin_row_gets_the_whole_oversized_prompt_on_stdin(tmp_path):
    r = _run(tmp_path, ['  command_template: "{cli} -p --model x"', '  prompt_stdin: "true"'])
    sent = r["prompt"].read_text(encoding="utf-8")
    assert r["seen"]["stdin"] == sent, "the prompt on stdin is not the prompt file, byte for byte"
    assert r["seen"]["stdin"].endswith(TAIL)
    assert all(len(a.encode("utf-8")) < ARG_LIMIT for a in r["seen"]["argv"]), r["seen"]["argv"]


def test_an_inlining_row_gets_a_pointer_instead_of_an_exec_failure(tmp_path):
    r = _run(tmp_path, ['  command_template: "{cli} -p {prompt_text}"'])
    argv = r["seen"]["argv"]
    assert all(len(a.encode("utf-8")) < ARG_LIMIT for a in argv), "an over-limit argv string"
    assert any(str(r["prompt"]) in a for a in argv), f"no pointer to the prompt file: {argv}"
    assert "argv limit" in r["stderr"], "the substitution must be announced, not silent"


def test_an_env_var_template_that_inlines_the_prompt_gets_the_pointer_too(tmp_path, monkeypatch):
    """The generic row's command lives in CAPEVOLVE_OPTIMIZER_CMD; the guard must see through it."""
    cli = tmp_path / "fakecli.py"
    monkeypatch.setenv("CAPEVOLVE_OPTIMIZER_CMD", f"{sys.executable} {cli} -p {{prompt_text}}")
    r = _run(tmp_path, ['  command_template: "${CAPEVOLVE_OPTIMIZER_CMD}"'])
    argv = r["seen"]["argv"]
    assert all(len(a.encode("utf-8")) < ARG_LIMIT for a in argv), "an over-limit argv string"
    assert any(str(r["prompt"]) in a for a in argv), f"no pointer to the prompt file: {argv}"


def test_a_small_inlined_prompt_is_unchanged():
    sys.path.insert(0, str(RUN_OPT.parent))
    import run as run_optimizer  # noqa: E402

    assert run_optimizer.inline_prompt_text("short prompt", "/p") == ("short prompt", False)


def test_claude_code_reads_its_prompt_from_stdin_not_argv():
    row = read_yaml((REPO / "skills" / "optimizers" / "registry.yaml").read_text(encoding="utf-8"))[
        "claude-code"]
    assert str(row.get("prompt_stdin")).lower() == "true"
    assert "{prompt_text}" not in row["command_template"]


def _per(n_tasks: int, n_trials: int, fb_len: int) -> list[dict]:
    per = []
    for i in range(n_tasks):
        trials = [(k, 0.5 + 0.1 * k, f"[task {i} trial {k}] " + "x" * fb_len + f" VERDICT-{i}-{k}")
                  for k in range(n_trials)]
        per.append({"task_id": f"t{i}", "reward": 0.6, "trial_rewards": [0.5, 0.6, 0.7],
                    "feedback": harness._join_trial_feedback(trials)})
    return per


def test_rendered_prompt_carries_every_trial_feedback_exactly_once(tmp_path):
    """The default template once listed the failure index twice (its prose mentions the slot)."""
    per = _per(12, 3, 6000)
    cur = SplitResult(split="val", reward=0.6, stderr=0.02, per_task=per, n_tasks=12, n_scored=12)
    text = harness._focus_instructions(cur, None, "every failing task", capabilities=["skill-package"],
                                       seed_empty=False)
    assert "EMPTY SEED" not in text
    for i in range(12):
        for k in range(3):
            assert text.count(f"VERDICT-{i}-{k}") == 1, (i, k, text.count(f"VERDICT-{i}-{k}"))
    assert "{{" not in text
    assert len(text.encode("utf-8")) > ARG_LIMIT  # i.e. this prompt NEEDS the stdin path


def test_fill_slots_leaves_quoted_mentions_and_filled_values_alone():
    out = harness._fill_slots("see the `{{FAILURES}}` block\n{{FAILURES}}\n{{OTHER}}",
                              {"{{FAILURES}}": "judge said {{FAILURES}}"})
    assert out == "see the `FAILURES` block\njudge said {{FAILURES}}\n{{OTHER}}"

