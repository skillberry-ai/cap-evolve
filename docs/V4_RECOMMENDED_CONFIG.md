# V4 recommended config (rerun)

Every V4 feature is off by default. Add this block to `capevolve.yaml` to turn them on. See `COST_AWARE_SEARCH.md` for the design.

## Stock hill-climb (paired gate, `algorithm_skill: hill-climb`)

```yaml
max_metric_calls: 3000        # the rollout budget R; leave max_iterations OUT so the budget decides
# max_iterations:             # (omitted) effectively unlimited; an explicit value still wins, 0 = zero iterations
cost_lambda: 0.5              # a marginal win that costs much more is rejected; a clear win (z >= 3) never is
cost_accept: true             # reward non-inferior and >= 15% cheaper is an accept (lands the compress edits)
cost_metric: tokens           # prompt + completion tokens per rollout, from the candidate's own rollouts
hc_compress_every: 4          # every 4th iteration asks for a compress/refactor edit of the champion
```

## HC-2 (P2 rounds, `hc2: true`)

```yaml
max_metric_calls: 3000
cost_lambda: 0.5
cost_accept: true
hc2_compress_every: 3         # every 3rd round one slot compresses the incumbent
p2_reuse_control: true        # reuse the unchanged incumbent's control draws from earlier rounds
p2_extend_z: 1.0              # a near-miss confirmation gets one more block of fresh C draws (stricter pooled bar)
# hc2_plateau_rounds: 0       # keep off: only the budget ends the search
```

## Agent-optimize (conductor)

```yaml
max_metric_calls: 3000
ao_compress_every: 8
cost_lambda: 0.5
cost_accept: true
p2_extend_z: 1.0
p2_reuse_control: true
```

The skills/scripts/determinism guidance in the proposer prompts needs no key: it is always on for hill-climb, HC-2 and agent-optimize.
The last round shrinks automatically (HC-2). Set `cost_accept: false` if the compress cadence should not also accept
any 15%-cheaper cluster candidate.
