---
name: skill-package
description: Optimize an Agent Skill package itself — its SKILL.md (frontmatter + body), references, and bundled scripts. Use when the capability under optimization IS a skill, you want the downstream agent to trigger it correctly and follow it without wasted steps. Enforces the skill-creator authoring rules (progressive disclosure, valid frontmatter, body budget, one-level references) so edits stay valid skills.
component: capability
argument-hint: "--path DIR"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: []
sources: [agentskills, skillgrad, trace2skill, skillopt]
---

# Capability: skill package

The thing being optimized is a skill directory (a `SKILL.md` plus `references/`,
`scripts/`, `assets/`). This capability treats that whole package as the editable
artifact and bakes in the **skill-creator** authoring rules (sourced to first-party
Anthropic docs — see [`references/concepts.md`](references/concepts.md)) so the
optimizer improves the skill without breaking it.

## What you can change (highest leverage first)

Each lever is an edit class; pick the one that fixes the biggest failure cluster.
One-line examples here; depth in the referenced files.

1. **The `description` / trigger** — the decision boundary that makes the skill
   fire, and the single highest-leverage edit. Write it **third person**, state
   **what** it does AND **when** to use it, and use the **keywords a user would
   actually say**. Lean slightly pushy for under-trigger; tighten the boundary and
   name near-miss cases for over-trigger. **Front-load the key use case** — the
   listing truncates `description + when_to_use` at 1,536 chars. *Ex:* "Formats
   data" → "Exports records to CSV. Use when the user asks to export or download a
   table." Full playbook: [`references/description-optimization.md`](references/description-optimization.md).
2. **The body** — improve clarity / altitude, remove dead weight, fix the step the
   agent keeps skipping. The body is loaded on every trigger and **stays in context
   all session — a recurring token cost**, so keep it **<500 lines AND ~5k tokens**
   and **state what to do, don't narrate why at length**. Imperative voice; explain
   the *why* of a rule briefly instead of piling on ALL-CAPS MUSTs.
3. **References** — factor mutually-exclusive or rarely-co-used detail into
   `references/*.md` as the body grows. Keep them **one level deep**, link each
   **directly from SKILL.md with an explicit pointer saying what it contains and
   when to load it**, and give long refs (>300 lines) a table of contents. Don't
   nest (a ref pointing to another ref) — the agent may only partially read it.
4. **Scripts** — when traces show the agent re-implementing the same helper, or a
   step is deterministic/repeatable, **bundle it in `scripts/`** and **state
   execute-vs-read intent**. A script runs via bash without its code entering
   context (output-only token cost); prose is only *likely* and costs context.
   Reserve prose for steps that need judgment.

> **Keep edits valid skills:** valid frontmatter (`name` ≤64/[a-z0-9-]/no XML;
> `description` non-empty ≤1024/no XML, with a "use when" clause), body within
> budget, references one level deep, no broken links. Don't introduce
> unaudited/exfiltrating content — a skill body is executable context.

## How agents use a skill (progressive disclosure)
Three loading levels — optimize for the cheapest that still works:
1. **Metadata** (`name` + `description`) — always in context (~100 tokens). The
   description is the *only* thing that decides whether the skill fires.
2. **SKILL.md body** — loaded when the skill triggers (recurring session cost).
3. **References / scripts** — loaded or executed only as needed.

So a vague description → the skill never triggers; a bloated body → wasted context
and worse behavior; detail that belongs in a reference → paid for on every trigger.

## Adapting to the reader's capability tier
Scale the SKILL.md body density to WHO follows it at runtime (see the `THE READER` block
in your instructions, if present). A **mid/weak** reader needs more worked steps, explicit
ordering, and examples in the body — it infers less, so a compact principle-first body
leaves it guessing. A **frontier** reader follows a compact, principle-first body and is
slowed by over-specification. Keep the progressive-disclosure structure and body budget
either way (push detail into `references/`); the tier changes how *explicit* the retained
body is, not how *long* it may be.

## The description is the trigger — optimize it as a separable step
Most triggering failures are fixed by editing the *description*, not the body.

- **Under-trigger** → enumerate the phrasings and contexts that should fire it,
  including when the user doesn't name the skill.
- **Over-trigger** → tighten the boundary and state the near-miss cases it does NOT
  cover. `CRITICAL`/`ALWAYS`/`MUST` in a description over-triggers current models —
  prefer plain "Use when …"; reserve pushy phrasing for genuine under-triggering.
- **Trivial single-step tasks** may not trigger any skill regardless of wording.

## Measure every edit against the objective
A skill edit is only an improvement if it raises the number we are optimizing.

- **The acceptance signal is the intake benchmark score** on the held-out **val**
  split, via cap-evolve `evaluate` → `gate`. Keep only gated wins; reject edits
  that don't clear the significance bar. **Never overfit the handful of iteration
  examples** — a skill is used many times; fiddly task-specific rules hurt.
- **For triggering**, also track trigger-rate on a held-out set of should-trigger /
  should-NOT-trigger prompts (with **near-miss negatives**), and pick the
  description that scores best on the held-out set — the skill-creator loop's own
  select-by-held-out discipline, which is exactly cap-evolve's train/val/test split.

## Handlers (scripts/abstract.py)
`materialize(dir)` → {SKILL.md, references/*} · `apply(dir, edits)` ·
`validate(dir)` → frontmatter (`name` ≤64/[a-z0-9-]/no XML; `description` ≤1024/no
XML with a "use when" clause; POV + all-caps + 1,536-listing lints), body ≤500
lines / ~5k tokens, references one level deep + TOC for long ones, links exist.

## Optimizing it each iteration (analyze → ideate → edit)
**Analyze before editing** (treat the skill like an evolving playbook you curate):
from the traces + the current skill, identify (a) recurring failures clustered by
root cause (the step the agent skips, the wrong trigger, the misread instruction)
and (b) good behavior seen only on some trials that should be made consistent. Then
make **ONE** targeted edit that fixes the biggest cluster and reinforces (b),
staying within the skill-creator rules. Be economical: one good edit, then stop.

## How to run
```
python scripts/check.py                                  # self-test (must pass)
python scripts/run.py --path <skill_dir>                 # candidate + validity report
python scripts/token_report.py --path <skill_dir>        # progressive-disclosure budget
```

## References
- [`references/concepts.md`](references/concepts.md) — the authoring model and the
  validity rules, with first-party sources. Load for grounding.
- [`references/description-optimization.md`](references/description-optimization.md)
  — the trigger-tuning playbook. Load when fixing under/over-trigger.
- [`references/anti-patterns.md`](references/anti-patterns.md) — common bad smells
  and the why. Load when a draft "feels off" or to review an edit.
