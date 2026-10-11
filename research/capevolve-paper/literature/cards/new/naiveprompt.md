# naiveprompt (SHORT)
Title: Naive Prompt Optimization: Rethinking the Need for Complex Prompt Search
Authors: Yuan Chang, Xiaoqi Chen (2; Purdue)
arXiv: 2608.27266 v1; first posted 2026-08-27; arXiv comment: "22 pages, 12 figures". Venue: preprint ("Preprint." p1). Code URL: none stated.
Surface: single prompt string (student LLM instruction).
Method: NPO = single-lineage, teacher LLM revises prompt each iteration from sliding-window of full rollout traces + rewards (Alg. 1, p3); no population, no Pareto, no explicit search. Teacher in {Qwen3-8B, DeepSeek-V4-Flash-preview-0424, GPT-5.5}; student Qwen3-8B (also Llama-3.1-8B for transfer).
Evaluation/held-out: each revised prompt scored on a separate 300-example validation set; curves are valset scores (Fig 4, p6) -- no separate test split result for IFBench/HotpotQA seen in main text (UNVERIFIED; appendices not read in full). Transfer experiments (Fig 5, p7) apply prompts verbatim to other students.
Headline: NPO matches/beats GEPA with fewer rollouts (NPO 3,500/6,800 vs GEPA 3,593/6,871 on IFBench/HotpotQA, p5; GEPA counts cite the GEPA paper [1], apparently not re-run -- UNVERIFIED); gap widens with stronger teacher (Fig 4 p6). 22 TextArena games: NPO ~ GEPA ~ GRPO, no universal winner (p7).
Cost: rollouts only (student), teacher token cost not itemised in main text. MIPRO not run.
RELEVANCE: MED. Evidence that a strong-LLM single-lineage reviser rivals GEPA: supports our hill-climb baseline and (f) controller-strength argument; does not touch (a)-(e) directly. Honest limitation: "limited set of tasks" (p9). Single seed handling UNVERIFIED.
