# coharness (SHORT) -- arXiv 2607.22688v1
- Title: Co-Harness: Co-Evolving Harnesses and Model Weights for LLM Agents
- Authors: Zhengyu Chen, Teng Xiao, Huaisheng Zhu et al. (6 authors; Meituan, AI2, independent)
- arXiv 2607.22688 v1; first/latest 2026-07-17; venue: arXiv preprint (no comment); code: none found in PDF text.
- Editable surface: harness (prompts, tools, skills, middleware, retry logic, context mgmt, memory) AND model weights (SFT on harness-generated trajectories). Weights trained => outside CapEvolve's frozen-weight scope.
- Search: alternating loops: HarnessCritic (LLM) analyses failed trajectories, attributes structured harness-level causes (prompt ambiguity, tool schema error, missing skill, middleware mismatch) and proposes local diffs; a patch is accepted only if it improves the targeted failure mode (delta_in > 0) without regressing held-out behaviors (delta_out >= 0) (Sec 3.5 p6) and goes into a versioned harness registry with rollback; accepted harness generates trajectories for SFT of the next model; stop when no patch validates or marginal gain small (p4).
- Evaluation/held-out: math reasoning benchmarks AIME25, HMMT25 etc. with Qwen3-8B and Qwen3-32B, two rounds: +20.4 pp average, +27.2 pp on HMMT25 for Qwen3-32B (p3); plus a 200+ hour autonomous case study; details of splits/seeds not read (UNVERIFIED).
- Budget/cost: not itemised in text read.
- RELEVANCE: LOW-MED. Per-patch gate with regression check on held-out behaviors and a versioned registry (e) are similar in spirit to our paired gate; weights training and math tasks differ. No threat to (a)(b)(c)(d)(f) beyond generic harness-critic proposer.
