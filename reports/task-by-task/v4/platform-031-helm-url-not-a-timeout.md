# platform-031-helm-url-not-a-timeout

<!-- BEGIN:auto -->

**task:** `platform-031-helm-url-not-a-timeout`  
**category:** platform  
**tranche:** challenge  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-031-helm-url-not-a-timeout/run_20260920_230721` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.677 |
| our baseline (v4_t1_e1) | test | 3 | 0.794 |
| seed (val, v4_t2_e1) | val | 5 | 0.441 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.860 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 0.965 |

delta vs JB: 0.288 · delta vs our baseline: 0.171

**T2 cost/time:** $26.42, 2,985,624 tokens, 2.54h (eval $9.00/2,791,144tok · optimizer $17.42/194,480tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-031-helm-url-not-a-timeout/run_20260920_230721/report.md`, `.capevolve/v4_t2_e1_platform-031-helm-url-not-a-timeout/run_20260920_230721/JOURNAL.md`

<!-- END:auto -->

## What this task is about

An AAP2 job failed on a Helm-chart download that retried ten times and gave up with a read timeout -- the obvious read is that something upstream was unreachable. The task requires checking whether anything else was downloading from the same host in that window and reading the role's own defaults to see how the failing URL is actually composed, to find the real, more specific cause.

## What the optimizer tried

Two iterations, both confined to `aap2_agent.md` alone — `orchestrator.md` and `shared_context.md` were untouched in both, because routing was already correct in every rollout. `cand_0001` made 12 edits (labeled A–L in JOURNAL.md): a numeric tool-call budget (checkpoint at call 12, ≤4 calls to locate one file); deleted the line gating Splunk as merely "supplementary" and made `search_by_guid` mandatory before naming a root cause against an external target, plus a new "Searching FOR contrast" section banning `errors_only=true` when looking for what else happened; a new Step 7a "Timeouts, Retries and Dead Dependencies" stating that exhausted retries are evidence *against* transience and that transience needs positive evidence or the answer should say undetermined; fixed a `Long = timeout` table row and an `Increase timeout` fix row that had licensed the wrong conclusion; corrected an owner table (`rhpds` → `agnosticd`) that contradicted the file's own other two references, plus a 3-step owner-resolution order; and a new Step 6b for deriving a failing config value from its variables rather than inventing one. `cand_0002` (the winner) made a further, disjoint set of edits in the same single file: it removed both of `cand_0001`'s own "state the limit" / negation-teaching paragraphs and replaced them with an affirmative fourth investigative question (fault duration and attempt consistency); renamed the output-contract's `**Ruled out:**` heading to `What the evidence settles:` and `**Evidence:**` to `How you determined it:`; added a "Name the evidence, never the hypothesis" section with a WRONG/RIGHT table covering violations in both polarities; added a pre-send gate; and fixed a pre-existing Splunk worked example that itself modeled the exact banned negation ("not the host, not the network").

## Why the winning candidate won

`cand_0001` was accepted first, moving val 0.441 → 0.860 (Δ+0.419). JOURNAL.md's diagnosis of the residual after that move found ~68% of the remaining loss concentrated in one forbidden item — the word "transient", present in 5/5 trials — and traced the cause to `cand_0001`'s own text: a rule reading "Only call a failure transient ... when you have positive evidence of transience" plus an output slot literally named `**Ruled out:**`. In every trial the agent wrote a correct evidence sentence and then appended a denial of the label, and because the checker's forbidden-substring match has no polarity handling, a denial scores identically to an assertion. `cand_0002` won by removing the rule that named the label at all (rather than tightening it further) and renaming the output slot that had been generating the denials — JOURNAL.md notes this refutes, by measurement, the general idea that "telling the agent when it *may* use a forbidden word" is ever safe. That fixed the `transient` item 5/5 and one other item (`mirror-outage`) 1/5, moving val 0.860 → 1.000 (Δ+0.140) — and unlike most of this batch's individual moves, the RESULT line for this one explicitly reports `fixed={platform-031-helm-url-not-a-timeout}` rather than `unresolved`. On the held-out test split, `report.md` records the baseline `seed` skills at 0.317 ± 0.094 versus the optimized skills at 0.965 ± 0.021 — a test-side improvement of +0.648. This task's val-seed score (0.441) is well above its test-seed score (0.317); the two splits disagree substantially, so the val-side improvement number is not a stand-in for the test-side one.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning. `report.md` itself flags a nonzero val→test gap of +0.035 (best val 1.000 vs. held-out test 0.965) as "selection optimism on val", and separately reports low run-to-run consistency on test (pass^1=0.600, pass^2=0.300). The auto block's "delta vs our baseline" figure above (0.171, against the separately-measured `v4_t1_e1` test score of 0.794) is much smaller than `report.md`'s own "+0.648" test-improvement figure (against this run's internal seed skills at 0.317) — the two are different baselines from different runs, not a contradiction, but worth not conflating. Two environment gaps are left explicitly unresolved after `cand_0002`: the `mirror-serving` fact is flagged as scoring 4/5 only because the checker's substring match has no polarity handling (the same defect class that caused `cand_0001`'s own regression), so JOURNAL.md warns "do not read 4/5 on this item as a solved behavior"; and seed 4 hit a run of five tool errors across three tools (`lookup_catalog_item`, `search_github_repo` ×2, `fetch_github_file` ×2, all `"Unable to process <tool>"`), to which the agent responded by inventing variable names — the implementer deliberately added no retry rule for it, only a placeholder-pass check, judging a prose fix would not have helped at the point the outage hit.
