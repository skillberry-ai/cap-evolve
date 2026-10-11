# triple (SHORT)
- Title (exact, arXiv): Efficient Prompt Optimization Through the Lens of Best Arm Identification (the brief's title 'Best arm identification for prompt learning under a limited budget' is NOT the arXiv title; method name is TRIPLE = besT aRm Identification for Prompt LEarning)
- Authors: Chengshuai Shi, Kun Yang, Zihan Chen, Jundong Li, Jing Yang, Cong Shen (6; UVA, Penn State). First 2024-02-15; read v3 (2024-05-30). arXiv API has no comment/journal_ref; venue UNVERIFIED (not claimed). Code URL: not checked.
- Surface: selection among a PRE-GENERATED pool of candidate prompts (also few-shot example selection, Table 4); generation not addressed (p.2).
- Method: casts prompt selection as fixed-budget best-arm identification: successive-halving/rejects family (TRIPLE-SH, -CSAR etc.) with embedding-based prediction variants (Alg. 4, App. E) under explicit LLM-call budget N (e.g. |P|=30, N=150).
- Evaluation: each pull = evaluate a prompt on a sampled example; test accuracy of the selected prompt reported normalized to Uniform baseline (Fig. p.10); validation 80/20 split only inside the embedding-predictor variant (App. p.31).
- Result: TRIPLE variants beat uniform/UCB-style baselines under fixed budgets for GPT-3.5 and Llama2 across BBH-like tasks (Fig. p.10; exact numbers not extracted).
- Budget: explicit call budget N is the core constraint.
- RELEVANCE: MED-HIGH as prior art for (a): fixed-budget BAI / successive halving over a candidate pool of prompts is established (2024). It does NOT cover evolving candidate DAGs, heterogeneous surfaces, or task-level posteriors. CapEvolve must cite and not claim novelty for 'budgeted racing/bandit selection among candidates'; a TRIPLE-SH baseline for the confirmation stage is a cheap comparison.
