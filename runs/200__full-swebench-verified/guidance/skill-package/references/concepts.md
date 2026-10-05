# Concepts — optimizing a skill package

> The authoring model below is first-party (Anthropic Agent Skills docs +
> skill-creator + the engineering blog; see Sources). When the optimizer edits a
> skill package, these are the rules that make the edit a *better skill*, not just
> different text. Load it for grounding; `SKILL.md` links the sibling references.

## What a skill package is
```
skill-name/
├── SKILL.md          (required: YAML frontmatter + Markdown body)
├── references/*.md   (docs loaded on demand)
├── scripts/          (code the agent EXECUTES; source never enters context)
└── assets/           (templates/icons/fonts used in the skill's OUTPUT)
```

## Progressive disclosure (the core idea)
Skills use a **three-level loading model**; optimize for the cheapest that works:

1. **Metadata** (`name` + `description`) — **always** loaded at startup into the
   system prompt, ~100 tokens per skill. The `description` is the **primary
   triggering mechanism**: it must say WHAT the skill does AND WHEN to use it.
2. **SKILL.md body** — loaded **when the skill triggers**, then it **stays in
   context for the rest of the session** (a recurring cost). Keep it **≤500 lines**
   (skill-creator's guidance, enforced by `validate`). When it grows, move detail
   into `references/` and add an explicit pointer.
3. **Bundled resources** — references, scripts and assets, loaded/executed **only as
   needed**, effectively unlimited. A reference costs **zero** context until read; a
   script runs via bash **without its code entering context at all** — only its
   *output* costs tokens.

## Frontmatter rules (hard invariants)
- **`name`**: ≤64 chars, lowercase `[a-z0-9-]` only, **no XML tags**, no reserved
  words (`anthropic`, `claude`).
- **`description`**: non-empty, ≤1024 chars, **no XML tags**. Should contain a
  "use when" clause (the triggering signal). A block scalar (`description: >`) is
  fine — the validator reads it.

**Listing truncation (host-specific).** The Claude Code skill listing truncates the
combined `description + when_to_use` text at 1,536 chars by default (configurable via
`maxSkillDescriptionChars`); another host may differ. That is tighter in practice than
the 1024-char validation limit, so **front-load the key use case**.

## Deterministic code beats prose
A body rule is *likely* to be followed; a script that runs is repeatable. The strong
signals to convert a step into `scripts/`: traces where the agent **skips the step**,
**re-implements the same helper**, or hand-executes a deterministic transform. Write
working code (not a stub), give it a `--self-check` so an edit that breaks it is
caught before rollouts are paid for, and **state execute-vs-read intent** in the body
so the agent runs it instead of reading it. Reserve prose for judgment.

## Organize by variant when the skill spans domains
A selection body plus one reference per variant (`references/aws.md`, `gcp.md`, …),
each linked **directly** from SKILL.md with a what/when pointer, so only the relevant
one is ever read. Keep references **one level deep**: a reference that points at
another reference can be missed when the agent reads only part of the first.

## Measurement is core-owned — do not re-implement it
cap-evolve already owns evaluation and acceptance, so this capability deliberately does
**not** carry skill-creator's own eval harness (`evals.json`, assertions, graders): a
second private eval loop would duplicate — and could contradict — the framework's own.
The one skill-specific measurement it adds is trigger rate
(`scripts/trigger_eval.py`), because a skill that never fires is invisible to task
reward.

## What `validate` decides
- **Fails** (hard problem): no `SKILL.md`; bad/missing `name`; empty/oversize/XML
  `description`; body >500 lines; a broken `references|scripts|assets/…` link; a
  bundled script that does not compile or whose declared `--self-check` fails.
- **Warns**: first-person POV, ALL-CAPS `CRITICAL/ALWAYS/MUST/NEVER`, a description
  near the host listing cap, a body over ~5k tokens (this repo's own heuristic, not a
  skill-creator rule), a nested or orphan reference, a long reference with no real
  table of contents, a stub script, a script with no `--self-check`, and
  network/subprocess/`eval` use in bundled code.

## Sources
- Anthropic Agent Skills docs — overview & best-practices:
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview ·
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- skill-creator skill (anthropics/skills, main):
  https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md
- Claude Code skills docs: https://code.claude.com/docs/en/skills
- Engineering blog, "Equipping agents for the real world with Agent Skills":
  https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
