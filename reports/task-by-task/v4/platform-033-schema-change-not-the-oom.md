# platform-033-schema-change-not-the-oom

<!-- BEGIN:auto -->

**task:** `platform-033-schema-change-not-the-oom`  
**category:** platform  
**tranche:** challenge  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-033-schema-change-not-the-oom/run_20260921_041054` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 1.000 |
| our baseline (v4_t1_e1) | test | 3 | 0.929 |
| seed (val, v4_t2_e1) | val | 5 | 0.402 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.721 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.967 |
| final (test, v4_t2_e1) | test | 5 | 0.967 |

delta vs JB: -0.033 · delta vs our baseline: 0.038

**T2 cost/time:** $43.57, 2,957,393 tokens, 2.46h (eval $8.64/2,732,135tok · optimizer $34.92/225,258tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-033-schema-change-not-the-oom/run_20260921_041054/report.md`, `.capevolve/v4_t2_e1_platform-033-schema-change-not-the-oom/run_20260921_041054/JOURNAL.md`

<!-- END:auto -->

## What this task is about

Every catalog item on a controller started failing right after a configuration change went out. The task is to trace the failure to the actual agnosticv pull request and the config field it superseded, while correctly treating a real, seeded OOM error as a contributing factor rather than the root cause -- the trap cuts both ways, since ignoring the OOM entirely is also wrong.

## What the optimizer tried

Two iterations, both confined to `babylon_agent.md` and `shared_context.md` — `aap2_agent.md`, `orchestrator.md` and the four other domain files stayed byte-identical to baseline throughout the run, because (as in the sibling task `platform-032-shared-secret-not-a-registry-outage`) `classify_fast()` fast-paths this instruction's "catalog item" phrasing to the `babylon` sub-agent before the orchestrator ever runs; JOURNAL.md records that five edits were first drafted for `aap2_agent.md`, then reverted once this was discovered, and preserved in an appendix for reuse on a genuinely `aap2`-routed task. `cand_0001` added a `## Critical Rules` block to `babylon_agent.md` (the report is the deliverable, three objective stop triggers, never end by asking to continue), a "Reading a File You Already Have the Path For" section with a canonical AgnosticV/AgnosticD repo table, a terminating 4-step "A Config Change Broke Everything At Once" chain (log → PR search → fetch the consumer file independent of the PR search → replacement name from the PR), a "Root Cause vs Contributing Factor" rule (a test/review/merge-time path is a contributing factor; a runtime-resolution path is the root cause) as a guard against this task's own OOM red herring, and the file's first output-format contract; `shared_context.md` got a corrected filter-widening rule. `cand_0002` (the winner) diagnosed that 3 of 5 `cand_0001` trials still exhausted the 8-round budget and produced no report at all, discarding facts the agent had already established; it replaced the soft "about six tool calls" guidance with a hard ceiling ("Six is your ceiling: your seventh response contains no tool calls and is the report" plus "a fact you hold and do not write down scores zero"), rewrote the config-change chain to 5 calls that terminate (a failing `{{ <parent>.<field> }}` has its definition in `includes/<parent>.yaml`, same owner/repo), gave the "new field name" and PR number deterministic sources independent of the flaky `search_agnosticv_prs` tool, and replaced a bare must-name table with a 5-line pre-labelled fill-in block.

## Why the winning candidate won

`cand_0001` was accepted first (val 0.402 → 0.721, Δ+0.319). JOURNAL.md's diagnosis of the residual ranks it: round exhaustion accounted for 7 of 13 missed answer checks (3 of 5 runs hit `max_rounds=8` and produced no report at all, dropping facts — like `governor-unchanged`, which every run had already fetched by its third tool call — that the run had already gathered); a "new-field" fact was never discovered in any of the 5 runs (4 of 13); and Splunk terms returning empty cost 2 of 13 in one seed. The winning move traced the round-exhaustion mechanism to a specific divergence point: every run's first three calls were already the three graded legs, but call 4 in every non-winning run was another empty guess at `search_agnosticv_prs`'s search term, burning 4–7 further calls the same way, while the one winning run's call 5 happened to hit. `cand_0002`'s hard 6-call ceiling plus removing the graded facts' dependency on that flaky tool (a design rule the entry states explicitly: "no graded fact may depend on a tool that flakes — keep the flaky tool for credit, take it off the critical path") is what the implementer expected to recover clusters 1 and 2, 10 of the 13 total misses, with an arithmetic estimate of Δ≈+0.215 against a 2×SE bar of ≈0.199. The measured move landed above that estimate: val 0.721 → 0.967 (Δ+0.245). On the held-out test split, `report.md` records the baseline `seed` skills at 0.4405 ± 0.025 versus the optimized skills at 0.9667 ± 0.020 — a test-side improvement of +0.5262. This task's val-seed score (0.402) is close to but not identical to its test-seed score (0.4405); the final optimized score, unusually for this batch, comes out identical on both splits (0.9667), which is why the val→test gap is reported as +0.0.

## Caveats

n=5 val trials is a small sample, and this was single-task tuning. Both iterations began from a routing misdiagnosis: the implementer's first five edits for this run targeted `aap2_agent.md`, on the assumption that the task's `services` metadata determined the loaded prompt file, and were reverted once `classify_fast()`'s actual pattern-matching was checked — the same mistake and the same fix as the sibling task `platform-032-shared-secret-not-a-registry-outage`. `cand_0002`'s own entry explicitly drafted and then dropped a plausible-sounding fix (a retry ladder for the PR search) after checking the losing runs' transcripts and finding they had already retried 4–5 times without it helping, because `search_agnosticv_prs` is non-deterministic under simulation — the same arguments that returned the real PR for the winning run returned empty 17 times across the four losers, fabricated PR numbers once, and threw an "Unknown store" error once. Two capability gaps are called out as unresolved by prose: `babylon`'s `max_rounds=8` budget is described as "too tight for its own documented chain" (it killed 3 of 5 `cand_0001` runs before `cand_0002`'s ceiling rule fixed it), and `search_agnosticv_prs`'s non-determinism under simulation is a workaround (route the graded facts around it), not a fix to the tool's flakiness itself. This is also the only task in this batch of six where the auto block's "delta vs JB" is negative (−0.033): the single JB baseline run (n=1) happened to score a perfect 1.000 on this task, edging out the final optimized test score of 0.967 — the delta against `our baseline` (n=3, 0.929) is positive at +0.038, and the delta against this run's own seed skills (test 0.4405) is the large +0.526 discussed above.
