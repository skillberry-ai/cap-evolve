---
name: hill-climb
description: Runs a global hill-climb optimization loop where the parent is always the current best candidate and the val significance gate decides acceptance. Use as the algorithm for most runs — the first run on a new project, binary pass/fail scorers, and small task sets. Pick how each iteration's reflection is focused with --focus all (every failing val task), cyclic (one task at a time), or hardest-first (lowest-scoring first). Switch to gepa when rollouts are expensive and per-task feedback is rich, or skillopt when you want an annealed edit budget.
component: algorithm
argument-hint: "--run-dir DIR --project DIR --optimizer CMD [--focus all|cyclic|hardest-first]"
allowed-tools: Read, Write, Bash
provides: [candidate]
needs: [scores, traces, candidate]
---

# hill-climb — one loop, three focus schedules

Greedy search over candidates: the parent is always the run's current best, and a
child replaces it only by clearing the val significance gate. The test split is
never touched here — that is `finalize`.

**Requires `baseline` first.** Without `--resume` the loop reads the seed's val
result from `<run-dir>/baseline.json` (`scripts/run.py:121-122`); with no run state
it raises `FileNotFoundError: no run state at .../state.json`. `--resume` instead
reads the current best's val from its stored rollouts, falling back to
`baseline.json` when the run has no best yet (`run.py:118-122`).

## One iteration, end to end

This is the mechanism the other algorithm skills vary; they describe only their
differences and point back here. One iteration is `harness.run_step`
(`core/cap_evolve/harness.py:1409`):

1. **Pick the parent — always the current best** (`harness.py:2224`,
   `run_dir.candidate_dir(run_dir.best_id)`). Copy it to `work/<cand_id>/`; the
   optimizer edits that copy in place, so the parent is never mutated
   (`harness.py:1454-1458`).
2. **Build the prompt.** The parent's val per-task rows are split into
   always-failing / flaky / infra-errored / solid (`harness.py:1775-1795`), rendered
   as the failure index plus an explicit *protect these passing ids* block
   (`harness.py:1803-1879`), and substituted into the project's optimizer-instructions
   template. `--focus` narrows which failures are emphasized; nothing else changes.
3. **Inject context and memory.** Full trajectories, capability guidance, and the four
   cross-iteration files land in the workdir (`harness.py:1062-1094`) — see
   `references/run-step.md`.
4. **Optimize.** The optimizer command mutates the workdir. A crash is caught, logged,
   and left as an unchanged copy of the parent, so the gate simply rejects it — a
   wasted iteration, not a dead run (`harness.py:1486-1500`).
5. **Evaluate on val only** (`harness.py:1516`), at `--n-trials` trials per task.
6. **Gate.** With per-task data on both sides the paired test is chosen automatically:
   accept iff mean per-task Δ > `k`·SE of those paired deltas (`harness.py:1524-1532`).
   `--no-regression` adds a second, harder condition on top.
7. **Commit.** *Every* candidate is snapshotted — accepted and rejected — so any
   iteration can be diffed (`harness.py:1557`); the version store commits it
   (`harness.py:1609-1612`). Only an accepted candidate calls `set_best` and becomes
   the next parent (`harness.py:1558-1559`); a rejected one is filed in the rejected
   memory that feeds the next prompt (`harness.py:1607-1608`).

**Why the parent is always the current best.** The gate already guarantees every
accepted candidate is a real improvement on val, so the best candidate is the only
one with evidence behind it — forking anything else spends budget on a lineage
already known to be worse. The cost is that a candidate which trades one task class
for another can never be kept as a specialist; wanting that is the reason to use
`gepa`, whose per-instance Pareto frontier keeps specialists on purpose.

**Why the bar is Δ > k·SE, not Δ > 0.** Rewards are estimates from a finite sample
of tasks and trials, so about half of all *no-op* edits measure as a small positive
Δ by chance. Accepting on Δ > 0 therefore ratchets on noise: val creeps up, the
sealed test does not move, and the run reports a gain that was never there. The bar
is the noise scale itself, so a win has to be larger than the measurement error that
produced it. `phases/gate` owns the full statement of the decision and its modes.

## Focus schedules

