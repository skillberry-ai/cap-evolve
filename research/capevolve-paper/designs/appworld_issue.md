DRAFT, not posted. Proposed title: "Experiment design: CapEvolve on AppWorld (Suite F), DeepSeek-V3.2 and gpt-oss-120b"

Full design (every command, build checklist, acceptance test and the UNVERIFIED list): [`research/capevolve-paper/designs/appworld_experimental_design.md`](https://github.com/skillberry-ai/cap-evolve/blob/research/capevolve-paper-20261011/research/capevolve-paper/designs/appworld_experimental_design.md). This issue is the short version. Nothing has been run on AppWorld yet.

## Goal

Measure whether CapEvolve improves a ReAct code agent on AppWorld, and compare it with ACE and ALTK-Evolve (the two memory methods our colleagues report on AppWorld) and with GEPA, SkillOpt and Trace2Skill under one harness, one prompt template and one optimizer model.

## Verified facts about AppWorld (2026-10-12)

- `appworld==0.1.3.post1`, Python 3.11+ (installed and tested on 3.12). Released splits: train 90 tasks (30 scenarios), dev 57 (19), test_normal 168 (56), test_challenge 417 (139). The paper lists 105 and 60 for train and dev; the released data has 90 and 57.
- test_normal difficulty counts are Easy 57, Medium 48, Hard 63 (levels 1, 2, 3). The colleagues' tier percentages are exact fractions of these counts.
- TGC = share of tasks passing all tests; SGC = share of scenarios (3 tasks each) where all pass. One task is 0.595 TGC points, one scenario 1.786 SGC points.
- Test ground truth is on disk in plaintext (evaluation code, and a non-null gold `answer.json` for 33 of 168 test_normal tasks), and failed-test traces contain gold values. So the design uses two data roots (search-time root with train and dev only, final root with a separate OS user), a feedback tier that strips traces, and a sealed-id refusal in the adapter.
- AppWorld rules: test sets are for aggregate scoring only; generic hints from train and dev are allowed; hardcoded API calls in agent logic are not.

## Reference numbers and the comparability problem

Colleagues' test_normal numbers (single runs, from the IBM Research blog posts of 2026-08-11 and 2026-08-18): DeepSeek-V3.2 no memory 79.8 / 64.3 TGC/SGC (148K tokens/task), ACE 80.4 / 73.2 (634K, 106 guidelines), ALTK-Evolve 89.3 / 80.4 (263K, 191); gpt-oss-120b no memory 39.9 / 21.4 (110K), ACE 54.8 / 35.7 (777K), ALTK-Evolve 56.0 / 37.5 (116K, about 29 guidelines). Per-tier numbers are in the full design.

The two memory systems use different no-memory baselines (72.0 vs 79.8 TGC for DeepSeek) because of a prompt-template difference, a 7.8-point effect as large as ACE's gain. The ACE paper's own gpt-oss-120b baseline is 54.8 / 33.9, 15 points above the colleagues' 39.9 / 21.4. Step caps differ (AppWorld 50, ACE 40, ALTK report 30), the ALTK mining split is train plus dev in the technical report, and nothing is paired (no per-task data), so 1.2 points on gpt-oss is about 0.2 SE. Our fix: one template for every arm (the official AppWorld ReAct prompt), every method's learned artifact rendered into the same slot, a template-sensitivity panel, and a side-by-side table that compares gains over each side's own baseline, never absolute scores. We ask the colleagues for per-task results, their templates, and ACE and ALTK-Evolve settings.

## Setup

- Targets: DeepSeek-V3.2 and gpt-oss-120b, endpoints as placeholders; each target is its own suite with its own N* and families. Optimizer, reflector, curator and extractor for every arm: Claude Sonnet 5.5. Decoding: temperature 0, 8000 tokens per step, `max_steps` 50, reasoning mode DeepSeek non-thinking, gpt-oss medium; 90 minute wall cap per rollout, 3 hour hang rule.
- Splits: optimize on train; select on dev (gate, GEPA valset, SkillOpt selection, ALTK-Evolve dose); report test_normal (primary) and test_challenge (secondary). No arm touches test before the final window; enforced by file isolation, an adapter seal, closed egress, REPL guards, proposer sandbox, transcript scans and registered tree hashes.
- Surfaces: prompt (P), tools (T: generic helpers plus API-doc notes, linted against hardcoded API calls), playbook/memory (M), full (F).

## Arms

CapEvolve (3 seeds each): `hcF` stock-gate hill-climb on the full surface (reference), `hcP`, `hcT`, `hcM`, `hcF-ruleP` (rule P with the earlier parameters), `aoF` (agent-optimize), `hcF-nohist` (history removed, hidden-history sandbox), `ctl-oneshot`. Controls: seed (10 final trials per task), seed-check, template panel.
Competitors: Tier 1 (3 seeds): ACE (official code; native in its own harness, adapter to run in ours; exploratory variants with target-as-reflector, ground-truth labels, and its native harness), ALTK-Evolve (v1.3.0 library plus a mining and rendering adapter, because its AppWorld harness is unreleased), GEPA 0.1.4, SkillOpt, Trace2Skill. Tier 2 (1 seed, exploratory): MIPROv2, EvoSkill, WikiSkill, Meta-Harness. HarnessLens: not run (its own target harness breaks the common-harness premise). ALTK-Evolve's known and unknown configuration is listed in the full design.

## Seeds, trials, budget

3 search seeds per arm. Final trials per task on test_normal: 3 for champions, 10 for the seed, 1 for Tier 2; test_challenge 1 (seed 3). Counted-rollout cap B = 900 per search, optimizer cap 10M non-cache-read tokens per search, matched checkpoint N* = largest count reached by every still-running primary seed, rounded down to a multiple of 50, floor 450, computed from counters only; other arms at min(N*, own count). Cutoff time registered before launch. All final rollouts of a target in one seeded, hashed, interleaved window with block-drift check.

## Statistics

Paired by task, clustered by scenario (56 clusters, df 55), cluster-robust t at the artifact level with the pipeline-level t(2) interval beside it. Holm families per target: F1 `hcF` vs {seed, ACE, ALTK-Evolve, GEPA, SkillOpt, Trace2Skill} (m = 6); F2 ablations (m = 10); F3 ruleP and AO vs {seed, ACE, ALTK-Evolve, GEPA} (m = 8); F4 SGC mirror of F1 (m = 6); F5 test_challenge (m = 4); F6 native end-of-run (m = 6). TOST margin 0.10 on non-significant rows (margin 0.05 has design power 0.43 to 0.63 at best, so it is not registered). Inert artifacts, infra_final scoring 0, retry-credit sensitivity and pessimistic missingness bounds as in analysis plan amendments 5, 9 and its errata.

Planning MDE (TGC points, 168 tasks, 3 champions, n = 3, seed n = 10, within-task variance 0.12, tau 0.15, scenario ICC 0.3): 0.058 conditional, 0.073 at Holm m = 6, 0.079 at m = 14; 0.143 pipeline-level. Tier MDE about 0.10; SGC MDE 0.08 to 0.13. These inputs are placeholders until a pilot null pool on dev re-estimates them. Gaps of 1 to 2 points between methods cannot be resolved by this or any single-run design at this size.

## Analyses

TGC and SGC by difficulty tier laid out like the colleagues' tables, tokens per task (cached tokens separate), steps and step-cap hits, guideline count and memory tokens per step, optimizer tokens and cost per +0.01 TGC, promotions per search, selection-to-final shrinkage, gate false-accept rates from a K = 20 dev null pool, side-by-side comparison table with caveats.

## Run order and cost

Build adapter and roots, probe (throughput, null pool, variance), register, search waves (CapEvolve P/T/M/F first, then Tier 1 competitors, then ablations, AO, Tier 2), compute N*, final windows, analysis. Upper bound about 63k rollouts per target (about 31k search, about 30k final); the lean plan is about 32k. At a sustained 300, 600 or 1,200 episodes per hour per target that is about 210, 105 or 53 hours (full plan), and about half for the lean plan. Target tokens are of order 10 to 20 billion per target for the full plan; Sonnet 5.5 optimizer tokens about 86M per target (of order $0.3k to $1k at proxy list prices). All are projections to be replaced by the probe. A fixed cut order (Tier 2, exploratory ACE variants, test_challenge, nohist, ruleP, then seeds 3 to 2) is decided by capacity only.

## What must be built

CapEvolve AppWorld adapter and surface lint, two data roots and split manifest, infrastructure classifier, Suite F entries in the final-evaluation tooling, and one adapter per competitor, each with acceptance tests A1 to A11 and the common competitor checks (the full design gives the step-by-step checklists).

## Claims this can and cannot support

Can: artifact-level statements on test_normal under this harness; pipeline-level statements only where the t(2) interval excludes 0; surface, gate and history ablations within the budget; descriptive tier and SGC patterns. Cannot: leaderboard claims, reproduction of the colleagues' numbers, cross-target claims from one target, "never seen by the model", rankings of gaps below the MDE, equivalence at the pipeline level.

## Open decisions

Lean or full plan and cut order; B = 900 and N* floor 450; Sonnet-reflector ACE as primary; whether Tier 2 and the native-harness ACE run; the cutoff time; whether colleagues share per-task data and templates; whether the helper-code surface is acceptable under AppWorld's hardcoding rule.

## UNVERIFIED

Leaderboard standings; the colleagues' exact harness, ACE and ALTK-Evolve settings and token accounting; that ALTK-Evolve's AppWorld harness is unreleased; why released splits are 90/57; guard-flag semantics in the installed AppWorld; CapEvolve skill-package and dev-only gate accounting; competitor adapter feasibility beyond campaign records; HarnessLens infeasibility; all planning parameters, throughput and cost projections; model contamination.
