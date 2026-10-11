# sage (FULL)
Exact title: SAGE: A Statistical Acceptance Gate for Self-Evolving Agents
Authors: Yihao Wang, Linhan Xia, Rui Liu, Zhaofeng Zhang, Hongyu Wu, Yang Yang, Jinglu He, Yu Guo, Kai Lei (Peking Univ., Univ. Oklahoma, Imperial, Michigan, Tencent, Edinburgh, Xunce, GienTech; first two equal contribution)
arXiv id + version read: 2609.36043 v1 (only)
First date / latest date: 2026-09-28 / 2026-09-28 (PDF header: "Preprint - September 30, 2026")
Venue/status + source: arXiv preprint; arXiv comment "10 pages, 2 figures, 2 tables"; no journal_ref.
Code URL + license: none stated in text. OpenAI-compatible: unverified.
Citation count: unavailable
Editable surface: a single persistent skill document (SkillOpt setting; workflow/tool-use rules text). SAGE changes only the ACCEPT gate; edits proposed by unchanged SkillOpt optimizer.
Search method: SkillOpt (Yang et al. 2026a, cited as [3]) generates a mini-batch of b candidate edits per step, bounded by a "textual learning rate", with a rejected-edit buffer (p3) -- i.e., prior art on claim (e) exists in SkillOpt, not in SAGE. Single-incumbent lineage, no archive, no merge. SAGE: accept iff discounted net gain Delta_lambda = w - lambda*l > 0, one-sided exact conditional binomial/sign test p_lambda(w,l) < alpha on discordant pairs (lambda=1 -> exact McNemar), and regression fraction rho = l/n_S <= tau (Eq 7-11, p5-6). Recovers naive gate at (lambda,alpha,tau)=(1,1,1).
Feedback signal: binary per-item verifier v in {0,1} on a held-out validation set, same items for incumbent and candidate (paired).
Task splits / held-out protocol: validation set used by the gate; "lambda, tau, alpha are tuned on held-out data only. The test set is unseen during the whole optimization" (p5). Whether Table 2 "final score" is test accuracy: not stated explicitly -- UNVERIFIED. Split sizes not given in main text.
Benchmarks and models: LiveMath, SpreadsheetBench, SearchQA, OfficeQA Pro, ALFWorld; backbones DeepSeek-V4-flash, GLM-5.2, MiniMax-M3, Qwen3.6 (p6).
Metrics: regression rate (fraction of incumbent-solved items an accepted edit breaks), final score.
Budget/cost reporting: "matched budget ... equal number of proposed edits and equal token cost" (p6); no token numbers shown in main text.
Reported limitations: binary verifier only; sign test discards magnitude; guarantee is per-comparison, validation reused across steps so trajectory-level error not controlled; alpha/lambda/tau need tuning; text-only (p8).
Key quantitative results: Table 1 p7 regression rate naive vs SAGE e.g. DeepSeek-V4 LiveMath 36.5% -> 0.0%, OfficeQA 42.8% -> 0.0%; 19/20 settings lower, 1 equal. Table 2 p7: DeepSeek-V4 LiveMath SkillOpt 34.15 -> paired-only (C1) 46.58 -> SAGE 48.78; OfficeQA 32.93 -> 45.12; mean +8.73 points over 20 settings, C1 +6.20, SAGE-over-C1 +2.53 (p6).
Candidate-evaluation allocation: none; each candidate evaluated on the full validation set; the gate is the only statistical element (no bandit/racing/successive halving).
Task selection/curriculum: none (though per-item regression ledger).
Merge/composition (verified?): none.
Optimizer self-modification: none.
Overlap with CapEvolve: hill-climb paired val gate. SAGE is a direct, earlier analogue (paired per-item gate with significance test and abstention) for skill documents -- threatens any novelty claim for the paired-gate in hill-climb (mean(delta)>k*SE is a z-style test on mean deltas; SAGE uses exact sign test on discordant pairs plus asymmetric regression penalty). Also threatens "regression-safe" claims.
What it means for our claims: we must not claim the paired-validation gate as novel; position as standard. Required comparison: sign/McNemar-style gate and asymmetric-regression gate vs our k*SE gate in hill-climb (binary verifiers only; our SE gate handles graded scores). Also cite PACE (Shawn 2026, "Anytime-valid acceptance tests for self-evolving agents", cited in 2610.04756 p12) -- NOT in our list; flagged for lead. Reproduction feasibility: HIGH (gate is ~20 lines; need SkillOpt).
Notes on evidence quality: no seeds, no CIs or tests on the headline score differences (single run per cell appears; UNVERIFIED), 8.7-pt average gain is large and suspicious for a gate-only change; final-score split unspecified; baselines not re-implemented beyond SkillOpt; claims 'highest in all 20 settings' with no variance reported.
