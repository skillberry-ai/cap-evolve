# parsec v6 — G2 arm: global-scope, shared-bundle hill-climb with a held-out test split

**Agent model:** `claude-sonnet-4-6`
**Optimizer model:** `claude-opus-5` (`optimizer_skill: claude-code`, `algorithm_skill: hill-climb`)
**Budget (per `source/state.json`):** `max_iterations: 6` (reached), `stall: 0` (never auto-stopped
on consecutive rejects — overridden mid-run; see "Why 6 iterations" below), `max_usd: 2500.0`,
`max_optimizer_usd: 600.0`, neither exhausted.
**Split discipline:** `split_mode: pooled`, `promotion_rule: P2` — a genuine 3-way split, unlike
every prior parsec arm's `train == train == val` convention. 200 tasks total, split into feedback
(F, 67 tasks, visible to the optimizer), confirm (C, 67 tasks, hidden — the only split the
accept/reject gate reads), and test (66 tasks, sealed, scored exactly once at the end).
**Ledger:** [`results.json`](results.json) (built by
[`../../../scripts/build_v6_g2_results_json.py`](../../../scripts/build_v6_g2_results_json.py)
from the vendored [`source/`](source/) files)
**Heatmap:** [`../../../ui/heatmap_v6_g2_e1.html`](../../../ui/heatmap_v6_g2_e1.html) — test split
only (see below for why)
**Artifacts:** [`../../../artifacts/v6/v6_g2_e1/`](../../../artifacts/v6/v6_g2_e1/) (`seed/`,
`accepted/cand_0002/`, `best/` = `cand_0005`, `rejected/cand_{0001,0003,0004,0006}/`)
**Per-task reports:** [`../../../reports/v6/v6_g2_e1/`](../../../reports/v6/v6_g2_e1/)
(`<task>.md`, 66 files, test split only — generated auto+diff blocks, no hand-written narrative yet)
**Cost/time source:** [`cost_time/`](cost_time/) (`v6_g2_e1_results_table.md`)
**Per-candidate process records:** [`source/process/`](source/process/) (each candidate's own
`PROCESS.md` — the optimizer's required, per-iteration explainability record) and
[`source/LEDGER.md`](source/LEDGER.md) (the framework's own factual accept/reject record)
**Run dir:** `.capevolve/v6_g2_e1/run_g2_e1/` in the `parsec-intake_v6` worktree (not committed
here — see [`source/`](source/) for the vendored subset this report is built from)

## The one-line result

v6_g2_e1 is the first parsec arm to show an accepted candidate's gain survive a genuinely
held-out, sealed test split. After 6 iterations (2 accepted, 2 rejected on the confirm split, 2
killed before reaching it), the final champion `cand_0005` scores **0.8496** on the sealed
66-task test split against the unmodified seed's **0.8126** — **+0.0369 (3.69pp)**, measured
once, after the champion was fixed, with no further tuning possible.

| | F (feedback, visible) | C (confirm, hidden gate) | test (sealed, final) |
|---|--:|--:|--:|
| seed | 0.8300 (67 tasks, 10 trials) | 0.8213 (full re-confirmation, 268 rollouts) | **0.8126** (66 tasks, 10 trials) |
| final champion (`cand_0005`) | 0.8730\* | 0.8046 (full re-confirmation, 268 rollouts) | **0.8496** |
| **Δ vs seed** | +0.0430\* | −0.0167 | **+0.0369** |

\*`cand_0005`'s F figure is its 12-task rung-1 screen score, not a full-67-task measurement (the F
split is never scored whole per iteration, by design — see below); it is not directly comparable
to seed's full-split 0.8300.

**The headline caveat, stated plainly:** the full-sample re-confirmation of `cand_0005` on C
(268 rollouts, all 67 confirm tasks) actually comes in *below* the seed (0.8046 vs 0.8213,
**−0.0167**) — the group-sequential test that accepted it ran on a smaller, early-stopped sample
(the C split's own `val` figure, 0.8728, computed from the sequential test's own paired statistic,
not the full re-confirmation). This is the same pattern seen in prior parsec arms (v4/v5): an
accept decision made on a partial sample doesn't always hold up under the full re-measurement.
**What's different here, and the actual news in this arm, is that the test-split number — sealed,
never touched by the optimizer, scored exactly once — is unambiguously positive.** Whichever of
the C-split numbers you trust, the sealed test result stands on its own.

## Why there's no per-task F/C ledger

Every prior parsec arm's `results.json` has one row per task, with a column per candidate, because
every candidate was scored on the same split every iteration (v4_g_e1: 34 tasks, every iteration).
v6_g2_e1 cannot do this for F or C:

- **F** is screened by a random 12-task **rung**, drawn fresh per iteration from the 67-task
  feedback split, specifically so the optimizer never sees the whole split scored at once (that
  would let it overfit the full F set across iterations). There is no stable per-task F ledger —
  only a per-iteration paired delta over whichever 12 tasks that iteration's rung drew.
- **C** is deliberately **hidden from the optimizer** — its task ids are never exposed anywhere the
  optimizer can read, and the accept/reject gate only returns a bit (accept/reject/kill), not a
  per-task breakdown. Confirming via a group-sequential test at increasing sample size (16, 33, 67,
  133, 200 cumulative) means even the *aggregate* C number is an early-stoppable estimate, not a
  fixed one.

The only split with a stable, full per-task ledger is **test** — scored exactly once, on all 66
tasks, for exactly two candidates (seed and the final champion). That's what `results.json`'s
`task_ledger` and the heatmap show. See `../../../scripts/build_v6_g2_results_json.py`'s own
docstring for the full account.

## Per-iteration record

See [`cost_time/v6_g2_e1_results_table.md`](cost_time/v6_g2_e1_results_table.md) for the full
table (F-screen delta/z, C decision, fixed/broke counts, optimizer cost per iteration). Summary:

| Iter | Candidate | C decision | What it changed |
|---|---|:--:|---|
| 1 | `cand_0001` | reject | A conclusion checklist draft, epoch-conversion repair, cost error-handling — all later folded into `cand_0002`. |
| 2 | `cand_0002` | **accept** | The conclusion checklist (shipped), the icinga epoch/elapsed-time rewrite, cost error-result repair. First champion. |
| 3 | `cand_0003` | reject | Weak F signal (+0.019), didn't survive the confirm-split test. |
| 4 | `cand_0004` | killed at F rung 1 | **Correctly diagnosed** a measurement confound (a 10× different tool-timeout rate between the seed's and the champion's measurement rounds) but the specific candidate shipped still scored below the F-screen threshold. |
| 5 | `cand_0005` | **accept** | Fixed the confound cand_0004 found; rewrote the retry rule for timed-out tool calls; deleted two "MANDATORY" instructions routing to tools served at a measured 0% success rate; fixed a fictional directory layout in `icinga_agent.md`. Final champion. |
| 6 | `cand_0006` | killed at F rung 1 | The most expensive optimizer call of the run (−0.032, the worst F-screen result of any iteration) — diminishing returns once the two highest-leverage fixes were already in `cand_0005`. |

Full narrative for every iteration, including what was tried and reverted mid-iteration, is in
each candidate's own `source/process/<cand>_PROCESS.md`.

## Test-split result, by category

| category | n | seed | champion | Δ |
|---|--:|--:|--:|--:|
| cloud | 9 | 0.7607 | 0.7666 | +0.0059 |
| cost | 10 | 0.8314 | 0.8652 | +0.0338 |
| icinga | 13 | 0.7801 | 0.8001 | +0.0200 |
| platform | 34 | 0.8333 | 0.8859 | +0.0525 |
| **overall** | **66** | **0.8126** | **0.8496** | **+0.0369** |

27 of 66 tasks improved by more than 0.05, 6 regressed by more than 0.05, 33 moved less than that
(not evidence of either direction at this sample size). The single largest move in either
direction is `platform-131-deployment-first-resource-blind-spot`, which regressed 0.3950
(0.985 → 0.590) — worth a transcript read before trusting this champion further; it is not
explained by anything in `cand_0005`'s own `PROCESS.md`, which did not touch that task's cluster.

## Why 6 iterations, not a clean budget stop

This run was extended twice beyond its original plan, on explicit instruction, specifically
because the first two iterations' results (iteration 1 rejected, iteration 2 accepted) looked
too thin to draw a conclusion from: `stall` was raised from 2 to 0 mid-run (so a second
consecutive reject would not auto-stop it), the iteration budget was raised from 5 to 6 after
iteration 4 (a cheap rung-1 kill) suggested there was more signal to find, and the run was
explicitly continued through iterations 5 and 6 regardless of outcome. `cand_0006`'s rejection
(the most expensive iteration, worst result) was the agreed stopping point.

## Data-quality caveats

1. **The sealed test-split `final.json` was reconstructed from completed rollouts, not re-run.**
   The driver that scored test (LSF job 1702040) finished both evaluations — champion as `FINAL`,
   seed as `FINAL_seed`, both logged in `source/events.jsonl` with final rewards — then crashed
   (exit 255, apparent host-level LSF fault) while starting the optional post-test train/val
   bookend. `final.json` was built by re-reading the 1,320 already-written test rollout files on
   disk (the same function cap-evolve's own `--resume` path uses,
   `split_result_from_rollouts()`), not by re-scoring test — the test seal was committed only
   after this reconstruction, and `source/final.json`'s own `reconstruction_note` field records
   this. The train/val bookend never ran and is not included in any report here.
2. **No per-task F/C ledger exists, by design** — see "Why there's no per-task F/C ledger" above.
   Do not expect this arm's heatmap to show F or C columns the way v4_g_e1's does.
3. **`cand_0005`'s full re-confirmation on C (0.8046) is below the seed's (0.8213)**, even though
   the group-sequential test that accepted it read a positive signal on a smaller sample — see
   "The one-line result" above. Read the test-split number as the arm's real headline; the
   confirm-split numbers disagree with each other depending on sample size.
4. **A real bug in the shared report-generator helper was found and fixed while building this
   arm's reports**: `v4_report_common.py`'s `build_report()` used `re.sub(diff_block, text)` with
   `diff_block` as a plain string replacement — `re.sub` interprets backslash sequences in a
   string replacement as regex escapes, so a diffed file containing the literal two-character
   sequence `\n` (as text, e.g. a worked example quoting a JSON/YAML string) was silently turned
   into a real newline on every regeneration. Two of `cand_0005`'s per-task reports
   (`cloud-319-billing-lab-unknown-to-babylon.md`, `cost-050-partial-account-coverage.md`) hit
   this, because `shared_context.md`'s cache-example worked text happens to contain `\n` literally.
   Fixed by passing a lambda instead of a string to `re.sub` (confirmed as a no-op on every
   already-committed v4/v5 report — none of them diff on a line containing a literal backslash
   sequence).

## Next moves (open)

- **Read `platform-131`'s transcript** — the one real regression large enough to investigate before
  trusting this champion for anything beyond this report.
- **Re-run the train/val bookend** for this run if the full seed-vs-champion comparison across all
  three splits is wanted (caveat 1) — cheap (val is free, train is one more eval sweep).
- **A competitor-framework arm** — this report only compares CapEvolve's own optimized bundle
  against the unmodified seed; there is no GEPA/AutoPrompt/other-framework comparison yet.
