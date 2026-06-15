# Concepts — optimizing a system prompt

> The system prompt (a.k.a. the instructions, the developer message, or in some
> agents a "policy") is the cheapest, highest-leverage parameter of most LLM
> agents: a few words can flip success on a whole class of inputs.

## What the system prompt controls
- **Role & task framing** — who the agent is and what "done" means.
- **Output contract** — the exact format the downstream/eval expects. A frequent
  *silent* failure is a capable agent that formats its answer wrong and scores 0.
- **Decision policy** — when to call which tool, when to ask vs. act, refusal and
  safety rules. (Tool/customer-service agents are scored on following such a policy.)
- **Reasoning scaffolds & few-shot exemplars** — added inline to shape how the
  model thinks before it answers.

## How agents consume it
The system prompt is prepended to context every turn, so the model is highly
sensitive to its **ordering, contradictions, and length**. Long, redundant
preambles dilute attention and can *lower* accuracy; conflicting instructions
resolve unpredictably; instructions that fight the model's defaults produce
inconsistent behavior. This is why "more instructions" is not "better."

## What to optimize (and how)
- Sharpen the **task framing** and make the **output contract** explicit and
  unambiguous (this alone recovers many "capable-but-mis-formatted" failures).
- Tighten the **decision policy**: name the precondition for each tool/action.
- **Remove** instructions that don't pull their weight (measure, don't assume).
- Prefer explaining the *why* over piling on ALL-CAPS MUSTs — modern models follow
  reasoning better than brittle rules, and over-constraining hurts generalization.
- Add a **minimal** exemplar only when the format/behavior is hard to describe.

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
- tau-bench (policy adherence as a scored behavior), arXiv:2406.12045.
