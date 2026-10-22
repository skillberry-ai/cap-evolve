# PROCESS — what I did this iteration (explainability; REQUIRED)

## TL;DR

The flakiness is **not** reasoning, routing, or tool use. All 28 available
only thing that ever fails is one answer-contract check, `lon-is-up`, and it
fails for a **presentation** reason: the agent writes a decorative status icon
**between** an entity's name and its status word (`| host | ✅ UP |`), which
breaks the name↔status adjacency that every `lon-is-up` form requires.

| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |
| --- | --- | --- | --- | --- | --- |

No routing cluster: `task.toml` has `services = ["icinga"]` and routing is
and is used correctly every time.

## How I diagnosed it (in order)

1. **`trajectories/*.json` were insufficient** — all 10 have `trace: null`
   and `tool_calls: []`. But the metric breakdown was already decisive:
   routing or tool edit could help.
   `required_missed = ["lon-is-up"]`, the same single check, never another.
   The other two required checks always pass; the forbidden check is never
   answer text instead of guessing. This reproduced the pass/fail split
   exactly, so I could test hypotheses mechanically.
5. **Found the discriminator.** Failing and passing answers look nearly
   identical to a human (seed-4 fail and seed-5 pass are near-copies). The
   difference is one character class. Regex for "glyph interposed between
   hostname and state word":

   |---|---|---|
   | yes | no  | 20 |
   | yes | yes |  4 |
   | no  | yes |  4 |

   host elsewhere that satisfied the check — the source of the intermittency.
   Failing rows: `| x | ✅ UP |`, `| x | 🟢 UP |`, `| x | ✅ **UP** — …`.
   Note `_strip_markup` is **not** active here (`fold_markup` unset), but
   `**UP**` forms are enumerated in `any_of`; the emoji is not, and nothing
   folds it.
6. **Verified mechanically before writing prose.** Stripping only decorative
   glyphs from the 4 failing answers and re-scoring:

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |

## Verify-the-fix (the trace → what the edited text now does on those exact inputs)

## Non-overfitting check
`grep` confirms **no** task literal (`ledger`, `-fra`, `-lon`, `10.61.4.22`,
`time to live`) appears anywhere in the edited files — examples use `web-01` /
`host-x` placeholders. Restating both rules without task-specific nouns:
*"put a named thing's status word right after its name, with no icon in
between"* and *"when a query returns many rows, give every row's state and

## Process & features used
- **Subagents / worktrees / parallel features used:** none — serial, deliberately. The guidance suggests one subagent per trajectory-group, but there is exactly **one** task, **one** failing check, and **one** mechanism, and the real verifier was available to test hypotheses directly and cheaply. Fanning out would have multiplied cost without adding coverage. The high-leverage move here was running `verify.py` against real answer text, not parallelism. Recorded in `META_INSIGHTS.md`.

## Good things to PRESERVE (do not let a future iteration undo these)
- The measured headroom was *presentation only*. Keep the name↔status adjacency rule.

## Deliberately skipped (cluster + why)
- **Prose telling the agent to match verifier phrasings** — that overfits to the grader instead of fixing a mechanism.
- **Any new-tool proposal** — no capability gap; this phase has no tools layer anyway.

## Escalation (honest scope note)
None blocking — this is genuinely fixable in prose. Worth recording: the
`lon-is-up` check passes/fails on whether an emoji sits between two tokens,
while the agent's *substance* (which host is down, why, and the other host's
cosmetic choice. `any_of` enumerates `**UP**` but not `✅ UP`, and nothing
folds leading glyphs the way `_strip_markup` folds markup. I fixed it on the
agent side because that is this phase's edit space, and because "status word
adjacent to the name" is defensible formatting advice on its own merits — but
a contract that folded leading glyphs would erase this flake class for every
task at once. Logged in `FRAMEWORK_IMPROVEMENTS.md`.
