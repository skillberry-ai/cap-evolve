# PROCESS — what I did this iteration (explainability; REQUIRED)

## How I got a real diagnosis (the trajectories/ files are empty)

`trajectories/*.json` carry `rollout.trace = None` and `tool_calls = []` — no
transcript. The real per-trial data is reachable via
`rollout.metadata.trial_dir`, which points at the harbor job dir. Under each
`<trial_dir>/<ts>/bench-*/` there is `agent/agent.jsonl` (full tool calls +
final answer) and, decisively, `verifier/reward-detail.json` — which names the
**exact rubric items missed, with the verifier's own rationale**. I read all 20
scored trials' reward-detail files rather than guessing from the 0.84 mean.
Future iterations: start there, it converts this task from "read a transcript
and infer" into "read the scoring key".

The rubric has 7 required items, 1 forbidden item, weights
`tool_calls 0.3 / answer 0.7`. `tool_calls` scored 1.0 in **every** trial — the
three expected calls are always made. **All lost reward is in `answer`**, so
nothing in the routing or tool-selection layer needs touching. `orchestrator.md`
is correctly out of scope (task.toml `services=["cost"]` → footprint is
`orchestrator.md` + `shared_context.md` + `cost_agent.md`).

## Ranked issue list (clusters by # failing trials, biggest first)
Frequency is over the 20 scored trials found under the trial dirs.

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **Fabricated cross-window ratio** — misses `share-not-meaningful` (9/20) and trips forbidden `naive-share` (7/20) | cost-418 | User asks for A as a % of B. The two sources return **different periods**. The agent will not return empty-handed: it either divides the mismatched figures outright, or (more often) annualizes/pro-rates the short window to a run-rate and quotes *that* percentage behind `[confidence: medium]`. It never considers that the honest move is to decline the figure. | BEHAVIORAL | Decision rule + worked example in `cost_agent.md`; narrow the confidence-marker rule in `shared_context.md` that was *licensing* this |
| 2 | **Computed the covered window instead of reading it** — misses `window-start` (1/20) | cost-418 | Result carries `period.start`. The agent instead subtracted its requested lookback from "now", concluded a window starting a different day, and asserted that as fact — never reading the returned field. Arithmetic was right; the premise (that the request determines coverage) was wrong. | BEHAVIORAL | "Read, don't compute, returned scope" rule in `cost_agent.md` + a general metadata-grounding rule in `shared_context.md` |
| 3 | **Read a placeholder `0` roll-up as a measurement** — misses `overall-utilization` (1/20) | cost-418 | Each metric preset populates only its own roll-ups; the other preset's roll-up comes back `0`. The agent sourced a headline figure from the preset that returns `0` for it instead of the preset that computes it. | KNOWLEDGE | Preset-roll-up semantics rule in `cost_agent.md` |

Note on flakiness: rank-1 is the whole story of the 0.84 plateau. The 2 trials
that scored 0.9125 are exactly the ones that *declined* the ratio. The good
behavior already exists in the policy's output distribution — this iteration is
about making it the default rather than the coin-flip.

## Changes made this iteration

| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BEHAVIORAL / decision rule + worked example | `cost_agent.md` → new `### Never compute a ratio across two different windows` | "Before dividing, compare the two returned periods; if they differ, report both figures with their own windows and state the share cannot be computed — and do **not** extrapolate/annualize/pro-rate to manufacture one." Includes a worked example (a quarter-length review vs a partial capacity window) showing two WRONG moves and the RIGHT phrasing. Closes the escape hatch the traces actually used (run-rate + confidence marker), not just naive division. Extended to totals/deltas/"X vs Y", so any mismatched-period comparison benefits. | Yes — only fires when two returned periods **differ**. Matched-period ratios (the normal case) are untouched. |
| 1 | BEHAVIORAL / narrow an over-broad rule | `shared_context.md` → `## Confidence Markers` | Added "a marker is not a licence to invent the number": a marker downgrades a *conclusion you may draw*, it does not authorise supplying a figure the data's **coverage** can't support. Distinguishes gaps in *interpretation* (mark-and-estimate is right) from gaps in *coverage of the requested measurement* (decline). This rule was the direct enabler — the seed text's "Medium = you are extrapolating from partial data … one data source was unavailable but you can still provide a useful answer" reads as explicit permission for exactly the forbidden behavior. | Yes — narrowing, not loosening. The medium-confidence examples the rule was written for (inferring sandbox ownership from timestamps) are named as still-correct. |
| 2 | BEHAVIORAL / grounding rule | `cost_agent.md` → new `### The window you ASKED for is not the window you GOT` | "The requested range is a request; the returned `period` is the fact." Read it off the result, never derive it from the lookback you sent; quote it verbatim when it differs; name which part of the user's span is uncovered; label every figure with its real window. | Yes — additive; when requested and returned windows agree there is nothing to report differently. |
| 2 | BEHAVIORAL / grounding rule (domain-general) | `shared_context.md` → `## Grounding` | "Result metadata is data too — read it, don't recompute it": period covered, row counts, `truncated`, freshness, applied filters all come from the result, never from the parameters sent. Placed in shared_context because every domain has tools whose returned scope can differ from the requested scope (truncation, retention, clamping) — genuinely domain-general, which is the bar for this file. | Yes — restates grounding the file already demands, extended from values to scope metadata. |
| 3 | KNOWLEDGE | `cost_agent.md` → `## AWS Capacity Manager (ODCRs)` | Preset roll-ups are populated only by the preset that computes them; a `0` from another preset is an unpopulated placeholder, not a measured zero. Take each headline figure from the preset that computes it; if a needed roll-up is `0` but per-dimension rows carry the values, sum the rows and say so. | Yes — tells the agent where to source a figure; adds no new tool call. |

