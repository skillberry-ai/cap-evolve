---
name: <skill-name>
description: <One paragraph. WHAT this skill does and WHEN an agent should reach for it. This is the host's activation signal, so be concrete and self-contained — an agent decides whether to load the skill from this text alone.>
component: phase            # one of: phase | capability | algorithm | optimizer | orchestrate
argument-hint: "[key=value ...]"     # optional: how the skill is parameterized
allowed-tools: Read, Bash, Edit, Write, Glob, Grep    # optional: tools this skill needs
provides: []                # tokens this skill produces (e.g. scores, traces, candidate)
needs: []                   # tokens this skill consumes (resolved against other skills)
sources: []                 # citations grounding the claims (urls or sources.bib keys)
---

# <Skill Title>

> One-sentence statement of what running this skill accomplishes.

## When to use this skill
Concrete triggers. What situation in the pipeline calls for it.

## Inputs
Read `inputs/INPUTS.md`. For every input marked **NEEDED** that is not already
present, **ASK THE USER** — quote the expected path, the command/options to
obtain it, and any alternatives — and do not fabricate it. **RECOMMENDED** inputs
may be skipped, with a logged note.

## What you must implement
The optimizer agent implements the abstract methods in `scripts/abstract.py`
(or confirms the project adapter already covers them). Then run `scripts/check.py`
— it refuses until every method is real and deterministic, and tells you exactly
what is still stubbed.

## How to run
```
python scripts/check.py        # gate: must pass first
python scripts/run.py <args>   # executes the step; prints a JSON result to stdout
```
The JSON on stdout is the contract surface — downstream skills (and hosts that
can't import Python) consume it directly.

## References — load only when you need them
- `references/concepts.md` — grounded background and the reasoning behind the design.
- `references/examples.md` — concrete worked examples.
- `references/pitfalls.md` — failure modes and important points to watch.

## Prompt
`prompt/PROMPT.md` is the prompt template handed to the using-agent when this
skill drives a model step. Fill its `{{placeholders}}` from the inputs.
