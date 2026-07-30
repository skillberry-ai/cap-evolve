# The cap-evolve benchmark zoo

A curated, **verifier-gated** library of ready-to-run benchmarks. Every entry is
declared by a `benchmark.yaml` manifest plus one file of real code, and carries a
`verified.json` stamp recording what `cap-evolve benchmark verify` actually measured
— not a hand-committed "verified" flag.

```bash
cap-evolve benchmark list                       # the zoo + each entry's verified status
cap-evolve benchmark add my_bench               # scaffold a new one (manifest + one code file)
cap-evolve benchmark add my_bench --from-zoo toy_calc    # start from an existing entry
cap-evolve benchmark verify my_bench            # check gate + a REAL smoke eval, then stamp
cap-evolve run --spec my_bench/project/capevolve.yaml --project my_bench/project
```

## Entries

| Benchmark | Measures | Scoring | Tasks | API cost |
|---|---|---|---|---|
| [`toy_calc/`](toy_calc/) | Arithmetic accuracy of a deterministic stand-in agent | `exact` | 8 | none |
| [`json_extract/`](json_extract/) | Structured-JSON extraction with per-field partial credit | `custom` | 12 | none |

Both are zero-API and fully deterministic, so they run in CI and are the reference
examples for the manifest format.

## Layout

```
<benchmark>/
  README.md
  mock_script.json          # optional: the deterministic edit the `mock` optimizer applies
  verified.json             # written by `verify` — the EVIDENCE (measured reward + hashes)
  project/                  # ← this IS the cap-evolve project dir
    benchmark.yaml          # the declarative manifest (you write this)
    target.py               # run(task, ctx, *, seed=0) [+ score()] (you write this)
    tasks.jsonl             # the dataset
    seed_capability/        # the artifact the optimizer edits
    adapters/adapter.py     # GENERATED — a bare ManifestAdapter subclass
    capevolve.yaml          # GENERATED from the manifest
```

Everything the grader depends on lives **inside** `project/`. That is deliberate:
[#142](../docs/HONEST_EVAL.md)'s tamper guard can only hash paths under the project
dir, so a manifest or scorer parked at the benchmark root would be declared-but-
unprotected. This layout makes the guard cover them by construction.

## What is declarative vs what is code

Declarative in `benchmark.yaml`: dataset file + field mapping, scoring mode, metric
direction, capability path, split seed/ratios/pinned ids, trial count, protected
paths.

Code in `target.py`: `run(task, ctx, *, seed=0)` — how the target agent runs. There
is no config language for it because running an agent is real logic, and a DSL that
reimplemented Python would be worse than the Python it replaced. Optionally
`score(task, rollout)` for a bespoke predicate (`scoring: custom`); the five built-in
modes (`exact`/`contains`/`regex`/`numeric`/`custom`) cover the common cases.

## What `verify` executes

Not a manifest parse. In order:

1. manifest parse + field validation (an unknown key is a hard error);
2. dataset load **through the real adapter** (missing / duplicate-id / empty → fail);
3. `cap-evolve check` on the generated project (stubs, task stability, scorer
   determinism, pure `materialize`);
4. seeded split + the honest-gate floor — `val >= MIN_VAL_TASKS` and a non-empty
   sealed test split, so a 3-task dataset fails **here**, not mid-run inside
   `gate.decide`;
5. a **real zero-API smoke eval**: every val task through `live()` → `run_target()` →
   `score()`, **twice**, comparing rollout fingerprints and rewards — this is what
   catches a non-deterministic `run_target()`, which `check` never runs;
6. protected-paths resolution: the grader, dataset and manifest must all be covered.

Then `verified.json` records the measured val reward, the split sizes, the dataset
SHA-256 and the list of steps that ran.
