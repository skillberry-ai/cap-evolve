# harnessceiling (SHORT, extra find)
- Title: Harness Evolution Hits a Ceiling: When Weight Training Should Begin
- Authors: Yuan Tian, Bing Hu, Hao Wang, Binghang Lu, Fang Wu (5; independent / Berkeley / Purdue / Stanford). arXiv 2610.11655 v1; 2026-10-08; "Preprint. Under review."
- Surface: harness (system prompts, memory tools, checkpoints, output gates, tools) of small Qwen3.5 4B/9B on DeepPlanning and WebArena-Lite; plus LoRA on evolved-harness trajectories.
- Search: self-evolving loop where an LLM proposes edits and a judge verifies them; accepted edits followed by a fresh anchor re-measurement; ablations show gains from capability-granting components rather than enforcement.
- Protocol: 48 development tasks for every decision, 72 held-out tasks no loop ever saw; per-rollout SD 0.023 so every config is a 4-rollout mean, differences <0.035 are noise (p.2).
- Headline: held-out DeepPlanning 4B 0.16 -> 0.30, 9B 0.32 -> 0.44 (abstract p.1); WebArena-Lite +0.09 on 117 unseen tasks.
- Budget: not reported as $ (UNVERIFIED).
- RELEVANCE: LOW-MED. Supports (d) practice (held-out split + explicit noise floor + fresh anchor after each accepted change); no threat to (a)-(c),(e),(f).
