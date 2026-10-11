# Suite B (tau2 retail) design record, E10B

Pin: sierra-research/tau2-bench@8ebb7499622fc2be9b9d510d6f7a7653461f4f29 (tau3 task content). Target, user simulator and NL-assertion judge:
`rits/openai/gpt-oss-120b-a100` through the campaign gateway (temperature 0, max_tokens 8000, max_steps 100 as in the CapEvolve tau2 adapter). Optimizer / reflection: `aws/claude-sonnet-5-5`.

## Splits (protocol/tau_retail_splits.json, made by protocol/make_tau_retail_splits.py)
Official retail: train 74, test 40, base 114. Seed-42 shuffle of the sorted official train ids: opt 49, sel 25. Official TEST (40) is sealed: the adapter exposes only opt+sel ids and raises
`RuntimeError` for any sealed id in `run_batch` / `run_trials` (override env `TAU_ALLOW_SEALED_TEST=final-eval-only` exists solely for the final evaluation by the coordinator).
CapEvolve arms: train = val = opt (optimizer feedback + gate; train==val so the baseline does not re-evaluate it), test = sel (sealed from the optimizer, scored once by finalize).
GEPA: trainset = opt (reflection minibatches), valset = sel (selection). The same ids/roles, so no arm's optimizer sees sel traces.

## Editable surface and issue #563 decision
Issue #563: on tau2, `system-prompt` edits the domain POLICY, i.e. the benchmark's specification (the evaluator's gold actions follow it); letting the optimizer rewrite it is letting the candidate edit the exam.
Decision: the benchmark policy is IMMUTABLE. The editable system-prompt artifact is `policy/policy.md` = additional agent guidance, appended by the adapter after the verbatim tau2 retail policy
under a heading. The seed is `(none)`, which the adapter treats as empty, so the unoptimized seed is exactly stock tau2. This changes what the agent is told, not any rule the evaluator checks, and
no optimizer can soften or delete a benchmark rule. Cost: the optimizer cannot restructure the benchmark policy text itself (a restriction relative to the airline example).
Tools: `tools/tools.py` (copy of tau2 retail tools, `REMOVE_TOOLS`) is the agent-side wrapper. Evaluator isolation (closes the airline evaluator-coupling gap in benchmarks.md section 3): `Adapter.apply`
wraps `tau2.runner.simulation.evaluate_simulation` so the DB/replay check always gets the PRISTINE registry constructor; candidate tools only affect the agent's own environment.
Environment tools, DB, user simulator, reward are immutable. GEPA edits the policy addendum only (text component); CapEvolve arms may edit both. Disclosed asymmetry.

## NL-assertion judge
29/74 train tasks (opt 20, sel 9) and 11/40 test tasks have `nl_assertions`; tau2 grades them with an LLM judge (default gpt-4.1-2025-04-14, NOT available on the gateway: "team not allowed").
Judge used for every arm: `rits/openai/gpt-oss-120b-a100` at temperature 0 (tag role `judge`). This is a deviation from tau2 defaults and must be disclosed with every number.

## Rollout accounting (budget 600 target rollouts per search, all evaluations included)
Counted: every (task, trial) attempt of the target agent, including retries of exogenous failures (analysis_plan section 6: up to 3 retries on infra error classes; cost charged to the arm).
User-simulator and judge calls are part of a rollout. CapEvolve arms: num_trials=1, val=opt (49 tasks), max_metric_calls 550, finalize on sel (seed + best, 25 each) = about 600.
Rationale for 1 trial x 49 tasks over 2 trials x 25: at a fixed rollout budget more distinct tasks gives a smaller paired SE than repeated trials.
