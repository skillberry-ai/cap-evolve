# tau2-airline — v2 pipeline end-to-end run (autonomous)

Evidence that the **v2 pipeline runs end-to-end with zero intervention**:
`cap-evolve check → baseline → hill-climb (ibm-bob) → finalize → report → dashboard`,
agent **and** user simulator = `watsonx/openai/gpt-oss-120b` via IBM RITS.

## Config
- Honest **holdout** split (better than the prior no-holdout fit): 12 train / 6 val / 6 test (`split_ids.json`).
- Capabilities: `[system-prompt, tools]` (policy.md + tools.py). Optimizer: **ibm-bob**.
- Algorithm: `hill-climb --focus all`; `num_trials 2`; `max_iterations 6`; `stall 3`; tau `max_concurrency 7`.
- Gate: **paired** significance (auto-selected; candidate & current share val tasks), `k_se 1.0`.

## Result (honest)
- Baseline val **0.583**. cand_0001 0.667 (Δ +0.083), cand_0002 0.500, cand_0003 0.333 — all **rejected**
  by the paired gate (the +0.083 gain was within 1·SE on a 6-task val, i.e. not significant).
- Stall-stopped after 3 rejects; **best = seed**; **sealed test = 0.417** (scored once; pass^1 0.417, pass^2 0.167).
- This truthfully exercises every step. On a 6-task val with a 1·SE paired gate the search is deliberately
  strict, and bob's edits did not yield a *significant* gain. To demonstrate an accepted improvement, scale val
  (more tasks/trials) or use the sample-efficient `gepa` / `skillopt` algorithms — the pipeline is identical.

## Artifacts
- `dashboard.html` — self-contained (no CDN, secrets redacted): KPI strip, cumulative-best stair, tasks×iterations
  heatmap, per-iteration diff, lineage tree, optimizer-vs-runner cost/tokens/latency, annotations.
- `report.md`, `events.jsonl`, `split_ids.json`.
