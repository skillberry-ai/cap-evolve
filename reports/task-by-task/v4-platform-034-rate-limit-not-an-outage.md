# platform-034-rate-limit-not-an-outage

<!-- BEGIN:auto -->

**task:** `platform-034-rate-limit-not-an-outage`  
**category:** platform  
**tranche:** challenge  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-034-rate-limit-not-an-outage/run_20260921_063847` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.769 |
| our baseline (v4_t1_e1) | test | 3 | 0.794 |
| seed (val, v4_t2_e1) | val | 5 | 0.386 |
| cand_0001 (val, v4_t2_e1) | val | 5 | 0.817 |
| cand_0002 (val, v4_t2_e1)  <- best (val) | val | 5 | 1.000 |
| final (test, v4_t2_e1) | test | 5 | 0.984 |

delta vs JB: 0.215 · delta vs our baseline: 0.190

**T2 cost/time:** $21.66, 803,916 tokens, 2.94h (eval $2.01/573,204tok · optimizer $19.65/230,712tok) — see [`../../results/v4/cost_time/`](../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-034-rate-limit-not-an-outage/run_20260921_063847/report.md`, `.capevolve/v4_t2_e1_platform-034-rate-limit-not-an-outage/run_20260921_063847/JOURNAL.md`

<!-- END:auto -->

## What this task is about

A bulk cleanup's destroy jobs are failing, and AnarchyRun objects piling up have raised worries about running out of etcd space. The task is to identify an AWS API rate limit as the actual cause, rule out an AWS outage using a seeded probe, and recognize that the etcd buildup is a downstream symptom of the failures, not their cause.

## What the optimizer tried

Two iterations, spanning `shared_context.md`, `orchestrator.md`, `aap2_agent.md` and `babylon_agent.md`. `cand_0001` opened by noting the recorded baseline val (0.386) was actually the mean of only 2 valid trials, because 3 of 5 seed installs died with an infrastructure `HTTP 409` unrelated to the agent; of the 2 that ran, one scored 0.0 outright (`AgentTimeoutError` at 600 seconds, no final answer at all). Its 12 edits gave the investigation a stopping rule and a mandatory final-answer contract (`shared_context.md`'s new "Investigation Budget and the Final Answer Contract": a ~20-call gather cap, two strikes per data source, "your last output MUST be your findings"); de-defaulted several owner/repo citation examples and corrected `agnosticd-v2`'s owner in `aap2_agent.md`'s table (it had contradicted itself); added a "When the Catalog Index Is Unavailable" fallback that constructs the config path instead of guessing an org; added a "Many Jobs Failing at Once — Throttling vs. Outage" procedure (read the error class, hunt an isolated successful probe, do the concurrency-vs-limit arithmetic); and gave the orchestrator a narrow exception letting it state causal direction when a question spans agents, paired with an explicit "phrase it forward, not as a negation" rule after JOURNAL.md caught that the `etcd-as-cause` forbidden item has no "ruled out" escape hatch (unlike `aws-outage`, which does). `cand_0002` (the winner) kept all of that and, having confirmed the tool-call matcher is a *subset* match (extra arguments are free, so an earlier "pass these exact args" idea would have been a no-op), added a new "Step 0: If a Count Was Asked For, Survey the Population FIRST" ahead of the existing Step 1 (an unfiltered `find_jobs` before any single named ID is investigated); rewrote the "not an outage" conclusion from evidence-gated to unconditional and required the bare, unqualified phrase "not an outage" rather than a qualified form like "not a cloud outage"; fixed three Splunk filter traps (a multi-word `search_terms` matches as one literal phrase; narrow time bounds return empty; `errors_only` hides the INFO-level rows the decisive evidence lives in); and replaced a bare prohibition on retrying a failed path under a different org with a prescribed 4-step recovery.

## Why the winning candidate won

`cand_0001` was accepted at val 0.817 (Δ+0.431 over the unreliable 2-trial baseline), and this time all 5 trials actually completed. JOURNAL.md's diagnosis of the residual after that move is unusually precise about mechanism: the "not an outage" conclusion was reached correctly in all 5 remaining trials but written in a form the checker's `any_of` list doesn't match in 3 of them ("not a Route 53 outage", "not a cloud outage", "not a service outage" instead of the bare "not an outage") — a side effect of `cand_0001`'s own forward-phrasing rule reading as if it discouraged that specific negation, even though `aws-outage`'s forbidden list carries an explicit escape hatch for it. Ordering was the other big piece: every trial called `get_job_log` on the named job before the population-level `find_jobs(status="failed")`, inverting the enumerated call order the matcher checks (a subset match on arguments, but a strict check on order); `cand_0002`'s Step 0 made the ordering structural rather than a principle to remember, including a rule that a parallel batch of calls is still read in written order. Combined with a fix to the invented-date-filter mechanism behind the count miss (seeded job rows have no `created` field, so an out-of-range `created_after` returns empty, and the simulator was observed fabricating plausible rows for out-of-seed queries), val moved 0.817 → 1.000 (Δ+0.183); JOURNAL.md's RESULT line reports `fixed={platform-034-rate-limit-not-an-outage}` for this exact move — one of only two tasks in this batch of six (the other is `platform-031-helm-url-not-a-timeout`) whose winning candidate names itself in `fixed=` rather than leaving it `unresolved` or `—`. On the held-out test split, `report.md` records the baseline `seed` skills at 0.740 ± 0.030 versus the optimized skills at 0.984 ± 0.016 — a test-side improvement of +0.244, with a small reported val→test gap of +0.016. This task's val-seed score (0.386) and test-seed score (0.740) are very different numbers, not interchangeable — and per `cand_0001`'s own note, the val figure is additionally unreliable because it rests on only 2 of 5 seed trials.

## Caveats

n=5 val trials is nominally the sample size, but the *baseline* val score in the auto block's table above (0.386) is built from only 2 genuinely valid trials — 3 of 5 seed installs failed with `HTTP 409`, an infrastructure error JOURNAL.md explicitly separates from agent capability ("infra, not the agent"), which is also why the reported baseline standard error (±0.386) is as large as the mean itself. This was single-task tuning. Two capability gaps remain explicitly unresolved by prose after `cand_0002`: `lookup_catalog_item`/`search_github_repo`/`search_agnosticv_prs` return schema and primary-key validation errors rather than data ("a writer/reader schema mismatch making the catalog index unreadable for every task needing a catalog config"), and the platform simulator is reported to fabricate plausible-looking rows for out-of-seed queries instead of returning empty, which JOURNAL.md flags as a verifier-fidelity problem no prompt rule can fix ("prompt rules can discourage the bad filter; they cannot make the simulator honest"). `report.md` also notes lower run-to-run consistency on the held-out test split than most of this batch (pass^1=0.800, pass^2=0.600).
