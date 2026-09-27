"""`SB_EMPTY_SEED` must remove EVERY surface the agent reads, not just `prompt.md`.

WHAT WENT WRONG

#281 added `SB_EMPTY_SEED` as a "no-skill-control knob for published comparisons", when
`prompt.md` was the whole capability. **#282 — the very next PR — made `task_template.md`
optimizable** and nobody revisited the flag. Its own rationale was that "~60% of the text the
agent reads" had been frozen in code; that is now exactly the fraction the no-skill flag misses.

So run 36261022325, dispatched as a no-skill control, actually measured *no system prompt but
keep the full tuned task template*:

    seed_capability/prompt.md          965 bytes  -> blanked
    seed_capability/task_template.md  2453 bytes  -> SURVIVED   (72% of the capability text)

and the task template is the MORE load-bearing surface, not the lesser one — in the smoke run
the same knowledge scored 0.600 on `task_template.md` versus 0.511 as `prompt.md` prose, and the
`full_verified` champion `r3_decide` was a `task_template.md` edit. The resulting 0.668 was
reported as a no-skill baseline and is not one.

WHY task_template.md IS DELETED RATHER THAN BLANKED

`_read_task_template` treats a *shipped* file as an override of the built-in `_TASK_TEMPLATE`.
Blanking it would hand the agent an EMPTY user message — no instruction, no paths, no
answer_position — and score every task 0. Removing the file restores the built-in, which is the
correct no-skill condition and is close to the paper's own Appendix E.1 prompt (the same fields
with an empty `{skill_section}`).

`prompt.md` keeps being blanked rather than deleted, deliberately: an empty file means NO system
message, while a missing file falls back to the adapter's built-in default prompt — which would
measure that default while claiming no skill.

THE GUARD THAT MATTERS

The last test enumerates the capability files the adapter actually reads and fails if the flag
does not handle all of them. That is the test #282 would have tripped.
"""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"
ADAPTER = REPO / "templates" / "adapters" / "spreadsheetbench" / "adapter.py"
SEED = REPO / "templates" / "adapters" / "spreadsheetbench" / "seed_capability"


def _empty_seed_block() -> str:
    """The SB_EMPTY_SEED branch, lifted verbatim."""
    src = RUN_SUITE.read_text(encoding="utf-8")
    start = src.index('if [ "${SB_EMPTY_SEED:-0}" = "1" ]; then')
    return src[start:src.index("\n    fi", start) + len("\n    fi")]


def _run_block(tmp_path: Path) -> Path:
    """Execute the real block against a scaffolded copy of the seed capability."""
    proj = tmp_path / "proj" / "seed_capability"
    proj.mkdir(parents=True)
    for f in SEED.iterdir():
        if f.is_file():
            (proj / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    script = f'set -euo pipefail\nPROJ={tmp_path / "proj"}\nSB_EMPTY_SEED=1\n' + _empty_seed_block()
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return proj


# --- the surfaces the agent reads ---------------------------------------------------------


def test_the_system_prompt_is_blanked_not_removed(tmp_path):
    """Empty means NO system message; a MISSING file would fall back to the adapter's own
    built-in default prompt and measure that while claiming no skill."""
    proj = _run_block(tmp_path)
    assert (proj / "prompt.md").is_file(), "prompt.md must still exist, just empty"
    assert (proj / "prompt.md").read_text(encoding="utf-8").strip() == ""


def test_the_task_template_is_removed_so_the_builtin_applies(tmp_path):
    """The bug. A shipped task_template.md overrides the built-in, so leaving it in place keeps
    2453 bytes of tuned instruction surface in a run labelled 'no skill'."""
    proj = _run_block(tmp_path)
    assert not (proj / "task_template.md").exists(), (
        "task_template.md survived SB_EMPTY_SEED — the control still carries the tuned "
        "per-task instruction surface, which is 72% of the capability's text"
    )


def test_the_task_template_is_not_merely_blanked(tmp_path):
    """Blanking would hand the agent an EMPTY user message — no instruction, no paths, no
    answer_position — and score every task 0. That is a broken run, not a control."""
    proj = _run_block(tmp_path)
    p = proj / "task_template.md"
    assert not (p.exists() and p.read_text(encoding="utf-8").strip() == ""), (
        "task_template.md was blanked rather than removed; an empty override yields an empty "
        "user message, so every task would score 0"
    )


def test_a_blank_task_template_really_would_break_the_run():
    """Pins the premise of the test above, from the adapter rather than by assertion."""
    src = ADAPTER.read_text(encoding="utf-8")
    body = src[src.index("def _read_task_template"):src.index("def _read_system_prompt")]
    assert "_TASK_TEMPLATE" in body, "no built-in fallback found"
    # The fallback is keyed on the file's ABSENCE, which is why removal is the correct operation.
    assert re.search(r"(exists|is_file)\(\)", body), (
        "the built-in fallback is not keyed on the file's existence; re-check whether removing "
        "task_template.md still restores it"
    )


def test_the_banner_names_what_it_removed(tmp_path):
    """A run labelled 'no skill' must say in its log which surfaces were cleared, or the next
    reader cannot tell what the number means."""
    proj = _run_block(tmp_path)
    block = _empty_seed_block()
    assert "prompt.md" in block and "task_template" in block, (
        "the banner/block does not mention both surfaces"
    )


# --- the guard: this is the test #282 would have tripped -----------------------------------


def test_every_agent_read_capability_file_is_handled_by_the_flag():
    """Enumerate what the adapter reads out of the capability, and require the flag to cover it.

    #281 wrote a correct flag for a one-file capability; #282 added a second file and the flag
    silently became partial. If a third agent-read surface is ever added, this fails rather than
    quietly producing another mislabelled no-skill number.
    """
    src = ADAPTER.read_text(encoding="utf-8")
    # Capability files the adapter opens relative to the candidate dir.
    read = set(re.findall(r'candidate_dir\s*/\s*"([a-z_]+\.md)"', src))
    read |= set(re.findall(r'ctx\s*/\s*"([a-z_]+\.md)"', src))
    # Fall back to the two known surfaces if the source shape changes, so the test still means
    # something rather than passing on an empty set.
    known = {"prompt.md", "task_template.md"}
    surfaces = read or known
    assert known <= surfaces, f"expected the known surfaces among {surfaces}"

    block = _empty_seed_block()
    unhandled = [f for f in surfaces if f.split(".")[0] not in block]
    assert not unhandled, (
        f"SB_EMPTY_SEED does not handle these agent-read capability files: {sorted(unhandled)}. "
        "A no-skill control that leaves any of them in place is not a no-skill control."
    )


def test_the_committed_seed_still_ships_both_surfaces():
    """Guards the premise: if the seed stops shipping task_template.md, the bug's blast radius
    changes and this whole file should be revisited."""
    assert (SEED / "prompt.md").is_file()
    assert (SEED / "task_template.md").is_file()


def test_run_suite_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(RUN_SUITE)]).returncode == 0
