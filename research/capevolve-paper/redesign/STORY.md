# CapEvolve paper: method-paper story (story-architect, 2026-10-12)

Status: proposal for coordinator and experiment-designer. Supersedes the measurement-study crux in reviews/paper_draft2/TRIAGE.md section S. The user's original paper (paper_zip/paper.tex) supplies the story and structure only; none of its numbers are reused (they failed the audit: scorer compliance, dev-exposed tests, gold leakage).

Facts checked in the repo and run directories while writing this (they change what is claimable):
- E10 Suite A CapEvolve arms edit ONE surface, `capabilities: [system-prompt]` (runs/E10/hill-climb/s0/project/capevolve.yaml).
- E10B/E10C CapEvolve hc arms edit TWO surfaces, `[system-prompt, tools]` (runs/E10B/hc/s*/.capevolve/project/capevolve.yaml). GEPA, MIPROv2 and ACE edit the prompt only. So on Suite B/C, CapEvolve-vs-GEPA is confounded with surface width. This is a threat to disclose and a reason to run a prompt-only CapEvolve cell (E2 below).
- No arm in the campaign edits a skill package through CapEvolve's `skill-package` capability, and nothing exercises `mcp-tool`. Surface width and capability-type claims therefore need new runs. Do not claim them from E10.
- `hill-climb/scripts/run.py` has `--no-regression` and `--gate-max-broke`, `--focus`, `--protected-paths`, but no switch that removes the causal history (LEDGER impact, protect set, JOURNAL, RUNMAP/prior_iterations; harness.py ~1286, 2183-2290). The history ablation needs a small, reviewed code switch.
- Suite A final = 70 ids sampled from the 239-id residual pool, so 169 residual ids are unused and could serve as a second sealed final set for new Suite A ablation arms (needs an exposure check by bench-steward).

---

## (a) Titles

1. CapEvolve: Optimizing Any Editable Surface of a Frozen Agent Under Code-Owned Evaluation
2. One Loop, Many Surfaces: Gated Optimization of Prompts, Tools and Skills for Frozen Agents
3. What to Edit and When to Accept: A Surface-Agnostic Optimizer with Code-Owned Gates

Recommended: **1**. It names the system, the two novelties (surface as a parameter, code-owned evaluation), and makes no "best optimizer" claim that a matched comparison on three suites cannot carry. Title 2 is the fallback if the byline limit bites.

## Update 2026-10-12 (lead, from analysis/out/searchtime/summary.md)

CapEvolve with rule P promotes almost nothing: it returns the seed in nearly every seed on A, B and C. CapEvolve HC with its stock gate (E12A, E12C) promotes and shows selection-split gains comparable to the competitors (selection-split numbers are optimistic and not cross-comparable). Consequences applied below:
1. The shipped configuration, **CapEvolve HC with the stock gate (hcstock)**, is a headline arm in RQ1 next to rule-P HC and AO. stats-reviewer adds amendment 6: hcstock vs baselines as a secondary Holm family, plus selection-to-final shrinkage for every arm.
2. The gate trade-off is a central RQ (new RQ2c is promoted to **RQ-G**): does strictness buy held-out reliability, or only inertia? Only the final evaluation answers it. The paper must not present rule P as an improvement before that evidence exists; the claim C2(ii) is stated as a two-sided test.
3. Suite D uses the STOCK gate as the default for the surface, history and orchestration cells (CapEvolve as shipped); rule P is one ablation cell (and the one-stage gate another). The reference cell becomes P+T, stock gate, full history.

Amendment 6 (stats-reviewer, protocol/analysis_plan.md, 33ff358b0) fixes how these claims are worded:
- Secondary confirmatory family S-stock: hcstock vs seed and vs each Tier 1 baseline (A 6 rows, C 2 rows, own Holm, compared at min(N*, own count)). The primary family (rule P arms) is unchanged; hcstock vs hc (rule P) is descriptive.
- Shrinkage (selection-split gain minus final-set gain, per seed, SE^2 = SE_sel^2 + SE_fin^2, own Holm per suite) is descriptive context.
- Both were added after seeing search-time selection-split results, so every table, caption and sentence that uses them carries the label "post-search-time".
- Allowed claim: stock-gate CapEvolve gains survive only if the final-set artifact-level interval excludes 0. Generalizing sentences need the pipeline-level interval (5M-2); equivalence wording only via TOST (5M-1).

