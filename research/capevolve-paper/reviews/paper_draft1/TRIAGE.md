# Draft 1 review triage (coordinator, 2026-10-11 21:45 UTC)

Five independent reviews: R1 senior adjacent, R2 mid-career same subfield, R3 early-career, R4 adversarial methodologist, R5 writing editor.
Agreement count in brackets.

## A. Science and design (coordinator decisions; executed before the cutoff, so before any final data is seen)
A1 [R1 R2 R4] Gate confound: CapEvolve uses rule P, while competitors keep their native gates, and E12 has no live arm.
  DECISION: launch E12 now as an exploratory arm, CapEvolve hill-climb with its stock gate on Suite C (and on B if gpt-oss headroom allows), 3 seeds, same budget.
  The paper states that the main comparison is "method plus its own acceptance rule". CapEvolve with rule P is the configuration under test, and E12 bounds the gate's contribution.
A2 [R2 R4] No pre-specified CapEvolve-vs-baseline test. DECISION: amend protocol/analysis_plan.md now (timestamped, before the cutoff).
  The confirmatory family per suite is:
  - each CapEvolve arm vs seed;
  - each CapEvolve arm vs one-shot control;
  - each CapEvolve arm vs each Tier 1 baseline.
  All are paired and cluster-robust, Holm within the suite. "Best baseline" is not used because it is data-dependent. Baselines vs seed are reported as secondary.
A3 [R4] B* truncation is unfair to budget-coupled schedules (SkillOpt cosine, iteration caps). DECISION: pre-specify a secondary analysis, each arm's native end-of-run artifact at the cutoff (unmatched budget, labelled as such). The primary analysis stays matched B*. The paper names which arms have budget-coupled schedules.
A4 [R4 R2] Optimizer compute is unmatched. DECISION: state that the matching is on target rollouts, not optimizer compute; report optimizer tokens (uncached, cache read, cache write) and USD per arm; the Pareto plot carries the compute comparison. Do not claim compute parity.
A5 [R4 R3] Operating characteristics are mis-stated or non-transferable. ACTIONS:
  - fix the unit (0.055 is per search of about 12 candidates, not per edit);
  - re-run the budget-exact simulation at the Suite B (opt 49/sel 25) and C (20/10) task counts;
  - recompute the MDE with variance taken from the observed baseline evaluations (real data now available);
  - explain why n_conf 5 / z 1.645 was not chosen (cost per confirmation within the 600 budget).
A6 [R1 R2 R4] Power: Suites B and C are near-uninformative and S=3. ACTION: say so up front. B and C are "transfer of the protocol" suites with descriptive results; inference is artifact-level only.
A7 [R1] The field-level claim rests on CapEvolve's own audit. ACTION: scope the abstract and intro claims to "a widely used optimizer's own history" and cite external evidence where it exists (Meta-Harness same-task search/score, SkillOpt sweep row) without over-claiming.
A8 [R1 R2 R3 R5] "fresh/untouched" over-claims. ACTION: use exact exposure language from audit/exposure_ledger.csv. Suite A final = never-scored residual pool sample (verify), B = sealed test, C = development-exposed; "fixed before any outcome" only where the decision log supports it.
A9 [R2 R3] CapEvolve sees val-40 only (D03). ACTION: disclose in setup as a data-exposure difference that disadvantages CapEvolve.
A10 [R1] The adapter zero-vs-drop issue on competitor feedback. ACTION: verify in decisions.md (ACE/MIPRO watchdog zeros before the 3 h rule); quantify the affected rollouts per arm and report them.

## B. Consistency fixes (one generated macro per number)
- active_eval off (3.3) vs on (App. A); 12 vs 6 candidates; 113k/$69 vs 118k/$82 totals; 2 vs 3 trials; 4M cap vs 14 to 43M (label as non-cache-read vs total); "last promoted" vs "best artifact" (3.1 vs 3.4); "nine competitors" is 8 on A and 2 on B/C, so count exactly.
## C. Rendering
- the % comment swallowing a sentence in 3.3; Table 1 clipped; Limitations labels overprinting; Fig. 2 B/C rows misaligned and unlabeled; dagger reused in Table 15.
## D. Writing (R5, R3)
- No issue numbers, repo paths, "user-approved", code identifiers or internal IDs (E1-E3, CR1, Tier 1) in the body; define RITS, MDE and T at first use, or avoid them.
- Repetition: each headline number appears once in the body plus the abstract.
- "seed" has three senses: rename to seed artifact, search seed, and trial index.
- The main finding (once real) must be in the abstract and intro; keep the \needs placeholder sentence explicit.
## E. Tables and figures (R2 R3 R4 R5)
- Main tables are too wide (11 columns). Redesign: score, delta vs seed [CI], delta vs one-shot [CI], Holm p, USD, missing. Move tokens and wall clock to the appendix, and add an appendix table with per-seed values and the missingness bound.
- Add a CapEvolve-vs-baseline contrast panel (forest) matching A2.
