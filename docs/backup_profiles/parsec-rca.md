# Backup profile: `parsec-rca` — `benchmarks/parsec/examples/rca_prompts`; CI `parsec`

Shared values: [`_core.md`](_core.md). Format, and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: [`INDEX.md`](INDEX.md).

Multi-agent root-cause-analysis prompts for parsec-live, scored by Harbor verifiers against simulator MCP services.

| Key | Value |
|---|---|
| Bench names | `parsec`; tiers `pilot`, `v2`, `v6`; variants (settings) `v4_t2_e1`, `v4_t_e1`, `v4_g_e1`, `h4`, `ccc`, `v5`, `v6`, `v6_t2`, `v6_t4`, `v6_g2_e1`; sweeps (`v4_t_e1`, `v6_t2_e1`) have one unit per task |
| Code | `benchmarks/parsec/examples/rca_prompts/` (`adapters/adapter.py`, `parsec_paths.py`, `optimizer/`, `RUN_H4.md`, `README.md`, `tests/`, variant dirs `v4_t2_e1/`, `h4/`, `ccc/`, `v5/`, `v6/` (`adapters/adapter.py`, `make_split.py`, `scaffold_project.py`, `build_v6_tree.py`, `run_v6.sh`), `v6_t2/`, `v6_t4/` (`audits/`, `cost_table.py`)); CI `ci/benchmarks/parsec/{pilot,smoke,v2,docker,utils}/`; use code from **before `aeee7126d`** (path-derived roots broke at that commit) |
| Reward | Harbor verifier `reward.json["reward"]`: partial credit in [0, 1], `weights.tool_calls × score_tool_calls + weights.answer × score_answer`, times 0 unless the agent's final event is `subtype=="success"` and not `is_error`. Success: reward = 1.0 (convention). Group metric: per category (cloud, cost, icinga, platform) |
| Infra rule | published: drop. Detector: `_agent_failure` (dead agent → `Rollout.error`); simulator-fabrication partial credit is audited in `h4/audit/audit_absence_traps.py` |
| Telemetry | tokens and cost from parsec-live `usage … in= out= cache_read= cache_write= cost_usd= latency_ms=` log lines in the episode's time window (`metadata.parsec_usage_window`); prompt/completion split only in the raw log; steps: `not-produced`; termination: the final event in `agent.jsonl` |
| Cost | agent: log-derived, **0 if the log is missing** (`zero_means: unknown`); simulator LLMs (`HARNESS_LLM_SIMULATION_MODEL`): not recorded (`aux_call` null); LLM merger (v6_t4): optimizer cost (`v6_t4/cost_table.py`) |
| Splits | v6: pooled F / C / test thirds (`v6/make_split.py --fractions 1,1,1 --seed 6`, stratified by category and drop; F 67, test 66), sealed by core; v4_t2_e1, h4, v6_t2: one task, train = val = test (no holdout); ccc: 34 tasks jointly; v5: 136 tasks |
| Baselines | seed |
| Capability | 8 system-prompt files of the multi-agent RCA pipeline (`parsec-live/config/prompts`, mutated during a run and restored) |
| Gold | `<tree>/_run/tasks/bench-v<N>-<id>/tests/{verify.py,expected.json}`, `provenance.md`; `<tree>/docs/jb-2026-10-16/`, `bench-v6-harbor-tasks/`; trial `verifier/{reward.json,reward-detail.json,test-stdout.txt}` (also copied into `metadata.trial_result`). Allowed: F-split verifier output (handed over by `trajectories()`). Forbidden: C / test material and `expected.json` |
| Isolation | none |
| Agent evidence | the agent reads only through MCP but runs as the same user: grep `logs/parsec-trace/trace.jsonl` and the trial dirs; `data/agent_learnings.md` is mutable agent state |
| Models as used | parsec-live config and `logs/sims/parsec-live.log`; simulator model `HARNESS_LLM_SIMULATION_MODEL`; optimizer `claude-opus-5`, target `claude-sonnet-4-6` (configs): confirm from logs and transcripts |
| External state | `$PARSEC_V4N|V5N|V6N/_run/`: `jobs/<suite>/<task>/seed-<k>/<ms>/` (trial dirs), `logs/sims/parsec-live.log` (**the cost source**), `logs/sims/<svc>.log`, `logs/parsec-trace/trace.jsonl`, `logs/pids/`, `parsec-live/config/prompts`, `h4-lanes/<lane>/`, `v6-queue/`, `skills/`, `tasks/`; `data/agent_learnings.md`; `<proj>.sealed/` (incl. `jobs/`, `V6_SEALED_JOBS_ROOT`) and `.capevolve.sealed/run_*`; `results/h4_<suite>/` (incl. `_sweep/`); `run_<task>.dead-<ts>/`; the podman image and `/tmp/podman-$UID` graphroot (volatile) |
| Sources | hosts: CCC LSF logs `$CCC_LOGS` (`/dccstor/.../ccc_logs/<jobid>.*`) and workareas; git `skillberry-runs/parsec` (= `parsec-history`: `artifacts/`, `reports/`, `results/vN/*/source/`, `recipes/`, `scripts/`, `presentations/`), branches `results/v5-g2-e1-arm`, `results/v6-*`, `parsec/v6*`, `records/parsec-v6-g2-and-tmrg` (unmerged: archive both versions); `benchmark-history` `20261019001__v6-parsec`, `20261021001__v6-parsec`; private task bundles `_incoming_2026-10-16/*.zip`; ledgers: as `_core.md` |
| Reproduce | code before `aeee7126d`; task bundles (MD5s in `v6/build_v6_tree.py`); dated checkouts (`v4_2026-09-16`, `v5_2026-10-10`, `v6_2026-10-16`); the podman image tar; parsec-live config and prompts at run start; unpinnable: simulator and agent endpoints |
| Licence | private bundles; none stated |
| Secrets | `config.local.yaml` (a LiteLLM key in clear); `LLM_API_KEY` |
