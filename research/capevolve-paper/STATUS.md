# Campaign status (plain language)

_Last updated: 2026-10-14 18:50 UTC (coordinator periodic check)_

## Update 18:50 UTC 10-14
- **Spend**: capped spend is 193.2M of 230M (gateway healthy).
- **Final windows**: all done and registered (v1 A-E; v2 A, D, E).
- **Running**: the A v2.1-AO2 searches.
  - s0 is at 600/600 and in final confirmation.
  - s1 is at 506/600.
  - s2 is at 584/600, in confirmation.
  - ETA ~19-21Z. Then champions_V2_A_ao21.json, its scoring if any champion is non-seed, and the v2 freeze.
- **Pending user decisions**: B/C transfer spend; the Overleaf branch.
- **Stalls/crashes**: none.

_Earlier: 2026-10-14 15:50 UTC (coordinator periodic check)_

## Update 15:50 UTC 10-14
- **Spend**: capped spend is 193.0M of 230M (gateway healthy).
- **SpreadsheetBench (A) v2 window**: DONE at 14:26Z (840/840, 0 infra). Registered and analysed (errata 41).
  - HC-2 0.505 vs seed 0.364: +0.140 [0.045, 0.236], Holm 0.014.
  - HC-2 vs GEPA: tie.
  - Scaffold alone: +0.007.
  - v2 HC-2 beats v1 rule-P hc by +0.112 [0.024, 0.200], and is indistinguishable from v1 hcstock.
- **v2 vs v1 overall**: A, v2 better; E, v1 better or equal; D, v1 better (v2 = seed).
- **Running**: the A v2.1-AO2 searches s0-s2 are at 443, 377 and 463 of 600 (ETA ~17-19Z). Then their champions file, their scoring, and the full freeze.
- **Pending user decisions**: B/C transfer spend; the Overleaf branch.
- **Stalls/crashes**: none.

_Earlier: 2026-10-14 12:50 UTC (coordinator periodic check)_

## Update 12:50 UTC 10-14
- **Spend**: capped spend is 192.5M of 230M (gateway healthy).
- **Running**:
  - The SpreadsheetBench (A) v2 final window launched 10:00Z: 840 jobs, 475 done at 12:26Z, 0 infra. ETA ~14:15Z.
  - The A v2.1-AO2 searches s0-s2 are at 362, 307 and 356 of 600. ETA ~16-19Z.
- **Decisions**:
  - The user kept the current v2 A runs, which start from the v1 seed plus an empty helper scaffold (errata 40). The scaffold effect is reported separately.
  - The A window is anchored on the v1 seed (errata 38).
- **Pending user decisions**: B/C transfer spend; the Overleaf branch.
- **Stalls/crashes**: none.

_Earlier: 2026-10-14 09:50 UTC (coordinator periodic check)_

## Update 09:50 UTC 10-14
- **Spend**: capped spend is 192.5M of 230M (gateway healthy).
- **Unblinded (user decision, errata 36-37)**: results in analysis/out/unblind_20261014/. Headline: no suite or run where v2 beats a v1 arm that found something.
  - D: v2 = seed in all 12 searches, vs v1 HC about +0.12.
  - E: v2 HC-2 +0.100, about v1 pt (+0.130) and below v1 rulep (+0.247).
  - A: v2 window pending.
  - Only B HC vs HarnessLens holds at pipeline level.
- **v2 Suite A**:
  - HC-2 s2 ended about 09:03Z (finalize_skipped). The champions file is being built, then the A window (standing go, canary >= 0.6).
  - v2.1-AO2 A s0-s2 are at 267, 247 and 281 of 600 (ETA ~16-19Z).
