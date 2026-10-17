"""Proposer guidance shared by every search algorithm (hill-climb, HC-2, agent-optimize): text only, no I/O.

``EDIT_KINDS_NOTE`` widens what a proposer considers an improvement beyond rewording prose: executable scripts
and code inside a skill or tool, and checklists that make the agent's behaviour more deterministic.
``COMPRESS_NOTE`` is the brief of the periodic compress/refactor operator (``hc2_compress_every`` /
``ao_compress_every``): rewrite the champion shorter, more deterministic and de-duplicated, with no loss of
behaviour. It is accepted by the same gate as any edit (non-inferior reward, lower agent cost; see ``costaware``).
"""

EDIT_KINDS_NOTE = (
    "Kinds of improvement (use whichever the failing traces call for; combine them):\n"
    "- CODE. Add or improve executable scripts and code snippets inside the skill or tool package (a helper the "
    "agent runs instead of reasoning in its head: a calculator, validator, lookup, parser, formatter). Give each "
    "script one clear entry point, a --help line, a short usage line in the skill text, and make it fail loudly "
    "with a readable message. Run it yourself on a small input before you finish whenever the sandbox allows.\n"
    "- DETERMINISM. Turn a step the agent keeps skipping or improvising into a fixed checklist, a verification "
    "command to run before the final answer, or a reusable helper script it must invoke. Prefer one command that "
    "does the whole check over several steps the agent must remember.\n"
    "- TEXT. Clearer, shorter, better-ordered instructions; concrete examples of the expected output; remove "
    "rules that conflict or repeat.\n"
    "Keep edits general (a rule or tool for a class of tasks, never a task id or an expected answer) and keep "
    "the package small: every line you add is re-read on every rollout, so delete what the new code or rule "
    "makes redundant.")

COMPRESS_NOTE = (
    "COMPRESS / REFACTOR. This is not a bug-fix round. Rewrite the current instructions, skills and scripts so "
    "they are shorter, more deterministic and free of duplication, WITHOUT changing what the agent does on any "
    "task it handles correctly today:\n"
    "- merge rules that say the same thing; delete rules that no trace supports, that contradict another, or "
    "that a script now enforces;\n"
    "- replace long prose procedures by a short checklist, or by a script the agent runs (keep the script's "
    "interface stable);\n"
    "- shorten tool descriptions and tool OUTPUTS the agent must read (return only the fields it uses);\n"
    "- keep every rule that fixes a failure class, every example the output format depends on, and every safety "
    "check.\n"
    "Your edit is accepted only if the reward is not worse and the agent's cost per rollout (prompt plus tool "
    "output tokens) is clearly lower, so aim for a large reduction (20% or more of the text and tool output) "
    "rather than a cosmetic one. Do not add new behaviour.")
