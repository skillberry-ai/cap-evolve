# Concepts — optimizing a skill package

> The authoring model below is first-party (Anthropic Agent Skills docs +
> skill-creator + the engineering blog; see Sources). When the optimizer edits a
> skill package, these are the rules that make the edit a *better skill*, not just
> different text. Sibling references:
> [`description-optimization.md`](description-optimization.md) (the trigger lever)
> and [`anti-patterns.md`](anti-patterns.md) (what not to do).

## What a skill package is
```
skill-name/
├── SKILL.md          (required: YAML frontmatter + Markdown body)
├── references/*.md   (docs loaded on demand)
├── scripts/          (executables; code never enters context, only output)
└── assets/           (templates/icons used in output)
```

## Progressive disclosure (the core idea)
Skills use a **three-level loading model**; optimize for the cheapest that works:

1. **Metadata** (`name` + `description`) — **always** loaded at startup into the
   system prompt, ~100 tokens per skill. The `description` is the **primary
   triggering mechanism**: it must say WHAT the skill does AND WHEN to use it.
2. **SKILL.md body** — loaded **when the skill triggers**, then it **stays in
   context for the rest of the session** (a recurring cost). Target **<500 lines /
   under ~5k tokens**. When it grows, move detail into `references/` and point to it.
3. **Bundled resources** — references and scripts, loaded/executed **only as
   needed**, effectively unlimited. A script runs via bash **without its code
   entering context** — only its *output* costs tokens. A reference file costs
   **zero** context until actually read.

## Frontmatter rules (hard invariants)
Two required fields, both validated:
- **`name`**: ≤64 chars, lowercase `[a-z0-9-]` only, **no XML tags**, no reserved
  words (`anthropic`, `claude`).
- **`description`**: non-empty, ≤1024 chars, **no XML tags**. Should contain a
  "use when" clause (the triggering signal).

**Listing truncation.** In the Claude Code skill listing the combined
`description + when_to_use` text is truncated (default 1,536 chars, configurable via
`maxSkillDescriptionChars`). This is tighter in practice than the 1024-char
validation limit, so **front-load the key use case** — put the most important
trigger words first, before they can be cut.

## Description-as-trigger optimization (a separable, measurable step)
See [`description-optimization.md`](description-optimization.md) for the full
playbook. In short: write **third person**, include the **keywords users actually
say**, lean slightly pushy (Claude tends to *under*-trigger); fix over-triggering
by making the description **more specific**, not by adding ALL-CAPS. Select the
description by **held-out** trigger score, not the iteration examples.

## What the optimizer should change (and how)
- **Sharpen the `description`** for triggering — the highest-leverage edit.
- **Tighten the body**: imperative voice; **state what to do, don't narrate** the
  why at length (every body line is a recurring token cost). Explain a rule's
  reasoning briefly rather than piling on ALL-CAPS MUSTs — today's models follow
  reasoning better than rigid rules.
- **Generalize, don't overfit** to the eval tasks — a skill is used many times.
- **Factor repeated work into `scripts/`**: a strong signal is traces where the
  agent independently **re-implements the same helper**, or a deterministic step.
  Code is repeatable where prose is only *likely*; **state execute-vs-read intent**.
- **Organize by domain** when multi-framework: a selection body + one reference file
  per variant linked **directly** from SKILL.md, so only the relevant one is read.
  Keep references **one level deep** with an explicit "what/when to load" pointer.

## How to optimize honestly (the loop)
Skill optimization is **empirical**: observe how Claude actually triggers and
follows the skill, cluster the failures, make one targeted edit, and **keep it only
if it raises the objective score on a held-out split**. This mirrors ACE's
generation → reflection → curation of an evolving playbook, and it is exactly the
cap-evolve discipline: propose → `evaluate` on val → `gate` on significance →
`finalize` once on sealed test. Never select on the training/iteration examples.

## Validity rules enforced by `validate`
- `name`: ≤64 chars, `[a-z0-9-]`, no XML tags, no "anthropic"/"claude".
- `description`: non-empty, ≤1024 chars, no XML tags, ideally a "use when" clause.
  Warns on first-person POV, all-caps CRITICAL/ALWAYS/MUST/NEVER, and length near
  the 1,536 listing cap.
- body ≤ ~500 lines AND ~5k tokens (else: split into references).
- references one level deep; long references (>300 lines) start with a TOC.
- files the body links to (`references/…`, `scripts/…`) must exist.

## Sources
- Anthropic Agent Skills docs — overview & best-practices:
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview ·
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- skill-creator skill (anthropics/skills, main):
  https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md
- Claude Code skills docs: https://code.claude.com/docs/en/skills
- Engineering blog, "Equipping agents for the real world with Agent Skills":
  https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills

## The four optimization layers (this capability owns Description + Snippets)
A skill decomposes into four independently optimizable layers. This capability edits
the first two; the others live in sibling capabilities:

| Layer | What | Optimize for | Owner capability |
|---|---|---|---|
| 1. Description | when to trigger | discoverability, precision/recall | this capability (`description`) |
| 2. Snippets | how to do the task (body + references) | reasoning, token cost, fewer hallucinations | this capability (body/refs) |
| 3. Tools | executable capabilities | invocation accuracy, latency | the `tools` / `mcp-tool` capability |
| 4. Tool implementation | internal code | reliability, runtime | the `tools` capability (`code`) |

Routing a failure to the right layer is the core move: **retrieval/routing wrong →
fix the Description; reasoning/workflow wrong → fix the Snippets; capability missing
or hard to call → fix the Tools; slow/unreliable execution → fix the Implementation.**
This mirrors cap-evolve's own loop: identify the target layer → make one targeted
edit → `evaluate` on val → `gate` → keep or roll back.

## Snippet-organization patterns (Layer 2)
The body and references are *instructional snippets* — they teach the agent how to
work. High-leverage patterns:
- **Split one giant document into focused snippets.** Instead of one long README,
  organize into named sections/references the agent loads only when relevant
  (Overview · Reading content · <the hard workflow> · Troubleshooting · Limitations ·
  Examples). Lower context, faster reasoning, cheaper inference.
- **Decision trees** — teach *when* to use each workflow with a compact branch:
  `Need only text? → convert to Markdown.  Need comments? → read the XML.  Need
  animations? → use the XML workflow.` A branch table steers selection better than a
  paragraph.
- **Failure-handling / recovery blocks** — state the recovery, not just the happy
  path: `If unpack.py is unavailable: 1) search for unpack.py  2) validate the ZIP
  3) retry extraction.`
- **Example quality** — examples should resemble *real* user requests, not toy
  fragments. `Extract XML.` is weak; `If the user asks to modify speaker notes, first
  unpack the presentation and edit ppt/notesSlides XML.` teaches the actual mapping.
- **Redundancy removal** — repeated instructions cost tokens every trigger;
  consolidate duplicate guidance into one place.

## Metrics for snippets (Layer 2)
Success rate · token consumption · tool-selection accuracy · hallucination rate ·
time-to-completion. A snippet edit is an improvement only if it moves the objective
on the held-out val split without inflating body token cost.
