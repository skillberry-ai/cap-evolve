# Benchmark: toy_calc

Arithmetic accuracy of a deterministic zero-API stand-in agent whose system prompt
is optimized. The smallest end-to-end proof in the repo: no model calls, runs in
seconds, and the optimization provably moves the number.

Declared in [`project/benchmark.yaml`](project/benchmark.yaml). The only code is
[`project/target.py`](project/target.py) — one function, `run(task, ctx, *, seed=0)`.
The stand-in computes correctly only when the candidate prompt contains `[CALC]`,
so adding it (which the `mock` optimizer does) raises val 0.0 → 1.0.

```bash
cap-evolve benchmark verify toy_calc
CAPEVOLVE_MOCK_SCRIPT=$PWD/mock_script.json \
  cap-evolve run --spec toy_calc/project/capevolve.yaml --project toy_calc/project
# -> baseline_val 0.0  ->  test_reward 1.0  (gate-accepted, test sealed)
```

`examples/toy_calc/` keeps the hand-written adapter form of the same benchmark — it
is the "before" side of the boilerplate measurement, and the reference for what a
custom `CapabilityAdapter` looks like when the manifest does not fit.
