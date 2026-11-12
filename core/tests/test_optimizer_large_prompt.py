"""The optimizer prompt stays inside the inline limit, and a bigger one still never fails exec.

With full LLM-judge feedback (every trial's rationale) one iteration's INSTRUCTIONS.md once
reached 460 KB on a 12-task x 3-trial run. ``claude -p {prompt_text}`` put all of it in ONE
argv string, Linux caps that at MAX_ARG_STRLEN = 128 KiB, and exec failed with E2BIG.

Pinned here: the rendered prompt is bounded (each failure-index entry at
``feedback_digest.entry_chars()``, at most ``DEFAULT_MAX_LISTED`` entries), so every row can
inline it; a row whose prompt is over the limit anyway gets a pointer to the prompt file
instead of an exec failure; and the template renderer no longer doubles the failure index
by also expanding the backtick-quoted ``{{FAILURES}}`` mention in its prose.
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


def test_no_optimizer_row_depends_on_stdin():
    """Every row gets its prompt the way it did before (inline or by path); none on stdin."""
    reg = read_yaml((REPO / "skills" / "optimizers" / "registry.yaml").read_text(encoding="utf-8"))
    assert not [n for n, row in reg.items() if isinstance(row, dict) and row.get("prompt_stdin")]
    assert "{prompt_text}" in reg["claude-code"]["command_template"]


def _per(n_tasks: int, n_trials: int, fb_len: int) -> list[dict]:
    per = []
    for i in range(n_tasks):
        trials = [(k, 0.5 + 0.1 * k, f"[task {i} trial {k}] " + "x" * fb_len + f" VERDICT-{i}-{k}")
                  for k in range(n_trials)]
        per.append({"task_id": f"t{i}", "reward": 0.6, "trial_rewards": [0.5, 0.6, 0.7],
                    "feedback": harness._join_trial_feedback(trials)})
    return per


def test_rendered_prompt_lists_each_task_once_and_fits_inline(tmp_path):
    """12 tasks x 3 trials x 6 KB of judge text: the size that once crashed exec (460 KB)."""
    per = _per(12, 3, 6000)
    cur = SplitResult(split="val", reward=0.6, stderr=0.02, per_task=per, n_tasks=12, n_scored=12)
    text = harness._focus_instructions(cur, None, "every failing task", capabilities=["skill-package"],
                                       seed_empty=False)
    assert "EMPTY SEED" not in text and "{{" not in text
    for i in range(12):   # the failure index is listed ONCE (the template's prose mentions the slot)
        assert text.count(f"- t{i} (reward") == 1, (i, text.count(f"- t{i} (reward"))
        assert f"VERDICT-{i}-0" in text, "the lowest-scoring trial's verdict must survive the cut"
    sys.path.insert(0, str(RUN_OPT.parent))
    import run as run_optimizer  # noqa: E402
    assert len(text.encode("utf-8")) <= run_optimizer.MAX_INLINE_PROMPT_BYTES, len(text.encode("utf-8"))


def test_fill_slots_leaves_quoted_mentions_and_filled_values_alone():
    out = harness._fill_slots("see the `{{FAILURES}}` block\n{{FAILURES}}\n{{OTHER}}",
                              {"{{FAILURES}}": "judge said {{FAILURES}}"})
    assert out == "see the `FAILURES` block\njudge said {{FAILURES}}\n{{OTHER}}"

