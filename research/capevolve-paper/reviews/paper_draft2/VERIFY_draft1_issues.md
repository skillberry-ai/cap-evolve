# Verification of draft-1 issues in draft 2

Draft 2: /home/dev/projects2/campaign-scratch/reviews/draft2 (COMMIT 8fc104ee4). Evidence quoted from paper_full.tex (line numbers `tex:NNN`) and the rendered PDF (26 pages; pages 6, 8, 9, 10, 22 inspected).
Repo evidence: decisions.md, protocol/analysis_plan.md (amendments 1 and 2), analysis/out/*.

## Totals

| Set | RESOLVED | PARTIAL | OPEN |
|---|---|---|---|
| TRIAGE items (A1-A10, B, C, D, E = 14) | 3 | 11 | 0 |
| Reviewer weaknesses (R1 9, R2 10, R3 8, R4 11, R5 7 = 45) | 7 | 36 | 2 |

Mechanical checks: dashes (3 hand-written en dashes plus "--" table cells), no banned words, 11 visible `\texttt` in body prose, 5 repo paths in body, 8 body lines with mocked outcomes written as prose findings. Details at the end.

New problems introduced or exposed by draft 2 are in section N, and several are higher priority than the PARTIAL items.

## TRIAGE items

### A1 Gate confound, E12 arm. PARTIAL
- Done: tex:869 "It is also not on acceptance rules: CapEvolve judges candidates with rule P and competitors keep their native rules. The comparison is therefore of each method together with its own acceptance rule. An exploratory arm, CapEvolve hill-climb with its stock gate on Suite C, bounds how much of any gap the rule explains." The arm exists (decisions.md 21:10, E12C-hcstock-s0..2). The sentence matches the decision.
- Remaining: (1) the arm is absent from the Arms table (tex:841-863) and from every results table; tex:1015 is still `\needs{Add the E12 ablation ... or state that the campaign has no such ablation}`. (2) "bounds how much of any gap the rule explains" is too strong for one 20-task development-exposed suite with an MDE of 0.22 (tex:876) and the stock gate also differs in footprint masking and coverage (decisions.md 21:10). (3) Suite B has no stock-gate arm (queue threshold); say so.
- Fix: add a row "CapEvolve hill-climb, stock gate (exploratory, Suite C, 3 seeds)" to Table 3 and a one-line result slot; replace "bounds" with "gives a descriptive estimate of"; state that Suite B has no such arm and why.

### A2 Pre-specified CapEvolve-vs-baseline family. RESOLVED (design); presentation is under E
- tex:874: "The primary family pairs each CapEvolve algorithm ... with the seed artifact and the main competitors. Suite A uses the seed artifact, GEPA, SkillOpt, Meta-Harness, WikiSkill and EvoSkill (12 contrasts). Suite B ... (8). Suite C ... (6)." Counts equal amendment 5A (2 x 6, 2 x 4, 2 x 3). Secondary family and "Holm inside the suite" also match 5B.
- Caveat, see N1: the Suite A table and text use a one-shot control that amendment 5A says does not exist on A.

### A3 B* truncation and budget-coupled schedules. RESOLVED
- tex:869: "Truncation at B* can penalise arms whose schedule depends on the full budget (SkillOpt's cosine schedule, EvoSkill's iteration cap), so a secondary analysis scores each arm's native end-of-run artifact at the cutoff, labelled as unmatched." Appendix tex:1258 adds GEPA's metric-call cap and "the same contrast rows as the primary family (12, 8 and 6 per suite), under its own Holm correction".
- Optional: R4 W2 also asked for ordering sensitivity across several checkpoints (see R4-W2).

### A4 Optimizer compute not matched. PARTIAL
- Done: tex:869 "The matching is on target rollouts. It is not on optimizer compute ... we report optimizer tokens and dollars per arm and make no claim of compute parity." USD is a column of the main tables; Table 15 and the Pareto figure carry tokens.
- Remaining: the triage asked for uncached, cache read and cache write separately. Table 15 (tex:1546-1550) merges cache writes into "Non-cache-read" and has no cache-write column (the mock data have `TokCw`). Turns per optimizer (Claude Code 80 or 300 turns versus single-call reflection) appear only in the appendix (tex:1126).
- Fix: add a cache-write column to Table 15; add one sentence in 4.3 that Claude Code agents (80 to 300 turns) and single-call reflectors differ in optimizer work per rollout.

### A5 Operating characteristics. PARTIAL
- Done: unit fixed (tex:693 "The error rate is per search, not per edit ... about one percent per candidate"; abstract "null search of about ten candidates"). Observed-variance MDE (tex:876, 1253; matches mde_observed.md 5F). The n_conf 5 / z 1.645 argument is in tex:1227 and matches 5G (400 of 600 on A; 490 > 452 on B).
- Remaining:
  1. The quoted rates are from `sim_budget_{A,B,C}` with the screen on val-40, opt-49 and opt-20 (plan 5G). Table 2 says the selection sets are 40, 25 and 10, and the stock CapEvolve gate screens on the selection split. The re-runs on the actual selection sets exist (`sim_budget_B_sel25.md`, `sim_budget_C_sel10.md`) but are not used or mentioned: option c gives 0.086 (B sel-25) and 0.125 (C sel-10) false promotion, and +0.08 power of 0.25 (B) and about 0.10 (C), against 0.040/0.33 and 0.113/0.17 in the abstract and tex:693. tex:1227 even says "Suite B: 49 optimization tasks". If CapEvolve gates on sel-25/sel-10, the abstract numbers are wrong.
  2. Section 5.4 (tex:1012-1013) still uses the old six-candidate val-40 table with assumed difficulty (0.050, 0.434, 0.199, 0.41, 0.54), unlabeled by suite, hard-coded rather than macros, and Figure 7 uses "six candidates". See B.
- Fix: tau-runner and stats owner confirm which split each suite's stock gate screens on, then regenerate the abstract, 3.3, 3.5, 5.4, Discussion and Table 12 from one source; if sel-25/sel-10, report 0.086 and 0.125 and say the abstract range is 0.04 to 0.125 (A 0.068, B 0.086, C 0.125).

### A6 Power stated up front. PARTIAL
- Done: abstract "the tau2 suites are descriptive"; tex:815 "they cannot resolve small differences ... inference there is at the artifact level only"; tex:874 and Limitations give the 2 df point and MDEs.
- Remaining: the abstract and intro do not say that even Suite A has an artifact-level MDE of 0.12 (pipeline 0.24, tex:876) while the contributed gains are of order 0.02 to 0.07, so most contrasts will read "no detectable difference". Intro tex:496 still promises "which optimizer finds the best artifact".
- Fix: one sentence in the intro and abstract: "With three search seeds and these task counts only differences above about 0.12 (Suite A) can be detected at the artifact level; smaller gaps are reported as undetected."

### A7 Field-level claim scoped. PARTIAL
- Done: abstract tex:476 "In one widely used optimizer's own SpreadsheetBench history"; intro tex:494 "One optimizer's own history"; Related Work cites external evidence (rethinkharness, Meta-Harness same-task search, nguyen2026rsea).
- Remaining: (1) "widely used optimizer's own" contradicts tex:494 ("An earlier CapEvolve draft") and reads as another group's system; it is the authors' own earlier draft, and "widely used" is unsupported. (2) Section 5.5 title tex:1017 "Most of the historical gain was scorer compliance" and tex:1022 "most of the as-saved gain is compliance with a scoring convention and not task skill" remain; Gemma is 14 of 33 (42%).
- Fix: abstract: "In an earlier version of our own optimizer's SpreadsheetBench results". Retitle 5.5 "Scorer compliance accounts for 14 to 39 points of the historical gain" and delete the "not task skill" clause.

### A8 Exposure language. PARTIAL
- Done: Table 2 (tex:825) "score-only exposed"; caption tex:818; tex:834 "We call it score-only exposed, not fresh."; Limitations tex:1077; Suite C labelled development-exposed.
- Remaining "fresh" or equivalent: Figure 1 node tex:799 "fresh, scored once"; tex:1027 "which is why Suites A and B use fresh final sets" (contradicts tex:834 for A); Related Work tex:1068 "fresh final sets". Figure 1 caption and legend (tex:805, 809) say teal items are "fixed before any search outcome is seen", but B* is computed from run counters (node says so), Suite C was added at 17:40, and the retry policy changed at 13:11. Suite B is still "sealed" (tex:826, 950) while decisions.md line 24 records "Retail exposure check (provenance) still pending" and Table 18 lists an earlier CapEvolve tau2 retail result.
- Fix: replace "fresh" with "not used by search" (B) and "score-only exposed" (A) at tex:799, 1027, 1068; change the Figure 1 legend to "fixed by the protocol before final-set scoring" and drop B* from the "before any outcome" set or say "from counters only"; report the retail exposure check result or call B "held out from this campaign's search".

### A9 CapEvolve sees val-40 only. PARTIAL
- Done: tex:573, 832 "so they see 40 tasks where competitors see 120. This disadvantages CapEvolve, and we keep it as the native design."
- Remaining: (1) "disadvantages" is asserted, not shown; R4 W3 notes the direction of net bias is unknown. (2) decisions.md (13:15) says stock CapEvolve evaluates the seed on train-80 and charges 80 rollouts to its 600; tex:571 says "the train split is unused". Reconcile, and state the charge. (3) The paper says nothing on Suite A being restricted to `capabilities=system-prompt` (only visible in Appendix config tex:1175), which the "editable surface is a parameter" selling point depends on (R2-2).
- Fix: "differs in exposure, in an unknown direction"; add one sentence on the seed-baseline charge; one sentence that Suite A edits the system prompt only for CapEvolve.

### A10 Adapter zero-vs-drop. PARTIAL
- Done: Appendix tex:1299-1316: the 40-minute watchdog zeros never reached search ("event logs hold no watchdog zero"); the uniform classifier and Table 17 count error rows per arm and seed; tex:1293 states pre-13:11 zeros remain and are labelled.
- Remaining: the number of affected pre-13:11 rollouts per arm is not given. Table 17 is "Live runs only" (post-fix) and so does not quantify the contamination. tex:1316 says they enter a sensitivity analysis, with no number. R1 and R4-W9 point out that search-time feedback is corrupted, so a final-score sensitivity analysis cannot repair it.
- Fix: add a per-arm column "pre-13:11 zero-scored rollouts / counted rollouts" (from the gateway log and ledger) and one sentence that these arms' selected artifacts may be worse for that reason; or exclude pre-13:11 candidates from B* eligibility if the rollouts are separable.

### B Consistency fixes. PARTIAL
| Item | Status | Evidence |
|---|---|---|
| active_eval off vs on | RESOLVED | 3.3 tex:709-710 and Appendix tex:1133 both say on (the `%` comment at tex:713 still says False default, invisible). |
| 12 vs 6 candidates | PARTIAL | Abstract, 3.3, Table 12: "about ten" (per-suite). 5.4 tex:1012 and Fig 7 still "six", old val-40 run; same gate has 0.434 in 5.4 and 0.578 in Table 12 (Suite A). |
| 113k/$69 vs 118k/$82 | RESOLVED | one macro set (`\costCalls` 123,808; `\costTokensM` 648; `\costUsdProxy` 84; per-suite sums 121,522 + smoke/untagged). |
| 2 vs 3 trials | PARTIAL | tex:876 MDE for A uses "70 final tasks, one trial"; mock Table 2 has 120 tasks and 2 trials (720 cells); Appendix tex:1253 "one to three trials". Needs one design statement. |
| 4M cap vs 14-43M | RESOLVED | tex:1005 and the Table 15 caption define non-cache-read vs including cache reads. |
| last promoted vs best artifact | RESOLVED | tex:593, 746, Table 3 all "last promoted". |
| "nine competitors" count | PARTIAL | tex:838 gives the exact matrix (8 on A, GEPA on B and C, HarnessLens on B). Abstract, intro tex:498 ("nine competing methods run from official code") and conclusion say nine with no per-suite matrix; eight are official, one is a port. |

### C Rendering. RESOLVED
- The swallowed sentence is now on its own line (tex:698) and appears in the PDF. Table 1 moved to the appendix (tex:1508-1526) and fits. Limitations (PDF p.10) labels no longer overprint. Figure 2 (p.9) B and C rows are labelled; (c) shares rows with (b). Dagger: `\pend` uses the dagger; Table 16 caption refers to a double dagger.
- Nits: Figure 2 caption does not say panels (b) and (c) share rows (Figure 4 caption does); Table 16 caption mentions a double dagger that appears nowhere in the table.

### D Writing. PARTIAL
- Done: no `#NNN`, no "user-approved", no E1-E3, CR1, Tier 1, "T" in the body. RITS (tex:815) and MDE (tex:876) are defined at first use. Seed is mostly "seed artifact" / "search seeds".
- Remaining: (1) repo paths and file names in body prose and captions: tex:512 `audit/historical_results.md`, tex:778 `audit/exposure_ledger.csv`, tex:954 `analysis/out/sim_mde.md`, tex:1014 `analysis/out/sim_budget.md`, tex:1032 `audit/recomputed_numbers.csv` (Figure 3 caption), plus `openpyxl` (tex:518) and the file/sha footnote (tex:815). (2) Undefined at first use: Holm (no definition or citation; tex:480, 800, 874), B* in Figure 1 (tex:798) before its definition (tex:867), "pregate", "context digest", "failure clustering", "parallel branching", "cost gating" (tex:709-710), "reward-gated judge" (tex:647), "footprint" is defined. (3) Repetition remains: +33.0/+18.7 and +49.1/+9.9 appear in abstract, intro, 2.1, 5.5, Fig 3, Table 18; 85.6 vs 76.4 in 2.2, 5.5, Table 18; the 0.33/0.49/0.52 rule-P figures in 3.3, Discussion (tex:1051) and Table 12; Section 5.5 restates Section 2 almost verbatim. (4) "Seed" still means three things: "Seed (no search)", "Delta vs seed", "paired with the seed" (seed artifact), "search seeds", "rollout seed 0", "split seed". (5) Placeholders for the main finding are explicit (`\needs` at tex:480, 504, 900, 1096): OK.
- Fix: move all paths to a footnote-free appendix or remove ("a table of every claim is in the supplementary material"); define Holm once ("Holm step-down correction") at tex:874; replace the switch list at tex:709-710 with a pointer to Appendix; merge 5.5 into Section 2 (keep Figure 3 in Section 2); rename column headers to "vs seed artifact".

### E Tables and figures. PARTIAL
- Done: main tables are 7 columns (score, delta vs seed [CI], delta vs one-shot [CI], Holm p, USD, missing); tokens and wall clock in Table 15; per-seed values with missingness bounds in Table 16 (tex:1586); contrast panel `fig_contrast` exists (PDF p.22).
- Remaining: (1) the CapEvolve-vs-baseline contrast, the primary confirmatory family, is only in appendix Figure 4, not in a main table or the forest figure; (2) the `p_Holm` column does not say which family/contrast it belongs to, and it mixes primary-family rows with secondary rows (e.g. ACE and MIPROv2 are in the secondary family) and, on C, development-exposed rows (R4-W6); (3) Suite A table has a one-shot column although A has no one-shot arm in the frozen design (N1); (4) the caption does not say which interval is printed (primary or the pessimistic bound; R4-W8 point).
- Fix: replace "vs one-shot" on Suite A by "vs best-pre-specified baseline" or drop it; add a short main-text table or forest panel "CapEvolve minus each primary baseline" with the 12/8/6 Holm p; footnote each p_Holm with its family; state the interval type.

## Reviewer weaknesses

Format: ID, status, evidence or reason, remaining fix.

### R1
- R1-1 central claim generalized from one system. PARTIAL. Abstract and intro scoped (tex:476, 494); "widely used ... own" wording and Sec 5.5 title remain (A7).
- R1-2 underpowered for the question. PARTIAL. Described honestly in 4.4, Limitations, B and C labelled descriptive (tex:815, 874); not in abstract/intro (A6).
- R1-3 inference about artifacts, not optimizers. PARTIAL. tex:874 "claim at the artifact level only", per-seed table added (Table 16). Not stated how the three seeds enter the contrast (mean of the three artifacts? clustered over tasks?) nor what would license a method-level claim; title and conclusion still speak of comparing optimizers. Fix: one sentence defining the estimand (mean over the three frozen artifacts, tasks as cluster) and the S needed for a method-level claim.
- R1-4 confounds not a clean ablation. PARTIAL. Gate (A1, E12 pending), exposure (A9), truncation (A3), compute (A4) are now disclosed; no statement of tuning effort per arm and none of the "which direction does each confound push" asked for. Fix: a short "Confounds" paragraph with direction per confound plus a tuning-effort statement (see R2-10).
- R1-5 incident record vs "protocol removes each problem". PARTIAL. Incidents in App E (tex:1284-1316), but pre-13:11 zeros not quantified (A10) and the abstract still says "a protocol that removes each problem" (tex:477), conclusion tex:1096 "our protocol removes each". Fix: "reduces" and list what remains (deployment-level isolation, adaptivity, incidents).
- R1-6 controls too weak (no compute-matched control). OPEN. Only seed and a one-shot of about 10 rollouts (tex:859-860, Table 15). No best-of-k one-shot or compute-matched control; no limitation sentence. Fix: add a limitation sentence that "search adds nothing measurable" can only be concluded against a single-pass control, or add a best-of-k validation-selected one-shot arm on B and C (cheap).
- R1-7 rule P headline narrower than abstract implies. RESOLVED. Abstract tex:478 gives search length and suite range and says it "pays with low power"; tex:767-770 states that same-task luck and adaptivity over the validation split are not controlled.
- R1-8 over-claims ("fresh", "untouched", "protocol removes each problem"). PARTIAL. "untouched" gone; "fresh" at tex:799, 1027, 1068; "removes each" at tex:477, 1096 (A8).
- R1-9 accessibility and narrative. PARTIAL. Issue numbers and most code names removed; 3.2 and 3.3 still carry ~4 pages of CapEvolve internals and switch names (tex:640-650, 709-710); measurement contract still split across 3.4, 3.5, App H and App E. Fix: move 3.2 to the appendix beyond a one-paragraph summary; put a 5-item contract checklist in 3.4.

### R2
- R2-1 gate confound. PARTIAL (A1).
- R2-2 exposure and proposer-capability confounds; surface width not exercised. PARTIAL. Exposure disclosed (tex:832); Suite A is system-prompt only for CapEvolve (appendix only), no surface-width arm (E16), seed-baseline charge not in the paper. Fix: state in 4.2 and Limitations.
- R2-3 underpowered; tables lack contrasts. PARTIAL. Contrast family stated (A2); contrast figure only in appendix (E).
- R2-4 "nine competitors" is thin; cross-suite rank claim. PARTIAL. Matrix stated in 4.2 (tex:838); abstract/intro/conclusion say nine; tex:955 still plans a rank correlation of paired deltas across suites although B and C have 2 to 3 comparable arms (only GEPA and HarnessLens, B). Fix: say "eight on A, one to two on B and C" in the abstract and drop the rank-correlation `\needs`.
- R2-5 matched-checkpoint validity. PARTIAL. (a) B* is still set by the slowest main arm (tex:867; Limitations "Capacity bound the search") and EvoSkill's restart is an incident in App E, with no sensitivity of ordering to B*; (b) which methods' artifacts are exactly reconstructible at B* and the straddling-candidate rule are not stated; (c) cheap-arm exemption from the 200 floor is only implied by the Table 3 caption, and the mock Table 15 still shows 532 to 536 rollouts for ACE, MIPROv2 and Trace2Skill (real: ACE 75, MIPROv2 129, Table 16); (d) a common definition of "rollout" across GEPA metric calls, SkillOpt, and CapEvolve confirmations is absent. Fix: add a short table "artifact at B*: exact / approximate" and a sentence on the exemption and the straddle rule.
- R2-6 rule P operating characteristics simulation-only. PARTIAL. Now real-code simulation at observed difficulty with a stated edit mix (tex:1251) and the SE-helper bias disclosed (tex:1255); still missing competitor native-gate false-accept rates (tex:1051 `\needs`) and the sel-25/sel-10 mismatch (A5).
- R2-7 framing claims outrun evidence (compliance, replay vs strict gates). OPEN. Sec 5.5 title and tex:1022 unchanged; the replay (tex:530, "blocked the champion path in 6 of 16 runs whose champions later gained") is not reconciled with the adoption of the strict rule P. Fix: state that champions that gained on an exposed split are not evidence for the gate, and soften as in A7.
- R2-8 "fresh" overstated; contamination of Gemma/gpt-oss. PARTIAL. Fresh language partly fixed (A8); model/benchmark contamination (public benchmarks) not discussed.
- R2-9 cost and metering inconsistencies. RESOLVED. One macro set for totals; cap definition in Table 15 and tex:1005; Table 16 caption states metering audit; CapEvolve optimizer cost reported.
- R2-10 competitor fairness documentation. PARTIAL. ACE rename and HarnessLens retry in App E (tex:1291-1292); no per-competitor deviation table, no statement of tuning effort or pilots, SkillOpt's removed gold reports and EvoSkill's replaced task interface are not mentioned in the paper. Fix: a table of deviations per arm and a "no arm was tuned beyond the defaults except X" statement.

### R3
- R3-1 hard to follow, undefined terms. PARTIAL (D). Fixed: Tier 1, E1-E3, CR1, T, RITS, MDE. Remaining: Holm, "pregate", "digest", "ledger" (defined in AO), B* in Figure 1.
- R3-2 raw identifiers, paths, issue numbers. PARTIAL. Issue numbers gone, 11 `\texttt` in body and 5 repo paths remain (listed below).
- R3-3 data-exposure story confusing. RESOLVED. tex:832 "they see 40 tasks where competitors see 120"; "74" is tied to 49+25 in Table 2. (Optional: put "CapEvolve: val 40 only" in the Table 2 caption.)
- R3-4 matched-checkpoint construction and mock contradictions. PARTIAL. Text improved (tex:867); mock Table 15 still has one-shot at 10 rollouts and the three cheap arms at 532-536; "about 12 rollouts per hour per search" (tex:867) gives 45 h for 540 rollouts while Table 15 wall clock is 11 to 29 h.
- R3-5 numbers disagree across sections. PARTIAL. Totals, cap definition fixed; trials (2 vs 3 vs 1) unresolved (B); "75.4 to 78.6" next to +18.7 at tex:520 is not explained (58.3 + 18.7 = 77.0; say the range is over the three runs).
- R3-6 98.6% ceiling vs 19 failing gold files. PARTIAL. tex:520 still gives the ceiling from the four unscorable tasks only, right after the 19-file sentence. Fix: state the ceiling with and without the 19 (on the 280 split) or say it excludes them.
- R3-7 two search lengths. PARTIAL (B).
- R3-8 broken passage and clipped Table 1. RESOLVED (C).

### R4
- W1 question cannot be answered by seed contrasts. PARTIAL. Pre-specified arm-vs-arm contrasts are in 4.4 (A2); title, abstract, conclusion still speak of comparing optimizers while claims are artifact-level; the interval vs bound issue in E.
- W2 B* counterfactual and budget-coupled schedules. PARTIAL. Secondary native-end analysis (A3); no ordering sensitivity across checkpoints; iteration caps (50 on A, 10 on B/C) and metric-call caps (600 vs 550) are only in the appendix tables, while the body says "600". Fix: add a B* sweep (e.g., 200, B*/2, B*) in the appendix and state the caps in 4.3.
- W3 fairness asserted. PARTIAL (R2-10). "Official code" is now qualified for WikiSkill; intro still says "nine competing methods run from official code"; no reproduction sanity check on native benchmarks.
- W4 compute not matched. RESOLVED. tex:869 disclaims parity; tokens, USD, Pareto plot reported.
- W5 privileged information asymmetry. PARTIAL. Disclosed in 5.6 and Limitations (tex:1041, 1078), and the shared scorer feedback is stated (tex:832). The statement "selection-time numbers are flagged" ignores that gold actions of the 74 tasks propagate into the final artifact; SkillOpt's removed gold reports not mentioned. Fix: flag the AO Suite B row in the main table and say the final-set score is also affected.
- W6 final-set provenance. PARTIAL. Suite A relabelled; family-prefix near-duplicate risk not discussed; Suite B "sealed" with provenance check pending (A8); Suite C still has p-values in the Holm-adjusted table (tex:979-985).
- W7 operating characteristics do not transfer. PARTIAL (A5).
- W8 MDE inputs unverified. RESOLVED. Observed variance replaces assumptions (tex:876, 1253); the task-level effect spread 0.15 is declared a remaining assumption, with 0.0 floors reported. (Minor: final task counts for A, 70 vs 120, still `\needs`.)
- W9 missingness/retry asymmetries contaminate search. PARTIAL (A10).
- W10 forking paths. PARTIAL. App E lists timed incidents; the roster changes (EvoSkill promotion, HarnessLens placement, Suite C added 17:40, ACE/MIPRO restart, AO reconfigured, rule P operating point re-chosen) are not in a dated changelog; Figure 1 still says "fixed before any outcome". Fix: a half-page dated changelog in the appendix with what was known at each point.
- W11 did searches change anything. PARTIAL. Per-seed deltas and missing counts added (Table 16); accepted-candidate counts and fraction of seeds whose B* artifact equals the seed are still `\needs` (tex:1051). Fix: add the two columns to Table 15 or 16 now so they are populated automatically.

