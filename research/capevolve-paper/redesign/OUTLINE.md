# Method-paper outline and section skeletons (story-architect, 2026-10-12)

For paper-core. Structure only: no outcome claims. Every result sentence below is a slot written as `[RESULT: ...]` and is filled only from the final evaluation. Follows STORY.md (claims C1 to C6, RQ1 to RQ5). Update 2026-10-12: hcstock (CapEvolve as shipped) is a headline arm; the gate trade-off is a central ablation (RQ-G); Suite D defaults to the stock gate. Lead decisions applied: Suite D is a separate pre-registered ablation family (Sonnet 5.5 optimizer, hill-climb only, no AO cell, may finish after the search cutoff); no new Suite A arms.

Amendment 6 wording rules: hcstock rows and the shrinkage analysis are labelled "post-search-time" in the table caption and the text; hcstock vs rule-P HC is descriptive; "gains survive" only if the artifact-level final-set interval excludes 0; "generalizes" only with the pipeline-level interval; "equivalent" only via TOST. Add the S-stock family (A 6 rows, C 2 rows) as its own block in Table 4.

Suite D frozen (EXPERIMENTS.md 0a): target gpt-4.1-mini, simulator and judge gpt-4.1, stock gate reference PT. Cells: PT, rule P, P, T, CTL, one-stage (3 seeds each); GEPA prompt-only (3 seeds). (Superseded: no-history, descriptions-only and PT+skills were cut.) TOST margin 0.10, so small differences are written "inconclusive". Panel mapping in 5.2: a = P, T, PT, TD (named "descriptions-only emulation of an MCP tool surface"), PTS if run; c = PT vs rule P vs one-stage (+ E26 gate ROC, E22 null pool); d = PT vs no-history; the GEPA cell (3 seeds) feeds 5.1 as the matched-surface competitor on the same target. 5.2b (HC vs AO) uses E10 arms only, there is no AO cell in Suite D.

SCOPE CUT (user approved Tier 1 only; lead message): no no-history, descriptions-only or PT+skills cells. Suite D = PT, rule P, P, T, CTL, one-stage (3 seeds), GEPA prompt-only (3 seeds). Section 5.2 therefore has panels a (P, T, PT, interaction), b (HC vs AO from E10 arms), c (gate, central), e (intake, analysis-only). Panel d (causal history) and all MCP/skill rows are removed. The causal history stays in section 2.4 as a design description without an ablation claim, and the limitations state: "the causal-history and the skill-package and MCP surfaces are not ablated."

Writing rules (PAPER_BRIEF + writing guide): no em or en dashes as punctuation, none of the banned words, every claim carries a number/citation/pointer, each paragraph opens with its point, one "In this paper, we" at most, no colon-titled headings, no bold lead-ins inside paragraphs, no rhetorical questions. Numbers via macros only; unfilled slots use `\pend`. Evidence statuses via `\prov`/`\needs` as in paper.tex.

Reuse map from the current draft (paper/sections): problem.tex and method.tex are rewritten; setup.tex trimmed; results.tex replaced; related.tex kept with the surface matrix added; limitations/ethics kept and extended; appendix config, deviations, protocol, contract, sim_table, mechanisms kept; fig_rulep, fig_forest, fig_anytime, fig_roles, fig_pareto reusable, fig_audit moves to appendix, fig_families/fig_contrast re-evaluated.

---

## Title and abstract
Title: CapEvolve: Optimizing Any Editable Surface of a Frozen Agent Under Code-Owned Evaluation.
Abstract (5 beats, about 170 words): (1) frozen-weight agents are improved by editing the files around them, but optimizers fix the surface and score themselves; (2) CapEvolve: surface as a parameter, code-owned gates, causal history, two orchestration modes; (3) evaluation scope in one sentence: three suites (list), ten competitors at a matched checkpoint, ablations of each design choice; (4) `[RESULT: headline vs seed with CI; vs best competitor; one ablation finding; one sentence on what each surface is worth]`; (5) code and artifacts released. No "best optimizer" wording.

## 1 Introduction (1.0 page)
Paragraphs:
1. Setting and concrete cost. Agents run on frozen models; their behavior is set by prompt, tool code, MCP tool descriptions and skill packages \citep{agent_skills_docs}. Optimizers edit these and report large gains \citep{...}. (cite the P/T/M/S/H matrix, point to Table 1 in section 6.)
2. Two gaps, named: (i) surface lock-in: each method edits one object (usually the prompt), so a failure that lives in tool code or a skill cannot be reached; (ii) self-scored acceptance: the optimizer or its loop decides what to keep using noisy scores it can influence. One sentence of evidence for (ii) from the sim (`\simPFalse...` vs `\simKoneFalse...`) and one for the audit (Gemma 43 percent and GPT-5.5 80 percent of an earlier reported gain was scorer compliance, appendix).
3. The idea. CapEvolve in one paragraph: surface is a parameter; code owns the evaluation; the optimizer sees a causal history; two orchestration modes. Name introduced once.
4. Evaluation scope, one sentence, then the numbers slot `[RESULT: ...]`.
5. Contributions as a short list (C1 to C6 from STORY.md, each one line, each with its section pointer).
Figure 1 (page 1): the loop. Left: four surfaces feeding one candidate; middle: optimizer with causal history; right: code-owned boundary (isolation, rule P, seal). Redraw from fig_roles.

