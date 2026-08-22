---
name: using-cap-evolve
description: 'Front door for cap-evolve: routes an optimization request to the right pipeline phase. Use when someone wants an agent, skill, system prompt, tool surface, or MCP toolset to score higher on an eval, benchmark, or task suite — "optimize my skill", "raise the pass rate on these tasks", "my agent keeps failing these cases", "get this prompt''s accuracy up on my evals" — even when they never say "optimize", and whenever a .capevolve/ project or an unfinished run is in the tree. Routes to intake, the check gate, a resumed run, or the report; optimizes nothing itself. Not for making code or a query faster, and not for rewording one prompt with no eval to score it against. When the user names a phase or algorithm outright (baseline, gate, hill-climb, gepa), use that skill directly.'
component: orchestrate
argument-hint: "[what to optimize] [--base .capevolve]"
allowed-tools: Read, Bash
provides: []
needs: []
sources: [evo, superpowers]
---

# using-cap-evolve — the router

The front door: it works out *where the user is* and hands off, running no phase and
editing nothing. Boundary: this router picks the door, `orchestrate` drives the run.

## Routing decision
Run from the user's project dir; `S` is the absolute path of the directory you loaded this
SKILL.md from — the one location always known here (no env var is set for a plugin install):
```bash
S=<this skill's own directory>; python "$S/scripts/run.py" --base .capevolve
```
Follow `next`; pass `reason` on to the user. Two things the JSON cannot say for itself:
- On a fresh request go through `intake`, and if an input it needs is missing, ask the
  user for it rather than inventing one (`intake` owns that rule).
- An existing run is never restarted from zero: interrupted → `cap-evolve run --resume`;
  sealed and the user wants another attempt → `cap-evolve run --reuse-baseline <run dir>`.

## Three ways to run — `orchestrate` has the detail
1. **Phase chain** — `/cap-evolve:<phase>` turn by turn, so each step is inspected.
2. **Deterministic** — `cap-evolve run --spec .capevolve/project/capevolve.yaml`
   sequences the check gate → baseline → algorithm → finalize → report. It presumes
   intake already happened; it does not run intake.
3. **Agent handoff** — with `orchestration_mode: agent`, `cap-evolve run` stops after
   baseline and hands the loop back to you; no sealed-test number until you finalize.

No plugin, or a non-Claude host: follow `RUN.md` step by step. Same engine, same rules.
