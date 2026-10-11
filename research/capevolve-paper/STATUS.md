# Campaign status (plain language)

_Last updated: 2026-10-11 16:20 UTC — coordinator periodic check_

## Where things stand
- **Protocol frozen**: matched-checkpoint comparison (user decision), search cutoff **2026-10-13 06:00 UTC**, B* from rollout counters only; rule P for both CapEvolve arms (k_se 1, n_conf 3, z 1.282, dmin 0, coverage 0.95); Suite A final = seeded stratified sample from the 239-id SpreadsheetBench-912 residual pool; Suite B final = sealed retail test-40.
- **Suite A running (Tier 1, 3 seeds each)** — rollouts done (of 600): GEPA 89/64/126, SkillOpt 80/80/80, Meta-Harness 78/71/67, EvoSkill 24/24/25, Trace2Skill 72/75/79, WikiSkill(community) 31/27/29, ACE 9/4/7, MIPROv2 11/6/10, CapEvolve hill-climb 13/10/10 and agent-optimize 12/14/12 (main seeds launched 14:42; AO now on the digest/act engine with rule P).
- **Suite B**: v2 relaunched 12:44 with judge GPT-5.5, rule P parity, candidate-error tagging, candidates.jsonl (v1 superseded, unused).
- **Throughput**: single Gemma deployment saturated; ≈12 rollouts/h per search → projected B* ≈ 300–450, below 600 (to be stated in the paper).
- **Spend**: 308.7M tokens total; 299.0M RITS (uncapped); 9.7M non-RITS of the 100M cap; proxy priced USD $30.16 of $1000.
- **Integrity**: proposer isolation verified for Meta-Harness (container), EvoSkill (capopt mount-ns), Memento (no tools); split files no longer readable by other uids; leaked-credential scan of likely locations: 0 hits. Content filter on chain-of-thought output fields confirmed; only ACE affected (documented rename).
- **Code**: 8 reviewed PRs merged into the campaign branch (#779, #783, #786, #788, #790, #791, #792, #793); none to main.

## Uncertain
- Whether CapEvolve main seeds start soon enough to reach B*.
- Whether Suite B relaunch completes in time.
