# harnessvalue (file slug only; paper title: Where Does Harness-Optimization Value Live? Localized Gains and the Budget-Splitting Trap in Self-Evolving LLM Agents; the paper names no system "HarnessValue") (FULL)
Exact title: Where Does Harness-Optimization Value Live? Localized Gains and the Budget-Splitting Trap in Self-Evolving LLM Agents
Authors: Michael Nguyen, Wei Chen Tan, Nurul Aisyah Hassan, Arvind Raman, Li Hua Lim, Ahmad Faiz Razak (affiliations printed: Monash Univ. Malaysia, Universiti Malaya, USM, UPM; a seventh name "Jia Hui Wong" appears in the PDF header but not in the arXiv API author list -- minor discrepancy)
arXiv id + version read: 2609.02889 v1 (only version)
First date / latest date: 2026-06-25 / 2026-06-25 (note: id prefix 2609 but v1 date is June 2026; as given by API)
Venue/status + source: arXiv preprint; comment "17 pages"; no journal_ref.
Code URL + license: none stated. OpenAI-compatible: unverified (uses Qwen2.5-7B).
Citation count: unavailable
Editable surface: harness text split into 4 named slots (role, task-strategy, tool/format-rules, reflection/control) rendered to one string injected in a ReAct preamble. Prompt-only.
Search method: GEPA reused unchanged per slot, coordinate ascent; GEPA = Pareto parent from candidate pool, minibatch reflect, accept-if-not-worse on train minibatch, rescore accepted child on full val, return best-val (p9). Slot-scoped reflection meta-prompt. No merge, no memory.
Feedback signal: ALFWorld/WebShop env success (binary / dense score) with rollout traces.
Task splits / held-out protocol: ALFWorld 30-task dev manifest (train+val small ~10 val) and disjoint held-out test n=134; WebShop test n=80; test fixed across methods (p10). Candidate selection on val; test evaluated once per evolved harness. But: 5 slot probes + LOO + several budgets are all run and reported on the same test set; headline slot choice was identified on test (post hoc), no correction for multiple comparisons stated.
Benchmarks and models: ALFWorld, WebShop; one backbone Qwen2.5-7B as both policy and reflector (p10), temperature 0.
Metrics: held-out success; 10k bootstrap CI; McNemar for ALFWorld; paired bootstrap for WebShop.
Budget/cost reporting: rollout budget B=64 (primary), B=120 (corroboration); single-slot at B/2=32; all-to-control at 64. Only rollouts counted; no tokens/dollars. Seed (single run per cell appears; multi-seed UNVERIFIED).
Reported limitations: single frozen backbone; two benchmarks; magnitude noisy at n=134 (p3, p17).
Key quantitative results: Table 2 p12: full structured 0.657 vs stock 0.642 vs GEPA-flat 0.642 (McNemar p=0.617/0.480). Table 3 p12: LOI control slot +0.119 (p=0.0046, 22 vs 6 discordant), role +0.030, strategy +0.007, format +0.007; sum of LOI +0.164 vs full +0.015 (sub-additive). Table 4 p14: all-to-control @32 0.761 (+0.119, p=0.0046), @64 0.724 (+0.082, p=0.0725 ns). Table 5 p14: accept-and-rescore floor ~16 rollouts per accepted iteration (2x3 minibatch + ~10 val); 16/slot -> 0 slots accepted; 32/slot -> 3 accepted, 1 froze text. WebShop 0.518/0.539/0.545 all ns.
Candidate-evaluation allocation: none adaptive; uniform even split across slots vs concentrate on high-credit slot (credit assignment from LOI/LOO runs, which themselves cost additional budget not charged to the "recovered" arm).
Task selection/curriculum: none.
Merge/composition (verified?): slots composed by coordinate ascent and concatenation; no verification beyond held-out test.
Optimizer self-modification: none.
Overlap with CapEvolve: partial (c) (multiple named surfaces of one harness, though all text) and (a) (budget allocation across surfaces); minimal elsewhere.
What it means for our claims: gives us a citable, concrete failure mode for splitting a fixed budget across multiple surfaces (relevant to our joint-surface claim (c): naive per-surface budget partition can starve gain; per-candidate minimum budget needed to pass an accept gate, comparable to our paired gate needing enough n). Required comparison: budget-concentration vs uniform-split ablation on our heterogeneous surfaces. Does not threaten novelty. Reproduction feasibility: MED (small scale; Qwen2.5-7B, ALFWorld).
Notes on evidence quality: small (64-rollout) budgets, single backbone, headline gain depends on a post-hoc best slot, 'recovered gain' arms cost extra LOI runs, @64 not significant; the explanation (floor) is mechanistic and plausible but the LOI c4 effect could be selection noise at n=134. Same first author as 2606.28374 (recursive held-out) -- both share very similar presentation style (conservative claims).
