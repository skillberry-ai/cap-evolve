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

## Handlers (scripts/abstract.py)
`materialize(dir)` → {SKILL.md, references/*} · `apply(dir, edits)` ·
`validate(dir)` → checks frontmatter (`name` ≤64/[a-z0-9-]; `description` ≤1024
with a "use when" clause), body ≤500 lines, references one level deep + TOC for
long ones, and that linked files exist.

## How to run
```
python scripts/check.py
python scripts/run.py --path <skill-package_dir>   # candidate + validity report
```

## Reference
- `references/concepts.md` — grounded background for this capability.

## References
- `references/concepts.md` — Agent Skills authoring + progressive disclosure (skill-creator).