## Verify-the-fix (traced to the exact point of failure)

- **Cluster 1, seed-0 / seeds 2,3,5,6,7,8,9.** At the point of failure the agent
  had both periods in context and wrote a run-rate percentage. Seed-4 trial-1:
  "$7,339.70 over ~16 days implies ~$13,800/month … projects to ~9.2% of EC2
  spend [confidence: medium]". Seed-0: "would be in the range of ~4–5%
  [confidence: medium | October ODCR data unavailable … extrapolated from
  November pattern]". Both cite the old `shared_context.md` medium-confidence
  licence almost verbatim. The new rule forbids this exact construction by name
  (extrapolate/annualize/pro-rate), states a marker does not make it acceptable
  here, and supplies the replacement sentence. The passing seeds (1,4 trial-2)
  already produce that replacement sentence unprompted — this makes it the
  instructed default. **Would have changed behavior at the failing step: yes.**
- **Cluster 2, seed-0.** The result said `period.start = <mid-November>`; the
  agent wrote "the API capped the lookback at 1,464 hours, which from the
  current time reaches back to **<start-of-November>** … covers only November,
  not October" — a start date it computed, contradicting the field it had. The
  new rule ("never derive the covered span by subtracting your requested
  lookback from the current time; quote the returned `period.start` verbatim")
  targets precisely this substitution. **Yes.**
- **Cluster 3, seed-0 trial-2.** The agent needed overall utilization and the
  `unused_cost` roll-up carried `overall_utilization_pct: 0`. A passing trial
  (seed-1) reasoned it out explicitly: "that field is a placeholder in this
  preset, not a measurement". The new rule states this as policy rather than
  leaving it to be re-derived per trial. **Yes.**

Cross-check for harm: the 2 highest-scoring trials were re-read against all
five edits. Every edit either instructs what they already did (clusters 1,3) or
is inert for them (cluster 2 — they quoted the returned window correctly).

## Process & features used
- **Serial, not fanned out.** The run-brief suggests one subagent per
  trajectory-group, but all 10 trials are the *same task* and all failures
  reduce to 3 mechanisms in 2 files, both of which I had to edit coherently
  (the `cost_agent.md` ratio rule and the `shared_context.md` confidence-marker
  narrowing are two halves of one fix — split across worktrees they would have
  conflicted in intent, not in text). Fan-out would have added merge risk for
  no coverage gain. The leverage this iteration was in **finding
  reward-detail.json**, not in parallelism.
- **Prior iterations read:** none exist (iteration 1/5; `RUNMAP.md`,
  `LEDGER.md`, `rejected.jsonl`, `history.jsonl` all empty of rows). Nothing to
  build on or avoid re-proposing.

## Good things to PRESERVE (do not let a future iteration undo these)
- **`reward-detail.json` under `rollout.metadata.trial_dir` is the ground
  truth.** Do not diagnose this task from `trajectories/*.json` — they are
  trace-less. Read the rubric's `required_missed` / `forbidden_hit` per trial.
- **`tool_calls` is already 1.0 on every trial.** Do not spend an iteration on
  routing, tool choice, or call ordering — there is no reward there. The full
  0.7 answer weight is the only surface.
- **The decline-the-figure behavior is the scoring behavior.** The rubric
  rewards `share-not-meaningful` and *forbids* the naive share. Any future edit
  that nudges the agent toward "be helpful, give them a number" will regress
  this task. Honesty about coverage is the objective here, not completeness.
- The `shared_context.md` confidence-marker section should stay **narrowed**.
  Reverting it to the seed's unqualified "extrapolating from partial data →
  medium" re-opens cluster 1.

## Deliberately skipped
- **`orchestrator.md`** — `services=["cost"]`, routing is correct in all 20
  trials, `tool_calls` scores 1.0. No signal.
- **Other 5 domain agents** — not in this task's prompt footprint.
- **Tool/code-level fixes** — out of scope this phase (no tools layer). See
  escalation below.

## Escalation (needs code, cannot be fixed by prose)
`query_aws_capacity_manager` **silently clamps** the requested window and
surfaces the truth only in `period`. Every trial burned reasoning on
reverse-engineering why (three different wrong explanations appeared across
trials: a 61-day API cap, a 90-day cap, data-retention limits — all invented).
A tool-layer fix would return an explicit
`requested_period` / `effective_period` pair plus a `window_clamped: true`
flag, so the discrepancy is stated rather than inferred. Likewise the preset
roll-up `0` placeholders (cluster 3) should be `null` or absent, not `0` — `0`
is indistinguishable from a real measurement and is a standing trap for any
model. Both are real defects in the tool contract; the prose rules added here
are mitigation, not a cure.

---

# DIAGNOSIS.json

See `DIAGNOSIS.json` alongside this file.
