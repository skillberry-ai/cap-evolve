# Context sources: `./guidance/<cap>/SKILL.md` and `optimizer/INSTRUCTIONS.md`

Two files Phase 0 points at, read once, before any edit.

## `./guidance/<cap>/SKILL.md` — one per declared capability

Baseline copies each `capevolve.yaml: capabilities` entry's own skill package (the
capability-TYPE brief — `system-prompt`, `tools`, `mcp-tool`, `skill-package` — not the
specific artifact under `capability_path`) into the run dir once, at baseline time, so it
is there regardless of `orchestration_mode`. This is that capability type's own edit-menu:
what is actually editable, the worked examples, the allowed-edit-space table. An edit made
without reading the one for the surface you are touching is a guess.

## `$P/optimizer/INSTRUCTIONS.md` — if intake scaffolded and customized it

Authored for the DETERMINISTIC per-iteration optimizer, so read it for what is uniquely
valuable there and ignore the rest:
- **Read for:** the benchmark's own facts and constraints — which files are editable,
  which tokens are load-bearing, what silently zeroes a score. Measured on this benchmark,
  repeated nowhere else, and binding.
- **Ignore:** anything about stopping after one edit, not evaluating, or a per-iteration
  budget — that is the OTHER loop. You own the whole search; SKILL.md's "Agent-mode loop"
  wins on process.

## The one deliberate redundancy

`optimizer/INSTRUCTIONS.md` carries its own failure-type → lever table, with runnable code
examples. SKILL.md's "Propose an edit per candidate" step (in the numbered loop, not here)
has a condensed version of the same table with no code. Both are visible to you now — this
is a known duplication, left for a human to resolve (fold one into the other, or drop the
condensed copy) rather than silently maintained twice. Until then: prefer
`optimizer/INSTRUCTIONS.md`'s version when the two disagree on wording, since it is the
richer, benchmark-grounded source.
