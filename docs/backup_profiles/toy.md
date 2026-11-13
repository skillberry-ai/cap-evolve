# Backup profile: `toy` — `benchmarks/toy/examples/{calc,skill}`

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

A zero-API, mocked proof of the loop.

| Key | Value |
|---|---|
| Bench names | `toy`; settings: `calc`, `skill` |
| Code | `benchmarks/toy/examples/calc/` (`adapter.py`, `tasks.jsonl`, `mock_script.json`, `run.sh`, `capability/`), `benchmarks/toy/examples/skill/` (`adapter.py`, `mock_script.json`, `capevolve.yaml`, `seed_capability/`); mock optimizer `skills/optimizers/run-optimizer/scripts/_mock_apply.py` |
| Reward | exact match with `task.target`: binary. Success: reward = 1. Group metric: `not applicable: no grouping` |
| Infra rule | as `_core.md` |
| Telemetry | `not-produced`: only `output` and a one-line `trace` |
| Cost | real $0 (`zero_means: zero`); optimizer: mock, $0 |
| Splits | core ratios: calc 8 tasks → 4/2/2; skill 10 tasks at 0.4/0.3/0.3 → 4/3/3 |
| Baselines | seed |
| Capability | calc: a capability file; skill: a skill with `scripts/normalize.py` |
| Gold | calc: `target` in `tasks.jsonl`; skill: the `TASKS` constant in `adapter.py`. The feedback quotes the target (allowed by design) |
| Isolation | not applicable: mock optimizer |
| Agent evidence | not applicable: deterministic stand-in (skill runs the candidate's `scripts/normalize.py` as a subprocess) |
| Models as used | not applicable: no models |
| External state | calc `run.sh`: `mktemp -d /tmp/toy_calc.*`; README: `/tmp/toy` (volatile) |
| Sources | none beyond the run dir |
| Reproduce | launch: `run.sh` or `capevolve.yaml` + `mock_script.json`; data: in-repo |
| Licence | in-repo (Apache-2.0) |
| Secrets | not applicable |
