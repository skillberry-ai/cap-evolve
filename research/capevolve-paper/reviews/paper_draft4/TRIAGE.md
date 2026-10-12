# Triage of review round 3 (draft 4, commit 35b73dd7e)

Editor: triage. Inputs: reviews/R1.md to R5.md (R1 senior AC, R2 same-subfield, R3 detail checker, R4 methodologist, R5 writing editor).

## 0. Conventions and caveats

- LIVE = /home/dev/projects2/cap-evolve-campaign. Paper root PAPER = research/capevolve-paper/paper/ ; campaign root RCP = research/capevolve-paper/. All file:line below are in the live tree. `git status` shows no modification under paper/ since 35b73dd7e (only decisions.md, experiments/final/*, two untracked scripts), so frozen-draft line numbers are still valid. decisions.md has uncommitted edits.
- Verdict vocabulary: CONFIRMED, REFUTED, PARTLY, UNVERIFIED (could not check from the sources).
- Class: TEXT, DATA, DESIGN, REBUT, DEFER. Severity: SINK (would sink acceptance if left as is), WEAKEN, POLISH.
- Owners: paper-core (body sections), paper-lit (sections/related.tex), paper-results (tables, figures, scripts under PAPER/scripts). Where another agent must supply a fact I name it.
- Many reviewer observations about Tables 4/5, 6, 14-16, 20-22, 31-33 are about MOCK or `\pend` values (red dagger). I report them as DATA/POLISH only when they expose a structural problem; arithmetic on mock numbers is not a finding about the science.
- Scratch-only evidence: the tau2 builders live in /home/dev/projects2/campaign-scratch/scripts/E10B, E10C, E20 (not in the repo). Anything the paper cites from them should be archived with the artifact (see I33).
- Known pending coordinator decisions, not re-analysed: amendment 8 (Suite D primary on test-40 instead of H65) and a possible no-history cell. I only list their text consequences (I01, I06).

## 1. Counts

Primary class per item (see index). Counted by script from the index rows.

52 merged items. By class: TEXT 31, DESIGN 9, REBUT 7, DATA 3, DEFER 2. By severity: SINK 6, WEAKEN 26, POLISH 20.

| Class | SINK | WEAKEN | POLISH | Total |
|---|---|---|---|---|
| TEXT | 4 | 14 | 13 | 31 |
| DATA | 0 | 2 | 1 | 3 |
| DESIGN | 1 | 8 | 0 | 9 |
| REBUT | 0 | 1 | 6 | 7 |
| DEFER | 1 | 1 | 0 | 2 |

Section 6 numbers the decisions D1 to D11. D1 (history cell) and D2 (amendment 8) are the two already pending with experiment-designer; D5 (equivalence margin) hangs off the TEXT item I08. The nine DESIGN-class items are I03, I25, I27, I34, I35, I36, I43, I44, I45.

## 2. Index (merged items)

Columns: ID, title, raised by, verdict, class, severity, owner.

| ID | Title | Raised by | Verdict | Class | Sev | Owner |
|---|---|---|---|---|---|---|
| I01 | History ablation promised in abstract, intro, 2.4; not run; "causal" label | R1 R2 R3 R4 R5 | CONFIRMED | TEXT | SINK | paper-core, paper-lit |
| I02 | "Any editable surface" while two surfaces are evaluated | R1 R2 R3 R4 R5 | CONFIRMED | TEXT | SINK | paper-core |
| I03 | Headline arm (stock gate) chosen after search-time results; headline estimand undeclared | R1 R2 R3 R4 | CONFIRMED | DESIGN | SINK | coordinator, paper-core |
| I04 | Abstract and contributions promise comparisons the design cannot resolve (power, MDE 11 to 15 points) | R1 R2 R3 R4 | CONFIRMED | TEXT | SINK | paper-core |
| I05 | Institution named in the anonymised paper | R5 | CONFIRMED | TEXT | SINK (if double-blind) | paper-core |
| I06 | Suite D final set H65 includes the 25 selection tasks, still labelled sealed | R3 R4 | CONFIRMED | DEFER | SINK | experiment-designer (amendment 8) |
| I07 | Which split gates acceptance is described inconsistently (Table 2, App. B, Fig. 6) | R3 | PARTLY | TEXT | WEAKEN | paper-core |
| I08 | Equivalence: text contradicts the analysis plan; margin equals the MDE; vacuous when both arms are inert | R3 R4 | CONFIRMED | TEXT | WEAKEN | paper-core |
| I09 | Suite A final set provenance, header "verified-400", scorer-audit coverage | R3 R4 | PARTLY | TEXT | WEAKEN | paper-core |
| I10 | Missingness and search-time infra handling: "one rule for every arm", win rule omits the pessimistic bound | R2 R4 | PARTLY | TEXT | WEAKEN | paper-core |
| I11 | "Official code" wording; competitors re-targeted; pins missing for five arms | R1 R2 R3 R4 | CONFIRMED | TEXT | WEAKEN | paper-core, baseline-eng |
| I12 | Gate narrative: shipped default vs rule P, unmasked comparator, "measured" vs simulated, tiny expected gain | R1 R2 R3 R4 | CONFIRMED | TEXT | WEAKEN | paper-core |
| I13 | DarwinX acceptance rule mischaracterised (it is screen then confirm) | R2 | CONFIRMED | TEXT | WEAKEN | paper-lit |
| I14 | Related work gaps: Meta-Harness history, EvoTool/DRAFT and the MCP novelty sentence, differentiation placed last | R1 R2 R5 | PARTLY | TEXT | POLISH | paper-lit |
| I15 | Roster and family labels inconsistent across Sec. 4.2, Tables 3 to 5, Figs. 2 and 4; "nine competitors" never compared together | R2 R3 R4 | CONFIRMED | TEXT | WEAKEN | paper-core, paper-results |
| I16 | Suite D primary Holm family is listed as nine contrasts but registered as ten | R3 R5 | CONFIRMED | TEXT | WEAKEN | paper-core |
| I17 | Cost totals ($84, 650M, 623M, 26.7M) are stale and mix definitions | R3 | CONFIRMED | DATA | WEAKEN | paper-results |
| I18 | SkillOpt exceeds the 4M optimizer-token guard (119%); text says every arm is capped | R3 | CONFIRMED | TEXT | WEAKEN | paper-core, paper-results |
| I19 | Tables and a figure are included twice | R3 R5 | CONFIRMED | TEXT | POLISH | paper-results |
| I20 | Mock/real mixing and snapshot drift across tables (Table 6 vs text, mock deltas, HarnessLens on C, two intervals for one contrast, candidate counts) | R2 R3 R4 | PARTLY | DATA | POLISH | paper-results |
| I21 | Table 7 denominators missing; two failure taxonomies | R3 | PARTLY | TEXT | POLISH | paper-core, paper-results |
| I22 | Notation clashes, internal run codes, uncited method names | R3 R5 | CONFIRMED | TEXT | POLISH | paper-core |
| I23 | Story and sentence level fixes (abstract, intro, contributions, captions, repetition) | R5 R1 | CONFIRMED | TEXT | POLISH | paper-core |
| I24 | Search-time outcomes stated as findings; "returned the seed" for searches still running | R1 R2 R3 R4 | CONFIRMED | TEXT | WEAKEN | paper-core |
| I25 | Suite B agent-optimize could read opt/sel gold; B and C AO arms in headline tables | R1 R4 | CONFIRMED | DESIGN | WEAKEN | coordinator |
| I26 | Orchestration comparison is a bundle; gate cells differ in more than "two-stage" | R4 R3 | CONFIRMED | TEXT | POLISH | paper-core |
| I27 | Inert seeds: final-window delta rule, shrinkage zero by construction, cost per point drops non-positive seeds | R3 R4 | CONFIRMED | DESIGN | WEAKEN | coordinator, paper-results |
| I28 | Cluster unit described three ways; Fig. 8 mock families sum to 120 | R4 | PARTLY | TEXT | POLISH | paper-core, paper-results |
| I29 | Multiplicity across families; unadjusted interval beside Holm p | R4 | PARTLY | TEXT | POLISH | paper-core |
| I30 | Pre-registration and amendment disclosure incomplete; selection of the 70 ids not stated | R4 | PARTLY | TEXT | WEAKEN | paper-core |
| I31 | Matched checkpoint: operating characteristics not at realised N*; 550 vs 600; six vs ten candidates | R3 R4 | CONFIRMED | DATA | WEAKEN | paper-results |
| I32 | Surface claims rest on Suite D and on search-time failure labels; decision guide | R1 R2 R4 | CONFIRMED | TEXT | WEAKEN | paper-core |
| I33 | tau2 tool edits could change the reference outcome | R2 | REFUTED | REBUT | WEAKEN | paper-core |
| I34 | Missing cheap controls and baselines (CASD, NPO, best-of-k on A/B, one-shot on A, k=2 gate, SAGE) | R2 R4 | CONFIRMED | DESIGN | WEAKEN | coordinator |
| I35 | Few seeds, small final sets, exposure asymmetry (40 vs 120 tasks), weak targets only | R1 R2 R4 | CONFIRMED | DESIGN | WEAKEN | coordinator |
| I36 | No stock-gate arm on Suite B, the one sealed main suite | R2 R4 | CONFIRMED | DESIGN | WEAKEN | coordinator |
| I37 | "Seal" wording, seed/proposer provenance, Suite C presented with Holm and stars | R1 R4 | CONFIRMED | TEXT | WEAKEN | paper-core, provenance-auditor |
| I38 | Statistical details: show the MDE formula, SE helper, judge validity | R4 | PARTLY | TEXT | POLISH | paper-core |
| I39 | MLSys systems measurements thin in main text | R1 | CONFIRMED | TEXT | POLISH | paper-results |
| I40 | One-shot control described as unconditional but gated on B and C | R3 | CONFIRMED | TEXT | POLISH | paper-core |
| I41 | Small disclosure gaps (step cap, Suite D noise claim, Table 8 M/S marks, artifact class on A) | R3 R1 | CONFIRMED | TEXT | POLISH | paper-core, paper-lit |
| I42 | Bib/author and optimizer-model details that need a check | R3 | UNVERIFIED | TEXT | POLISH | paper-lit |
| I43 | Title scope: keep "Any Editable Surface" (user decision) or retitle | R1 R3 R5 | CONFIRMED | DESIGN | WEAKEN | coordinator |
| I44 | Native-surface run of a re-targeted competitor | R2 | CONFIRMED | DESIGN | WEAKEN | coordinator |
| I45 | History ablation cell (E23-nohist) run or not | R1 R2 R3 R4 | CONFIRMED | DESIGN | WEAKEN | experiment-designer (pending) |
| I46 | Reviewer asks for evaluation-integrity as the lead claim | R1 | REFUTED | REBUT | POLISH | paper-core |
| I47 | "Rule P vs stock power curve is missing" | R1 | REFUTED | REBUT | POLISH | paper-core |
| I48 | "0.52 to 0.58 is far above a 16% per-candidate rate" | R3 | REFUTED | REBUT | POLISH | paper-core |
| I49 | "MDE is optimistic, 13 to 15 points on Suite A" | R4 | REFUTED | REBUT | POLISH | paper-core |
| I50 | "Table 7 implies 77 to 84% failure on B" | R3 | REFUTED | REBUT | POLISH | paper-results |
| I51 | "Table 6 and text disagree on promotions" and "Table 30 cap used = sum x 10" | R2 R3 | REFUTED | REBUT | POLISH | paper-results |
| I52 | Final evaluation results slots, E22 null pool, N*, shrinkage, Tables 4/5 numbers | all | n/a | DEFER | WEAKEN | results-collector, paper-results |

## 3. Top 10 (one line each, ranked)

1. I01 The abstract, intro and Sec. 2.4 advertise a history ablation that Sec. 5.2 and Sec. 7 say was not run (five reviewers); cut the claim or run E23-nohist.
2. I02 "Any Editable Surface" plus Fig. 1 and Table 8 show four surfaces while two are evaluated; scope the abstract and mark M and S "implemented, not evaluated".
3. I03 The stock-gate headline arm was chosen after search-time results (analysis_plan.md:138-146) and no dated headline estimand exists; commit one before any final score.
4. I04 The study is powered for 11 to 15 point artifact differences while search-time gains are a few points; rewrite abstract and contributions as descriptive estimates on three frozen artifacts.
5. I06 Suite D final set H65 contains the 25 gating-adjacent selection tasks (amendment 8 pending); Table 2 still says "sealed*".
6. I05 Sec. 4.1 names "IBM RITS (Research Inference Service)" in an anonymised submission.
7. I08 Setup:65 and Results:42 make equivalence claims that analysis_plan.md:111 forbids (Suite C, pipeline level); margin 10 equals the MDE and TOST power at true zero is about 0.5 on A.
8. I12 The 0.52 to 0.58 false-promotion figure is a simulation of the unmasked one-stage gate, rule P's expected gain is +0.0011 to +0.0024, and the shipped default is the other gate; say so in Sec. 3.
9. I16/I17 Two plain factual errors: the registered Suite D family has ten contrasts (the text omits prompt-only vs tools-only), and the cost totals ($84, 650M) are a stale snapshot (now $216 capped-proxy, 1,556M ledger tokens).
10. I27 Seeds that return the seed artifact have no stated final-window rule, make shrinkage zero by construction, and are dropped from cost-per-point means; decide the rule before final scoring.

## 4. Verification ledger for the specific claims you named

| Claim | Verdict | Evidence |
|---|---|---|
| R3: Suite A final set is 239 residual ids of the 912 release and is outside the scorer audit | PARTLY. The 239 are outside verified-400 by construction, but they ARE gold-as-output screened | RCP/protocol/final_set_candidates.md:13-26 (pool = 912 minus verified-400 = 512 ids; rule 5 gold scorable as saved, rule 6 scorable after LibreOffice 25.8.7.3 recalculation; 294 eligible), :42 (55 ids share a family with a dev-exposed task, leaving 239); decisions.md:70 (sample seed 20261013, hashed before scoring). The paper never says this: setup.tex:9, :24, limitations.tex:8, main_A.tex:13 ("verified-400" header is wrong for the final set). |
| R3: gating split 25/10 vs 49/20 | PARTLY. For CapEvolve arms on B and C the gate reads opt (49, 20); sel-25/sel-10 are not read by any CapEvolve gate. GEPA gates on sel-25. Table 2 caption wrongly says sel gates acceptance | analysis/out/searchtime/summary.md (split column: B hc/ao/oneshot "opt-49", B gepa "sel-25", C hc "opt-20"); protocol/analysis_plan.md:88 (rule P sim "screen on opt-49" B and "opt-20" C); redesign/EXPERIMENTS.md:91; decisions.md:195. So Table 14 was simulated at the true CapEvolve gating counts. Sensitivity sims at 25 and 10 exist: analysis/out/sim_budget_B_sel25.md (rule P c: 0.086 false promotion; one-stage 0.494), sim_budget_C_sel10.md (rule P c: 0.125). |
| R3: budget 600 vs 550 | CONFIRMED | config_generated.tex shows max_metric_calls=550 for B and C CapEvolve and one-shot, 600 for GEPA B/C, GEPA A max-metric-calls=555 with hard cap 600; analysis_plan.md:88 "550 counted search rollouts on B and C"; decisions.md:133 "600/550+finalize"; text says 600 for every arm (setup.tex:56, config.tex:24); Suite D 550 (setup.tex:56, registration json). Moot at N* below 550 but must be stated. |
| R3: $84 and 26.7M | CONFIRMED stale | numbers.tex:9-13 (costUsdProxy 84, costTokensM 650, costRitsM 623, costNonRitsM 26.7; all `\prov`). Current analysis/out/metrics/campaign_totals.json (09:27 UTC): 263,236 calls; ledger tokens 1,555.66M; RITS 1,425.60M; Azure 59.61M; capped (neither rits/ nor azoai/) 70.45M; Anthropic list proxy $216.03 (capped) plus Azure list $27.94 (not billed) = $243.96. R3's Table 36 sums also check: optimizer USD column sums to 83.97 on Suite A alone (coincidence with the stale $84), 130.8 over A to C; non-cache optimizer tokens sum to 40.4M; target tokens 986M (cost_so_far.tex). |
| R3: Tables 4/5 delta arithmetic | CONFIRMED on the mock numbers, no finding about the science | main_BC.tex:15-31 (every cell is `\pend`; e.g. GEPA 56.3 vs one-shot 57.9 shown -1.0; HC C 42.6 vs 39.2 shown +5.7); main_A.tex:21-33 shows "as shipped minus seed" as [-2.1,+10.9] and again [-1.7,+10.6]. Generator is paper/scripts/mock_numbers.py. Real deltas are paired with missing cells so small mismatches with the score column are legitimate; add a footnote. |
| R3/R4: Fig. 8 families sum to 120 | CONFIRMED, mock | scripts/mock_numbers.py:36 FAMILIES 31+24+21+17+15+12 = 120; real pool has 255 families over 294 ids (final_set_candidates.md:42), final set is 70 ids. |
| R3: Suite D Holm family has nine contrasts | CONFIRMED the text lists nine; the registered family has ten | experiments/configs/suite_D_registration.json "holm_primary_m10" includes "E20-P vs E20-T"; analysis_plan.md:161 item (3). setup.tex:63 omits it. |
| R3: SkillOpt at 119% of the 4M cap | CONFIRMED | analysis/out/metrics/metrics_by_arm.csv, row A skillopt seed 1: optimizer_noncache_tokens 4,778,086 and 119.5 percent; summary.md SkillOpt s2 4,674,105 at 08:47. decisions.md:339 header says the guard is frozen for all arms; SkillOpt has no soft/hard stop. |
| R3: Table 30 "Cap used = sum x 10" | REFUTED, placeholder table | cost_tokens.tex:5 caption ends "(placeholder)"; the real table cost_so_far.tex shows cap used per largest seed (0.43M sum gives 5%, 5.34M gives 69%). |
| R3: Table 7 implies 77 to 84% failure on B | REFUTED | B hc/ao gate and report on opt-49, not sel-25 (summary.md); 3 seeds x 49 = 147 units, 58 to 63 failed is 39 to 43%, matching seed score 0.53 to 0.65. A: 3 x 40 = 120 units; C: 3 x 20 = 60 units (29 to 31 failed). Denominators are simply not printed. |
| R3: Tables 20-22 equal 31-33; Figs. 2 and 4 same | CONFIRMED | appendix/v2_results_appendix.tex:6-8 and appendix/results_extra.tex:13-15 both `\input` ablation, decomp, rq4; fig_contrast.pdf at sections/v2_results.tex:23 and appendix/results_extra.tex:7. |
| R3: HarnessLens on C, MIPROv2/ACE on B and C | CONFIRMED inconsistent | v2_setup.tex:38-48 (HarnessLens B only; MIPROv2, ACE A only); decisions.md HarnessLens relaunch entries are all Suite B; summary.md has no harnesslens C row; but main_BC.tex:25 lists HarnessLens on C, and v2_results.tex:16, v2_limitations.tex:6 say GEPA, MIPROv2 and ACE edit the prompt only on B and C. |
| R3: Table 14 gain column | CONFIRMED | paper/appendix/sim_table.tex: rule P +0.0014, +0.0011, +0.0024; one-stage +0.0034, +0.0046, +0.0051 (from analysis/out/sim_budget_{A,B,C}.md). Not in the body. |
| R3: Table 14 numbers 0.068/0.040/0.113 and 0.58/0.52/0.55 | CONFIRMED | sim_budget_{A,B,C}.md option c and f rows. |
| R3: 6 vs 10 candidates | CONFIRMED | fig_rulep is built from the older Suite A only sim, analysis/out/sim_budget.md "6 candidates" (one-stage 0.434; caption says six); the per-suite sims screen 6.7 to 9.4 candidates for rule P, 10.0 for one-stage. |
| R3: one-shot control is not unconditional | CONFIRMED | summary.md B oneshot rows: "returned=seed True" in 2 of 3 searches, "native finish (iterations)"; Suite D registration "1 iteration, 200 rollouts, no selection". setup.tex:49 says "one unconditional step". |
| R3: Appendix E arithmetic | UNVERIFIED (not re-derived; audit/recomputed_numbers.csv is the source) | |
| R4: Suite D final set includes selection tasks | CONFIRMED (pending) | setup.tex:63, :9, :19; registration "final_set H65"; analysis_plan.md:158. |
| R4: TOST power at margin 10 | CONFIRMED | normal approximation with SE = MDE/2.8 gives about 0.51 (A), 0.63 (B), 0.18 (C) at true difference 0. The plan itself says the margin is "about the conditional MDE" and that Suite C is descriptive only (analysis_plan.md:111). |
| R4: power table (5 point gain, Holm first step) | CONFIRMED arithmetic | z = 5/4.29 = 1.17 gives 0.21 unadjusted and 0.045 at alpha 0.05/12. |
| R4: MDE reconstruction 13 to 15 vs stated 12 | REFUTED | stated MDE is for the mean of the 3 frozen champions (analysis_plan.md:105 "5L"; mde_observed.md A, T=70, n=1, tau 0.15: 0.117; B T=40 n=3: 0.110; C: 0.152). R4's 14.9 is the single-champion figure. The paper just does not show the formula. |
| R4: headline chosen after rule P looked inert | CONFIRMED | decisions.md:349-354 (08:33 user direction, 08:40 decision), analysis_plan.md:138-146 (amendment 6 labelled as made after seeing search-time results). |
| R4: win rule ignores missingness bounds | PARTLY | analysis_plan.md:63 and :180 require Holm p < .05, CI excluding 0, and the pessimistic bound; amendment 5O-1 says that if primary and sensitivity differ "the primary stands". setup.tex:65 states only the first two conditions. |
| R4: amendments 1 to 5 not listed | PARTLY | they exist with timestamps and "no final-set data seen": analysis_plan.md:68, 90, 107, 122, 126, 138, 150 (amendments 1 to 7). The paper reports only 6 and 5O. |
| R4: drift rule is a degree of freedom | PARTLY | rule is pre-specified (analysis_plan.md:99: block-adjusted estimate becomes headline if drift exceeds 2 SE) and all rollouts are one seeded permutation (experiments/final/order.py:7-9). The paper states neither. |
| R2: shared adapter scored Gemma failures as zero for competitors, CapEvolve dropped them | CONFIRMED | appendix/protocol.tex:42. Later uniform rules: decisions.md:79 (hang rule), :274 and :326 (infra retry), analysis_plan.md 5O. Search-time effect cannot be repaired post hoc. |
| R2: tau2 tool edits can change the gold state | REFUTED for the campaign builders | campaign-scratch/scripts/E10B/build_cap_project.py:28, E10C/build_cap_project.py:28, E20/build_d.py:31 ("the evaluator replays the agent's tool calls on the PRISTINE tau2 toolkit"); decisions.md:71 ("pristine evaluator constructor already in place"). The gap R2 describes is real for the stock airline example (protocol/benchmarks.md:183-191) and was closed. |
| R2: DarwinX is screen then confirm | CONFIRMED | literature/cards/new/darwinx.md:7 (screen at avg@3, preservation probe, steering nodes confirmed at avg@5 on full suite); related.tex:27 says only "must extend solved set without regressions". |
| R2: Meta-Harness omitted from the record-of-edits sentence | UNVERIFIED wording (related.tex:34-36 not checked sentence by sentence); literature/novelty_matrix.md:104 already lists AHE, DarwinX, HarnessEvolve, AutoSaddler as having per-task fix/break feedback. |
| R2: pins checked only for GEPA and SkillOpt | CONFIRMED | appendix/config.tex:46 (`\needs{pinned commit for each; run records say "not recorded"}`); decisions.md:58. |
| R2: Table 6 vs text on promotions | REFUTED as a contradiction among real numbers | e12.tex is all `\pend` mock with caption "(placeholder)"; the text uses real provisional macros (numbers_real_results.tex:25-57: A hc inert 2/3, B and C 3/3, AO 3/3, stock promoted 2.0 on A and 1.0 on C); decisions.md:351-353 gives E12A 6/18 and E12C 3/15 accepted, i.e. 2.0 and 1.0 per search. |
| R2/R4: stock gate absent on Suite B | CONFIRMED | analysis_plan.md:142-145 ("Suite B has no stock-gate arm"); v2_results.tex:16. |
| R5: institution named | CONFIRMED | v2_setup.tex:6 "IBM RITS (Research Inference Service)"; "RITS" also config.tex:14-15, protocol.tex:103, limitations.tex:12, results.tex:60. Whether MLSys 2027 is double-blind is UNVERIFIED; R5 says the author block is anonymised. |
| R5: em dash ban list | UNVERIFIED (not grepped by me); R5 reports no hits. |
| R3: "step cap disclosed in every Suite B table" | CONFIRMED false | sentence at appendix/config.tex:26; no table caption contains it. |
| R3: SkillOpt, Table 3 "every arm edits the same two prompt files" vs skill folders | PARTLY | deviations_table.tex EvoSkill row says skills are appended to the system prompt, so the caption is accurate in effect; it should say that skill methods emit prompt text. |
| R3: Suite A seed drift 8.8 points | CONFIRMED | analysis/out/mde_observed.md batch table (SD 0.088 vs binomial 0.047; six means 0.462 to 0.684); plan 5H interleaves. |

## 5. TEXT and DATA items with targets and fixes

### I01 History ablation and "causal" (SINK, TEXT, paper-core and paper-lit)
Evidence: abstract.tex:3 ("ablate ... the history"); intro.tex:16 (contribution 3 "a causal optimizer context") and :18 (contribution 5 "ablations of ... history"); capevolve.tex:40 last sentence "Section 5 tests whether this history matters by removing it" (and footnote 44 as R1 calls it); results.tex:48 "not approved"; limitations.tex:11 "not run"; conclusion.tex:4; paper.tex:78 and :109 (Fig. 1). redesign/EXPERIMENTS.md header 0a: E23 no-history is NOT RUN, feasibility one flag, about 1.2M capped tokens for three seeds, pending a decision.
Fix now, independent of the decision:
- Abstract line 3: "...and ablate the surface, the gate and the orchestration mode." Delete "the history" in intro.tex:18, capevolve.tex:40 and results.tex:48 wording "not approved" becomes "we did not run".
- Rename "causal history/record/context" to "fix and break ledger" everywhere listed (R1 and R2 both argue edit-level fix/break under noisy, multi-part edits is not causal; limitation of this is already admitted by results.tex:53).
- If E23-nohist runs, revert the deletion and write the claim as exploratory, three seeds, Suite D only (it is listed under exploratory_cells in the registration, so it is outside the Holm family).
- paper-lit: add the prior-art sentence that per-task fix/break feedback exists in AHE, DarwinX, HarnessEvolve, AutoSaddler (novelty_matrix.md:104) and Meta-Harness (full history) and state the design contrast: CapEvolve gives the proposer trajectories of the current best only (capevolve.tex:40).

### I02 Surface scope (SINK, TEXT, paper-core)
Evidence: paper.tex title; decisions.md:09:15 USER DECISIONS item (4) fixes the title; capevolve.tex:9 footnote and results.tex:53 admit MCP and skill are not evaluated; related.tex Table 8 CapEvolve row has Y for P, T, M, S.
Fix: abstract sentence 3 must name the two evaluated surfaces ("we evaluate prompt and tool code; MCP descriptions and skill packages are implemented but not evaluated"). Fig. 1 (paper.tex:56-80): hatch M and S with the label "implemented, not evaluated". Table 8 (related.tex:30): mark CapEvolve M and S as p or add a dagger footnote. Conclusion already says it. Whether to retitle is I43 (DESIGN).

### I04 Claims vs power (SINK, TEXT, paper-core)
Evidence: setup.tex:65-67 (MDE 11 to 15 points; method level 23 to 29; Holm first step 16/21/28); R4 power table; search-time gains in the few-point range (summary.md); limitations.tex:7 states it but only at the end.
Fix: (a) abstract result slot and intro.tex:10 must read "...paired estimates with intervals for three frozen artifacts per arm; comparisons smaller than about 11 to 15 points are reported as inconclusive"; (b) move the MDE next to the expected effect in Sec. 4.4; (c) add one sentence stating the pre-committed fallback: if no contrast clears Holm, the contribution is the measurement framework and the audit (R1 asked for this); (d) change "standing against nine competitors" to the actual per-suite counts (I15); (e) contribution 5 as "a controlled protocol and descriptive estimates with intervals" (R4).

### I05 Anonymity (SINK if double-blind, TEXT, paper-core)
Targets: v2_setup.tex:6, appendix/config.tex:14-15, appendix/protocol.tex:103, v2_limitations.tex:12, v2_results.tex:60. Replace "IBM RITS (Research Inference Service)" by "an internal inference service" and the bare acronym by "the internal service". The repository URL in setup.tex:6 footnote is the public benchmark, fine.

### I07 Gating split (WEAKEN, TEXT, paper-core)
Targets: v2_setup.tex:9 (caption), :16-19 (rows), appendix/protocol.tex (App. B simulation paragraph, confirmation cost "2 x 49 x 5" arithmetic), Fig. 6 caption, Table 25 caption.
Fix: replace the Opt/sel columns by three columns: "Proposer reads", "CapEvolve gate reads", "Competitor gate reads (GEPA)". Values: A val-40 / val-40 / val-40 (SkillOpt, GEPA: train-80 feedback, val-40 selection); B opt-49 / opt-49 / sel-25; C opt-20 / opt-20 / sel-10 (GEPA row from summary.md; confirm C with baseline-eng); D opt-49 / opt-49 / sel-25. State that sel-25 and sel-10 are never read by a CapEvolve gate and, for B and C, are not in the final set. Then Table 14 is "at the true CapEvolve gating counts" and add the sensitivity numbers from sim_budget_B_sel25.md and sim_budget_C_sel10.md for competitors' gate sizes. Recheck "sealed*" and the "Stock CapEvolve reads and gates on one validation set" sentence for consistency. Suite D "sel" statement depends on amendment 8 (I06).

### I08 Equivalence (WEAKEN, TEXT; margin choice is D5)
Targets: v2_setup.tex:65 last sentence; v2_results.tex:42; Table 20/31 caption (tables/ablation.tex:5); appendix/protocol.tex (margin paragraph).
Fix: (1) setup.tex:65: "Equivalence is tested on Suites A and B and at artifact level only; Suite C is descriptive" (analysis_plan.md:111). (2) results.tex:42: replace "they reach equivalent final gain" by "we test whether the three frozen hill-climb and the three frozen agent-optimize artifacts are equivalent within 10 points on Suites A and B; seeds that return the seed artifact are reported separately". (3) State TOST power at the realised SE next to every equivalence verdict; say the margin equals the planning MDE (plan 5M-1), so "equivalent" will often be unreachable and the expected outcome is "inconclusive". (4) Exclude seed-identical artifacts from equivalence statements or flag them (R4 3d); see I27.

### I09 Suite A final-set provenance (WEAKEN, TEXT, paper-core)
Targets: v2_setup.tex:9 caption and :24; v2_limitations.tex:8; tables/main_A.tex:13 (row header "verified-400"); appendix/audit.tex scorer-audit paragraph; appendix/config.tex:26.
Fix: one name for the pool ("the 912-release residual pool"). Add two sentences: "The final ids are drawn from the 512 ids of the 912 release that are not in verified-400; an id is eligible only if it is scorable with its gold file as output under the official comparator and after LibreOffice 25.8 recalculation, if no more than two earlier runs scored it and none used it for design, and if no sibling of its task family is development-exposed (294 eligible, 239 after the family rule; 70 drawn with a seeded stratified sample, seed fixed and the sample hashed before any final rollout)." Use the table 5 and 6 rule list from protocol/final_set_candidates.md:13-26. Change the Table 4 row header to "Suite A, SpreadsheetBench 912 residual (70 ids)". Do not claim "the scorer audit covers the final set" beyond that; the 19 of 400 figure is for verified-400 (limitations.tex:12).
Open fact: draw_final_a.py has not necessarily run yet (UNVERIFIED); the paper must not state the 70 are drawn until protocol/final_set/suiteA_final_tasks.json exists.

### I10 Missingness and arm-specific search handling (WEAKEN, TEXT, paper-core)
Targets: v2_evaluation.tex:12 ("handled by one rule for every arm"); v2_setup.tex:65; appendix/protocol.tex:42; appendix/config.tex:24 (Suite B retry differences); Table 4/5 captions.
Fix: "one rule at final scoring; search-time handling differed (Appendix C)". Add the win condition from analysis_plan.md:63 (Holm p < .05, CI excludes 0, and pessimistic bound CI excludes 0 for "robust"), noting that amendment 5O-1 keeps the primary result when the sensitivity analysis differs, and report both. Print the per-arm infrastructure rate with Wilson interval beside each delta (5O-4). State in the Table 4/5 captions that Gemma zero-scored failures before 13:11 UTC on 11 October remain in competitors' search feedback. Some arms restarted later under the uniform rule (decisions.md:79, :274, ACE relaunch decisions.md:317): list restart times per arm in the table in App. C (results-collector has the timestamps in runs.csv).

### I11 Competitor wording and pins (WEAKEN, TEXT, paper-core and baseline-eng)
Targets: v2_intro.tex:10; v2_setup.tex:28; v2_setup.tex:31 caption; appendix/config.tex:46; appendix/deviations_table.tex.
Fix: replace "official code for eight of nine" with "adapted official code with the deviations in Table 34 (direction judged by us)"; replace "nine published optimizers" in the abstract with "adapted versions of nine published optimizers" (R4). baseline-eng supplies commits for EvoSkill, Trace2Skill, ACE, MIPROv2, HarnessLens and the blob check; if unavailable, drop "pinned commits" for those. Add the sentence that Meta-Harness, EvoSkill, Trace2Skill and WikiSkill are edited down to the same two prompt files on Suite A (deviations_table.tex rows), so A measures loop quality for an adapted method, not the method in its native form. See D10 for a native-form run.

### I12 Gate narrative (WEAKEN, TEXT, paper-core)
Targets: v2_intro.tex:6 and :15; v2_evaluation.tex:8, :10; v2_results.tex:44; v2_limitations.tex:9; appendix sim paragraph.
Fix: (1) contribution 2: "measured" becomes "simulated"; intro:6 sentence "promotes a no-op candidate in 0.52 to 0.58 of ten-candidate searches" gets "in simulation of the unmasked one-stage gate". (2) Add the Gain column from sim_table.tex to Sec. 3: rule P +0.0011 to +0.0024 and one-stage +0.0034 to +0.0051 true gain per search, under the stated edit mix (60% null, 25% positive, 15% negative); say plainly that neither exceeds half a point. (3) Say the simulated one-stage gate is unmasked while the shipped stock gate masks by footprint with candidate-side coverage 0.6; sim_footprint.md shows masking leaves the null accept rate unchanged for outcome-independent footprints (0.422 vs 0.426) and raises it to 0.98 when the footprint depends on outcomes; the empirical null pool E22 (analysis_plan.md 7F; analysis/scripts/null_pool_replay.py, untracked) will give the shipped-gate rate (DEFER, I52). (4) Justify rule P off by default: it is inert at 550 to 600 rollouts (EXPERIMENTS.md section 0 item 1 and summary.md: B hc 3/3 inert, C 3/3) and Suite D is the test of what each rule buys. (5) Add that the rule P screen plus confirmation spends 2 |Dsel| n_conf rollouts per confirmed candidate so only a few fit at N*. (6) Say what the OC do not cover: edit-mix assumption, proposer adaptivity (already in evaluation.tex:10 last sentences), and that rule P was tuned against this simulator.

### I13 DarwinX (WEAKEN, TEXT, paper-lit)
Targets: related.tex:27 (cell "must extend solved set without regressions"), related.tex:36.
Fix: cell becomes "screen at avg@3, preservation probe, confirm at avg@5 on the full suite; merge must cover parents' solved sets". Sentence in :36: "DarwinX already confirms promoted children with repeated trials; rule P differs in running as a fresh-trial z-test inside core code that the proposer cannot edit, next to a sealed final set." Source: literature/cards/new/darwinx.md:7, novelty_matrix.md:104.

### I14 Related-work gaps (POLISH, TEXT, paper-lit)
Targets: related.tex:34 ("In the papers we read, none reports editing the descriptions an MCP server exposes"), :36, Table 8.
Fix: R2 names DRAFT (Qu et al. 2024) and EvoTool as prior art for tool-documentation or tool-use refinement. EvoTool is in references.bib:337 but uncited in related.tex; DRAFT is not in the bib and I could not verify it (UNVERIFIED, lit-lead to check). Either cite both and reword to "we found no paper that edits an MCP server's exposed descriptions inside a gated loop", or drop the negative claim since the surface is not evaluated. Move the differentiation paragraph (concurrent work, limitations.tex:13) into Sec. 6 (R5).

### I15 Roster and family labels (WEAKEN, TEXT and DATA, paper-core and paper-results)
Targets: v2_results.tex:16 and v2_limitations.tex:6 (delete MIPROv2 and ACE from the B/C sentence); v2_setup.tex:28 and :31 (table); tables/main_A.tex:5, :16 and tables/main_BC.tex:5, :10, :14 ("primary family" versus "S-stock" and "secondary" labels); sections/v2_results.tex:24 and appendix/results_extra.tex:8 (Fig. 2/4 captions); tables/main_BC.tex:25 (HarnessLens on C is a mock row for an arm that was never run); scripts/mock_numbers.py.
Fix: one roster table (method, suites actually run, family membership per plan 5A/5B/5P-1, status including "failed to reproduce" and "stopped"). Verified per-suite memberships: A primary = hc, ao, SkillOpt, GEPA, Meta-Harness, WikiSkill, EvoSkill vs seed and competitors (12 contrasts); B = seed, one-shot, GEPA, HarnessLens (8); C = seed, one-shot, GEPA (6) (setup.tex:65, analysis_plan.md:72). Replace "nine competitors" in the abstract and intro with per-suite counts. Label the competitor-versus-seed rows as the secondary family 5B(i) and the CapEvolve-versus-competitor contrasts as primary, as the plan does. Drop HarnessLens from Suite C rows. Cite or drop VERSE, CoEvoSkills, AHE, MCE, RHO, Memento-Skills, GraphSkillEvo (setup.tex:28; R5 S17).

### I16 Suite D Holm family (WEAKEN, TEXT, paper-core)
Target: v2_setup.tex:63 and appendix/protocol.tex last paragraph. Add "prompt-only against tools-only" to the list. The ten registered contrasts are: P vs PT, T vs PT, P vs T, rule P vs PT, one-stage vs PT, PT vs one-shot, P vs GEPA (test-40), P vs seed, T vs seed, PT vs seed. Note the registration frames rule P and one-stage as contrasts against the PT stock reference; the text says "against the stock gate", same thing. No p-values need recomputing because m = 10 was registered; only the prose was wrong.

### I17 Cost totals (WEAKEN, DATA, paper-results)
Targets: paper/numbers.tex:9-13 (generated by scripts/derive_numbers.py, which reads analysis/out/metrics/campaign_totals.json); v2_results.tex:60; appendix/protocol.tex:103; tables/cost_so_far.tex.
Fix: rerun derive_numbers.py after refresh_metrics.sh; the JSON schema changed at 09:26 to 09:27 UTC (buckets capped/rits/azure). Define the sentence from the buckets block: "calls, ledger tokens (cache reads excluded for Anthropic models; OpenAI prompt tokens counted in full), split into RITS, Azure and capped; Anthropic list proxy for the capped bucket; Azure list price not billed". Current values for reference only, they will move: 263,236 calls; 1,555.66M ledger tokens; RITS 1,425.60M; Azure 59.61M; capped 70.45M; $216.03 proxy capped plus $27.94 Azure list. Change "non-cache tokens" in results.tex:60 to "ledger tokens" because the RITS and Azure buckets include cached prompt tokens. R3's other cost questions (Table 28 per seed vs summed, Table 36 vs Table 16) disappear once one snapshot is used and the table says "summed over seeds" (cost_so_far.tex caption already does).

### I18 SkillOpt guard overrun (WEAKEN, TEXT)
Evidence in section 4. Targets: v2_setup.tex:56 ("up to 4M non-cache-read optimizer tokens"), appendix/config.tex:24, cost_so_far.tex caption. Fix: state that CapEvolve has a soft/hard guard (3.5M/3.9M, decisions.md:340) while competitors are checked after the fact and SkillOpt exceeded 4M in one seed by 19% (4.78M); compare at N* using tokens spent at N*, not at the end (reconstruct.py can produce it; paper-results). Also disclose the CapEvolve effective cap of 3.5M (decisions.md:340), a mild disadvantage to CapEvolve.

### I19 Duplicates (POLISH, TEXT, paper-results)
Delete `\input{tables/ablation}`, `decomp`, `rq4` from appendix/results_extra.tex:13-15 (keep v2_results_appendix.tex:6-8) and the second fig_contrast at appendix/results_extra.tex:7. Check the label pairs (tab:ablation etc.) for orphan refs. Replace "--" empty-cell markers by "n/a" in the listed tables if the house style wants it (R5 section 4).

### I20 Mock/real mixing and snapshot drift (POLISH now, must clear before submission, DATA, paper-results)
Targets: tables/e12.tex (all `\pend` while the Gate paragraph cites real macros: make promoted/screened/inert columns come from analysis/out/searchtime/gate_by_run.csv and label deltas "placeholder"); tables/main_BC.tex and main_A.tex (S-stock row of "as shipped minus seed" must reuse the primary-row interval; one estimand has one CI, only the Holm family differs); mock_numbers.py (make delta columns equal score difference when no cell is missing; remove HarnessLens on C); candidate counts: attrib_promotions.tex (A hc 8 candidates, stock 19, from attrib snapshot 08:47) versus searchtime tables; regenerate all search-time tables from one timestamped run of analysis/scripts/searchtime_results.py and attribution_analyses.py and print the timestamp in every caption (R3 11). I could not locate the specific "10 and 12 candidates" tables R3 cites; UNVERIFIED. Counts are monotone only if every table reads the same snapshot.

### I21 Table 7 (POLISH, TEXT, paper-core and paper-results)
Targets: tables/attrib_failure_types.tex:4-5, tables/attrib_surface_failure.tex. Add a "Units" column: A 120 (3 seeds x 40), B 147 (3 x 49), C 60 (3 x 20), all on the arm's gating split. Use one taxonomy: Table 7 uses prose labels and Table 26 uses raw codes (missing_action, wrong_argument, no_output_file, wrong_result, communication, state_side_effect); map them in the caption. Rename Suite A "knowledge or rule gap" to "wrong result" (the label only means output exists and fails the checks). Define "infra (unscorable)" and "other" in the caption.

### I22 Notation and codes (POLISH, TEXT, paper-core)
Collisions R3 lists: k (SE multiplier, best-of-k, subset size), N and N*, B (budget, branch, block, Suite B), rho (coverage, Spearman), Delta. Pick one symbol per quantity, rename Suite-B-style letters (use "budget N" and "branches J"). Replace stock gate/one-stage gate/one-standard-error gate/k=1 gate by "stock gate" (shipped, masked, coverage 0.6) and "one-stage gate" (unmasked, coverage 0.95, used only in Suite D and the simulation); define footprint, joint coverage, protect set, inert, shrinkage at first use; strip E12A, E12C, hcstock, ctl, rulep, onestage and pt from captions (R3 14, R5 section 5). Define "inert" in text, not only in Table 23 caption.

### I23 Story and sentences (POLISH, TEXT, paper-core)
Accept R5 S1 to S20 with these cautions: S2 depends on I01; S17 depends on I15; S18 depends on I16 (the contrast count is ten); S20 wording "we did not run" fine; S16 "may favor either side" is accurate (exposure difference, setup.tex:24). Story-level: name the two questions the paper answers in the abstract (surface width where failures need enforcement; whether the conservative gate buys reliability or only inertia) so the placeholder has a shape; add the audit clause to the abstract; define "code-owned evaluation" once; split evaluation.tex:10 into three paragraphs; delete the repeated percent triples in intro/evaluation (keep one copy); delete evaluation.tex:14 repetition. Figure 1: caption should open with a claim, label the dashed core-code box (paper.tex:79), raise tiny text. Caption hygiene list in R5 section 5 (file paths and "(placeholder)" in captions, 130-word captions) is accepted. R5's suggestion to demote intake and the context to one sentence is a story-architect call, not a fact error; I recommend keeping intake in the appendix with one sentence in the body since evidence is fault-injection only (evaluation.tex:12 \needs).

### I24 Outcome sentences (WEAKEN, TEXT, paper-core)
Targets: v2_results.tex:42 ("agent-optimize ended its own search early in several seeds on Suites B and C"; footnote still asks for the stop reasons), :44 (garbled "3, 3 and 3 of 3, 3 and 3" arises from macros \stInertAo* with \stSearchesAo*), v2_limitations.tex:9 ("promotes almost nothing"), v2_results.tex:53 ("the kind of failure tool code can enforce"). Evidence that searches were unfinished: summary.md status column shows A hc, B hc, C hc, A ao "running" at 08:47; native finish only for some AO seeds. Fix: write "held the seed artifact as incumbent at the 12 October snapshot" or move to the final-evaluation sentence; fix the macro grammar to "returned the seed in X of Y" lists; AO early stop is documented (decisions.md:318: Read permission denials, not a fault), so the stop reason can be stated once collected (results-collector).

### I26 Bundles (POLISH, TEXT, paper-core)
Targets: results.tex:42, setup.tex:63, tables/ablation.tex caption. Call the orchestration comparison "two shipped configurations" (controller, parent selection, screen design, accept rule, turn limit 80 vs 300, and on B gold visibility all differ). State that the gate cells differ as registered: reference stock gate = footprint masking on, candidate-side coverage 0.6, no confirmation; E21-1S = masking off, joint coverage 0.95, no confirmation; E21-ruleP = rule P with masking off and coverage 0.95 (registration json "tier1_cells"). So stock vs one-stage isolates masking plus coverage, and one-stage vs rule P isolates confirmation.

### I28 Clustering (POLISH, TEXT and DATA)
Targets: v2_setup.tex:65 ("The unit of inference is the task"), v2_results.tex:11 and tables/main_A.tex:5 ("family-cluster-robust"), appendix/results_extra.tex:44 and fig_families (mock). Plan says task clustered by family (analysis_plan.md:20), CR1 with t(C-1) when C < 30; for B, C, D task = cluster (mde_observed.md; plan 7D). On A the pool has 255 families for 294 ids (final_set_candidates.md:42), so family clusters are close to singletons. Write: "intervals cluster on task family on A, where families are nearly singletons, and on task on B, C, D; cluster counts are printed in every table". paper-results: rebuild Fig. 8 from the 70 drawn ids once drawn, or drop it (it is a mock whose families sum to 120). R4 asks for CR2 or wild cluster bootstrap below 30 clusters; analysis/scripts/paired_cluster_bootstrap.py already has a cluster bootstrap check (plan section 3), so report it as the companion.

### I29 Multiplicity (POLISH, TEXT)
Targets: setup.tex:65, protocol.tex. Say that Holm is per suite and a cross-suite claim needs both suites to pass (analysis_plan.md:61); give the number of families reported (primary 3, S-stock 2, D 2 plus TOST families) and that secondary families are labelled descriptive. State that "win" requires both Holm p and an unadjusted CI, which is conservative; optionally add Holm-simultaneous intervals for the primary family.

### I30 Amendments and pre-registration wording (WEAKEN, TEXT)
Targets: setup.tex:63 ("registered ... before launch"), appendix/changelog.tex or protocol.tex Table 19.
Fix: add the table: amendment number, UTC time, whether any search-time outcome had been seen, what changed. From analysis_plan.md: 1 (21:15 on 11 Oct, before cutoff, no final data), 2 (21:15, interleaved window and drift check), 3 (22:45), 4 (23:05, B* over primary arms), 5 (02:11 on 12 Oct, infra rule 5O), 6 (08:40, after seeing search-time selection results, adds S-stock and shrinkage), 7 (09:20, Suite D, before first Suite D rollout, designed after seeing search-time results of A to C and the azprobe baselines, registration json). Replace "registered" by "specified in a time-stamped repository commit"; give hashes from experiments/registry.jsonl (13 entries; first entry 2026-10-12T09:20:49Z). Add the selection rule for the 70 ids (I09). Disclose who saw the superseded first Suite B run and the 14:45 pilot (decisions.md:83).

### I31 Matched checkpoint (WEAKEN, DATA and TEXT, paper-results)
Targets: v2_setup.tex:56, appendix/sim_table.tex, fig_rulep (scripts/plots), appendix/protocol.tex.
Fix: (1) After the cutoff recompute Table 14 at the realised N* and report candidates screened per arm at N* beside N* (R4 9b). Observed at 08:47: B hc 294 to 392 rollouts with 1 to 7 screened, AO 172 to 198 (summary.md). (2) Replace Fig. 9 by the per-suite sims at the 10-candidate cap (sim_budget_{A,B,C}.json) or restate its caption as six candidates and stop citing it for the "ten-candidate" numbers. (3) State budgets: search cap 600 on A, 550 + finalize on B, C and D for CapEvolve and one-shot; GEPA and HarnessLens 600; matching is at N*. (4) One line per arm for the "own selection rule at N*" reconstruction (reconstruct.py logic; decisions.md:67 lists GEPA, SkillOpt, EvoSkill, Meta-Harness) and what happens below the floor of 200.

### I32 Surface evidence (WEAKEN, TEXT, paper-core)
Targets: results.tex:40, :53; setup.tex:6; limitations.tex:11. Fix: keep the surface-worth claim to Suite D, scored on test-40 (per amendment 8 if adopted); present Table 7 and 26 as hypothesis generating; delete "the kind of failure tool code can enforce" or soften to "failures that tool code could in principle enforce"; restrict the decision guide to Suite D cells; add that Suite D uses gpt-4.1-mini, so transfer to gpt-oss and Gemma is untested. Suite D similarity numbers: seed accuracy 0.612 vs 0.56 to 0.65 and null paired SD 0.57 vs 0.55 (redesign/EXPERIMENTS.md:35, E00-azprobe; add as a short table in App. B, I41).

### I37 Seal wording, provenance, Suite C (WEAKEN, TEXT)
Targets: abstract.tex:2 and evaluation.tex:4 ("a seal on the final set"); setup.tex:9 caption "sealed*"; main_BC.tex Suite C block.
Fix: state "scored once" in the abstract, and in Sec. 3 that the seal blocks scoring and edits but cannot stop reads (evaluation.tex:6 already says it for gold). Add one sentence that no text distilled from the earlier sealed-test evaluation reaches the current seed, skills or proposer prompts (UNVERIFIED; provenance-auditor must confirm; audit/provenance_issue_drafts and protocol hashes are the place to check). For Suite C drop Holm columns and stars or label the block exploratory (analysis_plan.md:142 says C is never the sole basis of a claim).

### I38 Statistical details (POLISH, TEXT)
Show the MDE formula or cite analysis/scripts/mde_observed.py in Sec. 4.4 and say it is for the mean of three champions (I49). Say that the SE helper that double counts within-task noise (plan section 3a) is not used for final intervals; the simulated gate OC were produced with the real gate code, so nominal z does not matter (R4 16 concern about "effective z of 1.1" is UNVERIFIED but harmless to the reported OC). Judge validity: GPT-5.5 as judge for B and C (setup.tex:6); no agreement audit against the default judge exists in the repo (decisions.md:21 plans a "later sensitivity sample"); say the absolute scale is not comparable to published tau2 numbers.

### I39 Systems measurements (POLISH, TEXT and DATA, paper-results)
Add a small table: rollouts per hour, wall hours per search, tokens and proxy USD per arm, intake time per benchmark (EVIDENCE slot). Data are in analysis/out/metrics/metrics_by_arm.csv (wall_h, optimizer tokens) and summary.md (wall h). Cost per accepted point only after final data.

### I40 One-shot description (POLISH, TEXT)
setup.tex:49: "a one-iteration CapEvolve run: one proposal, then the arm's gate (Suites B and C) or no selection (Suite D)". Reconcile with the "promoted per search" column in ablation.tex.

### I41 Small disclosure fixes (POLISH, TEXT)
- config.tex:26: delete "disclosed in every Suite B table" or add the step cap (100 vs default 200) to the Suite B table captions.
- Table 3 caption: add "skill methods emit their skills as appended prompt text" (deviations_table.tex EvoSkill, WikiSkill rows).
- Table 8 M/S marks (see I02) and HarnessLens "p" for M versus the Sec. 6 sentence.
- Table 17 optimizer for the historical audit is Opus 5 per R3; Sec. 1 and Table 9 do not mention it. UNVERIFIED; check audit/historical_results.md and add one clause.
- Suite D noise/accuracy claim: add the numbers from I32.
- Judge on D is gpt-4.1 (registration), on B and C GPT-5.5 (setup.tex:6): say so in Sec. 4.1 (it is there) and in the Suite D caption.
- App. A.4: trim raw config dumps (minimax_*, copilot_*, azure_*) in appendix/config_generated.tex via scripts/gen_config_tables.py; fix "rits/openai/gpt-oss-120b-a100" vs "gpt-oss-120b" in Table 9.
- "overstating variance by 12 to 33%" (protocol) is 13 to 33% per plan 3a "12-33%" vs "1.13 to 1.33 times": the plan's own text says 12-33% for kappa 1.5, so the claim of 12% is the source and "1.13" is for n=10; no change needed unless the paper prints both.

### I42 Unchecked small items (POLISH, UNVERIFIED, paper-lit)
references.bib:949 gives PACE author as "Shawn, Zayx" (arXiv 2606.08106); R3 suspects a given name used as surname; cards/new/pace.md may have the real name. N* printed as "N ?" in paper.txt: a font glyph issue to check in the PDF build (not examined).

## 6. DESIGN items (coordinator decisions)

Each lists options and an honest cost. Constraints I verified: search cutoff is 2026-10-13 06:00 UTC (setup.tex:56), the latest log entries are about 09:30 UTC on 12 Oct, so roughly 20 hours remain; Gemma on Suite A is the critical path (EXPERIMENTS.md section 0 item 5; about 12 rollouts per hour per search, setup.tex:56); the non-RITS token cap was raised to 170M with 70.45M used (decisions.md:09:15 item 3, campaign_totals.json); Azure is uncapped but about $1k for Tier 1 (EXPERIMENTS.md); the final-evaluation set sizes were fixed on capacity grounds (decisions.md:147, analysis_plan.md:105) and T may be lowered, "never raised".

### D1 History ablation cell E23-nohist (I45, PENDING with experiment-designer)
Options: (a) run it, three seeds on Suite D, exploratory outside Holm: about 1.2M capped tokens and a 25-line switch, plus about 2.2k Azure rollouts for two seeds in the original sizing (EXPERIMENTS.md section 7 row 9 and header 0a). (b) do not run it: apply I01 deletions. Cost of (b): no evidence for contribution 3 beyond description; R1 and R2 both state their score drops to 3 if the abstract keeps the claim. Not duplicated further here.

### D2 Amendment 8, Suite D on test-40 (I06, PENDING)
Text consequences once adopted: setup.tex:63 last sentence and Table 2 row D ("65 x 5" becomes "40 x 5", drop the dagger, "sealed*" now accurate except for file visibility); Suite D MDE recomputed (R4 estimates about 12 points at 40 tasks; registration json planning MDE test40_vs_seed 0.093, cell-vs-cell 0.102; use those, not R4's); H65 results reported descriptively. GEPA already uses test-40 only.

### D3 Headline estimand and analysis-plan amendment 9 bundle (I03, I30)
Question: which single estimand does the abstract report? Options:
(a) Stock-gate hill-climb vs seed on Suite A (plan S-stock row 1) as the headline, disclosed as post-search-time, with the three-config table beside it. Cheap (one line in the plan, a dated registry entry). Honest cost: it sits outside the primary family, so the abstract's headline is by construction a secondary, post hoc contrast (R4 forking-path argument).
(b) Rule P hill-climb vs seed on A as headline (registered primary). Cost: it returned the seed in 2 of 3 searches at the snapshot, so the likely headline is "no detectable gain".
(c) No single headline; abstract reports the per-suite table of all three configurations with intervals. Cost: weaker abstract, but matches the power in I04.
Recommendation: (c) in the abstract with (a) named as the shipped configuration. Whatever is chosen, write it into the plan and registry.jsonl before any final score is computed, together with the amendments table (I30) and the cross-suite rule (needs both suites to pass).

### D4 Rule for seed-identical artifacts in the final window (I27)
Currently unspecified. order.py:7-9 schedules every artifact as its own cell with common trial seeds and only de-duplicates an END artifact identical to the same arm's B* artifact; reconstruct.py:627 flags identical_to_seed but nothing consumes it. Options:
(a) Identity rule: an artifact with the seed's content hash is not rerun; its delta is exactly 0 and it is marked inert. Saves T x n rollouts per inert seed, makes arms that are mostly inert look as they are, and removes noise. Cost: intervals computed on the same footing but with structural zeros, the CR1 SE is smaller; equivalence between two inert arms is trivially true, so equivalence must exclude them (I08).
(b) Rescore it as an ordinary cell (current behaviour): its delta is re-measurement noise (within-task variance 0.088 to 0.148), which is a measurement check but contaminates the artifact-level mean.
(c) Do (a) for the primary test and (b) as a labelled measurement check.
Also decide: shrinkage over non-inert seeds only with the inert fraction beside it (plan 5P-2 currently zero by construction); cost per point as ratio of total cost to total gain with a bootstrap interval, not a mean over positive seeds (attrib_cost_per_point.tex:4). Recommendation (c). No new rollouts needed.

### D5 Equivalence margin and scope (I08)
Options: (a) keep margin 10 (plan 5M-1), claim equivalence only on A and B at artifact level, report TOST power, expect mostly "inconclusive". Zero cost. (b) tighten to 5 points: substantively more defensible as a smallest effect of interest, but TOST at true zero then has power of about 0.1 or less on A and B at the planned SE, so equivalence is essentially unreachable. (c) drop equivalence language, report intervals only. Recommendation (a) with the text fixes in I08; (b) is not worth the claim.

### D6 Suite B and C agent-optimize gold visibility (I25)
Facts: AO's evaluator overlay exposes tasks.json filtered to opt and sel ids, so AO can read gold actions of its own opt and sel tasks on B and C; sealed test never visible after the 14:55 to 15:00 namespace shim; before that hc/ao/ctl could read the full retail tasks.json from 12:44 to about 14:55 with no read found in transcripts (decisions.md:85, :206). Options: (a) keep B-AO and C-AO in the primary family, dagger them, add a sensitivity row for B and C excluding AO. Zero cost. (b) amend the plan to move B-AO and C-AO to the secondary family (family sizes B 8 to 6, C 6 to 4). Zero rollouts; requires an amendment before final scoring; reduces the Holm burden. (c) rerun AO with filtered gold: not feasible before the cutoff. Recommendation (a) plus a sentence in the abstract-level isolation claim (I37).

### D7 Missing cheap controls and baselines (I34)
Facts: Suite A has no one-shot control (main_A.tex:5); best-of-k exists only on Suite C and is exploratory (limitations.tex:10; decisions.md:195, guard 8M tokens per seed, k about 26); CASD and NPO are cited but not run (R2). Options, cheapest first:
(a) Offline: run GEPA's, SkillOpt's and SAGE-style accept logic through the Appendix B simulator (analysis/scripts/replay_gates.py and sim_budget.py exist). No rollouts. Answers R2 W4(c).
(b) One-shot control on Suite A: about 200 rollouts and about 0.2M optimizer tokens per seed (Suite B one-shot used 123 to 148 rollouts and 0.14M to 0.2M tokens), three seeds, plus 70-task final cells. Gemma is the critical path, so it competes with arms still running. Cost about 600 Gemma search rollouts plus about 210 final rollouts.
(c) Best-of-k on Suite B: up to about 24M capped tokens at the guard for three seeds (decisions.md:195 and EXPERIMENTS.md section 7 option 1 discussion), 550 gpt-oss rollouts per seed. High cost against the 170M cap with 70M used; exploratory only.
(d) k=2 one-stage gate cell on Suite D: about 3.3k Azure rollouts and 1.2M capped tokens (E21-ruleP-2x row analogue); a registered cell list change.
(e) CASD and NPO re-implementations: code availability UNVERIFIED; cite and state limited scope instead.
Recommendation: (a) now, (b) if Gemma capacity frees, otherwise soften "the loop beats sampling" language to "relative to a one-pass control" (R4 12).

### D8 Power remedies (I35)
Options: (a) accept and rewrite claims (I04), zero cost. (b) more seeds on the single key contrast (stock hill-climb vs seed on A): each extra seed about 600 Gemma search rollouts at 12 per hour per search (about 50 hours sequential, so only parallel seeds fit) plus 70 final cells; will not finish before the cutoff for more than about one or two extra seeds. Pipeline-level claims still need many more seeds (2 df now). (c) enlarge the Suite A final set: 239 eligible ids, 70 used; each added task costs about 14 final rollouts (about 12 arms at 1 trial plus 2 seed trials); at T=110 the MDE falls by roughly sqrt(70/110), about 20 percent, from 11.7 to about 9.3 points (my arithmetic from the stated formula, not from the repo). decisions.md:147 says T can be lowered but never raised, so this needs an amendment. (d) equalise exposure (CapEvolve with 120 tasks, or a competitor with 40): about 1,800 Gemma search rollouts for three seeds; not feasible before the cutoff; one seed possible. (e) a stronger target on one suite: needs new searches; not feasible. Recommendation (a) plus (c) only if final-eval capacity (experiments/final/capacity.py) allows.

### D9 Stock gate on Suite B (I36)
Options: (a) leave as is; state in Sec. 5.1 that the stock gate is evaluated on A (exposed), C (development-exposed) and D (sealed retail, different target). Zero cost; the headline then lacks a clean sealed main suite. (b) run E12B stock hill-climb on B: three seeds, 550 rollouts of gpt-oss, about 1.2M capped tokens per search at the observed hc range (summary.md: B hc 0.2M to 0.6M non-cache tokens); capacity unverified; the sealed test-40 is already in the final plan. Recommendation (b) if gpt-oss capacity allows, because it is the only way the shipped configuration gets a sealed main-suite estimate. UNVERIFIED capacity.

### D10 Native-surface run of a re-targeted competitor (I44)
Option: Meta-Harness in native form on one suite, single seed, to bound the re-targeting caveat. Cost: container, Opus-class proposer per the original, about the cost of a Tier 1 Meta-Harness run (A: about 600 rollouts); not feasible before the cutoff beside the matched arm. Alternative: state plainly (I11) and keep the Direction column. Recommendation the alternative.

### D11 Title (I43)
User decision on 2026-10-12 09:15 fixed the title. Options: keep and scope in the abstract and Fig. 1 (I02), or retitle (R2: "Prompts and Tool Code of a Frozen Agent"). A retitle needs the user; R1 lowers the score if the abstract also keeps "Any".

## 7. REBUT items, with the sentence the paper should add

- I33 (R2 W6, tool edits can change the gold). Evidence: build_cap_project.py:28 in E10B, E10C and E20 (evaluator replays the agent's calls on the PRISTINE tau2 toolkit); decisions.md:71. Add to Sec. 3 or App. A: "On the tau2 suites the evaluator replays the agent's tool calls on the pristine tau2 toolkit, so edits to tool code change how the agent acts but not how the reference state is computed." Also archive the builder scripts in the repo (currently only in campaign-scratch) and cite the E05 fault injection that exercises candidate-tool faults. A hostile-edit negative test beyond E05 is UNVERIFIED; if absent, add one unit test (tau-runner).
- I46 (R1 5, lead with evaluation integrity). Decision record: decisions.md:08:33 user direction made this a method paper; the measurement-study framing is superseded. Add nothing to the thesis, but accept R1's useful part: promote the audit to a main-text table (original gain, recomputed gain, what changed), which fits the method framing.
- I47 (R1, no power curve for rule P vs stock). Appendix sim_table.tex already gives power at +0.04, +0.06, +0.08, +0.10 for rule P and the one-stage gate on all three suites. Add one sentence in Sec. 3 pointing to it.
- I48 (R3 Q3). Evidence: sim_budget.md mean promotions for one-stage k=1 are 0.69 (A), 0.61 (B), 0.66 (C) per search while P(at least one) is 0.578, 0.524, 0.550; baseline update after the first promotion makes later candidates harder to pass. Add to App. B: "Mean promotions per search are 0.61 to 0.69; the probability of at least one false promotion is lower because a lucky promotion raises the baseline."
- I49 (R4 MDE). Add: "MDEs are for the mean of the three frozen champions (variance model in analysis/scripts/mde_observed.py); a single champion against the seed needs about 15 points."
- I50 (R3 Table 7 denominators). Add the Units column (I21).
- I51 (R2 Q3, R3 Table 30). Both are about placeholder tables; fixed by I20 and by removing "(placeholder)" values before submission.
- R3 #2 scorer-validity part: see I09 for the sentence on the gold-as-output screen of the final ids.
- R2 W4 "strawman comparator": partly valid, see I12 (the masked gate is not simulated at budget level; E22 replay will report the shipped gate).

## 8. DEFER (depends on final results)

- I06 amendment 8 text changes (D2).
- I52 every `\pend`/`\needs` slot: abstract and conclusion results, headline sentence, the verdicts (supported, equivalent, inconclusive, contradicted), N* and incomplete-seed list, E22 empirical null-pool false-accept rates (null_pool_replay.py), shrinkage, cost per point, Tables 4/5, Table 6, Fig. 2 to 4, decision guide. Reviewer R1 and R4 request that the same outcome language not appear before the final data; I24 covers the wording until then.
- Orchestration and gate verdicts (results.tex:42, :44) are DEFER; rewrite after final evaluation.

## 9. Things I could not verify (UNVERIFIED)

- Whether draw_final_a.py has produced the 70-id file.
- DRAFT (Qu et al. 2024) and the exact EvoTool characterisation R2 gives.
- The em dash ban-list grep (R5) and R5's word-count claims.
- R3's exact "10 and 12 candidates" tables and the "N ?" glyph.
- Any hostile tool-edit negative test beyond E05.
- Whether MLSys 2027 requires double-blind.
- The existence of a human or default-judge agreement audit for GPT-5.5 as tau2 judge.
- The "Opus 5" optimizer attribution for the historical audit.
- Capacity numbers for D7, D8, D9 beyond what is quoted from decisions.md and EXPERIMENTS.md.

## 10. Coordinator decisions (2026-10-12 ~09:58 UTC)
- D1: RUN. E26-nohist (registered as amendment 8F, primary family D, m=11; launch about 13:03). The paper keeps the history contribution, but the abstract and intro must say the ablation is on Suite D only, and "causal history" becomes "fixed/broke history" (or another non-causal name) everywhere.
- D2: ADOPTED (amendment 8, 3cd923166 plus erratum ed62e9966). Apply its text consequences.
- D3: (c). No single headline estimand: the abstract reports the per-suite table of configurations with intervals, and names the stock gate as the shipped configuration. It goes into amendment 9 before any final score, with the amendments table (I30) and the cross-suite rule.
- D4: (c). Identity rule for the primary test (seed-identical artifact: delta exactly 0, marked inert, excluded from equivalence), plus rescoring as a labelled measurement check. Shrinkage over non-inert seeds with the inert fraction beside it. Cost per point = total cost / total gain with a bootstrap interval. Goes in amendment 9.
- D5: (a). Margin stays 10; equivalence only on A and B at artifact level; report TOST power; failures read "inconclusive".
- D6: (a). B-AO and C-AO stay in the family, with a dagger and a sensitivity row excluding them; one sentence at the isolation claim.
- D7: (a) offline gate-logic replay now. No Suite A one-shot (Gemma is the critical path). Soften "the loop beats sampling" to "relative to a one-pass control" where no such control exists.
- D8: (a). Rewrite claims as descriptive estimates with stated MDEs; T is not raised (the pre-registered rule says never raised).
- D9: Capacity check requested from tau-runner. Default is (a) unless gpt-oss capacity is spare without slowing primary B arms.
- D10: the alternative. State the re-targeting plainly.
- D11: keep the user's title for now and scope "any" in the abstract and Fig. 1 (implemented: P, T, M, S; evaluated: P, T). The retitle option goes to the user.
- I05 anonymity: the template is double-blind by default (mlsys2025.sty without [accepted] prints "Anonymous Submission"). Replace "IBM RITS" with a neutral description everywhere.
