# Campaign status (plain language)

_Last updated: 2026-10-13 15:50 UTC (coordinator periodic check)_

## Update 15:50 UTC
- **Spend**: capped spend is 176.3M of 230M; the v1 final window stops itself at 198M.
- **v1 final window (15:26)**:

  | Suite | Done | ETA |
  |---|---|---|
  | A | 2086 / 2520 | ~1.5 h |
  | B | 1612 / 2520 | ~5.9 h (long pole) |
  | C | 890 / 1020 | ~1 h |
  | D | 11262 / 13080 | ~1.7 h |

  - Per-arm infra above 5% on the first attempt: B oneshot (infra_final 5.9%), D t (2.8%) and D ctl (1.1%). Ruled: no rule change; the tools-surface edits plausibly induce them; reported per arm with sensitivities.
- **Suite E final**: frozen (5a1edeac3), 5,100 jobs. It launches when D ends (~17:00). The ao block is late-registered when E32-ao s1 ends. No HL on E.
- **Stalls**: none. All final-eval outputs were written within 11 minutes.
- **v2**: no search launched yet; smokes only.
  - Smoke-found defects, all fixed and merged:
    - pooled split (#826);
    - budget-fit P2 rule (#832-#834);
    - AO-2 token basis, refusal detail and operator-session billing (#835, after #836);
    - read-only worktree crash (reverted);
    - helper_surface config.
  - Pins: HC-2 a3f5eeb6d, AO-2 d68775bbd (registered 54df3caab).
  - HC-2 launches after its smokes pass (E first in waves of 3, A next, D after the v1 D window). AO-2 follows its re-smoke.
- **Artifacts**: repo-sync finished the secret scan; the 12 hard hits are all third-party fixtures or binaries (nothing to rotate). The upload is in progress.

_Last updated: 2026-10-13 12:50 UTC (coordinator periodic check)_

## Update 12:50 UTC
- **Spend**: capped spend is 173.9M of the 230M cap; the v1 final window stops itself at 198M.
- **v1 final window (12:26)**:

  | Suite | Done | First-attempt infra rate |
  |---|---|---|
  | A | 1213 / 2520 | 0.1% |
  | B | 1120 / 2520 | 2.0% |
  | C | 450 / 1020 | 0.9% |
  | D | 7884 / 13080 | 2.3% |

  - No candidate errors.
  - HarnessLens finished: 480/480 rollouts, 7 trace failures, all retried.
  - V2 smokes slowed A (255 to 140 jobs/h), so the s98 witness smokes were stopped.
- **Stalls**: none. Every final-eval output was written within 6 minutes.
- **v2**:
  - The code is main at 6131641e6 (v2.0, registered).
  - Smokes confirmed the pooled split and the hidden C.
  - The smokes also showed that the default P2 sizes fund ZERO rounds within v1's budgets (the seed baseline is 4×|F|).
  - imp-gate is calibrating a budget-fit rule:
    - K 4, smaller rungs, 1 survivor, fewer control and baseline trials, no in-search final estimate;
    - 2 rounds per search;
    - per-round power at +0.10 is only 7-22%; power at +0.15/+0.20/+0.25 is pending.
  - Asked the user whether to add a 2× budget arm (non-matched).
  - Plumbing smokes (s97 on A; small-knob smokes on E) are running: AO-2 propose works.

_Last updated: 2026-10-13 09:50 UTC (coordinator periodic check)_

## Update 09:50 UTC
- **Spend**: capped spend is 172.6M. The cap was raised to 230M (user, 08:15) for the v2 reruns; the v1 final window still stops at 198M.
- **v1 final window**: running in registered interleaved order since 07:03.

  | Suite | Done | First-attempt infra rate |
  |---|---|---|
  | A | 512 / 2520 | 0.2% |
  | B | 541 / 2520 | 1.3% |
  | C | 151 / 1020 | 0.7% |
  | D | 3631 / 13080 | 1.75% |

  - No candidate errors.
  - B/C rebalanced, net zero: B default 10, C 10, HL 16.
  - Suite A idle-gap watch: max non-first-turn call 323 s; the pause threshold is 450 s.
- **Stalls**: none. All live dirs were active within 20 minutes. All v1 searches ended at the cutoff, except E32-ao s1 (running). E32-ao s0/s2 are native early stops.
- **CapEvolve v2**:
  - Every v2 PR is merged to main: #814, #817, #822, #823, #815, #821, #818, #825, #816 and #824. 11E v2.0 was registered at 6b94ccba0.
  - The smoke tests found a main bug: the pooled split never triggered because the spec was read before run_config was logged.
  - Fix #826 is open, the full suite passes, and it is being merged.
  - Then a new SHA, a new worktree, re-registration, re-smoke and launch (18 searches: A, D, E × HC-2/AO-2 × 3).
- **Artifacts**: repo-sync is uploading all run artifacts to the paper repo as release assets, with a secret scan and a manifest.

_Last updated: 2026-10-13 06:50 UTC (coordinator periodic check)_

## Update 06:50 UTC (search cutoff in progress)
- **Cutoff 06:00**: final-eval-eng is leading it.
  - Stops: B ao s2 (06:00:11), A ace s1 and mipro s0/s1 (06:03:06), and C gepa s0-s2 (06:03:21, about 3 min late; rollouts after 06:00 must be excluded from the counted search).
  - Counters are snapshotted with sha256 (campaign-scratch/cutoff_20261013/), and the stops are in experiments/final/manifests/cutoff_stops.json.
  - Next: N* per suite, B* reconstruction, freeze into registry.jsonl, then the final-eval launch.
- **170M rung**: applied at 04:22 (E12B hcstock s0/s2 stopped, champion cand_0003). Capped spend is 171.1M of 200M; the 18M final reserve remains.
- **Suite E** continues on its own schedule; hl s0 is held.
- **v2 PRs**: #817, #815 and #818 are open; #816 is in fix. The user decision on v2 rerun headroom is still open.

_Last updated: 2026-10-13 03:50 UTC (coordinator periodic check)_

## Update 03:50 UTC
- **Spend**:
  - Capped spend is 169.0M of 200M; proxy cost is $386. The pace slowed to about 1.8M/h over the last 30 minutes.
  - The 170M exploratory rung (E12B hcstock s0-s2 stop, finalized on sel only) is armed with tau-runner.
  - The last W4 cell (Suite E HarnessLens s0) is held.
  - The 178M rung (ACE, MIPROv2, then the W4 competitors) stays registered.
- **Stalls**: none; every live run dir has been active within 20 minutes.
- **v2 PRs**:
  - #814 merged.
  - #817 gate/P2: under review.
  - #815 HC-2 and #818 AO-2: open, stacked on v2/gate.
  - #816 helpers: fixing two review blockers.
- **Open user decision**: v2 rerun headroom (about 4M under 182M versus the 6-25M needed). The options are raising the cap, running HC-2 only, or holding the rest of W4.
- **Cutoff 06:00**: N*, reconstruct, freeze, then final evals.

_Last updated: 2026-10-13 00:50 UTC (coordinator periodic check)_

## Update 00:50 UTC
- **Spend**:
  - Capped spend is 158.6M of 200M; proxy cost is $380.
  - The pace is 3.65M/h over the last 2 h, mostly Suite E (GEPA, ACE, gepafull, 1S) and ACE s2 on Suite A, which projects about 177M by 06:00. That is above the 21:11 central forecast.
  - The metering auditor is re-forecasting and applying the registered 170M ladder, including holding Suite E wave W4 if needed.
- **Stalls**: none. No live run dir has been idle for more than 1 h.
- **Suite B**:
  - hc s0/s2 finalized with the seed as champion (sel 0.52 / 0.60); post_sel rescore is running.
  - HarnessLens: all four arms (matched s0-s2 and the extended run cut at 10M) end at v0 with no accepted candidate.
- **Suite E**: W1-W3 are running; W4 (13 cells) is queued.
- **Outage**: Claude Code subagent model access was refused from 22:09 to 22:20 UTC. The user moved teams. The searches were unaffected because they run through the campaign gateway.
- **CapEvolve v2**:
  - #814 is merged.
  - #817 (gate/P2): the full suite passes except the one failure that is already on main; review in progress.
  - #815 (HC-2): runs on the real P2 evaluator; the final estimate on C is being added.
  - #816 (helpers): fixing the 2 blockers from review (IPython traceback tagging, lint/smoke bypass).
  - AO-2: in progress on v2/ao2.

_Last updated: 2026-10-12 21:50 UTC (coordinator periodic check)_

## Update 21:50 UTC
- **Spend**: capped 144.7M of 200M; proxy USD $367. 21:11 forecast at 06:00: 154/160/171M (low/central/high) before the 18M reserve; no rung crossed centrally. On the current-attempt basis, nothing is over its per-search cap (hlext 8.72M of 10M; ACE s1 3.15M, s2 1.70M of 4M; ledger guards are armed).
- **Stall check**: one run is live but stale, the extended HarnessLens run (counter idle 12 h, tokens flat since 20:51); its owner has been asked to confirm. Every other stale counter belongs to a finished run.
- **Suite B**: hill-climb s0 and s2 (budget-stopped) are being finalized host-side, with champion = seed and sel only. ao s2 and HarnessLens s0-s2 are still running.
- **Suite E**: the zero-D admission clause fired at 20:40 and launched the no-history wave; waves W3 and W4 are queued.
- **CapEvolve v2** (user request): four diagnoses are in improve/ and V2_PLAN.md. Epic #808, sub-issues #809-#813.
  - PR-0 #814 (port of the campaign core) is merged to main with green CI (user-approved admin merge).
  - PR-1 gate/P2 is coded on v2/gate, with tests and a PR next.
  - PR-4 HC-2 #815 is open but waits for PR-1.
  - PR-2 AO-2 and PR-3 helpers are being built.
  - v2 reruns come after 06:00, on A, D and E (with no capped judge), HC-2 first.

_Last updated: 2026-10-12 18:50 UTC (coordinator periodic check)_

## Update 18:50 UTC
- **Spend**: capped 125.6M of 200M; proxy USD $337. Ladder 170/178/182M with 18M final reserve; next forecast 21:11.
- **Suite A**: N* about 350 (live, bound by WikiSkill s2). GEPA s0/s1/s2 all budget_cap at 600 (s1 final/ being rebuilt from state). WikiSkill s0 native finish (521). Gold-isolation negative tests for WikiSkill pass (v3, reviewed by provenance-auditor).
- **Suite B**: HarnessLens s1 and s2 guard-stopped with no accepted version (artifact v0); s0 in iteration 3, near its guard. E12B relaunched 16:01. Hill-climb s1 finished.
- **Suite D**: several cells finished (PT s0, P s0/s2, T s2, CTL); no-history arm running clean.
- **Suite E**: wave 1 directories have appeared (E30 PT s0-s2, P s0), launched by the admission loop; launch report requested.
- **Repo mirror**: bcarmeli/mlsys2027-cap-evolve-paper up to date; hourly metrics commits running.

_Last updated: 2026-10-12 15:50 UTC (coordinator periodic check)_

## Update 15:50 UTC
- **Spend**: capped 111.8M of 200M; proxy USD $300 of $1000. 15:09 forecast after ACE was capped on the current-attempt basis and HL-extended was cut to 10M: about 155M by 06:00 including Suite E, under the 170M exploratory rung.
- **Token cap basis** (amendment 9 errata 9-12): current-attempt ledger tokens, excluding infrastructure-superseded attempts. Only SkillOpt s1 and s2 end over 4M; their artifacts were produced before 4M, so the sensitivity list is empty. ACE now has a ledger guard (it had none on the shared definition). ACE s0's interrupted final validation is being rerun.
- **Suite A**: N* = 250 (bound by WikiSkill s2). GEPA s0/s2 and SkillOpt s1 are budget_cap stops; agent-optimize all stopped (native or guard); hill-climb s1 is finished at 600.
- **Suite B**: hill-climb at 490/550; HarnessLens screening with a 3.5 h cumulative per-trial cap (task 80 straggler); E12B paused until hill-climb ends.
- **Suite D**: searches at about 250-440 of 550; E26-nohist running clean (history scans 0). The candidate-induced infra-label pattern is disclosed; no accepted champion is affected.
- **Suite E**: registered, all waves queued; admission holding on the Azure mini queue (about 9 s).
- **Designs for colleagues**: AppWorld (#804) and SWE-bench Verified with GLM 5.3 (#805) posted.
- **Paper repo**: bcarmeli/mlsys2027-cap-evolve-paper mirrors every commit within 10 minutes (sync loop running).

_Last updated: 2026-10-12 12:50 UTC (coordinator periodic check)_

## Update 12:50 UTC
- **Spend**: capped (non-RITS) 95.4M of the 200M cap (user raised it from 170M at 11:30); proxy USD $261 of $1000. Stop ladder: 170M exploratory, 178M secondary, 182M all searches; 18M reserved for the final evaluation. Re-forecasts at 15:09 and 21:11.
- **Suite A**: Meta-Harness, Trace2Skill, EvoSkill s0 and GEPA s2 finished; agent-optimize s1 host exited with the seed selected (being classified); others running.
- **Suite B**: hill-climb at about 441/550 each; GEPA about 270-300; agent-optimize s2 still searching (search count 147 under the uniform definition, amendment 9 erratum 4); HarnessLens restarted after the bubblewrap fix and screening (s2 near its 4M guard); stock-gate E12B paused 11:41 under the load rule, relaunches automatically when B hill-climb ends.
- **Suite C**: hill-climb, GEPA and stock-gate running; agent-optimize finished natively; best-of-k truncated at k = 6/6/8.
- **Suite D (Azure gpt-4.1-mini)**: 21 searches plus E26-nohist (launched 11:46; history-free sandbox v2 also scrubs inherited PROCESS/DIAGNOSIS notes). E22 null pool done: false-accept per 10 null candidates 0.87 one-stage vs 0.23 rule P (about 6x the simulated rate). The mini deployment is at its quota; gateway cap 15 gives about 417 ok calls/min with 0 429s.
- **Suite E (airline replication of D, user request)**: registered (amendment 10 and addendum); waves admitted automatically when the mini queue drains (expected about 18:30-20:00); competitors ACE, MIPROv2, GEPA-full, AO and one exploratory HarnessLens seed ready.
- **Paper**: draft 7 zip in the user's home (Suite E, real E22 figure, history-ablation definition). Review round 3 triaged and applied.

_Last updated: 2026-10-12 09:50 UTC (coordinator periodic check)_

## Update 09:50 UTC
- **Spend**: capped (non-RITS) 75.2M of 170M; pace 13.0M in the last hour (HarnessLens restarts dominate), 7.6M/h over 3 h. Proxy USD about $217 of $1000. Azure direct 118M tokens (uncapped). Stop rule (updated for the 170M cap): 145M stops exploratory arms (HL-extended first), 155M stops secondary arms; final-eval capped need being estimated.
- **HarnessLens (Suite B)**: every earlier HarnessLens iteration failed because bubblewrap was missing on the host (materialization_failed; 0 candidates ever rolled out). Those runs are recorded as "not evaluated, environment defect", never as a method result. bubblewrap 0.6.3 installed 09:42Z; s0, s2 and HL-extended restarted from a clean cut (baseline-stage tokens kept, failed-loop tokens refunded); s1 kept running with a live refund (iteration 8 is the first candidate to reach rollouts).
- **Suite A**: Meta-Harness all three seeds finished at 600; EvoSkill s0 finished; GEPA s2 at 600; others progressing (no stalls over 3 h among live runs).
- **Suite D (tau2 retail, GPT-4.1-mini target)**: wave 1 running, E22 null pool running (finish about 11:00). Amendment 8 approved (primary contrasts on sealed test-40 only; H65 descriptive) with new cell E26 no-history (3 seeds, launch about 13:00 after a reviewed one-flag patch).
- **Paper**: redesigned method paper frozen as draft 4 (35b73dd7e); review round 3 done (scores 4, 4, 5 plus methodologist and writing editor); triage in progress.
- **Isolation**: capopt egress rules present (uid 1038 allowed only 127.0.0.1:4111); the systemd unit shows inactive but the rules are loaded.

## Where things stand
- **Protocol frozen**: matched-checkpoint comparison (user decision), search cutoff **2026-10-13 06:00 UTC**, B* from rollout counters only; rule P for both CapEvolve arms (k_se 1, n_conf 3, z 1.282, dmin 0, coverage 0.95); Suite A final = seeded stratified sample from the 239-id SpreadsheetBench-912 residual pool; Suite B final = sealed retail test-40.
- **Suite A (rollouts of 600, s0/s1/s2 at 08:22)**:
  - GEPA 546/407/569, Meta-Harness 600/600/583 (s0 and s1 finished), SkillOpt 417/523/497.
  - CapEvolve hill-climb 282/409/200 (s2 counter flat for 5.3 h; being checked), agent-optimize 216/372/333.
  - EvoSkill 332/320/320, WikiSkill 227/241/211.
  - MIPROv2 132/148/138, ACE batch 133/76/71, Trace2Skill finished at 200.
  - E12A stock-gate 306/366/355.
- **Suite B (tau2 retail)**: HC, AO and GEPA running (GEPA 217/200/190). AO was resume-restarted onto the isolated shim at 22:40. HarnessLens relaunched 22:39 on the fully isolated launcher (98-101, baseline done).
- **Suite C (tau2 airline)**: HC, AO, GEPA (42/29/39) and controls running; exploratory E12C stock-gate hill-climb running; best-of-k control starts when the controls finish.
- **Throughput**: single Gemma deployment saturated; ≈12 rollouts/h per search → projected B* ≈ 300–450, below 600 (to be stated in the paper).
- **Spend** (08:22): non-RITS 59.4M; the cap is 150M (user decision 03:5x). The pace of about 3.7M/h projects to about 139M. Stop rule: 125M stops the exploratory arms, 130M the secondary arms. Proxy USD $157 of $1000.
- **Isolation round (21:30-23:00)**: every web channel is closed for all arms (proposer egress, sandbox containers on sb_internal from 22:32:24Z, and the gateway strips web tools). /tmp is masked, and final_set files are no longer world-readable. Transcript scans found no web access.
- **Integrity**: proposer isolation verified for Meta-Harness (container), EvoSkill (capopt mount-ns), Memento (no tools); split files no longer readable by other uids; leaked-credential scan of likely locations: 0 hits. Content filter on chain-of-thought output fields confirmed; only ACE affected (documented rename).
- **Code**: 8 reviewed PRs merged into the campaign branch (#779, #783, #786, #788, #790, #791, #792, #793); none to main.

- **Paper**: draft 3 (MLSys 2027 format, 10-page body, check passes, results mocked as \\pend). Two rounds of five independent reviews done and triaged; final round after real results. Concurrent work (Piao et al. 2609.39148) is positioned.
- **Protocol amendments before the cutoff**: fixed comparison families; native end-of-run secondary; interleaved final window plus drift check; equivalence (TOST ±0.10); promotion counts; B* over primary arms only; final sizes A 70x1, B 40x3, C 20x3.

## Uncertain
- B* on Suite A is bounded by the slowest Tier 1 arms (EvoSkill, ACE, MIPROv2); at current pace B* may land near the 200 floor.
- Whether Suite B relaunch completes in time.
