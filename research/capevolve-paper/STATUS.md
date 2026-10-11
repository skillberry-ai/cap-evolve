# Campaign status (plain language)

_Last updated: 2026-10-11 21:50 UTC — coordinator periodic check_

## Where things stand
- **Protocol frozen**: matched-checkpoint comparison (user decision), search cutoff **2026-10-13 06:00 UTC**, B* from rollout counters only; rule P for both CapEvolve arms (k_se 1, n_conf 3, z 1.282, dmin 0, coverage 0.95); Suite A final = seeded stratified sample from the 239-id SpreadsheetBench-912 residual pool; Suite B final = sealed retail test-40.
- **Suite A (rollouts of 600, s0/s1/s2 at 21:47)**: GEPA 235/144/294, Meta-Harness 209/207/215, SkillOpt 170/221/202, Trace2Skill 145/160/175, WikiSkill 103/120/108, CapEvolve hill-climb 91/91/93 and agent-optimize 89/92/78 (still in the 120-rollout baseline; first decisions about 03:30-05:30), MIPROv2 50/45/55, EvoSkill 44/44/40, ACE 21/35/25 (switching to the official batch mode, K=4). New exploratory E12A stock-gate hill-climb 10/9/11. No stalls; Tier 2 is paused by design.
- **Suite B (tau2 retail)**: HC, AO and GEPA running (GEPA 185/163/166); HarnessLens trial e2e11 is running (idle watchdog plus a scrubbed sandbox) before the hand-over. Retail test-40 is sealed against scoring and selection, but its task files were filesystem-visible to optimizers (no access observed); closing that is in progress.
- **Suite C (tau2 airline)**: HC, AO, GEPA (42/29/39) and controls running; exploratory E12C stock-gate hill-climb running; best-of-k control starts when the controls finish.
- **Throughput**: single Gemma deployment saturated; ≈12 rollouts/h per search → projected B* ≈ 300–450, below 600 (to be stated in the paper).
- **Spend** (21:47): non-RITS 27.9M of the 100M cap; proxy USD $84 of $1000. A budget plan is in decisions.md: 15M reserved for final evaluation, exploratory arms stop first at 65M.
- **Integrity**: proposer isolation verified for Meta-Harness (container), EvoSkill (capopt mount-ns), Memento (no tools); split files no longer readable by other uids; leaked-credential scan of likely locations: 0 hits. Content filter on chain-of-thought output fields confirmed; only ACE affected (documented rename).
- **Code**: 8 reviewed PRs merged into the campaign branch (#779, #783, #786, #788, #790, #791, #792, #793); none to main.

- **Paper**: draft 3 (MLSys 2027 format, 10-page body, check passes, results mocked as \\pend). Two rounds of five independent reviews done and triaged; final round after real results. Concurrent work (Piao et al. 2609.39148) is positioned.
- **Protocol amendments before the cutoff**: fixed comparison families; native end-of-run secondary; interleaved final window plus drift check; equivalence (TOST ±0.10); promotion counts; B* over primary arms only; final sizes A 70x1, B 40x3, C 20x3.

## Uncertain
- B* on Suite A is bounded by the slowest Tier 1 arms (EvoSkill, ACE, MIPROv2); at current pace B* may land near the 200 floor.
- Whether Suite B relaunch completes in time.
