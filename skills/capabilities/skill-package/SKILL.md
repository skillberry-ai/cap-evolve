---
name: skill-package
description: Optimize an Agent Skill package itself — its SKILL.md (frontmatter + body), references, and bundled scripts. Use when the capability under optimization IS a skill (the SkillGrad / Trace2Skill / SkillOpt case): you want the agent to use the skill more effectively, trigger it correctly, and follow it without wasted steps. Enforces the skill-creator authoring rules (progressive disclosure, valid frontmatter, body length, one-level references) so edits stay valid skills.
component: capability
argument-hint: "--path DIR"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: []
sources: [skillgrad, trace2skill, skillopt]
---

# Capability: skill package

The thing being optimized is a skill directory (a `SKILL.md` plus `references/`,
`scripts/`, `assets/`). This capability treats that whole package as the editable
artifact and bakes in the **skill-creator** authoring rules so the optimizer
improves the skill without breaking it.

## What you can change here

Each lever is an edit class; pick the one that fixes the biggest failure cluster.
(1-line generic examples; depth in [`references/concepts.md`](references/concepts.md).)

1. **Edit the `description` / trigger** — the decision boundary that makes the skill
   fire. Sharpen *when* it applies for under-trigger; tighten the boundary + state
   near-miss cases for over-trigger. **Usually the highest-leverage edit.** *Ex:*
   "Formats data" → "Use when the user asks to export records to CSV."
2. **Edit the body** — improve clarity / altitude, remove dead weight, explain the
   *why* instead of rigid MUSTs, fix the step the agent keeps skipping. *Ex:* turn a
   vague "process the file" into a numbered procedure.
3. **Add / split references** — factor mutually-exclusive or rarely-co-used content
   into `references/*.md` (one level deep, TOC if long) as the body grows past ~500
   lines. *Ex:* split per-format guidance into `references/csv.md`, `references/json.md`.
4. **Add / edit bundled scripts** — when traces show the agent re-implementing the
   same helper, bundle it in `scripts/` and **state execute-vs-read intent**. *Ex:*
   add `scripts/validate.py` the skill runs instead of hand-writing the check.

> **Keep edits valid skills:** valid frontmatter (`name`/`description`), body
> < ~500 lines (progressive disclosure), references one level deep, no broken links.
> Explain the WHY over rigid MUSTs, and don't introduce unaudited/exfiltrating
> content — a skill body is executable context.

## What can be optimized
- **The `description`** — the primary triggering signal (what + when). Sharpening
  it is usually the highest-leverage edit.
- **The body** — clarity, the right altitude, removing dead weight, explaining the
  *why* instead of rigid MUSTs.
- **References** — adding/splitting `references/*.md` as the body grows past ~500
  lines (progressive disclosure).
- **Scripts** — factoring repeated work into `scripts/` the skill calls.

## How agents use a skill
Metadata (name+description) is always in context; the body loads when the skill
triggers; references/scripts load only as needed. So a vague description → the
skill never triggers; a bloated body → wasted context and worse behavior.

## The description is the trigger — optimize it as a separable step
The `description` is the decision boundary: it is what makes the skill fire. Most
triggering failures are fixed by editing the *description*, not the body.

- **Under-trigger** (the skill didn't fire when it should have) → make the
  description more explicit about *when* it applies: enumerate the phrasings and
  contexts that should fire it, including when the user doesn't name the skill.
- **Over-trigger** (it fired when it shouldn't have) → tighten the boundary and
  state the near-miss cases it does NOT cover.
- **Over-trigger caveat for newer models.** `CRITICAL`/`ALWAYS`/`MUST` in a
  description now causes over-triggering on current models — prefer plain
  "Use this when …". Reserve pushy phrasing for genuine under-triggering.
- **Evaluate triggering on held-out prompts.** Build a small set of should-trigger
  and should-NOT-trigger prompts including **near-miss negatives** (prompts that
  look close but shouldn't fire), and select the description that scores best —
  don't overfit to the handful of iteration examples. (Note: trivial one-step
  tasks may not trigger any skill regardless of description.)

## Bundle a script when traces show repeated re-implementation
If across runs the agent independently re-writes the same helper, or a step is
deterministic and repetitive, **bundle it as a script in `scripts/`** and have the
skill call it — code is consistent and repeatable where prose is only *likely*.
**State the intent explicitly**: whether the agent should *execute* the script or
*read it as reference*. (Scripts can run without their code entering context.)

## Handlers (scripts/abstract.py)
`materialize(dir)` → {SKILL.md, references/*} · `apply(dir, edits)` ·
`validate(dir)` → checks frontmatter (`name` ≤64/[a-z0-9-]; `description` ≤1024
with a "use when" clause), body ≤500 lines, references one level deep + TOC for
long ones, and that linked files exist.

## Optimizing it each iteration (analyze → ideate → edit)
The optimizer should **analyze before editing**: from the traces + the current
skill, identify (a) the recurring failures clustered by root cause (the step the
agent skips, the wrong trigger, the part of SKILL.md it misreads) and (b) the good
behavior seen only on some trials that should be made consistent; then make ONE
targeted edit (description/body/reference) that fixes the biggest cluster and
reinforces (b), staying within the skill-creator rules. Be economical: one good
edit, then stop.

## How to run
```
python scripts/check.py
python scripts/run.py --path <skill-package_dir>   # candidate + validity report
```

## Reference
- `references/concepts.md` — grounded background for this capability.

## References
- `references/concepts.md` — Agent Skills authoring + progressive disclosure (skill-creator).
