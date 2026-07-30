# Benchmark: json_extract

Structured-JSON extraction accuracy with **per-field partial credit**, on a
deterministic zero-API extractor. Zero cost, so it runs in CI.

Declared in [`project/benchmark.yaml`](project/benchmark.yaml). The only code is
[`project/target.py`](project/target.py): `run(task, ctx, *, seed=0)` plus a
`score(task, rollout)` — this benchmark uses `scoring: custom` because partial
credit over parsed JSON is real logic, not something a config key should express.

```bash
cap-evolve benchmark verify json_extract
cap-evolve run --spec json_extract/project/capevolve.yaml --project json_extract/project
```

The seed prompt asks for prose, so it scores 0. Adding `[JSON]` earns the name
field (1/3) and `[FIELDS]` earns all three (3/3) — a graded, non-binary signal.
