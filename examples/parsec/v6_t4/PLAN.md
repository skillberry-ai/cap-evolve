# v6_t4_e1 — merging the v6_t2 task edits into one bundle

v6_t2_e1 produced 34 task-specific bundles, one per feedback task, each reaching 1.0 on its own
task. v6_t4 merges them into ONE deployable bundle and scores it on held-out data, so T can be
compared with G (v6_g2_e1's cand_0005) on the same split. Decided with the author on 2026-10-21.

## The rule that keeps T separate from G

**No merge method may see an evaluation result during the merge.** A method that read F or C
scores while combining edits would be optimizing the shared bundle against a global objective,
which is what G does. Each merged bundle is built blind, frozen, and only then evaluated.

The one score that enters is inherent to T and fixed before merging: each task's edit was chosen
by that task's own optimization. Method 1 additionally uses the per-task gains T already recorded,
only to fix the merge order in advance. Nothing is measured during any merge.

## Inputs

34 diffs against the Seed (188 hunks over 7 of the 8 files; `ocpv_agent.md` untouched). About half
the hunks overlap a hunk from another task: 97–101 of 188 depending on the overlap rule, 61% of
the added lines. Only 2 of the 34 edits are entirely conflict-free. Hotspots: `shared_context.md`
(24 tasks touch it) and `aap2_agent.md` (15).

## The three methods (run in this order)

| # | Method | Rule | Judgment? |
|--:|---|---|---|
| 3 | **Smart merge** | An LLM merger, as a human integrator would, combines all 34 edits by meaning: dedupes overlapping rules, reconciles conflicts, keeps every task's intent. It reads only the Seed, the 34 diffs, each task's instruction and its PROCESS.md rationale **with every score scrubbed out**. Every decision is logged. | yes, no scores |
| 1 | **Merge by order** | Apply the 34 diffs one after another, `git merge -X theirs` semantics: a later diff wins any region it contests. Order: ascending absolute gain (T2 best − Seed), so the highest-gain edit lands last; ties broken by task name. (Error reduction is 1.0 for all 34 tasks, so it cannot rank them.) | none |
| 2 | **Non-conflicting hunks** | Keep every hunk no other task touches; drop every contested hunk. Hunk-level, not task-level (task-level would keep only 2 of 34 edits). | none |

Method 3's merger is a separate agent that has never seen the run's scores. A session that ran
v6_t2 cannot merge blind, because it has read every task's results.

## Evaluation (after all three bundles are frozen)

| | Tasks | Trials/task | Why |
|---|--:|--:|---|
| F (feedback) | 67 | 3 | what the merge does to the tasks T optimized, and to the ones it did not |
| test (sealed) | 66 | 3 | the held-out comparison with G and the Seed |
| C (confirm) | — | — | not used |

3 trials is a first look: enough to see a clear gain or a clear failure in a split mean (estimated
paired 95% interval about ±0.04–0.05), not enough for per-task claims (two sweeps of one bundle differ by
about 0.1 per task). Add trials later to a method whose result is borderline. Compare each method
with the Seed's existing 10-trial F and test numbers (v6_g2_e1), paired by task.

About 400 trials per method (~$100 at ~$0.25/trial), so ~$300 for all three.

**Execution:** one LSF job per task, on its own node (the h4 pattern, `examples/parsec/RUN_H4.md`),
at most 20 concurrent. No shared lane queue.

## Files

- `results/v6_t4_e1/merge_inputs/`: `seed/` (8 files) and `tasks/<task>/{edit.diff, instruction.md,
  PROCESS.md}`. PROCESS.md has every score, reward, trial count and percentage removed.
- `results/v6_t4_e1/m3_smart/`, `m1_order/`, `m2_nonconflict/`: each merged bundle plus its merge log.