Suite D frozen cell list (experiment-designer, EXPERIMENTS.md section 0a, bc80398b5; supersedes the cell lists and the 0.05 margin below):
- Target azoai/gpt-4.1-mini (seed 0.612 on opt-49), simulator and judge gpt-4.1, hill-climb, Sonnet 5.5, stock gate, reference cell E20-PT (prompt+tools).
- Cells: PT (3 seeds), rule P on PT (3), P-only (3), T-only (3), one-shot control (3), one-stage gate (3), no-history (2), GEPA prompt-only on the same target (2), descriptions-only as an MCP-style emulation (2), PT+skills (2, only if a tau skill loader is built; the tau adapter has none today). Plus E22 empirical null pool, E25 decomposition, E26 gate ROC (analysis).
- Contrasts (Holm within Suite D, paired by task): each cell vs PT, interaction PT - P - T + seed, P/T/PT vs seed. **TOST margin 0.10** (MDE about 0.10 at 65 held-out tasks; 0.05 could never pass). Small differences read "inconclusive"; all ablation claims use that wording.
- Consequences: mcp-tool is evaluated only as a descriptions-only emulation and must be named that way; the skill-package surface is evaluated only if PTS runs, otherwise it is a stated limitation; the digest-off and 2x-budget rule P cells are Tier 2 and not committed.

## (b) Crux (one paragraph)

Agent optimizers rewrite the files around a frozen model, but each published method fixes what it may edit (usually the prompt, sometimes a skill file or harness code) and trusts its own scores to decide what to keep. Both choices are weak. A fixed surface cannot repair a failure that lives elsewhere (a rule the model forgets belongs in tool code the model cannot skip; a knowledge gap belongs in the prompt), and a self-scored accept rule promotes noise: under trial noise a one-standard-error gate promotes a null candidate in a large share of ten-candidate searches, and an optimizer that can read gold or the scorer can look better than it is. CapEvolve makes the editable surface a parameter of one loop (prompt, tool code, MCP tool surface, skill package, each with its own edit policy), moves every decision the optimizer could game into core code the optimizer cannot edit (gold isolation, a two-stage promotion rule P, footprint and coverage checks, a seal on the final set, concurrent null controls), and feeds the optimizer a causal history of what each earlier edit fixed and broke. We show, at a matched rollout budget against ten published optimizers, which of these design choices carry the gain, what each capability type is worth, and when the gate correctly says no.

## (c) Contributions and the falsifiable claim behind each

| # | Contribution | Falsifiable claim | What would falsify it |
|---|---|---|---|
| C1 | **Surface as a parameter.** One loop, four capability types (system-prompt, tools, mcp-tool, skill-package), per-surface edit policies (change/consolidate/add, never bare-remove a tool, swap via wrapper), capability-scoped optimizer prompt. | Holding algorithm, gate, budget and optimizer fixed, editing prompt+tools beats prompt-only on tasks whose failures need deterministic enforcement (tau2), and does not lose on tasks that are knowledge gaps. Paired final-set difference with family-cluster CI. | Prompt-only cell within the equivalence margin of prompt+tools on tau2 retail, or wider surface strictly worse. |
| C2 | **Code-owned evaluation.** Gold isolation with negative tests, rule P (screen at k_se 1 + fresh-trial confirmation), footprint/coverage gates, seal on final, concurrent null controls and injected-fault tests (E04, E05, E06). | (i) Rule P cuts false promotion under null edits versus a one-stage gate (simulation exists: P ~0.04 vs ~0.57 per 10-iteration search; null-edit control E04 on real runs). (ii) TWO-SIDED, decided by the final evaluation: rule P has smaller selection-to-final shrinkage than the stock gate, but search-time data show it promotes almost nothing, so its final gain may equal the seed. The claim survives only if hcstock's final gain over seed is lower than rule P's per promotion, or hcstock's shrinkage is large; if hcstock simply gains more on held-out data, report rule P as inert and the stock gate as the recommended default. (iii) The negative tests catch the injected faults (15 pass, 7 partial, 6 gap, 1 info; gaps disclosed). | Stock gate final gain larger than rule P beyond margin with similar shrinkage (then rule P is inertia, not reliability); null controls promote at the same rate under both. |
| C3 | **Two orchestration modes over the same gate**: deterministic hill-climb (HC) and agent-mode agent-optimize (AO, a coding agent drives the loop through the skills). | HC and AO reach equivalent final gain at matched rollouts (TOST), but differ in cost and failure mode (AO stops early on its own stop condition: B s0 198, s1 172, C s1 110). | AO beats or loses to HC beyond the margin on any suite; then say which and why from transcripts. |
| C4 | **Causal optimizer context**: per-task BROKE/FIXED impact of prior candidates, protect set, LEDGER (framework facts) / JOURNAL (optimizer handover) / PROCESS (explanation), only the current best step's trajectories. | Removing the causal history raises the number of regressed previously-passing tasks and lowers the final gain at equal budget. | No difference in regressions or gain (then report as null; the context is cost without value at this scale). |
| C5 | **Agentic intake with a hard adapter gate.** Intake wires adapter, trajectories and capability sources; `cap-evolve check` refuses to spend budget until `score()` is deterministic and every method is real. | The gate rejects adapters with stub scoring, nondeterministic scoring and visible gold (E05/E06) before any rollout is spent; intake onboarded N benchmarks at recorded cost. | An injected fault that passes the gate (we already list 6 gaps; they are disclosed). |
| C6 | **A matched, audited comparison** against GEPA, SkillOpt, Meta-Harness, HarnessLens, EvoSkill, WikiSkill, Trace2Skill, ACE, MIPROv2 plus seed and one-shot controls. | Reported without a pre-committed winner. Claims are artifact-level, at matched checkpoint B*, Holm within suite. | n/a (descriptive; if a simpler method wins, that is a result). |

