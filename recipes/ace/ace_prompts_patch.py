"""exp895 ACE arm: the ONLY changes made to ACE's prompt text (issue #895 §7.8), applied in memory.

Upstream files under competitors/ace are never edited. `apply()` rebinds the prompt constants in the
upstream modules (ace.prompts.* and the ace.core.* modules that imported them by name), and
`write_diff()` writes the resulting text diff to arms/ace/prompt_patch.diff.

Two edits:
  1. Content-filter fix (§7.8): "your chain of thought / reasoning / thinking process, detailed analysis and
     calculations" -> "detailed analysis and calculations", in ALL ACE prompts (case of the leading word kept).
  2. Surface note (§4.1, §7.8 deviation): the common SURFACE_CONTRACT.md, verbatim, plus a short note on this
     benchmark and on the [skill]/[script] bullets, inserted into the Reflector (no-GT) prompt and both
     Curator prompts the batched flow uses (no-GT proposal, ComBEE reducer). Nothing else in a prompt changes.
"""
from __future__ import annotations

import difflib
import importlib.util
from pathlib import Path

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
ACE_DIR = EXP / "competitors/ace"
CONTRACT = EXP / "arms/common/SURFACE_CONTRACT.md"

FILTER_FIX = [
    ("your chain of thought / reasoning / thinking process, detailed analysis and calculations",
     "detailed analysis and calculations"),
    ("Your chain of thought / reasoning / thinking process, detailed analysis and calculations",
     "Detailed analysis and calculations"),
]

# (module file, constant names) of every ACE prompt
PROMPTS = {
    "generator": ["GENERATOR_PROMPT"],
    "reflector": ["REFLECTOR_PROMPT", "REFLECTOR_PROMPT_NO_GT"],
    "curator": ["CURATOR_PROMPT", "CURATOR_PROMPT_NO_GT", "CURATOR_OPERATIONS_AGGREGATION_PROMPT"],
}

REFLECTOR_NOTE = """**This experiment (SpreadsheetBench):**
- The "model" is a spreadsheet agent that solves each task by writing Python in a Jupyter kernel. The reasoning trace below is its transcript from the lowest-scoring of 3 trials of the same task (its system prompt is omitted: that is the playbook being trained), followed by the last code it ran.
- The predicted answer is a one-line score summary (the mean hard score over the 3 trials). The environment feedback is the scorer's gold-safe message: it says which cells or ranges mismatched and how, never the expected values.
- A Curator turns your insights into playbook bullets (and, where enabled, SKILL.md notes and deterministic helper scripts). The surface they land on:

"""

CURATOR_NOTE_TEXT_ONLY = """**This experiment (SpreadsheetBench): where your bullets go**
- Every bullet is appended to the agent's system prompt (`prompt.md`) under "## Playbook (ACE)". In this variant the bullets are text only: no SKILL.md and no helper scripts are written from them.
- The surface contract the agent lives under:

"""

CURATOR_NOTE = """**This experiment (SpreadsheetBench): where your bullets go**
- An ordinary bullet is appended to the agent's system prompt (`prompt.md`) under "## Playbook (ACE)".
- A bullet whose content starts with `[skill]` is written into `skills/ace-playbook/SKILL.md`, which is also appended to the agent's system prompt. Use it for when and how to call a helper script.
- A bullet whose content starts with `[script]` becomes a helper script. Its content must be: a first line `[script] <file_name>.py: <one line saying when to call it and what it returns>`, then a newline, then the complete Python source of the module (as a normal JSON string). The file name uses lowercase letters, digits and underscores. It is saved as `skills/ace-playbook/scripts/<file_name>.py` and is importable in the agent's kernel as `skills.ace_playbook.<file_name>`.
- Operations are ADD-only. To fix or replace a script, ADD a new `[script]` bullet with the same file name: the newest one wins.
- The surface contract the agent and its helpers live under:

"""

REDUCER_EXTRA = ("- When you keep a `[script]` proposal, copy its Python source exactly; do not shorten or "
                 "paraphrase code.\n\n")


def _contract() -> str:
    return CONTRACT.read_text(encoding="utf-8").strip()


def _insert_before(text: str, anchor: str, block: str) -> str:
    assert text.count(anchor) == 1, f"anchor {anchor!r} occurs {text.count(anchor)} times"
    return text.replace(anchor, block + anchor, 1)


def patched(name: str, text: str, skill_bullets: bool = True) -> str:
    """The exp895 version of one upstream prompt constant. skill_bullets=False is the text-only ablation."""
    out = text
    for old, new in FILTER_FIX:
        out = out.replace(old, new)
    contract = _contract()
    assert "{" not in contract and "}" not in contract, "contract must not contain format braces"
    cnote = CURATOR_NOTE if skill_bullets else CURATOR_NOTE_TEXT_ONLY
    if name == "REFLECTOR_PROMPT_NO_GT":
        out = _insert_before(out, "**Question:**", REFLECTOR_NOTE + contract + "\n\n")
    elif name == "CURATOR_PROMPT_NO_GT":
        out = _insert_before(out, "**Training Context:**", cnote + contract + "\n\n")
    elif name == "CURATOR_OPERATIONS_AGGREGATION_PROMPT":
        out = _insert_before(out, "**Training Context:**",
                             cnote + (REDUCER_EXTRA if skill_bullets else "") + contract + "\n\n")
    for note in (REFLECTOR_NOTE, CURATOR_NOTE, CURATOR_NOTE_TEXT_ONLY, REDUCER_EXTRA):
        assert "{" not in note and "}" not in note
    return out


def _load_prompt_module(stem: str):
    """Load ace/prompts/<stem>.py by path (pure string constants, no imports): no ACE package import needed."""
    spec = importlib.util.spec_from_file_location(f"_ace_prompts_{stem}", ACE_DIR / "ace/prompts" / f"{stem}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def originals() -> dict[str, str]:
    out = {}
    for stem, names in PROMPTS.items():
        mod = _load_prompt_module(stem)
        for n in names:
            out[n] = getattr(mod, n)
    return out


def apply(skill_bullets: bool = True) -> dict:
    """Rebind every ACE prompt constant to its patched text, in every upstream module that holds it."""
    import ace.core.curator as cur
    import ace.core.generator as gen
    import ace.core.reflector as refl
    import ace.prompts.curator as pcur
    import ace.prompts.generator as pgen
    import ace.prompts.reflector as prefl

    holders = {"generator": [pgen, gen], "reflector": [prefl, refl], "curator": [pcur, cur]}
    report = {}
    for stem, names in PROMPTS.items():
        for n in names:
            orig = getattr(holders[stem][0], n)
            new = patched(n, orig, skill_bullets)
            for m in holders[stem]:
                if hasattr(m, n):
                    setattr(m, n, new)
            report[n] = {"changed": new != orig, "filter_phrase_left": "chain of thought" in new.lower()}
    return report


def write_diff(path: Path, skill_bullets: bool = True) -> str:
    chunks = []
    for n, orig in originals().items():
        new = patched(n, orig, skill_bullets)
        if new != orig:
            chunks += difflib.unified_diff(orig.splitlines(keepends=True), new.splitlines(keepends=True),
                                           fromfile=f"upstream:{n}", tofile=f"exp895:{n}")
    text = "".join(chunks)
    Path(path).write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    import sys
    t = write_diff(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("prompt_patch.diff"))
    print(f"wrote prompt diff ({len(t.splitlines())} lines)")
