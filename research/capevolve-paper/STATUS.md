# Campaign status (plain language)

_Last updated: 2026-10-12 08:25 UTC — coordinator periodic check_

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
