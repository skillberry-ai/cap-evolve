# Adding a benchmark

Every benchmark gets its own directory under `benchmarks/<name>/`, built from one or
both of:

- **`template/`** — a minimal, copy-and-run adapter: config, not code. Point it at
  your data/credentials with env vars and run. This is what most benchmarks should
  ship, including yours if the adapter is otherwise generic.
- **`examples/<variant>/`** — a full worked run against the real benchmark: its own
  `setup.sh` (onboard the benchmark + dependencies) and `run.sh` (run the loop), plus
  whatever supporting scripts/tests the benchmark needs. Use this when the benchmark
  needs real infrastructure (Docker, an external service, a non-trivial dataset
  fetch) that a bare template can't express, or when you want a committed, reviewable
  reference run.

A benchmark may have a `template/` only (the common adapter-template case), an
`examples/` only (a worked integration that doesn't generalize into a template), or
both (e.g. `tau2/` ships a generic `template/` plus two real `examples/` variants).

## Steps

1. **Pick the shape.** Does a generic template (`generic/jsonl_litellm`,
   `generic/huggingface_litellm`, `generic/harbor`) already cover your task format and
   scoring mode? If so, you may not need a new benchmark directory at all — just use
   env vars. Only add a new `benchmarks/<name>/` when the task source, scoring, or
   agent harness is genuinely custom.

2. **Implement the adapter.** Subclass `CapabilityAdapter`
   (`core/cap_evolve/adapter.py`) and implement the three required methods —
   `tasks(split)`, `run_target(task, ctx, *, seed)`, `score(task, rollout)`. The full
   contract is in [`docs/ADAPTER_CONTRACT.md`](../docs/ADAPTER_CONTRACT.md). Start from
   [`_scaffold/project/adapters/adapter.py`](_scaffold/project/adapters/adapter.py).

3. **Lay out the directory:**
   ```
   benchmarks/<name>/
     template/                  # if genuinely copy-and-run
       adapter.py
       capevolve.yaml
       seed_capability/
     examples/<variant>/        # if a worked run is warranted
       adapters/adapter.py
       seed_capability/
       setup.sh  run.sh  smoke.sh
       capevolve.yaml
       README.md
       tests/
   ```
   Use `model_config.py` (`../../_shared/model_config.py` from a `template/`) for
   provider-agnostic model wiring instead of hand-rolling credential handling.

4. **Verify with `cap-evolve check`** — must print `{"ok": true}` before anything
   else. This is the adapter-contract gate (determinism, no stub methods, no leaked
   gold answers).

5. **Add a test.** Every benchmark adapter needs a smoke test under `core/tests/`
   (or its own `examples/<variant>/tests/`) that fails on a stub and on
   non-determinism — not just an import check.

6. **Document it.** Add a row to [`README.md`](README.md)'s table, and write the
   `examples/<variant>/README.md` (setup, what it measures, how to reproduce) if you
   added a worked example.

7. **Keep it cheap by default.** If the benchmark has a knob for a task subset
   (e.g. `SWEBENCH_INSTANCE_IDS`, `SPREADSHEETBENCH_TASK_IDS`), document the default
   and how to narrow it — most contributors should be able to smoke-test for cents,
   not dollars.

## House rules

- **The example is the source of truth, never duplicated into a template.** When a
  benchmark ships both `template/` and `examples/<variant>/`, CI sources the
  `examples/<variant>/` adapter directly (never a copy under `template/`) so a
  reviewer reading the example is reading exactly what ran. `tau2/examples/sierra_airline/`
  is the reference case; see `core/tests/test_ci_tau2_sierra_arms.py`.
- **Splits, gating, and sealing are core's job, never the adapter's.** Don't
  reimplement pass^k, the paired gate, or the sealed-test split inside an adapter —
  that is what keeps evaluation honest across every benchmark here.
- **Never leak the gold answer into `score()`'s feedback.** The feedback string is a
  learning signal the optimizer reads; describe *why* a rollout failed in general
  terms.