Order in the paper: C1, C2, C4, C3, C5 as method; C6 as the evidence for RQ1. The audit of historical inflation (Gemma 43% and GPT-5.5 80% of the reported gain was scorer compliance) moves from headline to motivation: one paragraph in the introduction and one in section 3, appendix table. It is the reason measurement is code-owned, not a contribution of its own.

## (d) Research questions

**RQ1. Comparison at matched budget.** Does CapEvolve as shipped (hcstock, stock gate) and in its conservative configuration (HC and AO under rule P) improve held-out reward over the seed, and how does it rank against ten competitors at the matched checkpoint B*? Sub-question RQ1b: at the same editable surface (prompt only), does the CapEvolve loop beat GEPA/MIPROv2? This isolates loop quality from surface width and is needed because B/C hc edits prompt+tools while GEPA edits the prompt.

**RQ2. Ablations, one per contribution.**
- 2a Surface width (C1): P vs T vs P+T vs P+T+S (and P vs S on Suite A).
- 2b Orchestration (C3): HC vs AO.
- 2c / RQ-G Gate (C2), central: rule P vs stock gate (E12A, E12C; hcstock is also a headline arm) vs one-stage gate; outcome measures: final gain, promotions per search, inert searches, selection-to-final shrinkage, regressions (accept on the single-stage delta, no confirmation); plus footprint on/off (E11) if capacity allows.
- 2d Causal history (C4): full vs no impact/protect/JOURNAL/RUNMAP (new switch).
- 2e Intake/adapter gate (C5): fault injection (E05/E06), analysis-only; intake cost records.
- 2f Search structure, only if capacity: DAG vs single lineage (E13), merge (E14). Planned and likely cut; say so.

**RQ3. Capability types: where each helps, what each is worth, when to use which.**
- 3a Marginal value: gain of each surface over prompt-only (from 2a), with CI.
- 3b Attribution: classify every accepted edit by surface and edit class (rule, example, tool code, return value, wrapper, skill document) and attribute fixed tasks to it using the LEDGER per-task impact. Analysis-only from candidates and diffs.
- 3c Failure-type map: label each failed seed task (knowledge gap, forgotten rule, tool misuse, long-horizon planning, user-simulator miss) and show which surface fixed which. Gives the "use tool code when the rule must be enforced, prompt when it is knowledge" guidance as a measured table, not an assertion. Needs a labelling pass (LLM-assisted, human-checked sample).
- 3d Interaction: is P+T larger than P plus T? (needs T-only cell).
- 3e MCP tool surface: implemented and tested, not evaluated unless a small run is feasible; otherwise stated as a limitation. Do not claim it.

**RQ4. Cost and efficiency.** Per arm at B*: rollouts, target tokens, optimizer tokens and USD, wall-clock, cost per held-out point, break-even number of deployments. Anytime curves (final-set gain of the best-so-far artifact versus rollouts). Metering caveats: RITS/self-hosted agent tokens are not metered; gateway ledger over-counts Suite B by 20 to 60% versus CLI transcripts; B* sits at 300 to 450, not 600.

