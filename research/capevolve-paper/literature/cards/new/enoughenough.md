# enoughenough (FULL)
Exact title: When Is Enough Enough in Self-Evolving LLM Systems?
Authors: Enoch Yin, Bin Liu, Zhengling Qi (George Washington Univ.; Fudan Univ.)
arXiv id + version read: 2610.04756 v1 (only)
First date / latest date: 2026-10-03 / 2026-10-03
Venue/status + source: arXiv preprint; arXiv comment "23 pages, 5 figures, 7 tables"; no journal_ref.
Code URL + license: none stated (Reproducibility Statement p10 gives no URL). OpenAI-compatible: unverified.
Citation count: unavailable
Editable surface: whatever the host system evolves: SkillOpt skill documents, GEPA prompts. The method is plug-and-play, edits nothing.
Search method: wraps an existing loop (SkillOpt, GEPA); consumes per-item paired validation outcomes (candidate vs incumbent) each round. Stopping: anytime-valid e-detector built from testing-by-betting restart wealth processes W_t^(s) (aGRAPA or fixed-mixture lambda in {0.1,0.2,0.4}), H0 = the "pre-change" condition (Eq 2, p4: proposals still yield worthwhile improvement, threshold epsilon) holds for all rounds u>=s, epsilon=0.01, delta=0.05 (p4-7; Prop 1 p6: E[T_alarm] >= 1/delta). Output selection: change-point estimate nu_hat = argmax restart wealth, return artifact theta_{nu_hat-1} (Prop 2 p6). No archive/merge/memory.
Feedback signal: per-item binary correctness on the fixed validation set (n=200 SearchQA/GSM8K, n=24 OfficeQA).
Task splits / held-out protocol: validation drives the detector; separate unseen test (SearchQA 1400, GSM8K 500, OfficeQA 172) used only to report returned-vs-full-run accuracy (Table 1 p8). Test not used for selection.
Benchmarks and models: SearchQA, GSM8K, OfficeQA, LiveMath, SpreadsheetBench; SkillOpt and GEPA; DeepSeek V4 Flash, Qwen3-32B, GPT-5.6 Luna (p6).
Metrics: alarm round, change point, token fraction saved, paired accuracy difference with 95% CI.
Budget/cost reporting: tokens (M) to alarm vs full run (Table 1 p8); GEPA token cost is ESTIMATED from metric-call counts (p8, App D p20). Full-run budget N=40/40/16 rounds.
Reported limitations: localization guarantee proven only for fixed lambda, not aGRAPA (p9); resolution scales with validation size (smaller val sets give less evidence per round, Cor. 1 p18/Table 6 p21).
Key quantitative results: Table 1 p8 (DeepSeek V4 Flash + SkillOpt): SearchQA stops round 4/40, saves 91.6% tokens (2.18M vs 25.85M), returned 82.43% vs full 82.00% (delta +0.43, CI [-1.10,1.96]); GSM8K saves 89.8%, 97.40 vs 98.20 (delta -0.80, CI [-1.91,0.31]); OfficeQA saves 48.4%, 32.56 vs 33.72 (delta -1.16, CI [-8.72,6.39]). GEPA: SearchQA stop round 5 saves 73.8%, GSM8K round 6 saves 65.5% (p8). On SpreadsheetBench full run would accept a degenerate 'answer A' skill at round 16; detector alarms at round 8 and returns round-1 artifact (p8).
Candidate-evaluation allocation: n/a (stopping rule across rounds, i.e., allocation of total rounds, not across candidates/tasks).
Task selection/curriculum: none.
Merge/composition (verified?): none.
Optimizer self-modification: none.
Overlap with CapEvolve: (a) partially at the run level -- budget-aware early stopping with anytime-valid paired evidence; (d) partially -- they report an honest unseen test and explicitly flag late-round evaluation overfitting/reward hacking in the full run.
What it means for our claims: agent-optimize's "spend awareness / when to finalize" decision is no longer new if framed as stopping; we need to cite and, ideally, compare/ablate vs an e-detector stopping rule. Claim (d) already has partial precedent for reporting unseen-test of an early-stopped artifact. Reproduction feasibility: HIGH for the detector (small statistics code); needs paired logs.
Notes on evidence quality: appears single-run per setting (seeds UNVERIFIED), CIs on test deltas wide (OfficeQA +/-7pp with n=172), val sizes small (24 for OfficeQA), GEPA tokens estimated, comparison is to the full-budget run of the same system rather than to other stopping rules, no GEPA/MIPRO baseline comparison in the allocation sense.