- **Pending user decisions**: B/C transfer spend; the Overleaf branch.
- **Stalls/crashes**: none (ao21 s1's last event was 102 min ago, under the 3h rule).

_Earlier: 2026-10-14 06:50 UTC (coordinator periodic check)_

## Update 06:50 UTC 10-14
- **Spend**: capped spend is 192.1M of 230M (gateway healthy). The v2 optimizer cost so far is about $77 priced, across 26 searches.
- **Azure**: per the user, the key is less contended. The azoai mini concurrency was raised from 15 to 30, and Azure windows now start at 96 workers (3% 429 rule kept).
- **v1 final**: complete for all suites, and registered by hash (54e459510). Blind until the v2 freeze (errata 28).
- **v2 final windows**:
  - E: ended, 796 of 800 jobs.
  - D: ended, 1200 of 1200 jobs (all D champions = seed).
  - Both are registered, blind.
  - v2.1 D/E: all six champions = seed, so there is no window; they map to the seed-check (errata 33-34).
  - A: waits for the A champions file.
- **v2 searches**:
  - D and E have all ended (HC-2 x6, AO-2 x6, v2.1-AO2 x6).
  - A: HC-2 s2 is at 600/600 started, with cand_0009 in confirmation. v2.1-AO2 A s0-s2 are at 141, 151 and 171 of 600 (launched 03:51Z; slow, est. several more hours).
- **Search-time findings** (internal, not held-out):
  - AO-2 has accepted no candidate on any suite (v2.0 or v2.1).
  - HC-2 promoted on A (s0, s1) and E (s1, s2), and nothing on D.
  - A post-promotion top-up gap was found (errata 29).
- **Pending user decisions**: unblinding now or at the freeze; B/C transfer spend (~$285, or ~$140 / ~$95 cut); the Overleaf branch.
- **Stalls/crashes**: none.

_Earlier: 2026-10-14 03:50 UTC (coordinator periodic check)_

## Update 03:50 UTC 10-14
- **Spend**: capped spend is 189.4M of 230M (gateway healthy). The v2 windows stop at 228M.
- **v1 final**: ALL SUITES COMPLETE. E: 5,480 done and 70 missing (infra_final) of 5,550. Held-out scores stay blind until the v2 freeze (11D). The extras (B/C transfer first) are queued behind the v2 windows.
- **v2 searches**:

  | Suite | State |
  |---|---|
  | E | v2.0 frozen. v2.1-AO2: s0 ended on budget, s2 on plateau at 80%, s1 running. |
  | D | v2.0 frozen (AO-2 plateau at 42-46%, HC-2 ended). Next: champions file, D window, v2.1-AO2 D. |
  | A | AO-2 all ended (plateau at 41%). HC-2 s0 and s1 ended; s2 in round 3. v2.1-AO2 A is being prepared. |

- **v2 final windows**:
  - E: launched 02:28Z (800 jobs, order c101de7d), finishing now. Results are hashed before any analysis.
  - D: next.
  - A: after HC-2 s2.
  - The v2 E launch gate was canary round 8 at 0.6 (round 7 had five real zeros; errata 23).
- **Disclosures**: held-out aggregates were seen before registration (errata 24-26). No window means are shared before the v2 freeze.
- **Stalls/crashes**: none.

_Earlier: 2026-10-14 00:50 UTC (coordinator periodic check)_

## Update 00:50 UTC 10-14
- **Spend**: capped spend is 185.8M of 230M (gateway healthy, not blocked).
  - The v1 final window stops itself at 198M. The v2 final windows stop at 228M (erratum 20).
  - v1 E uses the Azure-direct gateway, which is not capped, so it adds nothing.
- **v1 final**: E is at 4,783/5,550 (00:26), ETA ~01:30 UTC.
  - E t infra_final is 8.0%. 429s are 1.3%, below the 3% rule.
- **v2**:

  | Arm | Suite | State |
  |---|---|---|
  | HC-2 and AO-2 | E | all six searches ended (AO-2 s0-s2: plateau at 41% of budget; HC-2: finalize_skipped). Next: the champions file, then v2.1-AO2 for E (erratum 14). |
  | HC-2 | A | s0-s2 at 362/600, waiting on slow task 56427's confirm rollouts under the registered 3 h hang rule |
  | AO-2 | A | s0 265, s1 322, s2 362 |
  | HC-2 | D | s0-s2 running |
  | AO-2 | D | s2 running; s0 and s1 still in the seed baseline for ~112 min (checking) |

- **Isolation**:
  - The P2 confirm-chunk means were logged to run events.jsonl (#847).
  - On D/E these were readable by the optimizer until the shim swaps: HC-2 at 23:20:15Z and AO-2 at 23:21:19Z.
  - There are 0 transcript reads across 12 runs.
  - On A the file was never readable, and it has been hardened.
  - Disclosed in errata 16-19.
- **Scorers**:
  - The v1 and v2 scorers are code-equivalent: A gives 40/40 identical results, and the D/E guard is inactive (errata 21 and 22).
  - The A drain-error fix is covered by #824.
- **Paper repo sync**:
  - It was blocked between 17:46 and 23:30 by a gate false positive and an uncommitted artifacts dir. It is now fixed and caught up.
  - Artifacts wave a is verified (20 assets, 2.49 GB). Wave b is starting.
  - The Overleaf branch overleaf-2026-10-13-1437 would delete the current paper. It is NOT merged, and the user has been asked.
- **Stalls**: A HC-2 (task 56427 tail, handled by the registered rule) and D AO-2 s0/s1 baseline (under check). No crashes.

_Earlier: 2026-10-13 21:50 UTC (coordinator periodic check)_

## Update 21:50 UTC
- **Spend**: capped spend is 183.3M of 230M; the v1 final window stops itself at 198M.
- **v1 final**: A, B, C and D COMPLETE. E is at about 2,660/5,550, ETA ~01:45 UTC.
  - Tools-edit arms carry infra_final through tau2's tool-consistency check (live vs pristine replay); this is registered as an analysis note (34ee6789a).
  - E t is at 9.6% infra_final; E t s0 is flagged above 15%.
  - The A/B/C optimizer-token list is final (de6230f07).
- **v2**: 13 searches running or done, all registered.

  | Arm | Suite | Launched | State |
  |---|---|---|---|
  | HC-2 | A | 16:13 | in first-round confirmation |
  | AO-2 | A | 18:34 | round 1 |
  | HC-2 | E | 17:13 | s1 and s2 done (budget_unfunded; champions cand_0010 and cand_0001, both P2 confirmation accepts); s0 running |
  | AO-2 | E | 21:14 | s0 and s1 running; s2 queued |
  | HC-2 | D | 18:37 | s0-s2 running |

  - AO-2 D is queued until the V2 cap lifts from 6 to 9 when the v1 E final window ends (erratum 10).
- **v2 final windows**: machinery built (research/fe-v2-window, not merged until E main ends).
  - A scores every cell with main's adapter a3f5eeb6d plus the campaign api.py (10800 s); errata 12 and 13.
  - GEPA anchor at budget parity (erratum 11).
  - Open item: the drain-error fix in the A staged jupyter.
  - The scorer equivalence check is running.
- **Stalls**: none.

_Last updated: 2026-10-13 18:50 UTC (coordinator periodic check)_

## Update 18:50 UTC
- **Spend**: capped spend is 179.5M of 230M; the v1 final window stops itself at 198M.
- **v1 final**:

  | Suite | State |
  |---|---|
  | A | COMPLETE (2520, 0 missing) |
  | C | COMPLETE (1018/1020; the END-only extra is done) |
  | D | COMPLETE (13,080 with 66 infra_final) |
  | B | 2102/2520 at 18:32, ~2.5 h left |
  | E | launched 18:11 (5,550 jobs, 64 workers), ~00:30 ETA |

  - Azure mini 429s are external peak-load shedding (30-47%): 0 429-attributed infra. Holds were adjusted (decisions.md).
  - Held-out scores are deliberately NOT computed yet, so v2 launch decisions stay blind (amendment 11D).
- **v2**: 12 of the 18 registered searches are running, all fully registered.

  | Arm | Suite | Launched |
  |---|---|---|
  | HC-2 | A | 16:13 |
  | AO-2 | A | 18:34 |
  | HC-2 | E | 17:13 |
  | HC-2 | D | 18:37 |

  - AO-2 D/E waits on the E re-smoke (started 18:40) and the partition-hash check.
  - Errata 6-8: D/E use one shared unstratified F/C partition per suite.
- **Artifacts**: release artifacts-2026-10-13a exists on the paper repo (wave a); verification and manifest are pending from repo-sync.
- **Stalls**: none.

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
