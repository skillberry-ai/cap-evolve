# CapEvolve method paper: ablation and analysis experiments (experiment-designer, 2026-10-12)

Status: PROPOSAL for coordinator approval. Nothing below has been launched except three tiny probes under tag `E00-azprobe` (search-split ids only, no final set touched; 8.3k gateway calls and 34.8 M Azure tokens in total, no capped tokens, about $20 at list price). Visual version: `design/redesign_plan.html`. Story and RQ numbering follow `redesign/STORY.md`.

Inputs read: `decisions.md` (to 08:29 UTC today), `protocol/analysis_plan.md` (amendments 1 to 5), `design/experimental_design.html`, the original `paper.tex` and `CLAIMS_LEDGER.md`, `analysis/out/attrib/summary.md` (08:47), the tau2 adapter and builder in `wt-tau` / `campaign-scratch/scripts/E10B`, the live E10 / E10B / E10C project specs, and the gateway code.

---

## 0a. APPROVED SCOPE (coordinator, 2026-10-12): TIER 1 ONLY

Approved and registered (amendment 7): E22 null pool; E20-PT (reference), E21-ruleP, E20-P, E20-T, E20-CTL (3 seeds each); E21-1S (3 seeds); E20-GEPA (3 seeds); E25 decomposition at final evaluation. Hill-climb only, Sonnet 5.5, stock gate default, target `azoai/gpt-4.1-mini-2025-04-14`, user simulator and judge `azoai/gpt-4.1-2025-04-14`. Measured hc optimizer tokens: 0.20 to 0.73 M per search (mean 0.4 M); Tier 1 about 8 M capped (limit now 170 M). Azure is uncapped (user).

NOT RUN (not approved): E23 no-history, E20-TD (descriptions-only emulation), E20-PTS (skill package), E21-ruleP-2x, E24-AO, E27 airline, E26 beyond the descriptive scoring in amendment 7G. The text of sections 4 to 10 below describes them as proposals only. No-history feasibility is analysed in the coordinator thread (a one-flag proposer-context switch, about 25 lines, 3 seeds about 1.2 M capped tokens), pending a decision.

## 0. One-screen summary

1. **The surface ablation cannot be read off the running campaign.** On B and C the CapEvolve arms run `capabilities: [system-prompt, tools]` under rule P, and rule P is inert at this budget: 0 promotions in all hc and ao searches so far (attrib summary, 08:47: B hc 0/9 candidates, C hc 0/12, ao 0/3 and 0/1; stock gate on C promotes 1.0 per search). A surface grid under rule P would return the seed in nearly every cell and show nothing. The new ablation family therefore has to use the **stock gate** as its reference configuration and treat rule P as one of the cells.
2. **Use Azure-direct, target `azoai/gpt-4.1-mini-2025-04-14`, on tau2 retail** ("Suite D"). It matches gpt-oss in the two properties that matter to a gate: seed accuracy on opt-49 (0.612 vs 0.56 to 0.65) and trial noise (null paired SD per task 0.57 vs 0.55). It costs about $0.05 per rollout including the user simulator and judge, and does not touch the saturated gpt-oss and Gemma deployments.
3. **Recommended launch (Tier 1, about 12.5k Azure rollouts, about 8 M capped tokens, finishes about 8 h before the cutoff):**
   E22 empirical null pool, E20 surface grid {P, T, PT} x 3 seeds, E20 one-shot control, E21 gate cells {rule P, one-stage} x 3 seeds, E20 GEPA prompt-only on the same target. Tier 2 adds MCP-style descriptions-only, history-off and digest-off, rule P at 2x budget, gate ROC. Tier 3 (conditional on code) adds the skill-package cell, AO, airline replication.
4. **Two decisions are needed from the coordinator:** (a) the capped-token budget. The current projection is about 139 M at the cutoff against the 150 M cap with a 15 M final-eval reserve, so Tier 1 (about 8 M) has to be funded by cutting E12C best-of-k (up to about 24 M of guard) or by a cap raise for the ablation family only; (b) approval of Azure spend of roughly $0.7 to 1.2 k at list price (not capped, but large enough to state).
5. **Cannot be run in time or without harm to primary arms:** a skill-versus-prompt ablation on Suite A (needs evaluator-daemon changes and sandbox containers that Gemma arms use; Gemma is the critical path), the optimizer-mechanics 2x2 with a Gemma optimizer (E17), DAG and merge ablations (E13, E14). Say so in the paper rather than imply coverage.

---

## 1. Measured capacity (probes, tag `E00-azprobe`, search split only)

Script `campaign-scratch/scripts/E00/{raw_probe.py,tau_probe.sh}`; logs `runs/E00-azprobe/`. The tau probes run the seed capability (policy + tools) on **retail opt-49, 2 trials, concurrency 32**, user simulator and judge `azoai/gpt-4.1-2025-04-14`, through gateway :4112, native sims.

| target (Azure-direct) | mean reward opt-49 | tasks always 0 / always 1 / mixed | null paired SD per task (trial 1 vs 2) | SE of null split delta (49 tasks, n=1) | tokens per rollout | wall for 98 rollouts at c=32 | rollouts per minute | USD per rollout (list) |
|---|---|---|---|---|---|---|---|---|
| gpt-4.1 | 0.724 | 9 / 31 / 9 | 0.43 | 0.061 | 64 k | 434 s | 13.5 | about 0.15 |
| **gpt-4.1-mini** | **0.612** | 11 / 22 / 16 | **0.57** | 0.082 | 78 k | 457 s | 12.9 | about 0.05 |
| gpt-5-mini | 0.694 | 4 / 23 / 22 | 0.67 | 0.095 | 76 k | 880 s | 6.7 | about 0.05 |
| gpt-4o-mini | 0.367 | 24 / 11 / 14 | 0.53 | 0.076 | 69 k | 404 s | 14.5 | about 0.02 |

Reference: gpt-oss-120b seed on the same opt-49: 0.56 to 0.65 (ctl-seed, 2 trials); measured paired null SD 0.55 (analysis plan 5F). So gpt-4.1-mini reproduces B's difficulty and noise regime; gpt-4.1 is too clean (headroom 0.28, of which about 0.1 is unreachable) and gpt-5-mini is half as fast.