## 2 CapEvolve (2.25 pages)
2.1 Problem and the editable surface as a parameter. Define: frozen target model M, capability set C (files), tasks with adapter, reward. Table 1 (surface, what is edited, edit policy, safeguard): system-prompt (change/consolidate/add, never drop a needed rule), tools (edit tool code and return values, add composite tools, swap through a wrapper, never bare-remove), mcp-tool (descriptions and exposure), skill-package (multi-file skill with progressive disclosure). Each surface ships a capability skill with a "what you can change here" menu and edit boundaries; the optimizer prompt is capability-scoped. State which surfaces the paper evaluates: prompt (A, B, C, D) and tools (B, C, D). Skill package and mcp-tool are implemented but not evaluated.
2.2 Agentic intake and the hard adapter gate. Intake interviews or reads a brief, installs the benchmark, writes the adapter (tasks, run_target or run_batch, score, trajectories, capability_sources) and the capability-scoped optimizer instructions; `cap-evolve check` refuses to spend budget until each required method is real and score() is deterministic. Pointer to fault-injection results (section 5.2e, appendix).
2.3 Algorithms and orchestration modes. Algorithm 1: hill-climb iteration (diagnose clusters, propose multi-part edit, evaluate N trials, paired gate, commit, update memory). Agent-optimize: a coding agent drives the same phases through skills, gate and seal still enforced by core code and plugin hooks. Say what differs (who decides what to try next; stop condition) and what is shared (gate, splits, budget counters).
2.4 What the optimizer receives. LEDGER (framework facts: outcome and BROKE/FIXED task ids per prior candidate), JOURNAL (optimizer handover), PROCESS (explanation per candidate), RUNMAP and prior_iterations, current-best trajectories only, protect set of currently passing tasks. Table or boxed list with owner column (framework vs optimizer) to make "clean ownership" the point.
Figure 2: system diagram (phases, artifacts, who owns which file). Draw once; can double as Figure 1 detail if space is short.

## 3 Code-owned evaluation (1.0 page)
Opening point: every decision an optimizer could game is made in core code it cannot edit. Subsections as short paragraphs:
- Isolation: gold and scorer unreadable from the proposer sandbox, negative tests per arm, egress closed, split files unreadable; scans reported as scans with coverage.
- Rule P (the conservative configuration; the stock gate is the shipped default and is described alongside it, with the trade-off tested in 5.2c): unmasked screen at k_se 1, then fresh-trial confirmation (n_conf, z, dmin, coverage; frozen values). Algorithm box or equation. Figure 3: false-promotion vs power simulation (fig_rulep).
- Footprint and coverage checks; seal on the final set; errored-trial policy.
- Concurrent null controls and injected faults (E04, E05: 15 pass, 7 partial, 6 gap, 1 info; gaps stated).
- One paragraph: the audit that motivated this (scorer compliance decomposition, gold reads), details in the appendix.

## 4 Experimental setup (0.9 page)
- Suites table (Table 2): A SpreadsheetBench (Gemma-4-31B, prompt only, final exposure: score-exposed residual sample, 70x1), B tau2 retail (gpt-oss-120b, prompt+tools, sealed test-40x3), C tau2 airline (gpt-oss-120b, prompt+tools, development-exposed test-20x3), D tau2 retail ablation family (Azure-direct target/simulator, judge gpt-4.1, same splits as B). Columns: target, surface edited, split sizes, final-set exposure, seeds.
- Optimizer for all matched arms: Claude Sonnet 5.5; budget 600 rollouts nominal, matched checkpoint N* from rollout counters, 4M optimizer-token guard.
- Competitors (Table 3): ten methods, the surface each edits (P/T/M/S/H), official code or reimplementation, which suites. State the surface asymmetry here, not only in limitations.
- Statistics: paired, family-cluster CR1, Holm per suite, TOST margin, artifact-level claims, S=3 raw values shown. Ablation family: own Holm, pre-registered in experiments/registry.jsonl, margins listed.
- Ablation protocol: one factor changed against the reference cell P+T hill-climb, stock gate, full history; reference counted once. Rule P is itself an ablation cell.

