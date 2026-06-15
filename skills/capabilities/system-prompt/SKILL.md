---
name: system-prompt
description: Optimize an agent's system prompt or policy text — the instructions that shape its behavior. Use when the thing you want to improve is a prompt/policy file (not tools or a skill package). Covers what is safely editable, how prompt wording changes agent behavior, common failure modes (over-long preambles, conflicting instructions, missing output contracts), and what to measure. Provides concrete materialize/apply/validate handlers for prompt artifacts.
component: capability
argument-hint: "--path DIR"
allowed-tools: Read, Write, Edit, Bash
provides: [candidate]
needs: []
sources: [tau2bench]
---

# Capability: system prompt

The system prompt is the cheapest, highest-leverage parameter of most agents: a
few words can flip success on a whole class of tasks. This capability treats one
or more prompt/policy text files (`prompt.txt`, `policy.md`, `SYSTEM.md`) as the
optimizable artifact.

## What can be optimized
- **Task framing & role** — who the agent is and what "done" means.
- **Output contract** — exact format the downstream/eval expects (a frequent
  silent failure: the agent is *capable* but formats wrong).
- **Decision policy** — when to call which tool, when to ask vs. act, refusal
  rules (tool/customer-service agents are scored on following such a policy).
- **Few-shot exemplars / reasoning scaffolds** — added inline.

## How agents use it
The prompt is prepended to context every turn. Agents read it literally and are
sensitive to ordering, contradictions, and verbosity. Long preambles dilute
attention; conflicting instructions resolve unpredictably.

## Common problems (see references/pitfalls.md)
- Over-long, redundant instructions → worse, not better.
- Missing/loose output contract → correct content, wrong shape, zero reward.
- Instructions that fight the model's defaults → inconsistent behavior.

## Handlers (scripts/abstract.py)
`materialize(dir) -> {file: text}` · `apply(dir, edits) -> report` ·
`validate(dir) -> {ok, files, problems}`. Edit ops: `set`, `append`,
`ensure_contains`. A project adapter's `apply` can call these directly.

## How to run
```
python scripts/check.py
python scripts/run.py --path <capability_dir>     # prints the candidate + validity
```

## References
- `references/concepts.md` — why prompts are high-leverage; what to optimize; pitfalls.