Other facts measured:
- About 16 gateway calls per rollout (9 target, 6 user, under 1 judge). 7,800 calls in the probes, 5 HTTP 500 (0.06%), no 429 at 64 rollouts in flight (about 2 M tokens/min).
- Raw stress on gpt-4.1-mini at 19 k-token prompts, 64 concurrent requests: about 7.4 M tokens/min offered gave 25% failures (429 and connection resets). **Plan: at most about 128 tau rollouts in flight across the whole D family (about 4 M tokens/min), ramp in stages, watch 429 and `queue_s`.** gpt-4.1 and gpt-4.1-mini are separate deployments, so a second target would add headroom.
- Throughput per search at concurrency 12 to 16: a 49-task screen takes 5 to 7 min (tail-limited), so one 550-rollout search is about 2 to 2.5 h including about 10 optimizer turns.
- Optimizer tokens (non-cache-read, gateway ledger, measured on E10B/E10C/E12C): hill-climb 0.20 to 0.73 M per search (mean about 0.4 M), one-shot 0.09 to 0.31 M, agent-optimize 0.5 to 1.2 M, GEPA reflection about 0.4 M. The lead's "0.1 to 0.3 M per HC search" is slightly optimistic; I use 0.4 M.
- Gateway ledgers: :4111 shows capped 60.5 M, :4112 shows 29.3 M and an `azure_tokens` bucket. The two processes keep separate in-memory counters. Route the Claude optimizer through :4111 exactly as E10B does and the Azure target/user/judge through :4112; metering-auditor should confirm which counter the 150 M cap enforces.

---

## 2. What has run, what is running (08:30 UTC, today)

