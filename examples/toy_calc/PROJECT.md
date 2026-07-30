# cap-evolve project — toy_calc arithmetic stand-in

A **filled** version of `templates/project/PROJECT.md`. The template ships as a blank
form; this is what one looks like after `intake` has actually interviewed someone, so
you can see the shape of a real answer instead of a `<placeholder>`. Copy the
**template** to start your own.

Records the decisions behind this run so anyone (human or agent) can reproduce it.

## What we're optimizing
- Capability: `system-prompt`
- Artifact: `capability/prompt.txt` (copied to `<workdir>/seed_capability/` by `run.sh`)
- Allowed edits: `[edit]` — rewrite the prompt text. No adding or deleting files; the
  stand-in only ever reads `prompt.txt`.

## How we run the target (the RUNNER)
- Agent under test: a **deterministic Python stand-in**, not a model. It lives in
  `adapter.py::Adapter.run_target` and computes the arithmetic correctly **only** when
  the candidate prompt contains the marker `[CALC]`; otherwise it emits
  `"I think <expr> is roughly some number."` and fails the exact-match scorer.
- How `run_target` invokes it: reads `ctx/prompt.txt` (where `ctx` is the candidate dir
  yielded by the default `live()`), branches on `"[CALC]" in prompt`, and returns a
  `Rollout`. `seed` is accepted per the contract and unused — this runner is exact.
- Why a stand-in: it makes the whole pipeline provable at **zero API cost** and with
  byte-identical reruns, which is what lets this example be the CI gate. It buys
  determinism, not realism — see *Honest limits*.

## How we score
- Metric: exact string match against `task.target`, reward `1.0` or `0.0`.
- Feedback signal: on failure, `score()` reports what was expected vs produced **plus
  the hypothesis** that "the prompt likely lacks an explicit instruction to compute and
  output only the number". That sentence is the learning signal the optimizer acts on —
  it names the *cause*, not just the miss. It does not leak the gold answer beyond the
  expected value the optimizer would see in the trace anyway.
- Secondary metrics: none (`metrics_display: []`). The gate reads only the primary
  scalar reward regardless.

## Data
- Source: `adapter` — the adapter's own `tasks()` reads `tasks.jsonl` (8 arithmetic
  tasks) from `CAPEVOLVE_TOY_DATA`. `dataset_source: adapter` means the harness does not
  load a file itself; `tasks()` is the single source.
- Split: train 4 / val 2 / test 2, seed `0`, frozen once into `<run>/splits.json`. Test
  is sealed and scored exactly once at finalize — a second `finalize` raises
  `TestSealError`.
- `tasks(split)` deliberately returns **all** tasks and lets the harness filter by the
  frozen split. That is the supported shape; the split is the harness's job, not the
  adapter's.

## Optimizer + algorithm
- Optimizer (proposer): `mock` — applies `mock_script.json` verbatim
  (`ensure_contains` the `[CALC]` line). Deterministic, zero API calls.
- Algorithm: `hill-climb --focus all`
- Budget: `max_iterations: 5`, `stall: 2`. The winning edit lands on iteration 1; the
  next two are no-ops the gate rejects, so `stall` ends the run after **3** iterations.

## Inputs status
- NEEDED inputs resolved: capability + artifact path, runner (the stand-in), scorer,
  dataset, splits, optimizer, algorithm, budget.
- RECOMMENDED inputs skipped: `target_model` (there is no consuming LLM — the "agent"
  is Python, so there is no reader tier to tune edits for); `runner_repo_path` and
  `capability_sources` (the runner is 20 lines inside the adapter, nothing to surface);
  `metrics_display` (one metric).

## Honest limits — what this example does NOT prove

Worth more than the parts that work, because these are the claims people over-read.

1. **The significance gate never does real work here.** `gate_mode: paired`,
   `gate_k_se: 1.0` are set, but both val tasks move `0 → 1` *together*, so the spread
   of the per-task deltas is zero, `SE(Δ) = 0`, and the gate logs a `gate_warning` and
   applies its documented **STRICT fallback** (accept any `Δ > 0`). The run transcript
   says exactly that: `paired Δ̄=+1.0000 > 0 (SE=0 → STRICT fallback, warned; n=2)`.
   A deterministic scorer has no noise to reject.
2. **`k_se = 1.0` is stricter than it looks.** Improving exactly ONE of `n` val tasks
   gives `mean(Δ) = SE(Δ)` *exactly*, so the strict `>` **rejects** it — at every `n`,
   and no matter how large that single gain is. **Improve ≥ 2 tasks at `k_se = 1.0`, or
   bank nothing.** Set `gate_k_se: 0.2` (as the other examples do) to bank a 1-of-`n`
   gain.
3. **val = 2 is the floor, not a recommendation.** It equals the harness's
   `MIN_VAL_TASKS = 2`; a smaller val split is *refused*, and 2 is still under the
   low-confidence threshold. A real benchmark wants tens of val tasks.
4. **`cap-evolve check` passing is not proof the adapter is correct.** It proves the
   three abstract methods are implemented and non-stubbed, `tasks()` is non-empty and
   stable, `score()` is deterministic, and `materialize()` is callable. It does not run
   `run_target`, so a non-deterministic runner passes `check`. Notably a `materialize()`
   that *raises* can still yield `{"ok": true}`.
5. **The improvement is engineered.** The stand-in is written so `[CALC]` is the one
   thing that matters and `mock` is scripted to add it. `0.0 → 1.0` proves the loop
   plumbing, gate wiring, and seal — not that optimization works on a real benchmark.
   For that, see `examples/tau2_airline/` and `examples/skillsbench/`.

## Where the pieces live
| File | Role |
|---|---|
| [`adapter.py`](adapter.py) | the `CapabilityAdapter`: 3 required methods + one hook override |
| [`capevolve.yaml`](capevolve.yaml) | the filled run spec, with a note per choice |
| [`capability/prompt.txt`](capability/prompt.txt) | the seed artifact (no `[CALC]`) |
| [`tasks.jsonl`](tasks.jsonl) | 8 arithmetic tasks |
| [`mock_script.json`](mock_script.json) | the deterministic edit `mock` applies |
| [`run.sh`](run.sh) | the whole thing end to end, zero API |