### R5
- R5-1 broken text and clipped table/labels. RESOLVED (C).
- R5-2 story split across three papers. PARTIAL. Placeholders for the finding are explicit; the contribution list still mixes audit, rule and comparison, 5.5 duplicates Section 2, the title is unchanged. Fix: one-paragraph spine in the intro; fold 5.5 into Section 2.
- R5-3 repetition. PARTIAL (D).
- R5-4 ambiguous vocabulary. PARTIAL. "seed" senses (D), "HC"/"AO" in tables (undefined abbreviations; "HC" and "AO" appear in table row labels, never defined), "same-task luck" tex:769 used with a gloss. Fix: define HC/AO in Table 3 caption or spell out.
- R5-5 over-claims and contradictions. PARTIAL. Fixed: last-promoted vs best. Remaining: "fixed before any outcome" (tex:805, 809), "fresh" (A8), "not task skill" (tex:1022), and the uncited flourish "Evaluation hygiene is the oldest problem here" (tex:1068).
- R5-6 internal-process text leaks. PARTIAL. Issue numbers, "user-approved", scripts/derive_numbers.py gone; paths remain; Appendix still refers to `scripts/gen_config_tables.py`, `analysis/out/metrics`, `bypassed_usage.csv`, "campaign scratch store" (tex:1295).
- R5-7 tables and figures do not answer the question. PARTIAL (E).

