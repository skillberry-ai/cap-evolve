---
name: system-prompt
description: Optimize an agent's system prompt, developer message, or policy text — the instructions that shape its behavior. Use when the artifact to improve is a prompt or policy file rather than tools or a skill package: the agent lacks a rule, misses the required output format, or applies the wrong decision criterion. Covers the safe edit classes (rewrite, consolidate, add a sourced rule, reorder, tighten the output contract, soften over-strong wording), how to keep an edit general instead of overfitting one task, and the rule that a needed constraint is never deleted. A failure where the agent already knows the rule and skips the action belongs to the capability that edits tool code, not here.
component: capability
argument-hint: "--path DIR"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: []
sources: [tau2bench]
---

# Capability: system prompt

This capability treats one or more prompt/policy text files (`prompt.txt`,
`policy.md`, `SYSTEM.md`) as the optimizable artifact — whatever text the runtime
prepends to the agent's context as its instructions, output contract, and decision
policy.

Prose is the right lever when the agent lacks something it could be *told*: a
format, a rule, a decision criterion. It is the wrong lever when the agent already
has the rule and does not act on it — that needs the behavior enforced in code, so
it belongs to whatever capability edits the agent's tools, not here. Classify the
failure clusters first (`./guidance/diagnose/SKILL.md`, when present) and spend
prose only on the clusters this capability can actually move.

## Pick the lever

Each item is a bounded edit class. Fix the biggest cluster with the narrowest lever
that reaches it; ship every class the traces call for in one candidate. Examples are
1-line and generic; depth is in [`references/concepts.md`](references/concepts.md).

1. **Rewrite a rule for clarity, positively framed** — say what TO do, specifically.
   A prohibition fences off one wrong path; a positive instruction names the target.
   *Ex:* "Don't be vague" → "State the record ID in every reply."
2. **Add the reason to a bare rule** — a rule paired with its rationale extends to
   cases the rule's author never wrote down; a bare imperative does not.
   *Ex:* "Never use ellipses" → "Never use ellipses — the output is read by a TTS
   engine that cannot pronounce them."
3. **Consolidate redundant rules** — merge duplicates into one, keeping every
   distinct constraint. *Ex:* three "confirm before deleting" lines → one "Confirm
   before any destructive action (delete, overwrite, send)."
4. **Add a rule the source requires but the prompt omits** — it must trace to a real
   source (the policy doc, the runner, the task spec), never be invented. The added
   rule may introduce a constraint the prompt lacked, or state a stricter condition on
   an existing one. It may not broaden an existing permission or flip a decision the
   agent currently gets right: that changes behavior for every task in the class,
   including the passing ones whose gold answer was the stricter behavior. When a
   cluster needs different behavior, name the exact condition that separates the
   qualifying cases instead. *Ex:* the source says refunds need a manager code →
   "Require a manager code before any refund."
5. **Add an example** — one or a few `<example>`-tagged exemplars to pin a format
   that is hard to describe in prose. *Ex:* one `<example>` showing the exact JSON
   envelope expected. Examples are re-read every turn, so add the smallest set that
   pins the shape and treat a larger set as a hypothesis to gate, not a free win.
6. **Restructure** — separate instructions, context, examples, and input into their
   own sections or tags so the model does not conflate them, and put long reference
   data before the instruction that acts on it.
7. **Add a role / goal line** — one sentence on who the agent is and what "done"
   means, when the prompt has none. *Ex:* "You are a careful support agent; resolve
   the request in one turn."
8. **Tighten the output contract** — make the required shape explicit and exact.
   *Ex:* "Reply with only a JSON object `{status, reason}` — no prose." If the scorer
   reads the agent's final message, the contract must require the agent to state every
   value the scorer checks: agents routinely perform the action correctly and never
   report the result, and the scorer sees only the omission. (A missing action, as
   opposed to a missing report of it, is not fixable here — see the scope note above.)
9. **Soften over-strong wording** — when a cluster shows the agent over-doing rather
   than under-doing (excess tool calls, over-engineering, triggering a behavior where
   it did not apply), downgrade `CRITICAL/MUST/ALWAYS` to "Use … when …". The edit
   that fixes an over-eagerness cluster is a cut, not an addition.

## Never drop a needed rule — change, consolidate, or add

When an edit removes text, every distinct constraint that text carried must survive
somewhere: rewritten, merged into a combined rule, or relocated. Deletion is
legitimate when the information is genuinely redundant, contradicted by the source,
or now enforced deterministically elsewhere — and in the first two cases prefer
rewriting the conflicting rule. Consolidation cuts *words*, never *rules*.

An optimizer that deletes a needed rule can make one iteration's metric go up and
leave the class permanently broken, so the check is mechanical as well as stated:
`apply()` counts constraint-bearing lines before and after every edit and reports a
net loss in `report["warnings"]`. A warning is not a failure — a legitimate
consolidation triggers it too — it is a prompt to state, in `PROCESS.md`, where each
dropped constraint went. `op: "set"` on a whole file is the edit most likely to lose
one silently.

## Keep the edit general

- **Never hardcode a task's specifics.** A rule must state the general policy that
  holds across the class, not one task's case or answer. *Good:* "Reverse the charge
  to the original payment method on file." *Bad:* "If the record id is
  `<TASK_SPECIFIC_ID>`, apply the amount that task expects." Baking an id, value,
  date, or answer into the prompt overfits, gets rejected by the held-out gate, and
  can mislead other tasks. Use a failing task's specifics to identify the class, then
  write the general rule. The test for any edit: *would this help on a task the
  optimizer has never seen?*
- **Resolve conflicts, don't stack rules.** Before editing, list the rules that
  govern the same action and check that no two give a different verdict on the same
  input; rewrite toward the stricter one rather than dropping either. A contradiction
  is the one failure mode detectable by reading the artifact alone, so it is worth
  the pass.
- **Consolidate as constraints move out of the prompt.** When a rule is now enforced
  deterministically elsewhere, remove its now-redundant prose: the enforcement is
  authoritative and the duplicate sentence only competes for attention. The prompt
  should get shorter as constraints become enforced, not longer. (This drops no rule
  — the constraint still lives, enforced elsewhere.)
- **Watch length, but measure it.** `validate()` reports each file's line, token, and
  constraint-line counts. There is no universal length threshold worth quoting;
  compare a candidate against the accepted candidates of your own run and treat a
  prompt that grows every iteration without moving val as the signal to prune.

## Handlers (scripts/abstract.py)

`materialize(dir) -> {file: text}` · `apply(dir, edits) -> {changed, warnings}` ·
`validate(dir, baseline=None) -> {ok, files, stats, problems, warnings}` ·
`is_empty(dir) -> bool`. Edit ops: `set`, `append`, `ensure_contains`. Pass
`baseline` (a directory or a `{file: text}` dict, e.g. the parent candidate) to have
`validate` report a constraint-line drop against it. A project adapter's `apply` can
call these directly.

## How to run

```
python scripts/check.py
python scripts/run.py --path <capability_dir>                        # candidate + validity
python scripts/run.py --path <candidate_dir> --baseline <parent_dir>  # + rule-loss check
```

## References

- [`references/concepts.md`](references/concepts.md) — what the prompt controls, the
  six authoring practices and five failure modes in full, how to adapt a prompt to
  the runtime reader's capability tier, pitfalls, and cited sources. **Read once
  before your first non-trivial edit**, and again when a candidate is accepted but
  barely moves the metric.
