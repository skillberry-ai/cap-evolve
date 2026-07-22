# agent-optimize — rationale, and how honesty survives full autonomy

## Why a free-form agentic algorithm

The deterministic algorithms (hill-climb, gepa, skillopt) fix the *schedule* of the
search: which tasks each round reflects on, when the optimizer is called, how the parent
is selected. That is exactly right when rollouts are cheap and the schedule is known. It
is a poor fit when the best move is judgment: *this* failure cluster is worth a targeted
policy edit, *that* one is uncontrollable infra noise to ignore; a subset eval is enough to
kill a bad idea before paying for full val; the score goal is already met so stop now.

agent-optimize hands that judgment to the conversational agent. There is no fixed round
count and no delegated per-iteration optimizer subprocess — the agent decides what to edit,
what to evaluate, when, and when to stop, bounded by a free-text `stop_condition`.

## How honesty survives handing the agent the wheel

Full autonomy is only safe because the honesty guarantees are **not** the agent's to keep —
they live in `core/cap_evolve/{gate,rundir,splits,check}.py` and hold no matter what the
agent does:

- **Test is sealed by code.** The evaluate phase only accepts `--split train|val`; the test
  split is scored solely by the finalize phase, once, after which `RunDir.commit_test()`
  burns the seal and a second finalize raises `TestSealError`. The agent cannot peek at test
  mid-run even if it tries.
- **Acceptance is a code gate on val.** `gate.decide` applies Δ > k·SE; the agent's subset
  triage is advisory and never substitutes for it.
- **Edits are audited.** Every candidate is snapshotted in the git-backed store and every
  round is appended to `events.jsonl`, so the search is fully reconstructable.

So the "free" in free-form is freedom of *strategy*, not freedom to fake a result. The
headline number is still produced once, on data the search never saw.

## The constraint surface: free-text stop_condition + run-dir spend

Per the design, agent-optimize adds **no** new budget fields or status command. The agent
re-reads the project's free-text `stop_condition` and the already-tracked run-dir spend
(`RunDir.spent`: iterations, metric_calls, usd, optimizer_usd, tokens, seconds) every few
rounds and interprets them: score goal on full val, benchmark-eval cost, optimization cost,
and time all fit in one human-readable line the agent parses. This keeps the mechanism
zero-code and lets a single `stop_condition` express compound goals a fixed budget knob can't.

## Caveats

- With `train == val` the val gate is a *fit*, not a held-out check — only the sealed test
  number generalizes. Label val a fit metric in any report.
- At `num_trials: 1` on a stochastic benchmark, single-trial val means carry real variance;
  the paired k·SE gate curbs false accepts, but consider a re-eval before sealing if the
  score goal is only just met.

## Sources

- GEPA: reflective prompt evolution with a Pareto frontier (arXiv:2507.19457) — the
  deterministic sibling this loop's "read the feedback, propose one targeted edit" step echoes.
- cap-evolve honesty model: `docs/HONEST_EVAL.md`, `docs/ARCHITECTURE.md` (splits/gate/seal in core).
