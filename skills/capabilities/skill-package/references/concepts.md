# Concepts — optimizing a skill package

> Distilled from Anthropic's **skill-creator** skill and the Agent Skills standard.
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

## What the optimizer should change (and how)
- **Sharpen the `description`** for triggering (the highest-leverage edit).
- **Tighten the body**: imperative voice; explain the *why* rather than piling on
  ALL-CAPS MUSTs (today's models have good theory of mind and follow reasoning
  better than rigid rules). Remove instructions that don't pull their weight.
- **Generalize, don't overfit** to the eval tasks — a skill is used many times;
  fiddly task-specific rules hurt. Prefer better metaphors/patterns.
- **Factor repeated work into `scripts/`**: if every run reinvents the same helper,
  bundle it and tell the skill to call it.
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