## N. New or exposed problems in draft 2

- N1 (high). Suite A table and text use a one-shot control that the frozen design does not have on A. Evidence: Table 3 shows "One-shot control" on Suite A with a "Delta vs one-shot" column and a 10-rollout budget (tex:930-931, 1554); tex:912 "the second delta column ... is the test of whether search pays"; Figure 2 and Figure 4 list "One-shot ctrl" on A; Table 3 (Arms) lists one-shot on B and C only; analysis_plan 5A "No one-shot control on A". Fix: remove the A one-shot rows/column and the sentence at tex:912, 914, or add the arm to the design before the cutoff.
- N2 (high). The operating-point simulation set versus the gating split (A5 item 1). Needs tau-runner and the stats owner to confirm the split the stock gate screens on for B (25 or 49) and C (10 or 20).
- N3. Section 5.4 numbers (0.050, 0.434, 0.199, 0.41, 0.54) come from the old val-40, six-candidate, assumed-difficulty run and are hard-coded; "ten points" is not a gain the other tables use (+0.04 to +0.10).
- N4. tex:571 "the train split is unused" conflicts with decisions.md 13:15 (seed evaluated on train-80, 80 rollouts counted).
- N5. Intro tex:498 "nine competing methods run from official code": eight are official.
- N6. Mock internal consistency (will matter when real numbers replace them): Table 2 has 120 final tasks and 2 trials while 4.4 computes MDE for 70 tasks and one trial; Table 15 rollouts and wall clock contradict tex:867 (12 rollouts per hour).
- N7. Section 3 retains long `% src:` comment blocks with repo paths (tex:534-537, 557-781). Invisible in the PDF but present in paper_full.tex and the source, a risk if the anonymized source is submitted.
- N8. The method text now has three counts of what the stock gate is: "1 SE", "Bonferroni-corrected z-test with SE floor" (AO) and "Beta posterior" (tex:646); the paper does not say which is "the stock gate" in the E12 sentence (tex:869), which is hill-climb's masked 1-SE gate.