| family | state | relevance to ablations |
|---|---|---|
| E10 Suite A (Gemma, prompt only), 9 arms x 3 seeds | running; hc 282/409/200 rollouts, ao 216/372/333, competitors 71 to 569 | HC vs AO and rule P behaviour on A; surface is a single prompt file so no width ablation is possible |
| E10B (tau retail, gpt-oss, P+T) hc, ao, GEPA, HarnessLens, one-shot, seed | running | rule P inert (0 promotions); one-shot controls give 1 of 3 promotions; AO stopped itself at 198 and 172 rollouts |
| E10C (tau airline, gpt-oss, P+T) | running | same |
| E12A (A, stock gate) and E12C (C, stock gate), E12C best-of-k | running | stock gate promotes 2.0 (A) and 1.0 (C) per search vs about 0.3 and 0 for rule P |
| Done: E05 injected faults (15 pass, 7 partial, 6 gap), replay of historical gates (#791), gate simulations, observed-variance MDE | done | supports C2 analytically |
| Final-eval machinery (`experiments/final`) | built, dry-run on search splits | the D cells reuse it (needs a suite D entry, section 6) |

Nothing in the running campaign varies the surface, the causal history or the optimizer context. The three claims C1, C4 and the unreplicated part of C2 therefore need new runs.

---

## 3. Suite D: the shared configuration of the new ablation family

One family, one fixed environment, one factor changed per cell against a reference cell. Self-contained: never pooled with E10 tables.

| item | value | reason |
|---|---|---|
| benchmark | tau2 retail @8ebb7499, same builder and adapter as E10B (`scripts/E10B/build_cap_project.py`, parameterised for the target) | zero adapter risk for P, T, PT; E10B comparability |
| target agent | `azoai/gpt-4.1-mini-2025-04-14`, temperature 0, max_tokens 8000 | section 1: matches gpt-oss difficulty and noise |
| user simulator | `azoai/gpt-4.1-2025-04-14` (tau2 standard) | held constant across cells |
| NL judge | `azoai/gpt-4.1-2025-04-14` (tau2 default) | removes the judge deviation recorded for B |
| optimizer | `aws/claude-sonnet-5-5`, claude-code shim from `runs/E10B/_sbx_bin` (network namespace, no egress, `/tmp` masked) | same optimizer as E10; hill-climb |
| search splits | train = val = opt-49; test = sel-25 (never seen by the optimizer; finalize scores it once) | as E10B; sealed test-40 never in a search |
| budget | 550 counted rollouts, max 10 iterations, 4 M optimizer-token guard (soft 3.5 M) | E10B parity; about 10 candidates per search |
| reference gate | **stock** (`gate_mode paired`, `gate_k_se 1.0`, footprint masking on, candidate-side coverage 0.6, `errored_trial_policy fail`) = the E12C configuration | rule P is inert at 550 rollouts, see section 0 |
| seeds | 3 per cell for Tier 1 and 2 (optimizer randomness; split fixed), 2 for Tier 3 | S=3 gives artifact-level claims with t(2) caveats, as in the plan |
| held-out evaluation | H65 = sel-25 (scored when a search ends, before the cutoff) plus sealed test-40 (scored in the final window through the final machinery). n=5 trials per task for Tier 1 champions, n=3 for the rest. The seed artifact is re-scored in the same window with n=10 | sel-25 is clean for CapEvolve cells because no CapEvolve gate reads it; GEPA selects on sel, so GEPA contrasts use test-40 only |
| tags and dirs | tags `tag:E20-<cell>-s<k>:<arm>:{target,user,judge,optimizer}`; runs under `campaign-scratch/runs/E20/<cell>/s<k>` | gateway metering, separate ledgers |
| concurrency | at most 12 rollouts per search, at most about 128 in flight over the family | section 1 |
| code snapshot | campaign head at launch (`wt-tau` after tau-runner's last commit), plus the small switches in section 8 | pin SHA in the registry before launch |

**Surface lock (new, required for P-only, T-only, descriptions-only).** `capabilities:` only changes the guidance staged for the optimizer; nothing stops a candidate from editing the other file. Add `TAU_SURFACES=policy|tools|policy,tools` to the adapter's `apply()`: files of a locked surface are read from the pristine seed, never from the candidate, and every candidate that differs from the seed on a locked surface increments `surface_violations.json` (reported per cell). The optimizer instruction file also states the allowed files. About 40 lines plus a unit test. Owner tau-runner.

**Statistics for the family (pre-registered in `experiments/registry.jsonl` before launch).**
- Unit: task (each retail task is its own family). Paired by task. Estimators and intervals exactly as analysis plan sections 3 and 5M-2: artifact-level CR1 interval (headline for tests) and pipeline-level t(S-1) interval (needed for any sentence about the method). All three seed values shown.
- Two Holm families, separate from every E10 family: **D-1 surface**: {P vs seed, T vs seed, PT vs seed, PT vs P, PT vs T, interaction PT - P - T + seed}. **D-2 loop and gate**: {PT vs one-shot, P vs GEPA-P (test-40 only), rule P vs stock, one-stage vs stock}. Everything else is exploratory and carries no p-values in the abstract.
- Equivalence: TOST margin 0.10 (amendment 3, same as A and B). A margin of 0.05, as STORY.md suggests, is not reachable at this size (below).
- Planning MDE (my arithmetic from the null SD in section 1; confirm with `mde_observed.py` before freeze): per-task paired SD about 0.30 to 0.36 including tau = 0.15 heterogeneity. Contrast of 3 champions vs seed on T=65, n=5: MDE about 0.08; between two cells: about 0.10; on test-40 alone about 0.11 and 0.13. Consequence: the grid can establish PT vs seed if the gain is above about 0.08, and a surface difference only if it is 0.10 or larger. Smaller differences are reported as "inconclusive" with the CI, and the attribution analysis (section 5) carries the mechanism story. This is a limit to state, not hide.
- Cost per point and break-even: analysis plan section 9, with Azure tokens in their own column.

---

## 4. Experiments

Legend. Cost: R = counted rollouts (Azure unless stated), C = non-cache-read capped optimizer tokens, W = wall clock if launched at 11:00 with the stated parallelism, $ = Azure list price at $0.05 per rollout (gpt-4.1-mini target, gpt-4.1 user and judge). Fits = completes before 06:00 on 10-13. Owner = which agent launches it.

### E22 Empirical null pool (A3, null controls). Rank 1.
- **Question.** What is the false-accept rate of rule P, the one-stage gate and the stock decision rule under the real trial noise of this target, and how does it compare with the simulations (rule P 0.04, one-stage 0.57 per 10-iteration search)?
- **Design.** Evaluate the unmodified seed K = 40 times on opt-49 (one trial per task per evaluation; 40 independent seed evaluations in one `single.py --trials 40` run). A "null candidate" is another seed evaluation. Offline, drive the **real** `gate.decide` and `promotion.screen/decide` code with sampled pairs and with fresh-trial confirmations drawn from the pool (a 3-trial confirmation uses 3 more evaluations per side). This yields thousands of null decisions per gate, not 9.
- **Config.** Seed capability, target and user as section 3, opt-49, 40 evaluations, concurrency 64, tag `E22-nullpool`. Footprint-masked stock gate is evaluated with an empty footprint only (a null edit has none) and is flagged as such.
- **Cost.** R = 1,960, C = 0, $100, W about 1.5 h. Fits: yes.
- **Owner.** tau-runner (run), metrics-eng (replay script `analysis/scripts/null_pool_replay.py`).
- **Statistics.** Binomial CI (Wilson) on false-accept rate per gate; ratio to simulation; also gives the seed drift across evaluations (a noise floor for every other cell).
- **Shows.** C2(i) on a real target. **Cannot show** false-reject (needs true effects, see E26).

### E20 Surface width and capability type (A1). Rank 2.
Cells, all hill-climb, stock gate, section 3 config, differing only in the editable surface:

| cell | `capabilities` | `TAU_SURFACES` | seeds | status |
|---|---|---|---|---|
| E20-P | [system-prompt] | policy | 3 | launch-ready after surface lock |
| E20-T | [tools] | tools | 3 | same |
| **E20-PT** (reference) | [system-prompt, tools] | policy,tools | 3 | launch-ready (same as E10B/E12C spec with target changed) |
| E20-CTL | [system-prompt, tools], 1 iteration, 200 rollouts, no selection | policy,tools | 3 | launch-ready; a single proposal anchors "search vs one proposal" |
| E20-TD | [mcp-tool] guidance, descriptions-only | tools (AST-checked: docstrings and parameter descriptions only, tool hiding allowed) | 3 | Tier 2; needs ~1.5 h dev (section 8). It is an **emulation** of the MCP surface (client-visible descriptions), not an MCP server; label it so |
| E20-PTS | [system-prompt, tools, skill-package] | policy,tools,skills | 2 | Tier 3; needs a tau skill loader (about 4 to 6 h dev plus review); only run if ready by 14:00 |

- **Question.** C1 and RQ3: which capability type contributes how much, is there interaction (PT > P + T)? Is P+T worth its extra edit space on tau2 retail? Which types are not worth it (T-only, descriptions-only)?
- **Cost per cell (3 seeds).** P, T, PT, TD: R = 3 x 550 = 1,650, C about 1.2 M, $82, W about 2.5 h each. CTL: R = 600, C 0.7 M. PTS: R = 1,100, C 1.5 M. Tier 1 part (P, T, PT, CTL): R = 5,550, C = 4.3 M, W about 3 h (all 12 searches in parallel at c=10, about 120 in flight).
- **Held-out.** Champion of each (cell, seed) scored on sel-25 when its search ends, and on test-40 in the final window, n=5. If a search promotes nothing its champion is the seed, kept in the denominator (plan section 5).
- **Statistics.** Family D-1. Interaction as a difference of differences with seed-level resampling; effect of each surface reported as the paired mean with both intervals.
- **Reading guide.** If PT beats P and T and the interaction CI excludes 0: surface width matters and the types are complementary. If T is about PT and P is not: tools carry the gain on this task family. If neither differs beyond 0.10: inconclusive; do not write "surface width matters" (the old paper's 2x2 had different baselines and n=1).
- **Does not show.** Generality beyond one domain (see E27), the value of a skill package (E20-PTS only if built), MCP against a real server.

### E20-GEPA Loop quality on an identical surface (RQ1b). Rank 5.
- **Question.** Same target, same prompt-only surface, same 550-rollout budget: does the CapEvolve loop (E20-P) beat GEPA? On B and C the comparison is confounded by surface width (CapEvolve P+T vs GEPA P).
- **Config.** `scripts/E10B/gepa_tau.py` with env `TAU_AGENT_MODEL/TAU_USER_MODEL/TAU_JUDGE_MODEL/TAU_GATEWAY` pointing at Azure, `--exp E20 --arm gepa`, 3 seeds, 550 counted rollouts, reflection model Sonnet 5.5.
- **Cost.** R = 1,650, C about 1.2 M, $82, W about 2 h. Owner tau-runner. Held-out: test-40 only (GEPA selects on sel-25).
- **Statistics.** Family D-2 (P vs GEPA-P, artifact-level + pipeline-level).

### E21 Gate design (A3). Rank 4.
Cells on the PT surface, same budget, 3 seeds each; E20-PT is the stock reference.

| cell | spec delta vs E20-PT | what it isolates |
|---|---|---|
| E21-ruleP | the E10B block: `promotion_rule P, k_se 1, n_conf 3, z_conf 1.282, dmin 0, min_cov 0.95, gate_footprint false, gate_coverage joint` | the configuration used by every E10 CapEvolve arm, on a target where it can be compared with the stock gate |
| E21-1S | `gate_footprint false, gate_coverage joint, gate_min_coverage 0.95`, **no** `promotion_*` | one-stage unmasked gate: separates the confirmation stage from footprint and coverage changes. E12A/E12C change three things at once (confirmation, footprint masking, coverage); this cell makes the decomposition clean at the cost of one extra config |
| E21-ruleP-2x (Tier 2) | as E21-ruleP, 1,100 rollouts | whether rule P is "inert" or merely "needs budget" |

- **Is anything extra needed beyond E12A and E12C?** Yes, E21-1S. Without it a stock-vs-P difference cannot be attributed to the confirmation stage. E12A and E12C remain the evidence on the gpt-oss and Gemma suites.
- **Cost.** ruleP + 1S: R = 3,300, C = 2.4 M, $165, W about 2.5 h. 2x cell: R = 3,300, C = 1.2 M.
- **Outputs.** Promotions per search, inert searches, held-out gain, selection-to-held-out shrinkage (opt/val gain vs H65 gain), regressions vs seed on H65. Family D-2.
- **Shows.** Whether strictness buys reliability or only inertness (the central trade-off in the redesigned story). **Cannot show** that one gate is "better" without TOST: with margin 0.10 and MDE about 0.10 the expected verdict for small differences is "inconclusive".

### E26 Gate ROC on real candidates (A3, false accept and false reject). Rank 7.
- **Question.** Of the candidates a gate rejected, how many were truly positive on held-out tasks (false reject), and of those it accepted, how many were not (false accept)?
- **Design.** Every candidate created in E20-PT, E21-ruleP, E21-1S (about 80 candidates; all artifacts are kept in `candidates.jsonl` with `artifact_dir` and sha256) is scored on sel-25, n=2 per task (50 rollouts), together with the seed on sel-25 n=10. The gate's screen delta and decision are read from the run record. Held-out delta of each candidate gives a label (CI above 0, below 0, indistinguishable).
- **Cost.** Candidates at n=2 (50 rollouts each) plus the seed at n=10 (250): R = 80 x 50 + 250 = 4,250, $210, C = 0, W about 1.5 h. Sel-25 is search split, so this is permitted before the cutoff (not for GEPA).
- **Owner.** tau-runner (scoring), metrics-eng (analysis `gate_roc.py`).
- **Statistics.** Descriptive: sensitivity and specificity with Wilson CIs; per-candidate labels are noisy at n=2 on 25 tasks (SE about 0.07), so the claim is aggregate rates, not individual verdicts. No p-value family.

### E23 Optimizer context and causal history (A4). Rank 9.
- **Question.** Does the causal history (LEDGER per-task BROKE/FIXED, protect set, JOURNAL handover, RUNMAP and `prior_iterations/`) change the final gain or the regression count at equal budget? Does the digest (`context_digest`) matter?
- **Cells (PT surface, stock gate, 2 seeds each, with the seeds of E20-PT as the reference).**
  - E23-nohist: new switch `optimizer.ablation.history: false` (and env `CAPEVOLVE_HISTORY`) that skips `write_ledger`, `RUNMAP.md` / `prior_iterations/` and journal seeding in the optimizer workdir, and removes the protect-set text from the instructions. Default unchanged. Small reviewed PR (about 2 h incl. test); owner algo-eng, reviewer repo-auditor. There is no existing switch for this: the seven existing ablation keys are `dag_parallel, active_eval, smart_merge, cost_gating, failure_clustering, pregate, context_digest` (core/cap_evolve/optimizer_config.py).
  - E23-nodigest: `context_digest: false` (existing switch, no code).
  - E23-nocluster (optional): `failure_clustering: false` (existing switch).
- **Cost.** R = 2 x 550 x 2 cells = 2,200, C about 1.8 M, $110, W about 2.5 h. Fits: yes if the switch merges by 15:00.
- **Statistics.** Exploratory (S=2): paired CR1 on H65, regressions (pass to fail vs seed), accepted-candidate count, C per accepted candidate. Report effect sizes; do not claim "history helps" unless the interval excludes 0.
- **Optimizer mechanics (E17, the 2x2 of output guard and delegation with a Gemma optimizer): not feasible and not recommended.** It needs a self-hosted optimizer on Gemma and 7,200 Gemma rollouts. The original paper's n=1 result stays out of the new paper; say so.
- **Cheap optional cell: optimizer model.** `optimizer_model: aws/claude-sonnet-4-6` vs 5-5 on PT, 2 seeds: one config line, C about 0.5 M. Only if capped tokens allow.

### E24 Orchestration mode (A2). Analysis first; optional new cell.
- **From existing runs (no cost).** HC vs AO on A, B, C from E10, E10B, E10C: promotions per search, stop reasons (B s0 198, s1 172, C s1 110 are native stops), optimizer tokens and wall hours per search, held-out gain at the matched checkpoint. TOST with margin 0.10 (amendment 3).
- **What it can show.** Cost and behaviour differences (AO uses 3x to 5x the optimizer tokens and stops itself early); equivalence only if the TOST passes.
- **What it cannot show.** Which orchestration finds better edits: both arms run rule P and both are mostly inert (0 promotions in B and C), so the contrast measures inertness. AO and HC also differ in algorithm (agent-optimize vs hill-climb), not only in who drives the loop.
- **Optional new cell.** E24-AO: agent-optimize on D (stock gate, PT surface), 2 seeds. R about 2 x 400, C about 2.4 M, W about 3 h. Tier 3, because it spends capped tokens that Tier 1 needs more.

### E25 Artifact decomposition at final evaluation (A5). Rank 6 (Azure) and Tier 3 (gpt-oss).
- **Question.** For a champion that edits several surfaces, how much of its gain comes from the prompt edits, how much from the tool edits? Is the sum of parts equal to the whole?
- **Construction (deterministic, no model).** From a champion with files `policy/policy.md`, `tools/tools.py`: sub-artifact P-only = champion policy + seed tools; T-only = seed policy + champion tools. Skip a sub-artifact whose hash equals the seed or the champion. A small script `experiments/final/decompose.py` writes the extra order file.
- **On Suite D (recommended).** Champions of E20-PT, E21-ruleP, E21-1S, E20-CTL that differ from the seed on both surfaces (at most 12; expect 6 to 9, because of inert searches). Cells: sub-artifacts x test-40 x n=3 = at most 24 x 120 = 2,880 rollouts, plus the same on sel-25 before the cutoff (1,800). $240, Azure W about 1.5 h, no capped tokens. Gives the within-cell decomposition **and** a cross-check of E20-P/E20-T (a P-only run vs the P part of PT).
- **On Suite B and C (gpt-oss), not recommended before the primary window ends.** The one-shot champions always edit; hc/ao return the seed so far. Upper bound if every distinct B/C champion (about 15) were decomposed at n=3: 30 sub-artifacts: B 12 x 120 + C 18 x 60 = about 2,500 gpt-oss rollouts, about 8 h on a gateway whose B+C primary window is already about 9 h and HarnessLens occupies the rest. Reduce to n=1 over the one-shot and stock-gate champions only: about 700 rollouts, about 2.5 h; run last and drop first. Owner final-eval-eng.
- **Statistics.** Descriptive paired deltas per sub-artifact; additivity check delta(PT) vs delta(P) + delta(T) with seed-level intervals. Exploratory.

### E27 Second domain: airline replication of the grid (Tier 3).
- tau2 airline @8ebb7499 on Azure gpt-4.1-mini: P, T, PT x 2 seeds (opt-20, held-out sel-10 + test-20, which is development-exposed). R about 6 x 550, C about 2.4 M, W about 2 h. Doubles the number of domains from 1 to 2 for the surface claim; underpowered (30 held-out tasks, MDE about 0.12). Run only if capped tokens remain after Tier 2.

### Not recommended (and why)
- **Suite A skill-versus-prompt with an Azure target.** The Suite A evaluator is a daemon with Gemma baked in, sandbox containers on the shared podman network, and the seed capability has two text files (no scripts directory). A skill-package cell needs: a skills directory mounted into the sandbox, a loader in the daemon, an Azure target path, and exposure checks on the 169 residual ids. Each container run is also capacity the Gemma arms need; Gemma is the final-eval critical path (11 to 18 h). Verdict: do not run before the cutoff; list as future work. Suite A's "skill" competitors (SkillOpt, EvoSkill, WikiSkill) edit text injected into the prompt, so a prompt-versus-skill contrast on A would mostly measure text packaging anyway.
- **E13 DAG vs single lineage, E14 merge variants.** Agent-optimize features, 1,650 rollouts each on gpt-oss; cut as the plan already anticipates.
- **Real MCP server evaluation.** No MCP-backed tau2 harness exists. The descriptions-only emulation (E20-TD) is the honest substitute; the paper states `mcp-tool` is implemented and unit-tested but evaluated only as an emulation (or not at all, if E20-TD is cut).

---

## 5. Analysis-only list (no new rollouts; all on search splits until the final set exists)

| item | RQ | source | owner | note |
|---|---|---|---|---|
| per-surface edit statistics: files and lines touched per candidate, edit class (rule, example, checklist, tool code, return value, wrapper, docstring), per surface | 3b | `candidates.jsonl`, `artifact_dir` diffs; `analysis/out/attrib/candidates.csv` and `attribution_by_surface.csv` already exist | metrics-eng | extend with D cells |
| gain against surface | 3a | E20 held-out scores | metrics-eng | from the grid |
| failure-type map: seed failures labelled (missing action, wrong argument, state side effect, communication, other) and mapped to the surface of the fixing edit | 3c | `attrib/seed_failures.csv`, `surface_x_failure.csv` exist for A, B, C; add D | metrics-eng + labelling pass | label on opt/sel only, never on the final set; human-check a sample of 40 |
| regression and protect-set behaviour: fixed, broke, net per promoted candidate; protect-set violations per promotion | 5a, 2d | `attrib/regression_by_arm.csv` (B hc 0 promoted, A hcstock 6 promoted: fixed 8.3, broke 2.5) | metrics-eng | add E23 for the on/off contrast |
| selection-to-held-out shrinkage per arm | 5b | `attrib/shrinkage.csv`; final-set scores | metrics-eng | final needed |
| gate false-accept and false-reject | 5c, 2c | E22 (accept side, null) and E26 (both sides, real candidates) | metrics-eng | section 4 |
| null controls | 2c, C2 | E22 pool, E04 (planned), E05 (done) | metrics-eng | E22 replaces the need for a 9-search null run |
| cost per held-out point; Azure tokens vs capped tokens; anytime curves | 4 | `rollouts_metrics.jsonl`, `candidates.jsonl`, ledger by tag | metrics-eng | gateway over-counts B by 20 to 60% (decisions 21:30): report both ledger and transcript |
| transfer to a second target | 5d | planned Azure re-evaluation of B*/C* artifacts (gpt-4.1 or gpt-5-mini); add D champions to a third target (gpt-4.1) | final-eval-eng | exploratory, outside Holm |
| HC vs AO | 2b | E10, E10B, E10C | stats-reviewer | section 4 E24 |
| promotions per search, inert share | 5c | `attrib/promotions_by_arm.csv` | metrics-eng | already produced |

---

## 6. Final-evaluation cells added by this plan (all Azure-direct; none on gpt-oss or Gemma unless stated)

Order file `order_D.jsonl` through `run_final.py --suite D` (needs a D entry in `fe_common.py`, about 1 to 2 h for final-eval-eng; fallback: tau-runner's `single.py`-style script with the same classifier and retry rule and a hashed order file). One interleaved stream, seed artifact scored inside the same window with n=10 (drift rule 5H).

| block | artifacts | tasks x n | rollouts | Azure time at about 50 per minute |
|---|---|---|---|---|
| seed | 1 | 40 x 10 | 400 | 8 min |
| Tier 1 champions: E20 P, T, PT, CTL, E21 ruleP, 1S, E20-GEPA | 3x6 + 3 = 21 | 40 x 5 | 4,200 | 1.4 h |
| Tier 2 champions: TD, nohist, nodigest, ruleP-2x | up to 12 | 40 x 3 | 1,440 | 0.5 h |
| A5 decomposition (E25) | up to 24 sub-artifacts | 40 x 3 | up to 2,880 | 1 h |
| transfer of D champions to gpt-4.1 (optional) | 21 | 40 x 1 | 840 | 0.3 h |
| **Total D** | | | **about 9,800** | **about 3.3 h** |

Pre-cutoff, search split only: sel-25 scoring of champions (n=5 for Tier 1: 21 x 125 = 2,600; n=3 for Tier 2: 900), E26 (4,250), E22 (1,960).

Existing cells on gpt-oss (B and C) and Gemma (A) are unchanged. The only optional extra there is the E25 decomposition at n=1 (about 700 gpt-oss rollouts), scheduled last.

---

## 7. Ranking by value per cost, and the recommended set

Value: how much of the paper's claims it settles (C1 to C4, RQ1b, RQ3). Cost: capped tokens first (binding), then wall and risk to primary arms. Score = my judgement, 5 best.

| rank | id | what it settles | V | Cost | Fits | tier |
|---|---|---|---|---|---|---|
| 1 | E22 empirical null pool | C2(i) on real noise; noise floor for all cells | 5 | R 2k, C 0 | yes | 1 |
| 2 | E20 {P, T, PT} x 3 | C1, RQ3a/3d (the central missing ablation) | 5 | R 5k, C 3.6 M | yes | 1 |
| 3 | E20-CTL x 3 | does search beat one proposal; anchors cost per point | 4 | R 0.6k, C 0.7 M | yes | 1 |
| 4 | E21 {ruleP, 1S} x 3 | C2(ii): confirmation vs stock vs one-stage on a target where all can promote | 5 | R 3.3k, C 2.4 M | yes | 1 |
| 5 | E20-GEPA x 3 | RQ1b: loop quality at identical surface | 4 | R 1.7k, C 1.2 M | yes | 1 |
| 6 | E25 decomposition on D (final window) | within-champion attribution, additivity | 4 | R 2.9k+1.8k, C 0 | yes | 1 (final) |
| 7 | E26 gate ROC | false accept and false reject on real candidates | 4 | R 4.3k, C 0 | yes | 2 |
| 8 | E20-TD (MCP-style descriptions only) | fourth surface type, honestly labelled | 3 | R 1.7k, C 1.2 M, 1.5 h dev | yes | 2 |
| 9 | E23 {nohist, nodigest} x 2 | C4 causal history | 3 | R 2.2k, C 1.8 M, 2 h dev | yes | 2 |
| 10 | E21-ruleP-2x | inert or merely under-budgeted | 3 | R 3.3k, C 1.2 M | yes | 2 |
| 11 | E20-PTS (skill package) | fourth surface type with real skill semantics | 4 | R 1.1k, C 1.5 M, 4 to 6 h dev | only if code ready by 14:00 | 3 |
| 12 | E24-AO on D | orchestration where promotions occur | 2 | R 0.8k, C 2.4 M | yes | 3 |
| 13 | E27 airline P/T/PT x 2 | second domain | 2 | R 3.3k, C 2.4 M | yes | 3 |
| 14 | E25 on gpt-oss (n=1) | decomposition on the primary target | 2 | 0.7k gpt-oss | tight | 3 (drop first) |

**Recommended launch list.** Tier 1 now (ranks 1 to 6) and Tier 2 (ranks 7 to 10) as soon as the two small code items are merged. Tier 3 only with spare capped tokens. Totals:

| set | Azure rollouts (search + held-out) | capped tokens | USD at list | wall |
|---|---|---|---|---|
| Tier 1 | about 12.5k search + 7k held-out | about 8 M | about $1.0k | wave 1 about 3 h; done by about 16:00 |
| + Tier 2 | + 8k search + 2k held-out + 4.3k gate ROC | + about 4.2 M | + about $0.75k | done by about 21:00 |
| + Tier 3 | + about 5k search | + about 6.3 M | + about $0.3k | done by about 24:00 |

Capped-token position: 60.5 M used at 08:30, projection about 139 M at the cutoff before this plan (decisions 08:23), cap 150 M, final-eval reserve 15 M. Tier 1 + Tier 2 add about 12 M, which is above the headroom. Options in order of preference: (1) stop E12C best-of-k now (its guard allows 8 M per seed, up to 24 M, and it is exploratory and not binding B*); (2) raise the cap for the ablation family only by 15 M; (3) run Tier 1 only. Hill-climb searches stop at the 3.5 M soft guard and are mostly under 0.7 M, so the estimates are conservative.

---

## 8. Dependencies, code changes and owners

| item | what | who | effort | blocks |
|---|---|---|---|---|
| D builder | parametrise `build_cap_project.py` and `launch_cap.sh` for exp id, target/user/judge models, gateway URL, INSTRUCTIONS facts (currently says gpt-oss-120b, 40 k context), tag prefix; `--surfaces`; stock / ruleP / 1S gate blocks | tau-runner | 1 h | all E20, E21, E23 |
| surface lock | `TAU_SURFACES` in the retail adapter `apply()`, `surface_violations.json`, unit test | tau-runner | 1 h | P, T, TD |
| descriptions-only lock | AST check that `tools.py` differs from the seed only in docstrings and parameter descriptions (REMOVE_TOOLS hiding allowed) | tau-runner | 1.5 h | E20-TD |
| history switch | `optimizer.ablation.history` + env `CAPEVOLVE_HISTORY`; default on; test | algo-eng, review repo-auditor | 2 h | E23-nohist |
| skill loader for tau | `skills/<name>/SKILL.md` (+ references, scripts) delivered as a catalog line in the system prompt plus `load_skill`, `read_skill_file`, `run_skill_script` tools; scripts run in a subprocess without network or environment; candidate-fault tagging; `skillcheck` validation | tau-runner + repo-auditor | 4 to 6 h | E20-PTS only |
| null pool replay | `analysis/scripts/null_pool_replay.py` calling the real gate code | metrics-eng | 2 h | E22 analysis (the rollouts need no code) |
| gate ROC | `gate_roc.py` and a candidate scorer | metrics-eng + tau-runner | 2 h | E26 |
| suite D in final machinery + decomposition order builder | `fe_common.py` entry, `decompose.py` | final-eval-eng | 2 h | final cells |
| registry entries | config hashes, seeds, contrasts, margins, SHA, before the first D rollout | stats-reviewer + coordinator | 1 h | all |
| exposure note | D uses retail opt-49 / sel-25 / test-40 with a different target; no optimizer sees test-40; bench-steward records it | bench-steward | 0.3 h | all |
| ledger check | confirm that capped accounting for the 150 M cap sums :4111 and :4112 correctly | metering-auditor | 0.5 h | Tier 1 funding |

Disclosed deviations to record: stock gate reference (not rule P) for the D family; judge `azoai/gpt-4.1` (not azure/gpt-5.5) on D; target and simulator are different models here (gpt-4.1-mini target, gpt-4.1 simulator) unlike B; the descriptions-only cell is an emulation.

## 9. Proposed schedule (UTC, 10-12 to 10-14)

| time | step |
|---|---|
| 09:45 | coordinator approval; funding decision; launch E22 (needs no code) |
| 10:00 to 11:30 | tau-runner: D builder, surface lock, unit tests; stats-reviewer: registry entries; final-eval-eng: suite D entry |
| 11:30 | wave 1: E20 P, T, PT x 3 (c=10), E20-CTL x 3, E20-GEPA x 3 (c=8): about 130 in flight; ramp over 30 min, watch 429 |
| 12:00 to 15:00 | wave 1 runs; sel-25 scoring of champions as they finish; algo-eng merges history switch; descriptions-only lock ready |
| 15:00 | wave 2: E21 ruleP and 1S x 3, E20-TD x 3, E21-ruleP-2x x 3 (about 12 searches; start at most 8 at a time) |
| 15:00 to 19:00 | wave 2 runs; E26 candidate scoring in the gaps |
| 19:00 | wave 3: E23 nohist and nodigest x 2; E20-PTS and E24-AO if ready and funded |
| 22:30 | all D searches done (about 7 h of margin before the cutoff for infra reruns) |
| 06:30 to 10:00 (10-13) | final window: D test-40 cells and E25 decomposition run beside A/B/C; seed re-scored in window |
| by 14:00 (10-13) | D results frozen for the paper |

Stop rules: if the 429 rate exceeds 2% or the median `queue_s` for azoai exceeds 30 s, hold new launches; if capped tokens reach the existing 125 M / 130 M thresholds, stop Tier 3, then Tier 2, then wave 3. Primary arms are never slowed: D uses neither RITS deployment, only the :4111 optimizer path (16-slot `litellm` semaphore shared with the Sonnet optimizers; Tier 1 adds about 12 concurrent optimizer sessions that call it about once a minute each, which must be checked against the AO sessions that already hold it).

## 10. RQ to experiment map

| RQ (STORY.md) | experiments | status |
|---|---|---|
| RQ1 matched comparison | E10, E10B, E10C finals | running |
| RQ1b loop quality at equal surface | E20-GEPA vs E20-P; Suite A HC vs GEPA (prompt only both) | new; free |
| 2a surface width | E20 {P, T, PT, TD, PTS}, E20-CTL | new |
| 2b orchestration | E10 family analysis; E24-AO optional | analysis; optional new |
| 2c gate | E12A, E12C running; E21 {ruleP, 1S, 2x}; E22 null pool; E26 ROC | running + new |
| 2d causal history | E23 {nohist, nodigest} | new + code |
| 2e intake gate | E05 done; E06; intake cost records | analysis |
| 2f DAG, merge | E13, E14 | cut |
| 3a marginal value of a surface | E20 held-out | new |
| 3b edit attribution | `attrib` pipeline on all candidates incl. D | analysis |
| 3c failure-type map | `surface_x_failure.csv` plus D | analysis + labelling |
| 3d interaction | E20 interaction contrast | new |
| 3e MCP surface | E20-TD (emulation) | new, labelled |
| RQ4 cost and efficiency | ledger by tag, cost per point, anytime curves, E22 noise | analysis |
| 5a regressions | `regression_by_arm`, E23 | analysis |
| 5b shrinkage | opt/sel gain vs H65 | analysis + final |
| 5c gate says no | promotions per search, E21, E22, E26 | analysis + new |
| 5d transfer | Azure re-evaluation of B*/C* artifacts; D champions to gpt-4.1 | final extra |
| 5e seed variance, best-of-k | E10 seeds, E12C best-of-k, D seeds | running |
| 5f judge sensitivity | gpt-4.1 re-judge on B/C; D uses gpt-4.1 natively | final extra |

## 11. Risks and honest limits

- **Power.** About 0.08 vs seed and about 0.10 between cells (T=65, n=5, S=3). Small surface differences will read "inconclusive". Mitigation: pre-registered Holm family, TOST margin 0.10, attribution analysis for mechanism, airline replication if funded.
- **One domain.** Surface claims rest on tau2 retail with one target. Say so.
- **Gate reference choice.** The stock gate is the reference, so the E10 CapEvolve rows (rule P) and the D rows are not the same configuration; the paper must not mix them.
- **Held-out reuse.** sel-25 is used for champions of CapEvolve cells only; test-40 is scored once per artifact in the final window; GEPA and any selection-aware method use test-40 alone.
- **Azure rate limits.** Observed 429s at about 7 M tokens/min. Staged ramp, and a second target deployment as fallback.
- **Self-similarity of the simulator.** gpt-4.1 serves as user and judge for a gpt-4.1-mini agent; the same family may favour the agent. Constant across cells, so contrasts are unaffected; absolute levels are not comparable with B.
- **Search-time exposure.** D searches use the same opt-49 as E10B; optimizers run in the same no-egress sandbox; the adapter refuses test ids. The seal on test-40 is unchanged.

---

## 12. Suite E: replication of Suite D (and E26) on tau2 airline, plus competitors (design, 2026-10-12 11:20 UTC)

Status: DESIGN for the four-essentials check by the coordinator. Registered as amendment 10 before the first rollout (draft below). User authorised launch once the design is ready.

### 12.1 Fixed facts
- **Split file (unchanged, every cell and competitor):** `wt-tau/protocol/tau_airline_splits.json`, sha256 `371ab03ba85cf25913f31d37b727077a5d6bcccce7f7c7ca983a3fc5d61e6187` (identical copy in `wt-airE`). opt-20 + sel-10 = the official train-30, test-20 = the official test. tau2 airline has exactly 50 tasks (`tasks.json`, 50), so **no other airline pool exists**; the official test-20 is development-exposed (audit/exposure_ledger.csv) and Suite E is labelled replication, never sealed. Every optimizer, selection and early-stopping step may touch only train-30 (opt-20 for the screen and gate, sel-10 only at `finalize` as in Suite C). A competitor needing its own validation split carves it from train-30 only.
- **Models:** target `azoai/gpt-4.1-mini-2025-04-14`; user simulator and NL judge `azoai/gpt-4.1-2025-04-14`; temperature 0, max tokens 8000; Azure on :4112, the Claude optimizer on :4111 (the same shim, `runs/E10B/_sbx_bin`, except E36 which uses `runs/E26/_sbx_bin`).
- **Code:** worktree `wt-airE` (branch research/suite-e, commit `eb112a08c75e24d60711377c2cfbf3265b86ecd8`) = wt-nohist core (wt-tau 738a7b3ea plus the history flag, default on) plus the Suite D surface lock and judge temperature ported to `examples/tau2_airline_c` (3 unit tests pass). All E cells run on this one code base; E36 differs from E30-PT by the flag and sandbox only.
- **Probe (E00-azprobe-air, seed on opt-20, 3 trials, c=16, under heavy load):** reward 0.233; 14 of 20 tasks always 0, 4 always 1, 2 mixed; null paired SD per task 0.22 (retail 0.57); 65 k tokens per rollout; 0 errors. So airline has large headroom (0.77) and low trial noise: gates see a cleaner signal than on retail, rule P is less inert in expectation, and the MDE is dominated by task heterogeneity and T=20.

### 12.2 Cells (3 seeds each, hill-climb, Sonnet 5.5, run ids mirror D)
| id | = D cell | spec delta | budget |
|---|---|---|---|
| E30-PT (reference) | E20-PT | [system-prompt, tools], stock gate | 300 counted rollouts, 10 iterations |
| E30-P | E20-P | [system-prompt], `TAU_SURFACES=policy` | same |
| E30-T | E20-T | [tools], `TAU_SURFACES=tools` | same |
| E30-CTL | E20-CTL | 1 iteration, no selection | 100 rollouts |
| E31-ruleP | E21-ruleP | rule P (k 1, n_conf 3, z 1.282, dmin 0, cov 0.95), footprint off, coverage joint | same 300 (one confirmation costs 20 x 3 x 2 = 120) |
| E31-1S | E21-1S | one-stage unmasked | same |
| E30-GEPA | E20-GEPA | official GEPA 0.1.4, prompt only, selects on sel-10 | 300 |
| E36-nohist | E26-nohist | history flag off, E26 shim, derived instructions | same as PT |
Budget rationale: opt-20 makes a screen cost 20 rollouts, so 10 iterations cost about 220 plus finalize; 550 (D) would never be used. 300 is matched within E for all cells.

### 12.3 Competitors (owners asked 10:50; answers pending, later wave if late)
Same models, split, 300-rollout budget, 3 seeds; each leaves the family if it cannot finish by 06:00, with the reason recorded. Candidates: GEPA full surface (prompt + tools, only if its adapter allows; otherwise prompt-only is the E30-GEPA cell), HarnessLens (bl-harness), ACE and MIPROv2 (bl-context / baseline-eng), AHE, CapEvolve agent-optimize (my estimate from E10C: 0.5 M capped per search), one-shot control (= E30-CTL). Own Holm family E-comp: E30-PT vs each competitor on test-20.

### 12.4 Held-out scoring
Primary: official test-20, n = 5 trials per champion, seed artifact n = 10 in the same interleaved window. Secondary (descriptive, labelled as including selection tasks of GEPA): H30 = sel-10 + test-20. E25-style decomposition of two-surface champions: optional, n = 3.

### 12.5 Amendment 10 (draft for stats-reviewer; register before the first E rollout)
- 10A Setting and split as above, with the split-file sha256 and the train-only rule.
- 10B Cells and budgets as 12.2; competitor family as 12.3.
- 10C Primary set test-20 only; n = 5 / seed n = 10; H30 secondary.
- 10D Family E: m = 11 mirroring D (P vs PT, T vs PT, P vs T, ruleP vs PT, 1S vs PT, PT vs CTL, P vs GEPA, P vs seed, T vs seed, PT vs seed, nohist vs PT), Holm within E; family E-comp (own Holm); TOST margin 0.10.
- 10E Claim rule: Suite E only corroborates D. A Suite D contrast is 'replicated' if the matching E contrast has the same sign and its artifact-level 95% CI excludes 0; otherwise 'not replicated' (including inconclusive). No pooling of D and E, no cross-suite p-value or headline, and E-only contrasts without a D counterpart (competitors) are labelled replication-domain, exploratory for generality.
- 10F Planning MDE on test-20 (stats-reviewer to compute, tau 0.15, within variance from the probe 0.0475 (null SD 0.22) rather than 0.162): my approximation 0.10 vs seed and 0.11 cell vs cell uncorrected, about 0.14 / 0.15 at m = 11. Rule: failing TOST is 'inconclusive'.
- 10G Exposure: airline test-20 development-exposed (not sealed); no cleaner pool exists.

### 12.6 Cost
| item | Azure rollouts (mini) | capped tokens | USD at list |
|---|---|---|---|
| search, 18 hc searches (6 cells x 3), about 230 each | 4.1 k | 18 x 0.35 = 6.3 M | 0.20 |
| CTL 3 x 100, GEPA 3 x 300 | 1.2 k | 0.3 + 1.2 M | 0.06 |
| final: 24 champions x 20 x 5 + seed 200 + sel-10 n=5 (1.2 k) | 3.8 k | 0 | 0.19 |
| E36 included above | | | |
| **E replication total** | **about 9.1 k** | **about 7.8 M** | **about 0.5 k** |
| competitors (AO 3 x 1.0 M, others to be confirmed) | about 3 k | 3 to 12 M | about 0.2 k |
Capped allowance: replication 8 M (under the 12 M cap), E in total at most 20 M.

### 12.7 Azure capacity (the binding constraint)
Measured at 11:10 UTC from the gateway log (calls with deployment azoai/gpt-4.1-mini): about 480 calls a minute, 8.4% HTTP 429 since 10:20 (0% on gpt-4.1); causes are E22 (4 chunks, 64 in flight), the D wave 1 searches (21 searches) and my probes. D searches are running at about 65 rollouts an hour each, not the 250 planned. The gpt-4.1-mini deployment sustains roughly 25 rollouts a minute (about 1.5 k an hour) in total. Budget until 06:00 (about 18 h): about 28 k rollouts; D needs about 13.5 k more search rollouts and E needs about 5.3 k before 06:00, which fits only at near-full utilisation; D plus E final scoring (about 17 k rollouts) runs in the final window and takes about 11 h at this rate.
Rule: E may start only when (a) E22 has finished and (b) the 15-minute azoai-mini 429 rate is under 2%; waves are admitted by that rule, at most 4 concurrent rollouts per E search and at most 48 in flight for E. Options if the rule is never met: (i) sequence E after D wave 1 (about 14:00 to 15:00 at the current rate); (ii) run E on `azoai/gpt-4.1-2025-04-14` as target (separate quota, 0% 429), which is NOT an exact replication; (iii) ask the user for more quota on the mini deployment.
