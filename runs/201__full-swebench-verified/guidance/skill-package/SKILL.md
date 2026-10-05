---
name: skill-package
description: Optimize an Agent Skill package itself — its SKILL.md (frontmatter + body), its references, and its bundled scripts. Use when the capability under optimization IS a skill, you want the downstream agent to trigger it correctly and follow it without wasted steps, or you want a step the agent keeps skipping turned into deterministic bundled code. Checks every edit against the skill-creator authoring rules (valid frontmatter, progressive disclosure, one-level references, body budget, scripts that compile and self-check) so a candidate stays a valid, runnable skill.
component: capability
argument-hint: "--path DIR"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: []
sources: [agentskills, skillgrad, trace2skill]
---

# Capability: skill package

The artifact is a whole skill directory — `SKILL.md` plus `references/`, `scripts/`
and `assets/` — and **all of it is editable**: `materialize()` exposes every file as
a component, `apply()` can rewrite or CREATE one (a new bundled script included), and
`validate()` checks the result against the **skill-creator** authoring rules
(first-party sources in [`references/concepts.md`](references/concepts.md)).

## What you can change (highest leverage first)

Pick the lever that fixes the biggest failure cluster; depth is in the references.

1. **The `description` / trigger** — the only text loaded before the skill fires, so
   the single highest-leverage edit. Third person; state **what** it does AND **when**
   to use it; use the **keywords a user would actually say**. Lean slightly pushy for
   under-trigger, tighten the boundary and name near-miss cases for over-trigger, and
   **front-load the key use case** (hosts truncate the listing — 1,536 chars on Claude
   Code by default). *Ex:* "Formats data" → "Exports records to CSV. Use when the user
   asks to export or download a table." Playbook + the measurable loop:
   [`references/description-optimization.md`](references/description-optimization.md).
2. **A skipped step → a bundled script** (the determinism lever). Prose is only
   *likely* to be followed; code that runs is repeatable. When the traces show the
   agent skipping a step, re-deriving the same helper, or doing a deterministic
   transform by hand, **write it into `scripts/` and make the body invoke it** by
   command line. Write real, working code — never `...` or a docstring-only stub —
   give it a `--self-check` entry point (`validate()` runs it, so a broken script is
   caught before any rollout is paid for), and say **execute, don't read**: a script's
   source never enters the agent's context, only its output.
3. **The body** — improve clarity and altitude, delete dead weight, fix the
   instruction the agent misreads. The body loads on every trigger and stays in
   context all session — a recurring cost — so keep it **≤500 lines** (enforced),
   imperative, and explain a rule's *why* briefly instead of piling on ALL-CAPS MUSTs.
4. **References** — move mutually-exclusive or rarely-co-used detail into
   `references/*.md`. Keep them **one level deep** (a ref must not point at another
   ref — the agent may read only part of it), link each **directly from SKILL.md with
   a pointer saying what it holds and when to load it**, and give a long ref (>300
   lines) a table of contents **at the very top, above any orientation prose** — the
   check is positional because a TOC the head-reader never reaches is not a TOC.
   Multiple variants/domains → one ref per variant (`references/aws.md`, `gcp.md`, …)
   plus a selection body, so only one is read.
5. **Assets** — `assets/` holds files the skill *emits* (templates, icons, fonts),
   not context the agent reads. Edit one only when the skill's output depends on it.

> **Every edit must leave a valid skill.** `validate()` fails a candidate on: no
> `SKILL.md`; `name` missing/>64 chars/not `[a-z0-9-]`/containing an XML tag;
> `description` empty/>1024 chars/containing an XML tag; a body over 500 lines; a
> broken `references|scripts|assets/…` link; a bundled script that does not compile or
> whose `--self-check` fails. It *warns* on the softer authoring smells (POV drift,
> ALL-CAPS in the description, orphan or nested references, a missing TOC, a stub
> script, a script with no self-check, network/subprocess use in new code). A skill is
> executable context: keep bundled code auditable and free of surprises.

## Adapting to the reader's capability tier
Scale body density to WHO follows it at runtime (see the `THE READER` block in your
instructions, if present). A **mid/weak** reader needs more worked steps, explicit
ordering, and examples in the body — and benefits most from lever 2, since code it
executes cannot be skipped the way a rule can. A **frontier** reader follows a
compact, principle-first body and is slowed by over-specification. The tier changes
how *explicit* the retained body is, not how *long* it may be.

## Trigger rate is a second objective
Task reward is the gate signal, and cap-evolve owns that machinery — do not add a
private eval loop here. But triggering is invisible to task reward when the skill never
fires, so measure it separately with `scripts/trigger_eval.py` on a held-out set of
should-trigger / should-NOT-trigger prompts (with near-miss negatives) and keep the
description that wins on the **held-out** half.

## How to run
```
python scripts/check.py                            # self-test (must pass)
python scripts/run.py --path <skill_dir>           # candidate + validity report
python scripts/token_report.py --path <skill_dir>  # budget + script inventory
python scripts/trigger_eval.py --eval-set <json> --skill <dir> --judge-cmd '<cmd>'
```
Handlers in `scripts/abstract.py`: `materialize(dir)` → every file as a component ·
`apply(dir, edits)` → `{changed, refused}`, contained to the package and gated by the
action policy (`policy.json`: `frontmatter|body|reference|script|asset|add|remove`,
so a run can allow prose but forbid new code) · `validate(dir)` → `{ok, problems,
warnings, scripts}`.

## References
- [`references/concepts.md`](references/concepts.md) — the authoring model and the
  validity rules, with first-party sources. Load for grounding.
- [`references/description-optimization.md`](references/description-optimization.md)
  — the trigger-tuning playbook. Load when fixing under/over-trigger.
- [`references/anti-patterns.md`](references/anti-patterns.md) — skill smells and the
  why. Load when a draft "feels off" or to review an edit.
