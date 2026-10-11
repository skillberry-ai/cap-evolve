# codingagentsopt (SHORT)
Title: Coding Agents are Strong Prompt Optimizers
Authors: Agamdeep Singh, Srishti Gautam, Priyanshu Gupta et al. (6 total; Microsoft, incl. Sumit Gulwani)
arXiv: 2609.26261 v1; first posted 2026-08-13 (id/date inconsistent with 2609 prefix; as given by API); arXiv comment "Preprint". Code: none stated.
Surface: single system prompt / skill markdown file for an agent (ALFWorld, tau2-bench retail+telecom, SpreadsheetBench-Verified).
Method: CASD = one offline pass where an unmodified off-the-shelf coding agent (Claude Sonnet 5 per p5) writes analysis code over a static corpus of agent trajectories and writes the skill file; no search loop, no validation gate, no environment access (Sec 3, p3). 3 skills per benchmark, mean reported.
Evaluation/held-out: held-out test sets (ALFWorld 50 games, tau2 40 tasks, SSB 50 items); 3 seeds; limited-data regime (same static pool for all methods) and head-to-head regime where GEPA/SkillOpt get extra validation + env access (p5-6). Test not used for selection.
Headline: Table 1 p5 mean gain over baseline +16.6 pts (CASD) vs +10.9 (GEPA) vs +5.3 (SkillOpt); CASD beats GEPA on 3/4; Table 2 p6 with extra val GEPA wins retail (46.7) and SSB (56.7), SkillOpt wins telecom (44.2). Target GPT-5.4-mini no-think.
Cost: Table 3 p6 optimizer $ per prompt: CASD ~$1.6 (total $6.4), GEPA $8.4 total (120 metric calls), SkillOpt $142.5; CASD's rollout-corpus generation cost treated as already sunk.
RELEVANCE: HIGH for (f): shows a coding agent as optimizer (single offline pass) beats GEPA/SkillOpt under matched data; threatens our premise that an agent-driven loop needs probe/promote machinery, and undermines gate-based search at tiny data (their finding: gate overfits small pools). Not about merging/heterogeneous surfaces/sealed accounting. Caveat: small test sets (binomial SE ~7pts/seed, p5), GEPA/SkillOpt baselines run by authors.
