# Campaign status (plain language)

_Last updated: 2026-10-12 00:50 UTC — coordinator periodic check_

## Where things stand
- **Protocol frozen**: matched-checkpoint comparison (user decision), search cutoff **2026-10-13 06:00 UTC**, B* from rollout counters only; rule P for both CapEvolve arms (k_se 1, n_conf 3, z 1.282, dmin 0, coverage 0.95); Suite A final = seeded stratified sample from the 239-id SpreadsheetBench-912 residual pool; Suite B final = sealed retail test-40.
- **Suite A (rollouts of 600, s0/s1/s2 at 00:47)**:
  - GEPA 311/209/394, Meta-Harness 246/252/299, SkillOpt 233/311/266, Trace2Skill 200/200/198 (checking a possible phase pause).
  - CapEvolve hill-climb 134/164/133 (searching). Agent-optimize 120/120/120 (baseline done; optimizer sessions running).
  - EvoSkill 140/113/88, MIPROv2 74/73/79, ACE 29/64/33 (batch-mode restart).
  - **WikiSkill CRASHED at 120 on all seeds about 22:42** (missing runtime session.jsonl right after iteration 1; possibly caused by the 22:32 sandbox network change). The owner is fixing it.
  - E12A stock-gate 61/53/55.
- **Suite B (tau2 retail)**: HC, AO and GEPA running (GEPA 217/200/190). AO was resume-restarted onto the isolated shim at 22:40. HarnessLens relaunched 22:39 on the fully isolated launcher (98-101, baseline done).
- **Suite C (tau2 airline)**: HC, AO, GEPA (42/29/39) and controls running; exploratory E12C stock-gate hill-climb running; best-of-k control starts when the controls finish.
- **Throughput**: single Gemma deployment saturated; ≈12 rollouts/h per search → projected B* ≈ 300–450, below 600 (to be stated in the paper).
- **Spend** (00:47): non-RITS 34.5M of 100M (about 2.2M/h, so roughly 98M at the cutoff by linear projection; the 65M stop order is in decisions.md); proxy USD $100 of $1000.
- **Isolation round (21:30-23:00)**: every web channel is closed for all arms (proposer egress, sandbox containers on sb_internal from 22:32:24Z, and the gateway strips web tools). /tmp is masked, and final_set files are no longer world-readable. Transcript scans found no web access.
- **Integrity**: proposer isolation verified for Meta-Harness (container), EvoSkill (capopt mount-ns), Memento (no tools); split files no longer readable by other uids; leaked-credential scan of likely locations: 0 hits. Content filter on chain-of-thought output fields confirmed; only ACE affected (documented rename).
- **Code**: 8 reviewed PRs merged into the campaign branch (#779, #783, #786, #788, #790, #791, #792, #793); none to main.

- **Paper**: draft 3 (MLSys 2027 format, 10-page body, check passes, results mocked as \\pend). Two rounds of five independent reviews done and triaged; final round after real results. Concurrent work (Piao et al. 2609.39148) is positioned.
- **Protocol amendments before the cutoff**: fixed comparison families; native end-of-run secondary; interleaved final window plus drift check; equivalence (TOST ±0.10); promotion counts; B* over primary arms only; final sizes A 70x1, B 40x3, C 20x3.

## Uncertain
- B* on Suite A is bounded by the slowest Tier 1 arms (EvoSkill, ACE, MIPROv2); at current pace B* may land near the 200 floor.
- Whether Suite B relaunch completes in time.
