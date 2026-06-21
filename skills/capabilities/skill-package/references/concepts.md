# Concepts — optimizing a skill package

> Follows the Agent Skills standard and widely-published skill-authoring guidance.
> When the optimizer edits a skill package, these are the rules that make the edit
> a *better skill*, not just different text.

## What a skill package is
```
skill-name/
├── SKILL.md          (required: YAML frontmatter + Markdown body)
├── references/*.md   (docs loaded on demand)
├── scripts/          (executables; code never enters context, only output)
└── assets/           (templates/icons used in output)
```

## Progressive disclosure (the core idea)
Three loading levels — optimize for the cheapest that still works:
1. **Metadata** (`name` + `description`) — always in context (~100 words). The
   `description` is the **primary triggering mechanism**: it must say WHAT the
   skill does AND WHEN to use it. Claude tends to *under*-trigger, so descriptions
   should be slightly "pushy" ("Use when the user mentions X, Y, or Z, even if
   they don't say 'skill'").
2. **SKILL.md body** — loaded when the skill triggers. Keep it **under ~500
   lines**; when it grows, move detail into `references/` and point to it.
3. **Bundled resources** — loaded only as needed; scripts run without entering
   context.

## Description-as-trigger optimization (a separable, measurable step)
The description is the *only* thing that decides whether the skill fires, so
triggering is optimized by editing the description — a step you can measure on its
own:

- Diagnose the failure direction. **Under-trigger** → enumerate the phrasings and
  contexts that should fire it (slightly "pushy", since Claude tends to
  under-trigger). **Over-trigger** → tighten the boundary and name the near-miss
  cases it does *not* cover.
- **Over-trigger caveat for newer models.** `CRITICAL`/`ALWAYS`/`MUST` now causes
  *over*-triggering — soften to plain "Use this when …" unless under-triggering is
  the measured problem.
- **Held-out trigger eval.** Assemble should-trigger / should-NOT-trigger prompts,
  including **near-miss negatives**, and select the description by held-out score
  to avoid overfitting the iteration examples. Trivial single-step tasks may not
  trigger any skill regardless of wording.

## What the optimizer should change (and how)
- **Sharpen the `description`** for triggering (the highest-leverage edit; see
  above).
- **Tighten the body**: imperative voice; explain the *why* rather than piling on
  ALL-CAPS MUSTs (today's models have good theory of mind and follow reasoning
  better than rigid rules). Remove instructions that don't pull their weight.
- **Generalize, don't overfit** to the eval tasks — a skill is used many times;
  fiddly task-specific rules hurt. Prefer better metaphors/patterns.
- **Factor repeated work into `scripts/`**: a strong signal to bundle a script is
  when traces show the agent independently **re-implementing the same helper**
  across runs, or a deterministic/repetitive step. Code is consistent and
  repeatable where prose is only *likely*. **State execute-vs-read intent
  explicitly** — whether the agent should run the script or read it as reference;
  script code runs without entering context.
- **Organize by domain** when multi-framework: a selection body + one reference
  file per variant, so only the relevant one is read.

## Validity rules enforced by `validate`
- `name`: ≤64 chars, `[a-z0-9-]`, no "anthropic"/"claude".
- `description`: non-empty, ≤1024 chars, ideally contains a "use when" clause.
- body ≤ ~500 lines (else: split into references).
- references one level deep; long references (>300 lines) start with a TOC.
- files the body links to (`references/…`, `scripts/…`) must exist.

## Sources
- Anthropic skill-creator skill (`plugins/skill-creator/skills/skill-creator/SKILL.md`).
- Agent Skills standard (agentskills.io) — frontmatter + progressive disclosure.
- SkillGrad / Trace2Skill / SkillOpt — optimizing a skill package from traces.