## Mechanical checks

### Dashes
- Em dash U+2014: none in paper_full.tex or paper.txt. TeX "---": none outside comment rules (tex:19, 24 are `% ---` comment lines).
- En dash (TeX `--` or U+2013) hits:
  - tex:601 "propose--evaluate--promote" (paper.txt:197)
  - tex:1432 "Horvitz--Thompson" (paper.txt:1470)
  - table placeholder cells `-- & --` at tex:930, 971, 980 (paper.txt:549, 569, 579)
  - bibliography page ranges `9340--9366`, `7957--7968` in paper.bbl (2 lines; paper.txt:834, 858)
  - `\texttt{--parent}` tex:1519 (a flag, appendix)
  - `\draw[ar] (\a) -- (\b);` tex:802 is TikZ, not text.
  - U+2212 minus signs in paper.txt (38 lines) are math minus, not dashes.
- Fix: "propose, evaluate and promote"; "Horvitz and Thompson estimate"; empty cells as "n/a" or blank.

### Banned words
None found in paper_full.tex or paper.txt (delve, leverage, seamless, crucial, pivotal, landscape, tapestry, realm, underscore, showcase, unlock, notably, furthermore, moreover, "it is worth noting", "not only"). No hit in either file.

### Visible code identifiers (`\texttt`) in the body (before `paper:endofbody`, tex:1100)
- tex:512 `audit/historical_results.md`
- tex:518 `openpyxl` (twice)
- tex:778 `audit/exposure_ledger.csv`
- tex:815 footnote: `spreadsheetbench_verified_400.tar.gz`, `10ef893d`, `github.com/RUCKBReasoning/SpreadsheetBench`, `data/`
- tex:954 `analysis/out/sim_mde.md`
- tex:1014 `analysis/out/sim_budget.md`
- tex:1032 `audit/recomputed_numbers.csv` (Figure 3 caption)
- Also in the body, undecorated code names: "reward-gated judge" (tex:647), "pregate", "context digest", "failure clustering", "parallel branching", "smart merge", "cost gating" (tex:709-710), "rule P" is a defined term.
- Appendix `\texttt` (allowed but note): tex:1135, 1162 (`scripts/gen_config_tables.py`), 1258 (commit `029335d8c`), 1263, 1282 (`audit/recomputed_numbers.csv`), 1289, 1292, 1323 (`error_label_parity.csv`), 1403-1523 (switches), 1655 (`analysis/out/sim_budget.md`, Figure 7 caption), 1673 (`analysis/out/metrics`, `bypassed_usage.csv`), 1711 (`audit/recomputed_numbers.csv`). The config tables (tex:1175-1218) print raw run-record keys with backticks (`k-se=1.0``, `n-trials=1``) and a stray backtick.