**RQ5 (additional analysis questions, mostly free).**
- 5a Regression and protect-set behaviour: per arm, tasks that go pass to fail versus the seed on the final set; net vs gross movement; does the protect set reduce regressions (links to 2d).
- 5b Winner's curse: dev-selection gain versus final gain per arm (shrinkage), the empirical counterpart of the gate claim.
- 5c When the gate says no: promotions per search for every arm, inert searches (return the seed), E12 contrast, what the rejected candidates looked like (were they truly null? use best-of-k and the final set on rejected candidates to compute gate recall).
- 5d Transfer: B* artifacts re-run on a second target (Azure gpt-4.1 or gpt-5-mini; planned in decisions.md 21:10 (b)), outside the Holm family.
- 5e Seed variance (E3): S=3 raw values per arm; best-of-k control (does a single bold proposal beat the loop?).
- 5f Judge sensitivity on tau2 (GPT-5.5 primary vs gpt-4.1 re-judge).

## (e) Experiment and status for each claim and RQ

Legend: RUN = already running, NEW = needs a new run, ANA = analysis-only from existing logs/artifacts, FE = produced by the final evaluation after the cutoff.

| Item | Experiment | Status |
|---|---|---|
| RQ1 / C6 | E10 (Suite A Gemma, 3 seeds), E10B (tau2 retail, gpt-oss), E10C (tau2 airline) all arms at B*, final eval by experiments/final. hcstock (E12A, E12C) added as a headline arm; amendment 6 puts hcstock vs baselines in a secondary Holm family. Suite B has no hcstock arm (E12B not run), so on B the shipped-gate comparison is missing: state it | RUN; FE |
| RQ1b prompt-only fairness | CapEvolve HC prompt-only vs GEPA at one budget on one suite. Free version: Suite A (HC there is already prompt-only, so HC-vs-GEPA on A is already the matched-surface comparison). Add that framing to the paper; B/C get the cell from 2a | ANA (A) + NEW (see 2a) |
| 2a surface width | Suite D (proposed): tau2 retail with an Azure-direct target (uncapped; gpt-4.1-mini or gpt-5-mini; judge azoai/gpt-4.1-2025-04-14, simulator Azure-direct), same task splits as B so sealed test-40 is reused. Cells: P, T, P+T, P+T+S, all HC with the STOCK gate (CapEvolve as shipped; reference cell P+T stock), same budget (about 300 to 400 rollouts), 2 seeds each (P+T reference 3). A skill-package cell needs a tau2 skill loader; if not available in time, run the skill contrast on Suite A with an Azure target on the unused residual ids (P vs S vs P+S) | NEW, highest priority |
| 2b orchestration | HC vs AO from E10/E10B/E10C. Add AO on Suite D as the 4th ablation cell if capacity | RUN; ANA; optional NEW |
| 2c gate | E12A (Suite A stock gate), E12C (Suite C stock gate) running. One-stage gate: NEW cell on Suite D (cheap; confirmation off). Replay of the gate on historical logs (#791) and the null-edit simulation as supporting evidence. E04 null-edit control and E05/E06 already done | RUN; NEW (1 cell); ANA |
| 2d history | HC with history off (no impact/protect/JOURNAL/RUNMAP/prior_iterations) on Suite D vs full. Needs a reviewed code switch (small PR, env or yaml flag, default unchanged), then 2 seeds | NEW + code |
| 2e intake gate | E05 (done), E06 negative test, intake cost/time from past run records and dashboards; list of benchmarks onboarded | ANA |
| 2f DAG/merge | E13, E14 | NEW, expected cut |
| 3a, 3d | From 2a cells (marginal gain, interaction needs T-only) | NEW (same runs) |
| 3b edit attribution | candidates.jsonl, diffs and LEDGER impact for E10B/E10C/Suite D hc and ao | ANA |
| 3c failure-type map | label seed failures on the opt/sel splits (not the final set) and map to the fixing surface | ANA + labelling |
| RQ4 cost | metering ledger (azure_tokens bucket separate), rollouts_metrics.jsonl, run clocks; anytime curves from candidates.jsonl re-scored at final | ANA (+FE for held-out curves) |
| 5a regression | per-task final outcomes from FE vs seed; LEDGER broke/fixed on sel | FE + ANA |
| 5b shrinkage | sel-set gain vs final gain per arm | FE + ANA |
| 5c gate says no | promotions per search (analysis plan 5M), AO early stops, E12; best-of-k (E12C) | RUN; ANA |
| 5d transfer | Azure re-evaluation of B* artifacts | FE (planned) |
| 5e seed variance, best-of-k | E10 seeds; E12C best-of-k | RUN; FE |
| 5f judge sensitivity | gpt-4.1 re-judge via Azure-direct | FE (planned) |

Capacity notes for the designer. The binding limits are gateway throughput on gpt-oss/Gemma and non-RITS optimizer tokens (about 60M of 150M used, about 3.7M/h pace projects to about 139M, stop rules at 125M and 130M). A Claude Sonnet 5.5 optimizer spends about 2.5 to 4M per run, so new Suite D runs on the capped bucket would fit only about 3 to 4 runs. Options, in preference order:
1. Run the Suite D optimizer through an uncapped route (Codex CLI backend on Azure-direct via :4112, e.g. gpt-5.1-codex which is Responses-only; or a gpt-5/o3 chat backend if the registry supports it). Then all Suite D cells share one non-Claude optimizer. This changes the optimizer versus E10, so Suite D is a self-contained ablation family, never mixed into E10 tables. It also yields an incidental optimizer-model robustness point.
2. Keep Sonnet 5.5 for the P+T reference and the cells that matter most (T-only, P-only), cut seeds to 1 and say so.
3. Ask the user for a cap raise for ablations only.
Timing: Suite D cells are rollout-capped, not B*-bound, so they can finish after 2026-10-13 06:00 as a separate pre-registered ablation family if the coordinator agrees; they must be registered (config, seeds, contrasts, margins) in experiments/registry.jsonl before launch, and judged on sealed test-40 only through experiments/final.

Statistics for the ablation family: paired by task, family-cluster CR1, own Holm, TOST margin pre-set (frozen at 0.10, see update above), S=2 or 3 means artifact-level claims with t(S-1) caveats; effect sizes with CIs, "inconclusive" otherwise. All ablation results are labelled exploratory-confirmatory (pre-specified, outside the E10 Holm families).

## (f) Section outline and page budget (MLSys, 10 pages body, references and appendix extra)

| Section | Pages | Content |
|---|---|---|
| Abstract | 0.25 | Problem, CapEvolve in one sentence, ablation and comparison findings with numbers (after FE) |
| 1 Introduction | 1.0 | Fixed surfaces and self-scored gates as the two gaps; Figure 1 (loop with four surfaces and the code-owned boundary); contributions C1 to C6; one paragraph on the audit that motivated code-owned measurement |
| 2 CapEvolve | 2.25 | 2.1 Problem and editable surface as a parameter (per-surface edit policies, Table 1: surface, what is edited, policy, seed example); 2.2 Agentic intake and hard adapter gate; 2.3 Algorithms and the two orchestration modes (Algorithm 1: HC; AO as agent-driven); 2.4 What the optimizer receives (LEDGER/JOURNAL/PROCESS, BROKE/FIXED, protect set); Figure 2 system diagram |
| 3 Code-owned evaluation | 1.0 | Gold isolation, rule P (screen plus fresh-trial confirmation, parameters), footprint/coverage, seal, concurrent null controls; Figure 3: false-promotion vs power simulation; fault-injection summary |
| 4 Experimental setup | 0.9 | Suites A/B/C (+D), exposure of each final set, targets and optimizer, ten competitors and their surfaces (Table 2), matched checkpoint B*, statistics, ablation family |
| 5 Results | 3.0 | 5.1 RQ1 comparison (Table 3, forest plot) 1.0; 5.2 RQ2 ablations (one panel per ablation, Figure 4) 1.0; 5.3 RQ3 capability types (surface-by-failure-type table, decision guide) 0.6; 5.4 RQ4 cost and RQ5 regression/shrinkage/gate-says-no 0.4 |
| 6 Related work | 0.5 | Surfaces (P/T/M/S/H matrix), accept rules and measurement, concurrent work (Piao et al. 2609.39148, Rethinking Harness Evolution 2607.12227, PACE, SAGE) |
| 7 Limitations and discussion | 0.6 | Honest threats (g), mcp-tool unevaluated, S=3, one optimizer model |
| 8 Conclusion | 0.2 | |
| Total | about 9.9 | Appendix: competitor configs and deviations, incident log, per-suite tables, historical audit decomposition, edit examples, full ablation tables, prompts |

Reuse from the old draft: section 3 text on gates and the protocol, related.tex, appendices. Cut: the "audit and measurement protocol" as contributions 1 and 2, and the gate trade-off as finding 4 (it becomes ablation 2c).

## (g) Honest-comparison principles and threats to disclose

Principles
1. Matched checkpoint B* from rollout counters only; every arm sees the same splits, target, optimizer model (Sonnet 5.5), judge and error classifier. Secondary and exploratory arms are compared at min(B*, own count) with counts printed.
2. Claims are artifact-level (E2-conditional on S champions) with seeds shown raw; no "best optimizer" language; "inconclusive" and TOST equivalence rather than "no difference".
3. Same surface or the surface gap is stated beside every CapEvolve-vs-competitor number (B/C: P+T vs P). The prompt-only cell is the tie-breaker.
4. Ablations vary one factor against the same reference cell, with the reference run counted once and seeds paired.
5. Every dev-set number is a diagnostic. Only sealed-final numbers appear in tables that rank or ablate. Winner's curse is measured, not hidden.
6. Negative and null results are reported with the same prominence: AO early stops, inert gate searches, T-only or history ablations that do nothing, any competitor that beats CapEvolve.
7. Failed reproductions, adapter deviations and infra incidents go to an appendix table with direction of expected bias.

Threats and disclosures
- We built CapEvolve and ran every competitor: authors' tuning effort is asymmetric. Competitors run from official code with adapters; WikiSkill is our reimplementation; the roster of deviations is in the appendix.
- Surface asymmetry (above), optimizer-token asymmetry (4M non-cache-read guard, but tool-based optimizers read more per iteration), metering gaps on RITS/gpt-oss.
- Suite A final is score-exposed (residual pool, seeded sample); Suite B sealed; Suite C development-exposed, never the sole basis of a generalization claim.
- Rule P is conservative and, in the search-time data, promotes almost nothing (returns the seed in nearly every seed on A, B, C). Its parameters were fixed from simulation before the final set. The paper reports both gates and lets the final evaluation decide; selection-split gains are optimistic and not cross-comparable across arms. Suite B has no stock-gate arm.
- Same-split adaptivity: CapEvolve selects and gates on the same split D_opt = D_sel; competitors use train/val. Disclose and show the shrinkage measure (5b).
- Infra incidents: pre-13:11 zeros in competitor histories versus CapEvolve dropping errored trials; hot-swap incident (hc s2 outage); AO Read-tool permission denial (agents read the playbook through Bash; full SKILL.md read in all 26 sessions); hang rule difference on Suite B; EvoSkill starvation; ACE content-filter rename; HarnessLens relaunches.
- Judge substitution on tau2 (GPT-5.5 for gpt-4.1); targets saturated at Gemma and gpt-oss; transfer targets exploratory.
- Suite D ablations use a different target, judge, and possibly optimizer; they establish mechanism, not rank.
- mcp-tool surface not evaluated; intake evidence is a fault-injection suite, not a user study; small S (2 to 3).
- Concurrent work (Piao et al., Rethinking Harness Evolution, PACE, SAGE) overlaps in surface and gate ideas; we claim the combination and the controlled ablations, not any single idea.

## Requests to coordinator and experiment-designer

1. Decide whether Suite D (Azure-direct target, separate pre-registered ablation family, may finish after the search cutoff) is allowed; it is the only way to answer 2a, 2d, the T-only/P-only cells and 3a/3d.
2. Confirm an uncapped optimizer route (Codex or other backend on :4112) or a token allowance for about 14 to 17 runs.
3. repo-auditor / algo-eng: a reviewed "history off" switch and a one-stage gate setting; a tau2 skill-package loader (or choose Suite A for the skill contrast).
4. bench-steward: exposure ruling on the 169 unused SpreadsheetBench residual ids as a second sealed final set for Suite A ablation arms.
5. Priority if capacity shrinks (all cells stock gate unless noted): (0) rule-P cell on the reference configuration, (1) P vs P+T, (2) no-history, (3) T-only, (4) one-stage gate, (5) skill contrast, (6) AO on Suite D. Everything else in RQ3 to RQ5 is analysis-only and does not compete for rollouts.
