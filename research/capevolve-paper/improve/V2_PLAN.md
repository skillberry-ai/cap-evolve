# CapEvolve v2: synthesis of the four diagnoses and the build plan

Sources:
- `hc_diagnosis_and_design.md` (imp-hc)
- `ao_diagnosis_and_design.md` (imp-ao)
- `competitor_mechanisms.md` (imp-comp)
- `gate_budget_design.md` with `gate_budget_sim.py` (imp-gate)

User decisions (2026-10-12, decisions.md):
- PRs target main of skillberry-ai/cap-evolve.
- Admin force-merge is approved once a PR has been reviewed and its findings fixed.
- train and val are merged into one optimization pool.
- Agent-optimize (AO) runs on a single objective only.
- AO uses subset evaluation, parallel candidates, and a graph of branches with merges.
- Where the surface allows code, deterministic helper scripts are added.

## What the runs say (one paragraph each)

1. **The proposer is not the bottleneck; the evaluation loop is.**
   - Evaluation is 90-99% of wall time.
   - The first proposal on Suite A already reaches the 0.80-0.85 plateau that every competitor reaches. It fixes the target's tool-call format, worth +0.20 to +0.25.
   - Competitors' extra machinery adds roughly the size of selection noise (max-of-k on 25-49 tasks).
2. **Hill-climb (HC) lost real gains to two gate defects.**
   - Coverage veto: incumbent infra holes are never retried, so 18 screen-passing candidates were vetoed against 7 that reached confirmation.
   - Budget straddling: the budget is checked only at iteration start, which produced cut-off confirmations, verdicts recorded as rejects, and 16-43% overruns.
3. **Noise swamps the evidence loop.**
   - Two identical seed draws differ on 14 of 49 retail tasks, and the ledger reports those flips as broke/fixed.
   - Every candidate is compared with a single, sometimes lucky, baseline draw.
   - Rule P promotes a true +0.06 edit only 22% of the time at 49 tasks.
4. **AO never worked as designed.**
   - The LLM was the scheduler. It polled with sleeps, which consumed 75-91% of its tokens.
   - It ran blocking 2 h evals that were killed or orphaned on `end_turn`.
   - It turned prose budget notes into hard caps and stopped with 60-80% of the budget unused.
   - It never reached a rule-P verdict.
   - The graph, `sched.pick/halve` and `merge_n` exist but are never scheduled.
5. **Candidate tool-code crashes are dropped as missing.** That hides about -0.056 per 10% crash rate and triggers coverage vetoes. The tau adapters never tag `error_kind=candidate`.

## Design (v2)

### D1. Gate and budget correctness (shared by HC and AO)
- **Coverage.** Retry the incumbent's infra-missing cells after the baseline and after each promotion. Quarantine cells still missing. Compute coverage on the paired set. Replace the 0.95 veto with a floor of 0.75 plus a tipping-point check that imputes missing deltas at -0.5.
- **Budget.** Reserve rollouts before every `evaluate_candidate`. A confirmation that does not fit returns `unconfirmed` (the candidate is pending, not a reject). Never exceed `max_metric_calls`.
- **Candidate faults.** Attribute an error to the candidate when the traceback has frames under the candidate workdir (`trials.py`). Candidate-fault cells score 0 under `errored_trial_policy: fail`. Add the tagging hook to the tau adapters.
- **Ledger noise.** At n<3 trials, show no causal broke/fixed lists; show counts against the null flip expectation. Pool all draws of a capability hash for per-task rates.

### D2. Pooled splits with a hidden confirm stratum (train=val merge)
- `split_mode: pooled`: pool = train ∪ val. It is partitioned once (seeded, stratified, persisted, sealed like test) into feedback F (about 50%) and confirm C (about 50%).
- The proposer and the rungs see F: traces, scores, failures.
- C is used only by confirmation. The proposer gets accept or reject bits for C, never traces or per-task scores.
- Test is untouched.
- Final internal estimate: champion vs seed on C, 4 fresh trials per side.
- Simulation (imp-gate): no power cost; round false-accept 0.12-0.14 under memorisation, against 0.53 for a naive merged gate.

