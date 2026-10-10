# Objectives, cost gating, budget

`cost_gating` on (default): `promote` uses the `reward_gated` sequentially valid test vs the champion
(reward must not drop; cost/latency can win ties). Peeking repeatedly stays valid. Off: the plain paired
gate, NOT valid under repeated peeking:

```bash
python "$A/gate_check.py" --run-dir "$R" --candidate TAG --k-se 1.0
```

`objectives:` in capevolve.yaml use `gate_mode: epsilon_constraint` + `constraints`, or pareto (legacy loop
option; archived algorithm.md, "Pareto acceptance").
Budget: digest `budget` shows remaining USD and rollouts. Spending verbs refuse when EXHAUSTED unless
`--over-budget REASON`. `runner_spend_metered: false` means $0 is unmetered, not free: count rollouts.
Optimizer spend is metered from the session log by every verb; never hand-total it.
`stop_condition`: `spend.py` prints parsed predicates; ask the user if `constraints.ambiguous` is non-empty.
