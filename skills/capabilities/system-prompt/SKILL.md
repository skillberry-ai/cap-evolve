---
name: system-prompt
description: Optimize an agent's system prompt or policy text — the instructions that shape its behavior. Use when the thing you want to improve is a prompt/policy file (not tools or a skill package). Covers what is safely editable, how prompt wording changes agent behavior, common failure modes (over-long preambles, conflicting instructions, missing output contracts), and what to measure. Provides concrete materialize/apply/validate handlers for prompt artifacts.
component: capability
argument-hint: "--path DIR"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: []
sources: [tau2bench]
---

# Capability: system prompt

The system prompt is the cheapest, highest-leverage parameter of most agents: a
few words can flip success on a whole class of tasks. This capability treats one
or more prompt/policy text files (`prompt.txt`, `policy.md`, `SYSTEM.md`) as the
optimizable artifact.

## What you can change here

The prompt is **HIGH-VALUE to edit, not a last resort.** When the traces show the
agent doesn't know a rule, a format, or a decision criterion, a sharper prompt is
the fastest fix. Each lever below is a safe, bounded edit class — pick the one
that fixes the biggest failure cluster. (1-line generic examples; depth in
[`references/concepts.md`](references/concepts.md).)

1. **Rewrite a rule for clarity / positive framing** — say what TO do, specifically.
   *Ex:* "Don't be vague" → "State the record ID in every reply."
2. **Add the WHY to a bare rule** — append the reason so the model generalizes.
   *Ex:* "Never use ellipses" → "Never use ellipses — output is read by a TTS
   engine that can't pronounce them."
3. **Consolidate redundant rules** — merge duplicates into one, keeping every
   distinct constraint. *Ex:* three "confirm before deleting" lines → one "Confirm
   before any destructive action (delete, overwrite, send)."
4. **Add a missing rule grounded in the source/policy** — add a rule the source
   requires but the prompt omits (must trace to a real source, never invented). The
   added rule must be ADDITIVE (a constraint/predicate the prompt lacked) or NARROWING
   (a stricter condition) — NEVER one that LOOSENS or broadens an existing
   permission/decision, which regresses the whole class.
   *Ex:* source says refunds need a manager code → "Require a manager code before
   any refund." (A *narrowing* add. Adding "anyone may refund without a code" would be
   a loosening — forbidden.)
5. **Add an example** — 1, up to 3–5, `<example>`-tagged exemplars to pin format.
   *Ex:* add one `<example>` showing the exact JSON envelope expected.
6. **Reorder** — long context/data to the top, query + instructions last; group
   mixed content under headers / XML tags. *Ex:* move a long reference block above
   the task instruction.
7. **Add a role / goal line** — one sentence on who the agent is and its objective.
   *Ex:* "You are a careful support agent; resolve the request in one turn."
8. **Tighten the output contract** — make the required shape explicit and exact.
   *Ex:* "Reply with only a JSON object `{status, reason}` — no prose."
   **If the eval scores COMMUNICATION of computed values** (totals, refunds, savings,
   counts, balances), the contract must require the agent to STATE each computed figure
   explicitly in its final message. The agent often performs the DB action correctly
   but never reports the number, and the eval marks the omission as a miss. This is a
   KNOWLEDGE / output-contract gap — prose-fixable here — and is DISTINCT from a missing
   DB action/write (a behavioral execution failure, which prose cannot fix and is out of
   scope for this capability). *Ex:* "After computing a total/refund/savings, state the exact figure in
   your final message (e.g. 'Your refund is $42.00')."
9. **Soften over-strong language** — downgrade `CRITICAL/MUST/ALWAYS` to "Use …
   when …" when a cluster shows over-eagerness/over-triggering on current models.
   *Ex:* "CRITICAL: you MUST call the tool" → "Use the tool when you need live data."

> **NEVER drop a needed rule — change, consolidate, or add; don't delete.** When an
> edit removes text, every distinct constraint that text carried must survive
> somewhere (rewritten, merged, or relocated). Deletion is legitimate only when the
> information is genuinely redundant or contradicted by the source — and even then,
> prefer rewriting the conflicting rule. Consolidation cuts *words*, never *rules*.

