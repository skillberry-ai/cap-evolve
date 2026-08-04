"""The agent must be allowed to check its own answer before the episode ends.

MEASURED on run 30740145597: the agent used **2.2 of 30 available turns** (seed: 1.9). The
cause was one line in the CodeAct loop:

    exec_results.append(exec_result)
    messages.append({"role": "user", "content": exec_result})
    if case1_path.exists():
        break          # ← episode over the instant ANY output file appeared

So every behaviour that has to happen *after* writing was unreachable. That is not a
hypothetical: `cand_0003` of that run had itself rewritten the job description to say

    "3. Verification code: re-open output_path, print the values in answer_position …
     You are done only once that verification looks correct."

and turn usage moved 1.9 → 2.2. The optimizer wrote the right skill and the harness refused to
execute it. It also matches the dominant failure mode — 40% of tasks produced a file whose
values were wrong, and 0% failed to produce a file at all.

Comparable published work reports its skill learning exactly these post-write behaviours
("reopening the saved file to verify boundary rows", "inspect the real workbook rather than
trusting previews"), which our loop made impossible to perform.

Two traps that a literal one-line deletion walks straight into, both covered below:

1. **Cases 2 and 3 are scored by REPLAYING the agent's code.** Replay must use the code that
   WROTE the answer, not whatever ran last — a trailing verification snippet writes nothing, so
   replaying it scores 0 on two of three test cases and turns the fix into a big regression.
2. **Cost.** Each round is an LLM call. Unbounded, MAX_TURNS=30 is ~15x the token cost of the
   old behaviour, so the post-answer phase is bounded by VERIFY_TURNS.
"""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"


def _adapter():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_verify", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SRC = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")


# --- the break is gone -------------------------------------------------------------------


def test_the_loop_no_longer_ends_on_first_file_write():
    loop = SRC.split("for _round in range(MAX_TURNS):", 1)[1].split("if not case1_path.exists()", 1)[0]
    assert "if case1_path.exists():\n                    break" not in loop, \
        "the episode must not end merely because an output file exists"


def test_the_post_answer_phase_is_bounded_so_cost_cannot_explode():
    """Unbounded, 30 turns is ~15x the old token cost per rollout."""
    mod = _adapter()
    assert mod.VERIFY_TURNS == 3, "default should allow inspect+fix without paying for 30 rounds"
    loop = SRC.split("for _round in range(MAX_TURNS):", 1)[1].split("if not case1_path.exists()", 1)[0]
    assert "verify_left -= 1" in loop and "if verify_left <= 0" in loop


def test_a_no_code_reply_after_an_answer_exists_ends_the_episode():
    """That is the agent saying it is finished; nagging it costs a round for nothing."""
    loop = SRC.split("for _round in range(MAX_TURNS):", 1)[1].split("if not case1_path.exists()", 1)[0]
    seg = loop.split("if code is None or not code.strip():", 1)[1].split("last_code = code", 1)[0]
    assert "if solution_code:" in seg and "break" in seg


def test_an_agent_that_never_writes_code_is_cut_off():
    loop = SRC.split("for _round in range(MAX_TURNS):", 1)[1].split("if not case1_path.exists()", 1)[0]
    assert "no_code_replies >= 3" in loop


# --- trap 1: the replay must use the code that WROTE the answer ---------------------------


def test_replay_uses_the_writing_code_not_the_last_code():
    replay = SRC.split("for idx in (2, 3):", 1)[1].split("return Rollout", 1)[0]
    assert "solution_code.replace(input_file.name" in replay, \
        "replaying a verification snippet would score 0 on cases 2 and 3"
    assert "last_code.replace(input_file.name" not in replay


def test_the_recorded_solution_is_the_writing_code():
    assert "output=solution_code or last_code" in SRC


def test_artifact_stamp_detects_a_rewrite_but_not_a_read(tmp_path):
    """The stamp is how the loop tells 'wrote the answer' from 'looked at the answer'."""
    mod = _adapter()
    f = tmp_path / "1_x_output.xlsx"
    assert mod._artifact_stamp(f) is None            # absent
    f.write_bytes(b"PK\x03\x04one")
    s1 = mod._artifact_stamp(f)
    assert s1 is not None
    assert mod._artifact_stamp(f) == s1              # merely reading changes nothing
    f.write_bytes(b"PK\x03\x04two-different-size")
    assert mod._artifact_stamp(f) != s1              # a rewrite does


# --- the loop's decision logic, simulated ------------------------------------------------


def _simulate(mod, rounds, tmp_path):
    """Replay the loop's post-exec decisions over a scripted sequence of rounds.

    Each round is (code, writes_answer). Mirrors the adapter's ordering exactly; kept here
    because the real loop needs an LLM, a container and a dataset to run.
    """
    case1 = tmp_path / "1_x_output.xlsx"
    solution_code, artifact, verify_left, executed = "", None, mod.VERIFY_TURNS, 0
    for code, writes in rounds:
        executed += 1
        if writes:
            case1.write_bytes(b"PK" + str(executed).encode() * 4)
        stamp = mod._artifact_stamp(case1)
        if stamp is not None and stamp != artifact:
            artifact, solution_code = stamp, code
        elif solution_code:
            verify_left -= 1
            if verify_left <= 0:
                break
    return solution_code, executed


def test_verification_rounds_do_not_steal_the_solution(tmp_path):
    """The exact regression: write, then verify. Replay must still use the writing code."""
    mod = _adapter()
    sol, n = _simulate(mod, [("SOLVE", True), ("PRINT_CHECK", False)], tmp_path)
    assert sol == "SOLVE" and n == 2


def test_a_correction_supersedes_the_earlier_answer(tmp_path):
    """Inspect, write, verify, fix — the FIX is what cases 2 and 3 must replay."""
    mod = _adapter()
    sol, _ = _simulate(mod, [("LOOK", False), ("SOLVE_V1", True),
                             ("PRINT_CHECK", False), ("SOLVE_V2", True)], tmp_path)
    assert sol == "SOLVE_V2"


def test_endless_verification_is_cut_off_at_the_budget(tmp_path):
    mod = _adapter()
    rounds = [("SOLVE", True)] + [("CHECK%d" % i, False) for i in range(10)]
    sol, n = _simulate(mod, rounds, tmp_path)
    assert sol == "SOLVE"
    assert n == 1 + mod.VERIFY_TURNS, f"should stop after {mod.VERIFY_TURNS} idle rounds, ran {n}"


def test_rounds_before_any_answer_are_never_charged_to_the_verify_budget(tmp_path):
    """Inspection BEFORE writing is the behaviour we want most; it must be free."""
    mod = _adapter()
    rounds = [("LOOK%d" % i, False) for i in range(8)] + [("SOLVE", True)]
    sol, n = _simulate(mod, rounds, tmp_path)
    assert sol == "SOLVE" and n == 9
