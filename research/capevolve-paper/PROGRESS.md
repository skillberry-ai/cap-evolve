# Progress log

Newest first. Times are UTC. Sources: `decisions.md`, `protocol/analysis_plan.md`, the git log of the campaign branch. Amendments are numbered as in the analysis plan ("5-AMENDMENT n"). Every amendment below was written before any held-out score existed.
Plain-language status is in [`STATUS.md`](STATUS.md); real results are indexed in [`RESULTS.md`](RESULTS.md).

## What happens at the search cutoff

**Search cutoff: 2026-10-13 06:00 UTC** (fixed 2026-10-11, before any outcome).
1. Searches stop. Each arm's matched checkpoint N* is computed from rollout counters only (largest count every seed of every primary-family arm reaches, rounded down to a multiple of 50, floor 200). Other arms are compared at min(N*, own count).
2. The Suite A final ids (70 of the 239-id residual pool, seed 20261013) are drawn and hashed before any final rollout is scored.
3. The final evaluation scores every arm, the seed artifact and the one-shot control in one interleaved randomized window per suite (amendment 2). The sealed sets are touched here for the first time (Suite B test-40, Suite C test-20, Suite D test-40, Suite A sample). Capped-token reserve for it: 18M.
4. Contrasts, intervals and Holm adjustments run exactly as registered; mock tables and figures in the paper are replaced by real ones. Suite E searches may run past the cutoff up to their own 300-rollout budget (amendment 10I).

## 2026-10-12

- 13:14 Amendment 9 erratum 8: descriptive column `identical_to_own_seed` next to the shared-seed inert flag. No rule change.
- 13:03 Amendment 10 erratum 1: tau2 adapters log `infra_detail` (exception type, tool call) per failed attempt. Logging only, before any Suite E rollout.
- 12:59 Amendment 9 erratum 7: "no retry credit" sensitivity analysis added; the primary rule 5O-1 is unchanged.
- 12:50 Run status: spend 95.4M of the 200M capped-token cap. Suite A: Meta-Harness, Trace2Skill, EvoSkill s0 and GEPA s2 finished. Suite B: hill-climb about 441 of 550 rollouts. Agent-optimize Suite A s1 ended natively with the seed selected (classified as a native termination, not a crash). See [`STATUS.md`](STATUS.md).
- 12:31 E26 no-history sandbox v2 also scrubs inherited PROCESS and DIAGNOSIS notes (history leak fix, 8H addendum).
- 11:58 Paper: real E22 null-pool figure and table replace the mock ones.
- 11:52 Amendment 10 addendum (10I to 10L): Suite E search-end rule, wave admission by Azure capacity, fixed cut order (competitors first), frozen competitor list.
- 11:47 E22 null-pool replay finished: one-stage gate accepts a null candidate in 18.4% of cases (0.87 per 10 candidates), rule P as run 2.6% (0.23 per 10). Details in [`RESULTS.md`](RESULTS.md).
- 11:46 E26-nohist (Suite D, history removed) launched.
- 11:42 Amendment 9 erratum 6: E12B (stock gate on Suite B) paused under the load rule; it relaunches when the Suite B hill-climb ends.
- 11:30 User raised the capped-token cap from 170M to 200M. Stop ladder: 170M exploratory, 178M secondary, 182M all searches.
- 11:17 Incident, Azure quota: the gpt-4.1-mini deployment hit its token quota (429s at 11 to 19% around 10:55). Gateway cap set to 15 in flight, 429 rate 0.0% since 11:00.
- 11:16 Amendment 10: Suite E (tau2 airline replication of Suite D) registered on user request, on the same Azure target.
- 11:07 Amendment 9 erratum 5: final truncation of the exploratory best-of-k control on Suite C (paused 09:54).
- 10:55 Amendment 9 erratum 4: one uniform definition of counted rollouts for N*, budgets and the matched checkpoint.
- 10:48 E26 pre-launch test with real Claude passed and found 3 history leaks (seed PROCESS note, end-of-run insights sentence, a diagnose bullet), all fixed; amendment 8H in force.
- 10:07 Paper: E12B, HarnessLens search-time judge and draw-at-cutoff added to setup and results.
- 10:00 Amendment 9H: seeds whose Suite D champion edits outside its cell's surface lock stay in the cell and are flagged.
- 09:57 Amendment 9 errata 2 and 3: E12B relaunched 09:56 with the 7200 s simulator timeout of the other Suite B hill-climb arms.
- 09:55 Amendment 9 (after review round 3): no single headline estimand, cross-suite rule, amendments table, inert (seed-identical) artifacts get delta 0, equivalence scope and power, agent-optimize on B and C carries a dagger, E12B and truncated best-of-k disclosed.
- 09:52 Paper review round 3 on draft 4 (35b73dd7e): five reviews (scores 4, 4, 5, plus a methodologist and a writing editor), triaged and applied by 10:02.
- 09:49 Amendment 8 erratum: exact Holm first-step MDEs for Suite D on test-40.
- 09:42 Incident, HarnessLens environment defect: every earlier HarnessLens candidate edit failed because bubblewrap was missing on the host (materialization_failed; zero candidates reached a rollout). Those runs are recorded as "not evaluated, environment defect", never as a method result. bubblewrap 0.6.3 installed; s0, s2 and the extended run restarted from the post-baseline state.
- 09:42 Amendment 8: Suite D primary contrasts on the sealed test-40 only (H65 descriptive); new no-history cell E26.
- 09:20 Amendment 7: Suite D pre-registered (tau2 retail on Azure gpt-4.1-mini; cells, contrasts, E22 null pool, E25 and E26 as descriptive analyses).
- 09:15 User decisions: Azure token spend uncapped; second gateway port refuses non-Azure models so capped calls cannot bypass the budget guard.
- 08:40 Amendment 6: stock-gate arms get their own secondary family and selection-to-final shrinkage is reported for every arm. Disclosed as written after seeing search-time selection-split results.
- 08:28 CapEvolve Suite A optimizer-token guard changed from a hard kill to two stages (soft 3.5M, hard 3.9M non-cache-read tokens).
- 08:22 User raised the capped-token cap from 100M to 150M.
- 02:11 Amendment 5: infrastructure errors are retried three times with new trial seeds; a cell still failing counts as 0.
- 00:50 Incident, WikiSkill community port: infrastructure restart of all three Suite A seeds. HarnessLens Suite B relaunched on a patched timeout (relaunch 2 and 3).

