---
name: using-cap-evolve
description: Entry-point router for cap-evolve. Use the moment a user asks to OPTIMIZE an agent capability against an eval — "optimize <X>", "make <X> score higher on <benchmark>", "improve this skill/tool/prompt". Decides whether a project already exists and routes accordingly: to intake (Phase 1) for a fresh request, or straight into the phase chain / `cap-evolve run` when `.capevolve/project/` is already scaffolded. Explains the two ways to run (standalone `/cap-evolve:<phase>` chain vs the fully-automatic `cap-evolve run`) and restates the non-negotiable honesty rules. Does no optimization itself.
component: orchestrate
argument-hint: "[what to optimize] [--base .capevolve]"
arguments: "$ARGUMENTS"
allowed-tools: Read, Bash
provides: [report]
needs: [project]
sources: [evo, superpowers]
---

# using-cap-evolve — the router

This is the front door. When someone says **"optimize \<X\>"**, you land here
first. The router does not run any phase — it figures out *where the user is* and
sends them to the right next step, then gets out of the way.

## Routing decision
Run the resolver to see the current state and the recommended next command:
```bash
python scripts/run.py "$ARGUMENTS" --base .capevolve
```
It prints `{state, next, sequence, ...}`:
- **state `fresh`** (no `.capevolve/project/`): route to **`/cap-evolve:intake`** —
  it interviews the user, scaffolds the project, and gathers inputs. Never skip
  intake on a fresh request; never fabricate a NEEDED input.
- **state `scaffolded`** (`capevolve.yaml` exists, check not yet green): route to
  **`/cap-evolve:implement-and-check`** and stop at the hard gate
  (`cap-evolve check` must print `{"ok": true}`).
- **state `ready`** (check green): offer the two run modes below.
- **state `running`/`finalized`**: route to **`/cap-evolve:report`** for status /
  the sealed-test result.

## Two ways to run (both honest, same engine)
1. **Standalone phase chain** — drive it turn by turn, inspecting each step:
   `/cap-evolve:intake` → `/cap-evolve:implement-and-check` →
   `/cap-evolve:baseline` → `/cap-evolve:<algorithm>` (e.g. `hill-climb`, `gepa`,
   `skillopt`) → `/cap-evolve:finalize` → `/cap-evolve:report`.
   Use when you want to review each phase, or to run just one phase.
2. **Fully automatic** — `/cap-evolve:orchestrate --execute`, or directly:
   ```bash
   cap-evolve run --spec .capevolve/project/capevolve.yaml
   ```
   Sequences every phase, enforces the hard gate before spending budget, decides
   when to stop (budget/stall), and ends with the sealed-test number.

Host-agnostic fallback (no plugin / non-Claude host): point the agent at
`RUN.md` and follow it step by step. Same rules, no Claude-only features needed.

## The non-negotiable rules (restated; enforced by core + hooks)
- Split train/val/test once, seeded; **test is scored only at finalize**, once.
- Accept on **val** by significance, never on the data the optimizer edited.
- Do **not** edit `splits.json`, `rollouts/test/*`, or `*test*gold*` files —
  the plugin's PreToolUse hook blocks it; the seal lives in core.
- An iteration may not "finish" while `cap-evolve check` is red (Stop hook).

## References
- `references/routing.md` — the state machine, the session-start injection JSON
  shape, and how this router relates to `orchestrate`.
