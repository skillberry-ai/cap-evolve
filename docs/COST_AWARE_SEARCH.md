# Cost-aware, budget-driven search

Three opt-in behaviours of the P2 evaluator (hill-climb HC-2 and agent-optimize), added after a campaign in which a
reward-only hill-climb tripled its prompt and tool size (per-rollout agent cost 0.010 USD to 0.027 USD, input tokens 47k to
155k) and stopped at an iteration cap with a third of its rollout budget unspent. Everything below is off, or equal to the
previous behaviour, unless a key is set.

## 1. Cost-aware acceptance

Keys: `cost_lambda` (0 = off), `cost_accept` (false), `cost_metric` (`tokens` | `usd`), `cost_clear_z` (3.0), `cost_margin`
(0.03), `cost_min_saving` (0.15), `cost_noninf_z` (1.0), `cost_min_n` (10). Code: `core/cap_evolve/costaware.py`.

The cost of a candidate is measured from its own rollouts (prompt plus completion tokens per rollout; USD when the adapter
reports no tokens) and compared with the incumbent's cost on the same tasks: `rel = cand / incumbent - 1`. A side with fewer
than `cost_min_n` priced rollouts gives no cost verdict, and the reward verdict stands.

Design goals: a clear reward win is never rejected, and a smaller artifact is never penalised.

* **Reward path.** A candidate that passes the reward test is rejected only if `mean - lambda x max(rel, 0) < dmin` and
  `z < cost_clear_z`. So the term only ever acts on a marginal win (a tie-break), and a candidate at `z >= cost_clear_z` is
  accepted whatever it costs.
* **Cost path** (`cost_accept: true`). A candidate that fails the reward test is accepted when its reward is non-inferior
  (`mean - cost_noninf_z x se >= -cost_margin`) and `rel <= -cost_min_saving`. This is how a compress edit lands.
* **Ranking.** Among several accepted candidates of a round the champion maximises `mean - lambda x rel`.

It applies to the P2 confirmation (`Round.close_confirm`), the group-sequential test (`Round.sequential`) and the HC-2 cheap
accept. At the rungs, with `cost_accept` on, a clearly cheaper candidate with a non-inferior screen mean is kept alive for the
confirmation instead of being killed for a non-positive mean.

The decision is recorded: a confirmation verdict carries `rel_cost` and `path`, and the verdict reason names the relative cost.
The C-stratum numbers stay in the private ledger, as before.

## 2. Compress / refactor operator

`hc2_compress_every: N` (HC-2) makes one slot of every N-th round a COMPRESS proposal from the incumbent; `ao_compress_every: N`
(agent-optimize) makes slot 0 compress the champion once every N proposals, at most once per champion, never the untouched seed.
The proposer is told to merge duplicate rules, delete rules no trace supports, replace long prose by a checklist or a script,
and shorten tool output, with no new behaviour (`core/cap_evolve/proposer_guidance.py`, `COMPRESS_NOTE`). The result goes
through the same gate as any edit; configuring the operator turns the cost path on unless `cost_accept: false` is set.

## 3. Budget-driven search

* `max_iterations` is no longer a hidden second budget. If `max_metric_calls` is set and `max_iterations` is left
  out, the cap is effectively none, and the loop proposes until the budget binds (it also stops after 5 consecutive rounds that
  evaluate nothing). An explicit `max_iterations` still wins (`0` = zero iterations, as before), and so does `hc2_max_rounds`.
* The last round shrinks. When not even one candidate with its rungs fits, HC-2 runs one direct round (no rungs, the control plus
  a confirmation) if that fits, instead of stopping.
* The only plateau stop is explicit and off by default: `hc2_plateau_rounds: N` stops after N rounds without a champion change.
  Agent-optimize keeps `ao_plateau_n`.
* `p2_reuse_control: true` reuses the control draws that an earlier round measured for the same, unchanged incumbent, so a
  round pays only the shortfall. `p2_extend_z: z` gives a near-miss confirmation (`0 < mean`, `z` between `p2_extend_z` and
  `p2_z_conf`) one more block of fresh C draws, pooled with the first and judged at `p2_z_conf + p2_extend_margin`, rather than
  rejecting it and throwing the rollouts away.

## 4. Proposer guidance

Every proposer prompt (hill-climb, HC-2 and agent-optimize) lists three kinds of improvement: code (an executable script or code
snippet inside a skill, with a clear entry point, a usage line and loud failures), determinism (a checklist, a verification
command, a reusable helper the agent must run), and text. It also tells the proposer that every added line is re-read on every
rollout, so redundant text should go.

Note: configuring a compress operator turns the cost path on for every candidate, so any cluster candidate that is at least 15% cheaper with non-inferior reward can also be accepted. Set `cost_accept: false` to prevent that.
