# rethinkharness (SHORT)
- Title: Rethinking the Evaluation of Harness Evolution for Agents (note: distinct from existing card oeo_rethinking, 2608.09629)
- Authors: Yike Wang, Huaisheng Zhu, Zhengyu Hu, et al. (11 authors; AI2 / UW); last author Teng Xiao
- arXiv 2607.12227 v4 read (first 2026-07-14, latest v4 2026-10-05 per PDF header); venue: "preprint" (p.1). Code: https://github.com/rethinking-harness-evolution (as printed in abstract; URL looks incomplete - UNVERIFIED).
- Surface: harness = prompts, tools, middleware, memory (AHE meta-agent with explore agent disabled, p.4); also "harness scaling" (per-instance harness revision).
- Method compared: AHE-style harness evolution vs parallel sampling, sequential refinement, harness scaling under matched budgets K=5 (p.5).
- Evaluation: Terminal-Bench 2.1, Claude Opus 4.6 / GPT-5.4 / GPT-5.4 mini, 2 runs avg (p.5). Held-out protocol: 45 train / 10 val / 34 test tasks; harness selected on val, test reported (p.7).
- Headline: no unit tests: HE 67.4 avg vs direct 68.2 vs parallel sampling 72.3 (Table 1 p.6); with unit tests: HE pass@1 69.7 vs parallel sampling 82.0 (Table 2 p.6); disjoint split: HE avg 63.2 vs initial 63.2, i.e. +0.0 (Table 3 p.7). Games: harness scaling +80% on ARC-AGI-3 and +11% on EdgeBench vs sequential refinement (abstract p.1).
- Budget: matched compute budget K=5 rollouts/rounds; no $ reporting.
- RELEVANCE: HIGH (supports (d)). Strongest external motivation for sealed held-out evaluation and matched-budget baselines; CapEvolve should (i) cite it, (ii) include a matched-budget non-evolution baseline (best-of-K / sequential refinement) on at least one benchmark, otherwise a reviewer can raise exactly this critique. Threatens the novelty of the "honest held-out" half of (d) as a standalone claim (they propose disjoint search/eval); our remaining novelty = accounting of search spend and sealed-until-finalize across heterogeneous surfaces.