### D3. Evaluation policy "SH-C" (new named rule `P2`; rule P stays frozen as run)
- Rounds of K candidates (K=8, or 6 when the budget is 600 or less), proposed in parallel from distinct failure clusters.
- Kill-only successive-halving rungs on random F subsets (12, then 36 rollouts). Ranking uses the pooled incumbent F draws.
- At most 2 survivors go to one fresh confirmation on C against a concurrently re-measured incumbent (m=4 trials). The threshold is calibrated for round FWER of about 0.10.
- With a single pending candidate, use a group-sequential test with looks at 12/24/49/98/147.
- Simulated: -44% rollouts per round and -39% rollouts per true champion compared with rule P, with similar power.

### D4. AO-2: a code-driven graph conductor
- `ao/conductor.py` runs a tick loop: reap jobs, promote (P2), merge or rebase, run rungs, propose, then check stop.
- The LLM only runs bounded one-shot jobs (propose, diagnose, merge-resolve), each with its own token cap. The LLM never waits or polls.
- Chunked 20-rollout eval jobs run in a shared slot pool, so several candidates evaluate in parallel.
- Graph state lives in `graph.jsonl` and `conductor.json` (jobs and reservations). It is resumable, finalize is idempotent, and a supervisor relaunches the conductor until exit 0.
- Branch merge uses `merge_n`/`funcmerge` when two survivors on different branches touched disjoint units, or when the LLM merge-resolve job is used. A merged node is a candidate like any other.
- Stopping is structured: budget, tokens, wall time, and a plateau with a floor. Prose constraints are never parsed into caps.
- Single objective: AO refuses multi-objective specs. Cost is reported, not optimized.
- Duplicate-candidate guard by content hash. AO skips the train-80 baseline.
- Regression test: with K=1, rungs off and merge off, the conductor reproduces HC decisions.

### D5. HC-2
- HC uses the same P2 evaluator with K parallel proposals per round. HC is the K-round special case of the conductor, so one code path is used.
- Forward `--workers` (`cli.py:960-966`) and parallelise the baseline.
- Proposer context:
  - fresh failures from F (rotating minibatch);
  - contrastive pass/fail trace pairs from pooled draws;
  - a diversity gate against the last K rejected diffs;
  - a cross-trace consolidation mode, the Trace2Skill pattern.

### D6. Deterministic helper code in the surface
- Surfaces may declare executable files. Suite A v2 uses `[system-prompt, skill]` with `skills/<name>/{SKILL.md, scripts/*.py}`.
- The SpreadsheetBench adapter stages only the current candidate's `skills/` into each rollout's view. It mounts them read-only through a second `ro` bind, outside `spreadsheet/`, with gold-free checks.
- The tau suites carry helpers as methods in `tools.py`.
- Proposer guidance: codify a procedure into a helper once it fails or recurs in 2 or more distinct F traces.
- `helper_smoke` pregate stage: it imports, is deterministic, writes only to its declared output, and runs on fixtures from recorded F traces with no network and no gold. A failure costs 0 rollouts.
- Lint: no task ids, no copied answers, no branching on task identity or evaluator paths, no network or subprocess calls.
- A helper's own crash is a candidate fault.
- Determinism metric: per-task reward variance across trials, seed against champion.

## PRs (all to main; each gets a review agent, fixes, CI green, then admin merge)
- **PR-0 `port`.** Port the campaign's reviewed core changes (rule P, screen accounting, gold isolation, history flag, paper-mode switches) from the campaign branch to main. This is the base for every other PR.
- **PR-1 `gate`.** D1 + D2 + D3 (`promotion.py`, `harness.py`, `splits.py`, `trials.py`, `screen.py`/`sched.py`, tau adapter tagging).
- **PR-2 `ao2`.** D4 (`ao/conductor.py`, host and supervisor, AO skill docs). It depends on PR-1's evaluator API.
- **PR-3 `helpers`.** D6 (the surface manifest, SpreadsheetBench staging and mount, pregate `helper_smoke`, lint, proposer guidance).
- **PR-4 `hc2`.** D5 (workers, K-round HC on the P2 evaluator, proposer context).

## Experiments (registered before any run, as amendment 11; test is scored once per registered version)
- **Arms:** HC-2 and AO-2 on Suites A, B and D (and E if quota allows). 3 seeds each.
- **Data:** pooled train ∪ val with F/C. Same rollout budgets as v1.
- **Optimizer:** Sonnet 5.5, 4M tokens per search.
- **Iteration:** compare v2 versions only on C-internal estimates. The sealed test is touched once per frozen version.
- **Disclosure:** v2 is post-hoc method development after v1 search-time results. It is reported as such, beside the v1 registered results.