The good practices, failure modes, and the full never-drop rule are in
[`references/concepts.md`](references/concepts.md) — read it before a non-trivial edit.

## What can be optimized
- **Role line** — a single sentence stating who the agent is. A known cheap win:
  one role sentence focuses behavior and tone.
- **Task framing** — what "done" means.
- **Output contract** — exact format the downstream/eval expects (a frequent
  silent failure: the agent is *capable* but formats wrong). **Diagnose
  output-shape failures first** — right content / wrong shape scores zero, and is
  the cheapest class to fix.
- **Decision rules** — when to call which tool, when to ask vs. act, refusal
  rules (many agents are scored on adherence to such decision rules).
  **DANGER — a global decision/permission/refusal rule has UNBOUNDED blast radius.**
  Loosening or broadening one to fix a failing cluster (e.g. relaxing "restricted
  records may not be modified", or "any role may approve the request") flips behavior
  for the WHOLE class and
  regresses every currently-passing task where the original, stricter behavior was the
  gold answer. NEVER loosen a global decision rule to fix a cluster. If a cluster needs
  different behavior, state the EXACT discriminating CONDITION that NARROWS the rule to
  the qualifying cases only. A prompt edit to a decision rule is safe ONLY when it ADDS
  a predicate the agent lacked or NARROWS the rule — never when it broadens a permission
  or flips a decision the
  agent currently gets right.
- **Few-shot exemplars / reasoning scaffolds** — 3–5 diverse, relevant examples
  wrapped in `<example>` tags steer format (caveat: long example dumps can hurt
  reasoning models — keep it to a handful).

## How to write the edit (authoring rules)
These are *how* to phrase a prompt edit so it actually changes behavior:

- **State instructions positively — say what TO do, not just what not to do.**
  "Respond in flowing prose paragraphs" beats "don't use markdown." Positive
  phrasing gives the model a target; prohibitions only fence off one wrong path.
- **Explain the WHY, not bare MUSTs.** A rule with its reason generalizes; a bare
  `MUST`/`CRITICAL` does not. "Never use ellipses" works far better as "your output
  is read by a TTS engine that can't pronounce ellipses." Teach the optimizer to
  write the reason, not the command.
- **Model-sensitivity caveat — sometimes the fix is to REMOVE or soften an
  instruction.** Newer models over-comply: stale anti-laziness phrasing
  (`CRITICAL`/`MUST`/`ALWAYS`) now causes over-eagerness and over-engineering.
  Prefer plain "Use … when …". If a cluster shows over-doing rather than
  under-doing, the edit is to *cut or soften* an instruction, not add one.
- **Ordering / structure.** Put long context first and the query / output contract
  last (end-placement can lift quality on long inputs); separate
  instructions / context / examples with lightweight `<xml>` tags so the model
  doesn't conflate them.
- **Generalize, never hardcode.** A prompt rule must state the GENERAL policy that
  holds across the whole class of inputs, never a specific task's case or answer.
  *Good:* "Reverse the charge to the original payment method on file." *Bad:* "If the
  record id is `<TASK_SPECIFIC_ID>`, apply the exact amount that one task expects."
  Baking one task's id/value/date/answer into
  the prompt overfits, fails the held-out gate, and can mislead other tasks. Use a
  failing task's specifics only to understand the class, then write the general rule.
- **Ground new rules in a source; don't fabricate.** You MAY add a rule the source
  or policy requires but the prompt omits (menu item 4) — that is a high-value edit.
  What you must not do is invent a normative rule, exception, or workaround that no
  source supports and that conflicts with the existing instructions. Trace every
  added rule to a real source (the policy doc, the runner, the benchmark spec). If
  two existing rules conflict, rewrite toward the more restrictive one rather than
  dropping either.

## Prose fixes KNOWLEDGE gaps — behavioral failures are OUT OF SCOPE here
The system prompt is the right lever when a failure is a *knowledge* gap — the
agent doesn't know the required output format, a decision criterion, or a rule.
Telling it teaches it, and behavior changes. The prompt is the WRONG lever when a
failure is *behavioral* — the agent already "knows" what to do (it analyzes,
explains, even confirms) but then skips the action (e.g. stalls before issuing a
write and stops). More prose does not fix a behavior the model already agreed to
and declined: that class of failure is OUT OF SCOPE for the prompt — only enforcing
the action deterministically (outside this capability) fixes it. So before reaching
for a prompt edit, classify each cluster as KNOWLEDGE (fix here) vs behavioral
(not a prompt fix), and spend prose only on the knowledge gaps.

**If a rule is a VIOLATION the agent commits despite knowing it (not a knowledge
gap), do NOT add prose.** Adding another sentence to a rule the agent already read
and broke just grows the prompt without changing behavior — a known-but-broken rule
needs deterministic enforcement the prompt cannot provide, so it is out of scope here.

**A DECISION / PERMISSION cluster is NOT a knowledge gap — never loosen a global rule
to fix it.** When a cluster shows the agent making the wrong ACT-vs-REFUSE call, the
agent usually already "knows" the rule; the real condition is just more specific than
the prose. Relaxing the global rule makes the agent act on the WHOLE class and regresses
every task where refusing/escalating was the gold answer (unbounded blast radius). The
only safe prompt fix is a NARROWING rule that states the EXACT discriminating predicate
that separates the qualifying cases — a prompt edit may only ADD knowledge or NARROW,
never broaden a permission or flip a decision the agent currently gets right. If the
condition cannot be expressed as a narrowing rule, it is out of scope for the prompt.

**Each prompt iteration should also CONSOLIDATE.** When a rule is now enforced
deterministically elsewhere (no longer dependent on the prompt), REMOVE its
now-redundant prose so the prompt stays sharp — the deterministic enforcement is
authoritative and the duplicate sentence only dilutes attention. This prevents prose
pile-up: the prompt should get shorter as constraints become enforced, not longer.
(This is consolidation under the never-drop rule — the constraint still lives,
enforced elsewhere, so removing its prose drops no rule.)

## How agents use it
The prompt is prepended to context every turn. Agents read it literally and are
sensitive to ordering, contradictions, and verbosity. Long preambles dilute
attention; conflicting instructions resolve unpredictably.

## Organize the prompt for the agent reader (snippet patterns)
The prompt is a *snippet* the agent re-reads every turn — organize it the way an agent
parses fastest, and write it for that reader (third person, imperative, no marketing
tone, reason-in-one-clause):
- **Decompose instructions into concrete, ordered steps** rather than one dense
  paragraph; number them when order matters.
- **Decision trees for when-to-do-what.** A compact branch (`If X → do A; if Y → do B`)
  steers the act/refuse and tool-choice decisions better than prose.
- **Failure-handling / recovery lines** — state the recovery path, not only the happy
  path (e.g. "If the lookup returns empty, ask for the id instead of guessing.").
- **Redundancy removal** — repeated guidance dilutes attention and costs tokens every
  turn; consolidate duplicates into one rule (never dropping a distinct constraint —
  see the never-drop rule below).
These are organization moves; they never loosen a decision/permission rule (unbounded
blast radius) — keep the narrowing-only discipline from `references/concepts.md`.

## Common problems (see references/pitfalls.md)
- Over-long, redundant instructions → worse, not better.
- Missing/loose output contract → correct content, wrong shape, zero reward.
- Instructions that fight the model's defaults → inconsistent behavior.

## Handlers (scripts/abstract.py)
`materialize(dir) -> {file: text}` · `apply(dir, edits) -> report` ·
`validate(dir) -> {ok, files, problems}`. Edit ops: `set`, `append`,
`ensure_contains`. A project adapter's `apply` can call these directly.

## Optimizing it each iteration (analyze → ideate → edit)
The optimizer should **analyze before editing**: from the traces + the current
prompt, identify (a) the recurring failures clustered by root cause (the rule the
agent keeps breaking) and (b) the good behavior seen only on some trials that
should be made consistent; then make prompt edits for EVERY knowledge-gap cluster,
paired with the tool-code fixes for the behavioral clusters in the SAME candidate,
and reinforce (b) — sharpen or correct the offending rules rather than appending
more preamble.

## How to run
```
python scripts/check.py
python scripts/run.py --path <capability_dir>     # prints the candidate + validity
```

## References
- `references/concepts.md` — why prompts are high-leverage; what to optimize; pitfalls.
