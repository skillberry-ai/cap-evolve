# recursiveheldout (FULL)
Exact title: Recursive Self-Evolving Agents via Held-Out Selection
Authors: Michael Nguyen, Quoc Nguyen, Paul Vuong (Monash University Malaysia)
arXiv id + version read: 2606.28374 v1 (only)
First date / latest date: 2026-06-17 / 2026-06-17
Venue/status + source: arXiv preprint ("Preprint." p1); no comment/journal_ref.
Code URL + license: "we release the full harness, the six baseline re-implementations, and pre-registered manifests" (abstract) but no URL found in text -> license n/a. OpenAI-compatible: unverified (local vLLM serving of Qwen).
Citation count: unavailable
Editable surface: a 3-layer natural-language state injected as a preamble to ReAct: strategy, skills, playbook (all text, prompt-level; no tool code, no MCP).
Search method: RSEA = per generation: roll out current state on an evolve pool, the same frozen LLM rewrites all three layers from success/failure trajectories, candidate scored on a disjoint held-out validation split; accepted as working state if val >= current (lateral accept), frozen best updated only on STRICT improvement; returns empty state (= vanilla ReAct) if nothing strictly improves (Alg. 1 p5). Single lineage, no archive/merge/memory of failed edits.
Feedback signal: env-verified success (ALFWorld, tau-bench) or dense reward (WebShop); trajectories.
Task splits / held-out protocol: dev pool split into evolve set D_e and val set D_v (ALFWorld 30-task dev pool); only the frozen best state is run on the held-out test split (balanced 134 ALFWorld tasks x 5 seeds; GAIA L1 30 tasks; tau-bench retail 60 eval; WebShop 100 eval) (p5). For tool-use benchmarks, evolve/val/eval slices carved from a seed-shuffled test pool because official dev saturated (p5). Test not used for selection.
Benchmarks and models: ALFWorld (Qwen2.5-7B-Instruct), GAIA L1, tau-bench retail, WebShop (Qwen3-30B-A3B-Instruct); vLLM on 4xA100.
Metrics: success rate / dense score, mean +/- 95% CI over seeds, paired McNemar.
Budget/cost reporting: "iso-rollout budget" per method claimed (p6, p8); meta-LLM overhead O(G) calls, e.g. 190 meta+selection calls on tau-bench evolution (p8); no token/dollar table seen.
Reported limitations: transfer benchmarks single seed and modest eval sizes; GAIA noisy; NL-state regime only; strict gate guarantees safety on val, not on every test draw when val small (p9).
Key quantitative results: Table 2 p7 ALFWorld single-pass: ReAct 64.6+/-4.3, GEPA 63.9+/-5.3 (below ReAct), AWM 65.4, ACE 66.9, DC 70.7, RSEA 69.3+/-9.3 (McNemar p=0.015 vs ReAct); RSEA+retry 79.4 vs Reflexion 76.4. Table 4 p8: WebShop DC 0.136 vs ReAct 0.429, RSEA 0.437 (gate rejects all candidates -> empty state); tau-bench AWM 51.7 vs RSEA 40.0 vs ReAct 41.7. Table 6 p9: no held-out gate: 100% in-sample vs 66.7% test; strict gate 67.3 vs ReAct 63.6 (ALFWorld 54-task x3 seeds ablation; note baseline varies 64.6/64.2/63.6 across tables).
Candidate-evaluation allocation: none; every candidate gets a full val rollout; no adaptive allocation, no noise-adaptive stats.
Task selection/curriculum: none.
Merge/composition (verified?): none; 3-layer rewrite is a single-shot holistic rewrite, accepted atomically.
Optimizer self-modification: the agent rewrites its own state (strategy/skills/playbook) using itself as meta-optimizer; the optimizer procedure is fixed.
Overlap with CapEvolve: (d) -- sealed held-out test with strict keep-better gate and explicit overfitting ablation (100% in-sample vs 66.7% test); (c) loosely (three textual layers under one gate). Fits our hill-climb with a gate; gate has no significance test (strict > on val).
What it means for our claims: (d) cannot be claimed in the weak form "held-out gate prevents overfitting" -- RSEA shows it. Our differentiator must be accounting of unsuccessful search/failed proposals and multi-surface heterogeneity (tool code, MCP, skill packages). Required comparison: strict-improvement val gate vs paired SE gate on identical surfaces. Reproduction feasibility: MED-HIGH (small, local models; harness promised).
Notes on evidence quality: baselines re-implemented by the authors (GEPA scores below ReAct on ALFWorld, suggesting weak GEPA run); transfer results single seed; RSEA's ALFWorld gain 69.3 +/- 9.3 has wide CI; multiple baseline numbers for ReAct differ across tables; GEPA budget/config not itemised in extracted text (UNVERIFIED); same first author and Monash affiliation as 2609.02889 (similar conservative reporting style).
