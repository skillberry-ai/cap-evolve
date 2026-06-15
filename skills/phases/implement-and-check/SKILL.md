---
name: implement-and-check
description: The HARD GATE that must pass before any optimization budget is spent. Use right after intake. Walks the agent through implementing the 4 adapter methods (and any selected skill's abstract methods), then runs `acapo check` on the project plus each involved skill's check.py, refusing to proceed until everything is implemented and deterministic — and listing exactly what is still stubbed.
component: phase
argument-hint: "--project .agentcapo/project --skill-check PATH"
allowed-tools: Read, Write, Edit, Bash
provides: [checked]
needs: [project]
sources: [skillopt]
---

# implement-and-check — make the contract real

Optimizing against a half-wired adapter produces a number that means nothing: if
the scorer is a stub, every candidate scores the same; if `tasks()` is empty, the
mean is computed over nothing; if `run_target` is non-deterministic in a way the
scorer can't see, the gate chases ghosts. This phase is the **hard gate** that
ensures the contract holds *before* a single unit of budget is spent. It is
cheaper to fail here than after a full optimization run.

## Inputs / outputs (manifest tokens)
- **needs:** `project` — the scaffolded `.agentcapo/project/` from intake.
- **provides:** `checked` — the proof that the adapter (and any involved skill)
  is fully implemented and deterministic. `baseline` will not run without it.

## Steps
1. **Implement the four adapter methods** in
   `.agentcapo/project/adapters/adapter.py` (see `docs/ADAPTER_CONTRACT.md`):
   - `tasks(split)` — yield the evaluation tasks (non-empty, stable across calls).
   - `run_target(task, capability)` — run the agent under test; capture output +
     trace into a `Rollout`.
   - `score(task, rollout)` — return a reward in `[0,1]` + general feedback (no
     gold-answer leakage — it becomes the diagnosis signal).
   - `apply(capability, edit)` — materialize a proposed edit onto a copy.
2. **Implement any selected skill's `scripts/abstract.py`** (most are concrete and
   need nothing).
3. **Run the gate:**
   ```
   python scripts/run.py --project .agentcapo/project \
       --skill-check <skills>/capabilities/<cap>/scripts/check.py
   ```
   It runs `acapo check` (adapter: no stubs, `tasks` non-empty + stable, scorer
   deterministic, `apply` callable) and each named skill's `check.py`. **Exit 0 =
   green; the JSON lists exactly what is still stubbed or non-deterministic.**

## What the check actually verifies (and why)
- **No stubs** — a `NotImplementedError`/`pass` body means the method silently
  returns nothing; the resulting score is meaningless.
- **`tasks` non-empty and stable** — an empty or shuffling task set makes the
  mean and the split irreproducible.
- **Scorer determinism** — score the same rollout twice; differing rewards mean
  the "reward" includes scorer noise the optimizer cannot learn from. (Target
  *stochasticity* is fine and is handled by multi-trial evaluation; *scorer*
  nondeterminism is a bug.)
- **`apply` callable** — an edit that cannot be materialized cannot be evaluated.

## Do not proceed until green
If it reports stubs or non-determinism, fix them and re-run. This is the standard
validation-gate discipline for self-improving systems: prove the measurement
apparatus works before you trust any measurement it produces. A green check is
the only honest entry into `baseline`.

## What good vs bad looks like
- **Good:** `{"ok": true}` with all four methods concrete, a deterministic scorer,
  and every involved skill's check green.
- **Bad:** proceeding on a red check "to save time"; a scorer that returns
  different rewards for the same rollout; an empty/placeholder `tasks()`; feedback
  that leaks the gold answer (passes the wiring check but corrupts diagnosis).

## References
- `references/concepts.md` — the adapter contract, why each check exists, the
  scorer-determinism-vs-target-stochasticity distinction, and the
  validation-gate-before-budget rationale, with sources.