## 2026-10-11

- 23:05 Amendment 4: N* is computed over primary-family arms only.
- 22:45 Amendment 3: TOST equivalence rule (margin 0.10), which interval supports which claim, E12A and E12C stock-gate arms, promotion counts per search.
- 22:32 Isolation round 3 closed web egress for every arm (proposer shims, sandbox containers on an internal network, gateway strips web tools); `/tmp` masked and final-set files no longer world-readable. Transcript scans found no web access.
- 21:25 Paper review round 2 on draft 2 (five independent reviews), triaged.
- 21:15 Amendments 1 and 2: fixed primary and secondary comparison families, native end-of-run secondary analysis, interleaved final window with drift check, planned final sizes (A 70x1, B 40x3, C 20x3).
- 21:10 Azure OpenAI direct endpoint available; E12C (stock gate, Suite C) launched.
- 20:59 Paper review round 1 on draft 1 (five independent reviews), triaged.
- 20:55 Metering audit: no optimizer usage bypassed the gateway; credential-exposure fixes applied. No credential is known to have leaked.
- 20:26 Paper scaffold (MLSys 2027 format, mock-number pipeline, `check_paper.py`).
- 19:50 Incident, HarnessLens trial errors: upstream aborts the whole baseline stage on any worker error; timeouts patched (see 00:50 on 10-12).
- 18:40 Incident, gateway priority tags: a stale low-priority tag slowed EvoSkill (and HarnessLens) for about 15 minutes after promotion to Tier 1. EvoSkill relaunched on fresh tags; the stalled runs are kept as waste, not results.
- 15:00 Incident, Suite B isolation gap: the CapEvolve optimizer on Suite B ran with read access to tau2 `tasks.json`. Fixed 14:57; transcript scan found no read of split or gold files.
- 14:42 CapEvolve main searches (hill-climb and agent-optimize, three seeds each) launched on the campaign SHA with merged rule P.
- 13:59 PRs #779, #783, #786, #788, #790, #791, #792, #793 merged into the campaign branch (paper-mode switches, gold isolation, rule P, merge verification, screen accounting, gate replay, Method section, final-set manifests). None go to main.
- 11:15 User decision: keep the 72 h envelope and compare at a matched checkpoint instead of a fixed rollout count.
- 09:36 VERSE, CoEvoSkills and HarnessLens on Suite A recorded as failed reproductions.
- Through the day: competitor searches (GEPA, SkillOpt, EvoSkill, WikiSkill, Meta-Harness, ACE, MIPROv2, Trace2Skill) launched, and several relaunched on a uniform infrastructure-retry rule.
- 01:24 Analysis plan and methodology preflight written; rule P and the primary family defined.
- Campaign branch `research/capevolve-paper-20261011` created from main `e3cb513`. Historical audit finds the old SpreadsheetBench gains do not survive the recalculating scorer (Gemma +33.0 as saved, +18.7 recalculated; GPT-5.5 +49.1 vs about +10); the old test sets are marked development-exposed.