## 5 Results (3.0 pages)
5.1 RQ1 Comparison at a matched budget (1.0). Table 4: per suite, seed vs each arm (CapEvolve rows: hcstock, HC rule P, AO rule P; hcstock is the shipped configuration and the headline; Suite B lacks an hcstock row, say so), paired delta with CI and Holm p, N* and count per arm. Figure 4: forest plot (fig_forest). Text slots: `[RESULT: CapEvolve vs seed]`, `[RESULT: rank vs competitors, equivalence statements]`. **Required caveat sentence directly under the table, not in limitations:** on Suites B and C the CapEvolve hill-climb arm edits prompt and tools while GEPA, MIPROv2 and ACE edit the prompt only, so the gap mixes loop quality and surface width; Suite A (prompt only for all) and the prompt-only cell of Suite D (5.2a) separate the two. 
5.2 RQ2 Ablations (1.0). One compact panel per ablation, shared layout (reference vs variant, paired delta, CI, n), Figure 5 as a small-multiples forest:
 a. surface width (Suite D: P, T, PT, with the interaction contrast; skill and MCP surfaces are not evaluated);
 b. orchestration, HC vs AO (Suites A, B, C from E10 arms; promotions per search and stop reasons);
 c. gate (central, give it the most space, about 0.35 page): rule P vs stock gate (E12A, E12C) vs one-stage (Suite D). Report promotions per search, inert searches, final-set gain, selection-to-final shrinkage and regressions, so the reader sees whether strictness buys held-out reliability or only inertia. Neutral wording until results exist; do not describe rule P as an improvement;
 e. intake/adapter gate: fault-injection table (appendix) plus a sentence.
 Each paragraph: claim tested (from STORY.md), result slot, verdict in the pre-specified vocabulary (supported, equivalent, inconclusive, contradicted).
5.3 RQ3 Capability types (0.6). Table 5: surface by failure type (rows: knowledge gap, forgotten rule, tool misuse, long-horizon planning, simulator miss; cells: share of fixes by surface, from edit attribution on opt/sel splits). Paragraph: marginal value of each surface from 5.2a, interaction term. Closing paragraph (limited to prompt vs tools vs both): a decision guide stated as a short numbered rule list, each rule traceable to a table cell. mcp-tool and skill-package are not evaluated (state in one sentence; do not imply coverage).
5.4 RQ4 and RQ5 Cost, regressions and when the gate says no (0.4). Figure 6 (fig_pareto or anytime): held-out gain vs cost per arm. Three sentences each for: cost per held-out point; regressions vs seed (pass to fail counts) and winner's curse (sel gain vs final gain); promotions per search and inert searches. Transfer to a second target and judge sensitivity: one sentence each pointing to the appendix.

## 6 Related work (0.5)
Paragraph 1: optimizers by editable surface (matrix P/T/M/S/H, Table 1 in appendix if space), GEPA, MIPROv2, ProTeGi, SkillOpt, EvoSkill, Trace2Skill, WikiSkill, ACE, Meta-Harness, HarnessLens. Paragraph 2: acceptance and evaluation integrity (holdout reuse, one-stage vs confirmation gates). Paragraph 3: concurrent work (Piao et al. 2609.39148, Rethinking Harness Evolution 2607.12227, PACE, SAGE) and what we do not claim.

## 7 Limitations and discussion (0.6)
Short paragraphs, each with a number (add: causal history, skill-package and MCP surfaces not ablated): surface asymmetry; we built the system and ran the baselines; S=3 and artifact-level scope; B* below nominal budget; conservative rule P; same-split adaptivity; exposure of each final set; Suite D differs in target/judge; mcp-tool unevaluated; intake evidence is fault injection; metering gaps. One paragraph of discussion: when to use which surface and which mode, taken from 5.3 and 5.2b only.

## 8 Conclusion (0.2)
Three sentences: the system, the ablation finding `[RESULT]`, what remains open.

## Appendix (not counted)
A Competitor configs and deviations table; B incident log; C per-suite full tables and seeds; D historical audit decomposition (fig_audit); E rule P parameters and simulation; F ablation cell configs and registry hashes; G example accepted edits per surface (feeds 5.3); H transfer and judge sensitivity; I prompts and capability skills excerpts; J reproducibility checklist and artifact manifest.

## Figure and table inventory
F1 loop with boundary (new), F2 system diagram (new), F3 rule P sim (reuse), F4 forest RQ1 (reuse, regenerate), F5 ablation small multiples (new), F6 cost vs gain (reuse). T1 surfaces and policies (new), T2 suites (rewrite), T3 competitors and surfaces (rewrite), T4 RQ1 results (regenerate), T5 surface by failure type (new, analysis).

## Dependencies for paper-core
- Experiment plan approval and the frozen Suite D cell list from experiment-designer (the 5.2 panels follow it; drop panels for cells that are cut).
- Analysis scripts needed (metrics-eng): edit attribution (3b), failure-type labelling (3c), regression and shrinkage tables (5a, 5b), promotions per search, cost per point.
- Code: history-off switch and one-stage gate setting (algo-eng); tau2 skill loader only if the skill cell stays.
- No section may state a result before the final evaluation; until then slots stay `\pend`.