### Issue numbers and repo paths in the body
- Issue numbers `#NNN`: none in non-comment text. "issues #785/#786", "user-approved" gone. (Source comments contain `#`-free path references only; `decisions.md` is cited in comments.)
- Repo paths in visible body text: the five listed above (tex:512, 778, 954, 1014, 1032). Appendix and captions: tex:1162, 1282, 1323, 1655, 1673, 1711, plus "Blocker files are in the campaign scratch store" (tex:1295).
- Internal IDs: "E12" only inside a `\needs` footnote (tex:1015); no E1-E3, CR1, Tier 1 outside comments.

### Undefined terms at first use
- B*: first used in Figure 1 (tex:798), defined at tex:867.
- rule P: first used in 3.2 (tex:647), defined in 3.3; abstract and intro avoid it.
- RITS: defined at tex:815 (first use).
- MDE: defined at tex:876; earlier body use of the full phrase is fine.
- T: not used in the body any more (only `\mdeATasks`). OK.
- Holm: never defined or cited (tex:480 `\needs`, 800, 874, 902).
- HC and AO: used as row labels in Tables 3, 4, 15, 16 and figures, never defined.
- "pregate", "context digest", "reward-gated judge": undefined (tex:647, 709-710).
- "cheap arms": defined only in the Table 3 caption (tex:841).

### Mocked (`\pend`) outcomes stated as findings in prose
Each renders red with a dagger, and tex:904 says so, but the sentences are written as results:
- tex:909 "On Suite A, 2 of the ten optimizer arms beat the seed with Holm-adjusted p<0.05, and the largest paired delta is +6.7 points, held by SkillOpt".
- tex:910 "The final set has 120 tasks, each scored with 2 trials, for 3 search seeds per arm" (design values, mocked).
- tex:950-951 "Suite B ... its 40 test tasks ... the largest paired delta is +6.3 points (HarnessLens), and 0 arms clear Holm-adjusted p<0.05".
- tex:952-953 "Suite C ... 20 tasks ... Its largest delta is +8.5 points (HarnessLens), and 0 arms clear p<0.05".
- tex:867, 903 B* values 540, 480, 420 (mock) and the Table 2 cell "120" (tex:825).
- Not found: the abstract, introduction, Discussion and Conclusion contain no mocked numbers; they use `\needs`.
- Fix: replace tex:909-911, 950-953 with the `\needs` footnotes only (keep one sentence of structure without a number), so no result sentence exists until the data do.
