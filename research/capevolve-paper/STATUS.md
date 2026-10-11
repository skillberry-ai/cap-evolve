# Campaign status (plain language)

_Last updated: 2026-10-11 13:00 UTC — coordinator periodic check_

## Where things stand
- **Protocol frozen**: matched-checkpoint comparison (user decision), search cutoff **2026-10-13 06:00 UTC**, B* from rollout counters only; rule P for both CapEvolve arms (k_se 1, n_conf 3, z 1.282, dmin 0, coverage 0.95); Suite A final = seeded stratified sample from the 239-id SpreadsheetBench-912 residual pool; Suite B final = sealed retail test-40.
- **Suite A running (Tier 1, 3 seeds each)** — rollouts done of 600: GEPA 43/46/63, SkillOpt 56/59/57, Meta-Harness 28/25/25, EvoSkill 22/36/20, Trace2Skill 38/41/46 (native budget ~200), ACE 5/3/6, MIPROv2 10/2/10. **CapEvolve hill-climb / agent-optimize: pilots only; main seeds not yet launched (chased).** WikiSkill (community port): smoke.
- **Suite B**: v2 relaunched 12:44 with judge GPT-5.5, rule P parity, candidate-error tagging, candidates.jsonl (v1 superseded, unused).
- **Throughput**: single Gemma deployment saturated; ≈12 rollouts/h per search → projected B* ≈ 300–450, below 600 (to be stated in the paper).
- **Spend**: 164.7M tokens total; 160.2M RITS (uncapped); 4.5M non-RITS of the 100M cap; proxy priced USD $12.81 of $1000.
- **Integrity**: proposer isolation verified for Meta-Harness (container), EvoSkill (capopt mount-ns), Memento (no tools); split files no longer readable by other uids; leaked-credential scan of likely locations: 0 hits. Content filter on chain-of-thought output fields confirmed; only ACE affected (documented rename).
- **Code**: 8 reviewed PRs merged into the campaign branch (#779, #783, #786, #788, #790, #791, #792, #793); none to main.

## Uncertain
- Whether CapEvolve main seeds start soon enough to reach B*.
- Whether Suite B relaunch completes in time.
