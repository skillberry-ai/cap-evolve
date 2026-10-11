# Campaign status (plain language)

_Last updated: 2026-10-11 19:16 UTC — coordinator periodic check_

## Where things stand
- **Protocol frozen**: matched-checkpoint comparison (user decision), search cutoff **2026-10-13 06:00 UTC**, B* from rollout counters only; rule P for both CapEvolve arms (k_se 1, n_conf 3, z 1.282, dmin 0, coverage 0.95); Suite A final = seeded stratified sample from the 239-id SpreadsheetBench-912 residual pool; Suite B final = sealed retail test-40.
- **Suite A running (Tier 1, 3 seeds each)** — rollouts done (of 600) at 19:10: GEPA 154/117/213, SkillOpt 127/129/155, Meta-Harness 141/120/120, Trace2Skill 113/113/117, WikiSkill(community) 65/82/68, CapEvolve hill-climb 59/51/58, agent-optimize 54/53/44, MIPROv2 23/20/23, ACE 16/9/18, EvoSkill 17/16/14 (EvoSkill restarted 18:28 after a coordinator error left it on the low-priority gateway list, 13:05–18:40; pre-18:28 EvoSkill data invalid, see decisions.md). All counters advanced within the last ~40 min (no stalls).
- **Suite B (tau2 retail)**: v2 (12:44) running; counted rollouts HC 147/147/98, AO 123/123/74, GEPA 145/126/145; one-shot controls finished and are being scored on sel. HarnessLens hand-over pending (trial run in progress).
- **Suite C (tau2 airline, user order)**: running since ~18:00; HC/AO/one-shot controls in first baseline evals (0 counted), GEPA 10.
- **Throughput**: single Gemma deployment saturated; ≈12 rollouts/h per search → projected B* ≈ 300–450, below 600 (to be stated in the paper).
- **Spend** (19:08): 517.5M tokens total; 502.4M RITS (uncapped); 15.2M non-RITS of the 100M cap; proxy priced USD $47.18 of $1000 (incl. $7.9 restart waste, reported separately).
- **Integrity**: proposer isolation verified for Meta-Harness (container), EvoSkill (capopt mount-ns), Memento (no tools); split files no longer readable by other uids; leaked-credential scan of likely locations: 0 hits. Content filter on chain-of-thought output fields confirmed; only ACE affected (documented rename).
- **Code**: 8 reviewed PRs merged into the campaign branch (#779, #783, #786, #788, #790, #791, #792, #793); none to main.

## Uncertain
- B* on Suite A is bounded by the slowest Tier 1 arms (EvoSkill, ACE, MIPROv2); at current pace B* may land near the 200 floor.
- Whether Suite B relaunch completes in time.
