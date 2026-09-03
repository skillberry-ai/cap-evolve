# parsec

**Parsec** ([`rhpds/parsec`](https://github.com/rhpds/parsec)) is Red Hat's
internal LLM-agentic troubleshooting tool for the Red Hat Demo Platform. It
routes a user question to one of six sub-agents (`orchestrator`, `icinga`,
`aap2`, `babylon`, `ocpv`, `cost`), each running an LLM → tool loop over a
shared pool of ~21 tools until it produces an answer.

This benchmark evaluates cap-evolve's ability to optimize a **single Parsec
sub-agent's SKILL.md** against a curated set of tasks. The phase-1 pilot
targets the **aap2 sub-agent** — 30 tasks derived from real Parsec traces by
the RH team.

## Task set

Tasks were extracted from real Parsec traces by RH's task-extractor pipeline
into the `harbor-tasks/` format:

```
harbor-tasks/traces_parsec-aap2-<NNNN>/
├── task.toml           # docker_image + [[environment.mcp_servers]] pointing at ${BACKEND_MCP_URL}
├── instruction.md      # the user turn (one line)
└── tests/
    ├── expected.json   # gold: expected tool sequence + assertions
    ├── verify.py       # scorer: reward = gate · (0.5 · trajectory + 0.5 · assertions)
    └── test.sh         # runs verify.py inside the container
```

30 aap2 tasks total. Curated tiers:

| Tier | Count | Purpose |
|---|---:|---|
| `smoke` | 5 | Quick end-to-end check; mix of `perfect-solve` (aap2-0037), `trajectory-match` (aap2-0023, 0074), and `gate-failed` (aap2-0047, 0048). |
| `pilot` | 30 | The full aap2 set. Seeded 60/20/20 split → 18 train / 6 val / 6 test. |
| `full` | *(not yet published)* | Awaiting the icinga/babylon/ocpv/cost/orchestrator sub-agent task-set extractions. |

## Environment

Harbor-based, same runner shape as `swebench` — but with `HARBOR_LOCAL_ASIS=1`
because Parsec's `harbor-tasks/` already ships every per-task artifact and the
default `package_dataset` repacking would blow it away.

**Four kaegis simulation-harness endpoints** back the tools the aap2 sub-agent
uses:

| Sim endpoint | Port | Tools |
|---|---:|---|
| aap2 | 8086 | `query_aap2` |
| github | 8087 | `fetch_github_file`, `search_github_repo`, `search_github_code`, `search_agnosticv_prs` |
| babylon | 8088 | `lookup_catalog_item`, `query_babylon_catalog` |
| provisions_db | 8090 | `query_provisions_db`, `db_describe_table` |

The icinga sim (`:8089`) is optional; not used by any aap2 task. Its `api.json`
currently fails kaegis skill-generation (no `components.schemas`) and is
tracked for a future upstream fix.

Sims are spawned from `github.ibm.com/kaegis/simulation-harness` — one process
per endpoint, each seeded with the corresponding `parsec-simulation-skills/`
OpenAPI spec.

## What's optimized

Phase-1 pilot: `capabilities: [system-prompt]` — cap-evolve mutates the aap2
sub-agent's SKILL.md only (copied from
[`rhpds/parsec:config/prompts/aap2_agent.md`](https://github.com/rhpds/parsec/blob/main/config/prompts/aap2_agent.md),
PR #40 SDK-migration branch). Tools are held fixed at their sim-served
implementations. The wrapper architecture for tool-code optimization is queued
for phase 2.

## Scoring

Each task's `tests/verify.py` (stdlib-only, deterministic) reads the agent's
transcript from `/logs/agent` and writes `/logs/verifier/reward.json`:

```
reward = gate · (0.5 · trajectory + 0.5 · assertions)
```

- **gate** ∈ `{0, 1}` — 0 if the agent didn't complete or produced an empty answer.
- **trajectory** ∈ `{0, 1}` — subset match against the expected tool sequence.
  Task extractor writes bare tool names to `expected.json`, but claude-code
  emits MCP-prefixed names (`mcp__aap2__query_aap2`); the shadow patcher fixes
  `parse_transcript` to strip the `mcp__<server>__` prefix.
- **assertions** ∈ `[0, 1]` — fraction of `answer_contains` substrings present
  in the answer. All assertions are currently `needs_review: true` (LLM-drafted
  by the task extractor) — quality is a phase-1 open item to raise with RH.

## Baseline (2026-08-12)

30 aap2 tasks, seed capability unmodified, `aws/claude-sonnet-4-5`, 4 sims live,
single trial per task:

- **mean 0.240** · stdev 0.281 · min/max 0.000/1.000
- 5 tasks hit `trajectory=1.0` (the query_aap2-only subset) — mean **0.730**
- 25 multi-tool tasks — mean **0.142**
- 1 perfect solve: `aap2-0037`
- 3 tasks scored `assertions=1.0` without trajectory — 50/50 weighting caps
  them at 0.5 (honesty check working as designed)
- 2 gate-failed tasks (`aap2-0047`, `aap2-0048`) — agent looped combinatorially
  and never emitted a final answer

## N=30 optimization pilot (2026-08-17)

**Question:** can cap-evolve's optimizer discover a SKILL.md edit that improves
reward on the two hardest-scoring aap2 tasks (`aap2-0047`, `aap2-0048`)?

**Setup:**
- Same 2 tasks, both gate-failed at the Aug-12 baseline (combinatorial-sweep
  failure mode).
- `train = val = test = {0047, 0048}` — no true holdout, so results are a
  fit metric (`splits_warning` fires; publishing tier should be `smoke`-style
  no-holdout, not `pilot`).
- `num_trials: 30` (60 trial-cells per split). Chosen to average out per-trial
  `gate=0/=1` stochasticity that N=10 could not distinguish from optimizer
  signal.
- `hill-climb`, `max_iterations: 5`, `stall: 2`, paired-SE gate with `k=1.0`.
- Optimizer: `claude-code` / `claude-opus-4-7`, `optimizer_max_turns: 60`
  (raised from the default 30 after prior N=10 runs hit that cap and produced
  byte-identical candidates on retry).

**Result:**

| | val reward | stderr | verdict |
|---|---:|---:|---|
| seed | 0.317 | 0.035 | baseline |
| seed (train) | 0.342 | 0.033 | consistent |
| cand_0001 | 0.225 | 0.025 | **rejected** (Δ = −0.092, 2.5 · SE) |
| cand_0002 | 0.157 | 0.029 | **rejected** (Δ = −0.160, 7 · SE) |
| finalize test (best = `seed`) | 0.326 | 0.050 | `test_delta = 0.000` |

Both optimizer proposals regressed reward. `stall = 2` triggered → run halted
at iter=2 (of 5). Optimizer spend: $8.61 of $40 budget. Wall time ≈ 40 h
(much of it macOS sleep on the local runner).

**What we learned:**

1. **Parsec's seed `aap2_agent.md` prompt (from
   [`rhpds/parsec` PR #40](https://github.com/rhpds/parsec/pull/40)'s SDK migration)
   is already at a local optimum** for these 2 tasks. Optimizer-proposed
   additions ("always emit final report", "budget your rounds", "no controller
   sweep") over-constrain the agent and hurt reward. The paired-SE gate
   correctly detected both regressions.
2. **N=10 is not enough on gate-stochastic tasks.** An earlier N=10 pilot on
   the same 2 tasks measured seed val = **0.017** → cand_0001 val = **0.215**
   (Δ = +0.198). That "improvement" evaporated on finalize test
   (`test_delta = −0.003`). The N=30 run showed the seed's true mean is
   **0.317**; the N=10 measurement was dominated by an unstable evaluation
   window where 95% of trials scored `gate=0`.
3. **The paired-SE gate produced false-positive accepts at N=10.** With N=30,
   all stderrs shrink to ~0.03 and the gate correctly rejects noise-dominated
   deltas.
4. **Default `optimizer_max_turns=30` was too tight** for substantial SKILL.md
   edits (parsec's `aap2_agent.md` is ~24 KB) — it caused the optimizer to
   produce byte-identical candidates on retry. Raising to 60 fixed it: both
   `cand_0001` and `cand_0002` in the N=30 run had distinct, coherent diffs.

**Framework implications for cap-evolve upstream** (not blocking this PR, but
worth surfacing):

- For tasks with `gate` stochasticity (agent sometimes emits final answer,
  sometimes doesn't), N ≥ 25–30 is required to distinguish optimizer signal
  from measurement noise at reasonable paired-SE gate `k` values.
- Consider surfacing `completion` (the `gate` term) as a first-class
  side-metric so users can distinguish "same capability, higher emit rate"
  from "genuinely better answers".
- Consider a longer default `optimizer_max_turns` for capabilities whose seed
  content exceeds ~15 KB.

**Data:** run_dir `.capevolve/run_20260814_214843` in the parsec-intake
worktree (`final.json` + `events.jsonl` + per-trial rollouts under
`rollouts/{val,train,test}/`).

## Running

```bash
# smoke (5 tasks, single trial each)
BENCH=parsec TIER=smoke bash ci/benchmarks/lib/run_suite.sh

# pilot (30 tasks, seeded 60/20/20 split)
BENCH=parsec TIER=pilot bash ci/benchmarks/lib/run_suite.sh
```

The suite reads:
- `ci/benchmarks/parsec/<tier>/tasks.json` — task IDs + tags
- `ci/benchmarks/parsec/pilot/split_ids.json` — train/val/test partition
- `ci/benchmarks/parsec/pilot/overrides.env` — parsec-specific env

Before running, the shadow task dir must exist at `$PARSEC_HARBOR_TASKS_DST`
(default `e2e/parsec/harbor-tasks-patched/`). Regenerate via
`ci/benchmarks/parsec/utils/patch-harbor-tasks.sh` (mirrors the intake helper
at `.capevolve/project/scripts/patch-harbor-tasks.sh` but writes to a
CI-friendly location).

## Related

- `templates/adapters/harbor/` — the adapter (unchanged from swebench;
  `HARBOR_LOCAL_ASIS=1` is set via `overrides.env`).
- `.capevolve/project/PROJECT.md` in the parsec-intake worktree — the
  intake-time run book with the full pilot's env, decisions, and open items.
- `PalmPalm7/parsec#4` — draft PR against `PalmPalm7:migration/full-sdk` that
  adds the `PARSEC_TOOLS_DIR` hook to Parsec's `src/__init__.py` (needed for
  the phase-2 wrapper architecture; harmless in phase 1).
