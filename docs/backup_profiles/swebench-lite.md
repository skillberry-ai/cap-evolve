# Backup profile: `swebench-lite` — `benchmarks/swe_bench/template` (local only)

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

SWE-bench Lite with a single-shot litellm coding agent, scored by the SWE-bench Docker harness. CI `swebench` uses Harbor instead (`swebench-verified-harbor`).

| Key | Value |
|---|---|
| Bench names | `swe_bench`; settings: `oracle` when `SWEBENCH_ORACLE=1`, else none |
| Code | `benchmarks/swe_bench/template/` (`adapter.py`, `capevolve.yaml`, `seed_capability/prompt.md`); `docs/ADAPTER_TEMPLATES.md` |
| Reward | 1.0 iff the instance is in the harness report's `resolved_ids`: binary. Success: resolved. Group metric: per `Task.metadata.repo` |
| Infra rule | published: drop. Detectors: `error_ids`, `incomplete_ids`, a missing report (`raw.errored`); a patch that fails to apply is a real 0 |
| Telemetry | tokens: litellm `usage.total_tokens`; steps: always 1; latency and termination: `not-produced` |
| Cost | agent: litellm `response_cost` (`zero_means: unknown`) |
| Splits | core ratios 0.34 / 0.33 / 0.33 over HF `princeton-nlp/SWE-bench_Lite` split `test` (or `SWEBENCH_INSTANCE_IDS`) |
| Baselines | seed |
| Capability | coding-agent system prompt |
| Gold | HF fields `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`; `princeton-nlp/SWE-bench_Lite_oracle` (with `SWEBENCH_ORACLE=1` its gold-derived file list goes into `Task.input` and every rollout: disclose it). Allowed: none. Forbidden: all of these |
| Isolation | none |
| Agent evidence | not applicable: a plain litellm call, no file-system access |
| Models as used | rollout `metadata.model` |
| External state | HF cache `~/.cache/huggingface/datasets/princeton-nlp___swe-bench_lite/` (+ `_oracle`); Docker images `sweb.base.*`, `sweb.env.*`, `sweb.eval.*` (built locally, `NAMESPACE=none`); leftover containers `sweb.eval.<iid>.capevolve_<uuid>`; harness logs go to a deleted temp dir (only an excerpt survives, in feedback: `not-produced`) |
| Sources | the local `.capevolve*/` only; no CI; ledgers: as `_core.md` |
| Reproduce | dataset snapshot (`save_to_disk`) + fingerprint; `swebench` package version; `docker save` of the `sweb.*` images; unpinnable: the model endpoint |
| Licence | SWE-bench code MIT; dataset: `unverified` (the HF card states none) |
| Secrets | as `_core.md` |