| `--focus` | what each iteration emphasizes | when to use |
|---|---|---|
| `all` (default) | every failing val task — find the one edit that lifts the most | broad capability gaps; the usual choice |
| `cyclic` | one val task at a time, round-robin | many distinct, unrelated failure modes |
| `hardest-first` | val tasks ordered by the parent's per-task reward ascending, then cycling | a few very hard tasks dominate the gap |

All three index the **val** per-task results, because those are the only per-task
data the loop holds. Non-regression protection covers the whole val split under
every schedule, not just the focused task. `hardest-first` costs no extra evaluation:
it orders off the per-task rewards already in hand.

Back-compat: `--focus all-at-once` is accepted and treated as `all` (`run.py:35`).

## Key flags

Beyond `--run-dir` / `--project` / `--optimizer` / `--focus` / `--max-iterations` /
`--n-trials` / `--resume` (`scripts/run.py`):

- `--gate-mode` (default `auto`) + `--k-se` (default `1.0`) — `auto` lets the engine
  pick the paired gate; `significant|paired|strict|threshold` pin it. Raising `k-se`
  makes acceptance stricter.
- `--protected-paths` — globs sealing the eval surface (scorer, gold, tasks, splits;
  `default` expands to the built-in set). A candidate that edits one is *indecisive*,
  never scored: the measurement would grade a compromised harness, so no reward is
  recorded, the stall counter is untouched, and best is unchanged
  (`harness.py:1440-1446`). Leave this on for any run whose number you intend to
  quote.
- `--capabilities` — comma-separated capability skills under optimization. When empty
  the optimizer receives **no** allowed-edit-space block at all
  (`harness.py:1735-1737`), so it guesses the edit surface from the files.
- `--no-regression` — reject a candidate that lowers any val task the parent scored
  higher on, even when the mean improves.
- `--convergence` — graded plateau signal (`ok` → `warn` → `paradigm_shift` → `stop`)
  appended to the prompt, so a plateau escalates the ask instead of burning the
  remaining iterations on more of what failed.
- `--workers N` — concurrent rollouts per evaluation. Only safe when the adapter's
  `run_target` is thread-safe; a shared client, temp path, or cwd will corrupt scores
  rather than fail loudly.
- `--store git|copy|command` (+ `--store-commit-cmd`) — how each iteration is
  versioned; git is the default and every candidate becomes a commit.
- `--instructions-file`, `--bench-repo`, `--capability-sources`, `--optimizer-name`,
  `--target-model`, `--target-profile-file` — prompt and read-context wiring; `cap-evolve
  run` fills these from the spec.

## Standalone use

```bash
python scripts/run.py --run-dir .capevolve/run_X --project .capevolve/project \
  --optimizer 'python .../run-optimizer/scripts/run.py --name mock --workdir {workdir} --prompt {prompt}' \
  --focus hardest-first --max-iterations 10 --n-trials 4 --protected-paths default
```

## Known gate edge case (open, issue #351)

Under the default paired gate with `k_se = 1.0`, a candidate that improves **exactly
one** val task and changes nothing else has `Δ̄ == SE(Δ)` algebraically, so a strict
`>` resolves it on floating-point representation alone. Expect a genuine one-task
gain not to bank, unpredictably by split size. Do not lower `k-se` to work around it —
that disables the bar for every candidate; prefer edits that generalize across a
class of tasks, which is what the loop is asking for anyway.

## Agent mode

When `orchestration_mode: agent`, drive the loop yourself with the same mechanism as
above: parent = current best, one edit per iteration, evaluate on **val**, gate,
accept → snapshot / reject → revert, seal once with the finalize phase script
(`skills/phases/finalize/scripts/run.py`), then report. `orchestrate` owns the
agent-mode rules; the hill-climb-specific obligation
is that you must reproduce the handover surface `run_step` normally builds —
`LEDGER.md`, `JOURNAL.md`, `PROCESS.md`, `RUNMAP.md` + `prior_iterations/` — and carry
rejected edits into the next iteration's prompt. Skip it and the dashboard goes dark
and the optimizer re-proposes edits already refuted.

## References

- `references/run-step.md` — the shared step's exact contract: the handover files and
  their ownership, the rejected/accepted memory, the version store, the snapshot
  filter, and the tamper path. Load it when you need the contract verbatim, or when
  writing an algorithm that reuses `run_step`. The sibling algorithm skills link this
  file rather than this body.
- `references/focus-schedules.md` — how each schedule builds its focus set. Load when
  choosing between the three or debugging a focus set.
