---
name: implement-and-check
description: The HARD GATE that must pass before any optimization budget is spent. Use right after intake. Walks the agent through implementing the 4 adapter methods (and any selected skill's abstract methods), then runs `cap-evolve check` on the project plus each involved skill's check.py, refusing to proceed until everything is implemented and deterministic — and listing exactly what is still stubbed.
component: phase
argument-hint: "--project .capevolve/project --skill-check PATH"
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
- **needs:** `project` — the scaffolded `.capevolve/project/` from intake.
- **provides:** `checked` — the proof that the adapter (and any involved skill)
  is fully implemented and deterministic. `baseline` will not run without it.

## Steps
1. **Implement the four adapter methods** in
   `.capevolve/project/adapters/adapter.py` (see `docs/ADAPTER_CONTRACT.md`):
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
   python scripts/run.py --project .capevolve/project \
       --skill-check <skills>/capabilities/<cap>/scripts/check.py
   ```
   It runs `cap-evolve check` (adapter: no stubs, `tasks` non-empty + stable, scorer
   deterministic, `apply` callable) and each named skill's `check.py`. **Exit 0 =
   green; the JSON lists exactly what is still stubbed or non-deterministic.**
4. **Pipeline-wiring self-test (runs automatically once the check is green).** A
   green adapter is necessary but not sufficient — the optimizer also needs its
   *context* wired. After the check passes, `run.py` runs `pipeline_selftest.py`,
   a cheap, benchmark-agnostic check (no API cost) that asserts the plumbing the
   optimizer depends on:
   - the optimizer-prompt template is scaffolded at `optimizer/INSTRUCTIONS.md`
     and still carries its `{{...}}` placeholders (intake must not delete them);
   - `capevolve.yaml::optimizer_instructions_file` points at a file that EXISTS;
   - rendering that template through the REAL harness renderer leaves NO `{{`
     placeholder behind (every dynamic block substitutes);
   - the adapter either DEFINES `trajectories()` (native traj dir → copied verbatim
     into the optimizer's `./trajectories/`) or intentionally inherits the base
     default (cap-evolve falls back to its per-rollout JSON) — both valid, reported.

   It reports the precise missing/broken artifact so you can iterate until green.
   (Pass `--no-pipeline-selftest` to skip it; run it standalone with
   `python scripts/pipeline_selftest.py --project .capevolve/project`.)

   A full one-iteration mock run is intentionally NOT done here: it would need a
   baseline + frozen split + run dir that do not exist yet at gate time, and those
   are benchmark-specific. This self-test exercises the same workdir-building and
   prompt-rendering code paths instead — the wiring an optimizer actually consumes.

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

## Dual-mode
This phase runs two ways from the **same** SKILL.md: standalone as the slash command `/cap-evolve:implement-and-check` (the `argument-hint` shows its run.py args), and orchestrator-callable — `cap-evolve run` / the `orchestrate` skill invokes the same `scripts/run.py` headlessly and threads the run dir between phases.

## References
- `references/concepts.md` — the adapter contract, why each check exists, the
  scorer-determinism-vs-target-stochasticity distinction, and the
  validation-gate-before-budget rationale, with sources.
