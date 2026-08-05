# Optimizer playbook for the `tools` capability

What the **authored optimizer instructions** must demand when `tools` is among the
selected capabilities. `intake` writes those instructions
(`.capevolve/project/optimizer/INSTRUCTIONS.md`) but stays capability-agnostic; this
file is the `tools`-specific half it points at. Encode every item below into the
authored INSTRUCTIONS — verbatim or tightened for the benchmark at hand.

- [Depth mandate (tools wording)](#depth-mandate-tools-wording)
- [The EXISTING-tool-code mandate](#the-existing-tool-code-mandate)
- [The explicit TWO-PHASE subagent pattern](#the-explicit-two-phase-subagent-pattern)

## Depth mandate (tools wording)

`intake` demands a substantial multi-root-cause pass in capability-neutral terms.
When `tools` is selected, make that demand concrete with this snippet:

> "Each iteration is a substantial, multi-root-cause pass. Diagnose ALL clusters
> and fix as many as possible in ONE candidate — improve multiple tools' code,
> validation, and return values/errors; add new tools; sharpen many tool docs;
> and fix the prompt (only if `system-prompt` is ALSO among the selected
> capabilities — on a `tools`-only run drop this clause and leave the prompt
> alone) — together. Scope each fix to protect passing tasks; do NOT
> trade breadth for caution. A single small edit is an under-used iteration."

## The EXISTING-tool-code mandate

Demand: convert violated textual rules into in-code checks across MANY EXISTING tool
bodies — most violated rules govern a tool that already exists, so the fix is an
in-body guard there, not a new tool. State plainly: *a docstring-only iteration (or
one that only adds a single new tool + rewords docstrings, leaving rules as prose)
is under-used.*

The edit classes this mandate ranges over — and the before/after diffs that show an
in-body guard replacing a prose rule — are in
[`../SKILL.md`](../SKILL.md) ("What you can change here", "The highest-leverage
edit") and [`examples.md`](examples.md).

## The explicit TWO-PHASE subagent pattern

Require:

1. **Phase 1 — diagnose fan-out.** One read-only subagent per trajectory-group → a
   tight issue list; the main agent dedups those into clusters.
2. **Phase 2 — implement fan-out.** One edit-subagent per ISSUE, each in its own
   worktree, each PREFERRING to edit the EXISTING tool's code body to enforce its
   rule.
3. **Merge.** The main agent merges all edits into ONE candidate.

Point the optimizer at `./guidance/optimizer/<name>.md` for that agent's concrete
trigger phrasing.

Authored INSTRUCTIONS fail this playbook when they omit either mandate above.
