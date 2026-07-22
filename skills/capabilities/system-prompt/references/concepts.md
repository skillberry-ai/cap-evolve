# Concepts — optimizing a system prompt

> The system prompt (a.k.a. the instructions, the developer message, or the
> decision rules / output contract an agent is held to) is the cheapest,
> highest-leverage parameter of most LLM agents: a few words can flip success on
> a whole class of inputs.

## What the system prompt controls
- **Role & task framing** — who the agent is and what "done" means.
- **Output contract** — the exact format the downstream/eval expects. A frequent
  *silent* failure is a capable agent that formats its answer wrong and scores 0.
- **Decision rules** — when to call which tool, when to ask vs. act, refusal and
  safety rules. (Many agents are scored on adherence to such decision rules.)
- **Reasoning scaffolds & few-shot exemplars** — added inline to shape how the
  model thinks before it answers.

## Knowledge gaps vs. behavioral gaps (what prose can and cannot fix)
Prose is the right tool for KNOWLEDGE/format/decision-criteria gaps: a missing
output contract, an unstated rule, an ambiguous criterion — telling the agent
fixes it. Prose is WEAK for BEHAVIORAL failures the model already "knows" but
skips: it analyzes, explains, confirms, then fails to perform the action (the
classic stall before a write). You cannot instruct a model out of a behavior it
already agreed to and then declined — that class is OUT OF SCOPE for the prompt; it
needs the action enforced deterministically (outside this capability). Classify each
failure cluster before editing and spend prose only on the knowledge gaps.

## How agents consume it
The system prompt is prepended to context every turn, so the model is highly
sensitive to its **ordering, contradictions, and length**. Long, redundant
preambles dilute attention and can *lower* accuracy; conflicting instructions
resolve unpredictably; instructions that fight the model's defaults produce
inconsistent behavior. This is why "more instructions" is not "better."

## Adapting to the reader's capability tier
The right edit depends on WHO reads this prompt at runtime (see the `THE READER` block
in your instructions, if present). Much of the advice in this file — "soften MUSTs",
"explain the why", "newer models over-comply" — is a **frontier/strong-reader** tactic.
Flip it for weaker readers:

- **frontier / strong reader:** lean, reasoning-first prose; explain the WHY; keep
  few-shot minimal; soften brittle imperatives — over-constraining *hurts* this reader.
- **mid / weak reader:** be EXPLICIT. Prefer imperative step-by-step rules; include at
  least one worked few-shot example per non-trivial behavior; keep decision chains short;
  make the output contract rigid and literal; and push behavioral rules into tool CODE
  (see the `tools` capability) rather than prose the reader will skip.

When no reader is declared (`target_model` empty), default to the frontier/strong advice
below — but say so in `PROCESS.md` so a later run can set the tier.

## What to optimize (and how)
- Add a one-sentence **role line** if absent — a cheap, well-documented win that
  focuses behavior and tone.
- Sharpen the **task framing** and make the **output contract** explicit and
  unambiguous (this alone recovers many "capable-but-mis-formatted" failures);
  diagnose output-shape failures *before* content failures.
- Tighten the **decision policy**: name the precondition for each tool/action.
- **Remove** instructions that don't pull their weight (measure, don't assume).
- Prefer explaining the *why* over piling on ALL-CAPS MUSTs — modern models follow
  reasoning better than brittle rules, and over-constraining hurts generalization.
- Add a **minimal** exemplar only when the format/behavior is hard to describe.

## How to phrase the edit
- **Positive instruction.** Tell the model what TO do, not only what not to do —
  "respond in flowing prose paragraphs" steers better than "don't use markdown,"
  because a prohibition fences off one path while a positive instruction names the
  target. Treat the model as a brilliant new hire with no context: if a colleague
  with minimal context would be confused by the instruction, so will the model.
- **Explain the WHY.** A rule paired with its rationale generalizes to unseen
  cases; a bare `MUST`/`CRITICAL` does not. "Output is read by a TTS engine that
  can't pronounce ellipses" beats "never use ellipses."
