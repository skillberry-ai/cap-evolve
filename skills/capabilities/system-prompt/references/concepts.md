# Concepts — optimizing a system prompt

Depth behind `SKILL.md`'s lever menu: what the prompt actually controls, the
authoring practices and failure modes in full, how to adapt to the runtime reader,
and the pitfalls that look like improvements.

## What the system prompt controls

- **Role & task framing** — who the agent is and what "done" means.
- **Output contract** — the exact shape the downstream consumer or scorer expects.
  The common silent failure is a capable agent that formats its answer wrong and
  scores zero, so diagnose shape before content.
- **Decision rules** — when to call which tool, when to ask versus act, refusal and
  escalation rules. Many agents are scored on adherence to such rules.
- **Reasoning scaffolds & exemplars** — added inline to shape how the model works
  through the task before answering.

## Adapting to the runtime reader

The right prompt edit depends on WHO reads this prompt at runtime (see the
`THE READER` block in your instructions, if present). Most of the advice here — soften
imperatives, explain the reason, keep exemplars minimal — assumes a strong reader.
Flip it for a weaker one:

- **strong reader:** lean, reasoning-first prose; give the reason; keep exemplars
  minimal; soften brittle imperatives, because over-constraining hurts this reader.
- **mid / weak reader:** be explicit. Prefer imperative step-by-step rules; include at
  least one worked exemplar per non-trivial behavior; keep decision chains short; make
  the output contract rigid and literal; and push behavioral rules into tool code
  rather than prose this reader will skip.

When no reader is declared, default to the strong-reader advice — and say so in
`PROCESS.md` so a later run can set the tier deliberately.

## The six authoring practices

1. **Be clear, direct, and specific — write for a capable new hire with no context.**
   If a colleague with minimal context would be confused by the instruction, so will
   the model. Spell out the desired output and the constraints; number steps when the
   order matters.
2. **Give the reason, not just the command.** A rule with its rationale extends to
   cases the author never enumerated. The canonical rewrite: "never use ellipses" →
   "the output is read by a TTS engine that cannot pronounce ellipses."
3. **Say what TO do, not only what NOT to do.** "Compose your reply in flowing prose"
   beats "do not use markdown" — a prohibition fences off one path, a positive
   instruction names the target.
4. **Structure deliberately.** Wrap instructions, context, examples, and input in
   their own sections or tags so the model does not conflate them; put long reference
   data before the instruction that acts on it, and keep the output contract adjacent
   to the point where the model produces the output rather than buried mid-preamble.
5. **Define the output contract explicitly, and use exemplars where prose cannot
   describe the shape.** For structured output, a schema or enum in the tool surface
   constrains it more reliably than prose asking for it.
6. **Keep the prompt lean and self-consistent, and tune trigger strength to the
   reader.** Redundant preambles and conflicting clauses compete for attention; when a
   cluster shows over-eagerness, soften `CRITICAL/MUST/ALWAYS` rather than adding more.

## The five failure modes

1. **Missing or loose output contract** — right content, wrong shape, zero reward.
   The most common silent prompt failure; diagnose shape before content. When the
   scorer reads the final message, the contract must require the agent to state every
   value the scorer checks. *Illustration:* on a customer-service benchmark scored on
   communicated figures (a total, a refund, a saving, a count, a balance), agents
   performed the write correctly and never reported the number — "After computing a
   refund, state the exact figure in your final message (e.g. 'Your refund is
   $42.00')" recovered the class. Read it as one instance of the general shape, not as
   a rule about money.
2. **Conflicting or over-broad instructions** — a later clause contradicts an earlier
   one and the resolution is not predictable. Detectable by reading the artifact
   alone: list the rules governing the same action, check for two different verdicts on
   one input, rewrite toward the stricter.
3. **Redundant preamble** — repeated or stale guidance competes with the rules that
   matter. Length is not safety, and `validate()` reports the counts so growth is
   visible across iterations.
4. **Negative-only phrasing** — "don't do X" with no positive alternative leaves the
   model to guess what Y is.
5. **Stale over-strong language** — anti-laziness `MUST/ALWAYS` phrasing that helped
   an older reader produces over-engineering, excess tool calls, and behaviors
   triggered where they did not apply. The fix for an over-doing cluster is a cut.

## Edit model

Artifact = one or more text files (`prompt.txt`, `policy.md`, `SYSTEM.md`). Edit ops:
`set`, `append`, `ensure_contains`. `validate` requires at least one non-empty prompt
file, reports per-file line/token/constraint-line counts, and — given a `baseline` —
warns when the candidate carries fewer constraint-bearing lines than its parent. That
warning implements `SKILL.md`'s never-drop rule mechanically; it flags a net loss for
a human or the optimizer to justify, and cannot tell a legitimate consolidation from a
lost rule.

## Pitfalls

- **Verbosity creep** — each iteration tends to add. Prune deliberately; the counts
  from `validate()` make the trend visible.
- **Overfitting to the scorer's quirks** rather than the task — watch the val→test
  gap on an accepted candidate.
- **Prompt-injection surface** — a rule that task input can override is not a rule.
  Prefer phrasing that survives adversarial input, and enforce anything security-
  relevant in code.
- **Editing prose where the failure was never a knowledge gap** — the most expensive
  wasted iteration in this capability, because a longer prompt looks like progress.

## Sources

- OpenAI / Anthropic prompt-engineering guides (instruction following, output
  contracts, exemplars) — https://platform.openai.com/docs/guides/prompt-engineering ,
  https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview
- "Large Language Models Are Human-Level Prompt Engineers" (APE), arXiv:2211.01910.
- "Large Language Models as Optimizers" (OPRO), arXiv:2309.03409.
- tau-bench (adherence to decision rules as a scored behavior), arXiv:2406.12045.