- **Model-sensitivity.** Newer models over-comply, so stale anti-laziness phrasing
  (`CRITICAL`/`ALWAYS`/`MUST`) now over-triggers — prefer plain "Use … when …".
  When a cluster shows over-eagerness or over-engineering, the right edit is to
  **remove or soften** an instruction, not add one.
- **Ordering / structure.** Long context first, query / output contract last;
  separate instructions / context / examples with `<xml>` tags. End-placed
  instructions are acted on more reliably on long inputs.
- **Ground new rules in a source.** Adding a rule the source/policy requires but
  the prompt omits is a high-value edit (menu item 4). What regresses is *inventing*
  a normative rule that no source supports and that conflicts with the existing
  instructions — trace every added rule to a real source. Behavioral failures (the
  model knows the rule but skips the action) belong in **code/tools**, not more prose.

## The six good practices
1. **Be clear, direct, specific — write for a capable new hire with no context.**
   If a colleague with minimal context would be confused, so will the model. Spell
   out the desired output and constraints; number steps when order matters.
2. **Give the reason, not just the command.** Context lets the model generalize;
   the TTS-ellipses rewrite is the canonical before/after.
3. **Tell it what TO do, not what NOT to do (positive framing).** "Compose your
   reply in flowing prose" beats "do not use markdown."
4. **Structure with sections / XML tags and order deliberately.** Wrap
   instructions, context, examples, inputs in their own tags; long data at the top,
   the query / contract last (end-placement can lift quality on long inputs).
5. **Use a few diverse examples (3–5) and define an explicit output contract.**
   Examples are the most reliable way to steer format; prefer a schema / enum tool
   over prefill for structured output.
6. **Keep prompts lean and self-consistent; tune trigger strength to the model.**
   Over-long, redundant preambles and conflicting instructions dilute attention; on
   current models, soften `CRITICAL/MUST` rather than piling on more.

## The five failure modes
1. **Missing or loose output contract** — right content, wrong shape → zero reward
   (the most common silent prompt failure; diagnose shape before content).
2. **Conflicting / over-broad instructions** — a later clause contradicts an
   earlier one; the model resolves it unpredictably and behavior gets *worse*.
3. **Over-long, redundant preamble** — repeated or stale guidance dilutes
   attention; length is not safety.
4. **Negative-only phrasing** — "don't do X" without the positive alternative
   underperforms "do Y."
5. **Stale over-strong language → over-eagerness** — anti-laziness `MUST/ALWAYS`
   prompting that helped older models now causes over-engineering, excessive tool
   use, and over-triggering on current models.

## The never-drop rule (non-negotiable)
**Never delete a rule, policy, or constraint the agent still needs — change,
consolidate, or add instead.** When an edit removes text, every distinct constraint
that text carried must survive somewhere (rewritten more clearly, merged into a
combined rule, or relocated). Deletion is legitimate only when the information is
genuinely redundant or contradicted by the source — and even then, prefer rewriting
the conflicting rule over dropping it. Consolidation reduces *words*, never *rules*.

## Edit model
Artifact = one or more text files (`prompt.txt`, `policy.md`, `SYSTEM.md`). Edit
ops mirror the optimizer: `set`, `append`, `ensure_contains`. `validate` requires
at least one non-empty prompt file.

## Pitfalls
- Verbosity creep: each iteration tends to *add*; periodically prune.
- Over-fitting the prompt to the eval's quirks rather than the task (the val gate
  + held-out test guard against this, but watch the val→test gap).
- Burying the output contract at the bottom; put format requirements where the
  model will act on them.
- Prompt-injection surface: instructions that can be overridden by task input.

## Sources
- OpenAI / Anthropic prompt-engineering guides (instruction following, output
  contracts, few-shot) — https://platform.openai.com/docs/guides/prompt-engineering ,
  https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview
- "Large Language Models Are Human-Level Prompt Engineers" (APE), arXiv:2211.01910.
- "Large Language Models as Optimizers" (OPRO), arXiv:2309.03409.
- tau-bench (adherence to decision rules as a scored behavior), arXiv:2406.12045.
