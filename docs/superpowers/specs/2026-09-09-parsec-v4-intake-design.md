# parsec v4 intake — design

Written 2026-09-09. Companion to `HANDOFF.md` at the worktree root, which has
the full v1/v2 lessons this design is trying not to repeat.

## Goal

Get a baseline measurement of parsec's stock (unmodified) agent prompts against
v4's 30 hand-authored Harbor tasks / 5 simulated backends, landed in
`parsec-history` the same way v1 and v2's results were — without yet solving
v4's hardest open problem (how a cap-evolve candidate would actually get
injected into a live, host-side parsec process).

## Decision already made

Between three options — (a) full optimizer integration now, (b) baseline only
in a cap-evolve-shaped project, (c) standalone via v4's own README procedure,
no cap-evolve involvement — **(b) was chosen**. Rationale: v4's candidate has
nowhere to go yet (v2 injected a skill file into a claude-code agent running
*inside* the Harbor container; v4's `ParsecAgent` instead POSTs to a **host-side**
parsec service, so real injection means rewriting `config/prompts/<agent>.md` in
a live clone and restarting its uvicorn process per candidate — a mechanism that
doesn't exist and whose design is intentionally deferred). Building the
project in cap-evolve's shape now, without exercising injection, keeps the
option open later at low cost while avoiding speculative engineering against an
unsolved problem.

## What v4 is (for readers who haven't read the v4 README)

30 tasks against 5 simulated backends (platform, github, icinga, cost, cloud;
20 tools total), scored by a per-task `verify.py` against a `bench/v4` contract
(`completion` gate × (`w_tool·tool_calls + w_answer·answer`)). Every simulated
tool response is model-synthesized and takes 30–60s; a full 30-task pass takes
~3 hours. Parsec itself is multi-agent: an `orchestrator.md` routes to
`aap2_agent.md`, `babylon_agent.md`, `cost_agent.md`, `icinga_agent.md`,
`ocpv_agent.md`, `security_agent.md`, sharing `shared_context.md` — this is the
"capability" being measured, not any of the five *simulation* skill bundles
(those are the fake backends, not the thing under test).

## Components to build

All under `parsec-intake_v4/.capevolve/project/`, forked from the shared
`templates/adapters/harbor/` template (present fresh in this checkout at
`8efb1e88` — v2 forked from an older copy of the same template and had to
borrow `PYTHONPATH` from the v1 worktree because `capevolve_harbor`/
`capevolve_telemetry` weren't at repo root yet; both now ship at this
checkout's root, so that workaround is not needed here).

| component | notes |
|---|---|
| `harbor-tasks-v4/` | Unpacked from `bench-v4-harbor-tasks.zip`. `task.toml` MCP URL templates are per-service (`${PLATFORM_MCP_URL}` etc.), not v2's single `${BACKEND_MCP_URL}` — the patch step generalizes to a per-service loop. |
| `adapters/adapter.py` | Forked from the template. `run_batch()`: seed the task (shells out to v4's own `install_seeds.py`) immediately before each run, invoke `harbor run -a parsec_harbor_agent:ParsecAgent -t <task>` with that task's declared `<SERVICE>_MCP_URL`s, **no `HARBOR_PARALLEL`** — all 30 tasks share the same 5 live services, so runs are serialized. `score()` reads `reward.json`/`reward-detail.json`. No candidate-injection path is implemented this phase — the adapter always runs whatever's checked out in the patched parsec clone. |
| `scripts/start-sims-v4.sh` / `stop-sims-v4.sh` | 5 harness instances, fixed ports 8086 (platform) / 8087 (github) / 8088 (icinga) / 8089 (cost) / 8090 (cloud), per the v4 README. github and icinga already have harness code on disk from v1/v2 (`simulation-harness-github`, `simulation-harness-icinga`); platform/cost/cloud are new instances of the same generic harness. `curl .../healthz` to confirm each — podman's `(unhealthy)` status column is a known false negative. |
| `scripts/start-parsec.sh` | Fresh `git clone --shared` of the parsec reference repo (never the reference checkout itself) at `28e2c40`, apply `parsec-simulation-redirect.patch`, `uv pip install -e .` + the 4 missing runtime deps, start uvicorn with `PARSEC_SIM=1`, a shared `PARSEC_SIM_TRACE` path, `PARSEC_SIM_TIMEOUT=240`. |
| `seed_capability/` | Snapshot of the patched clone's `config/prompts/` (orchestrator + 6 sub-agents + shared_context) as it stood when the baseline was measured. Recorded for the history, not wired for editing. |
| `splits-v4.json` | A real disjoint train/val/test split, pinned now even though this phase doesn't use it — 30 tasks makes an actual holdout feasible (v2's 10 didn't), and pinning it now means a future optimizer decision inherits a real split instead of v1/v2's `train == val == test` mistake. |
| `capevolve.v4.yaml` | Same shape as v2's recipe (dataset via adapter, model/settings) for structural consistency; no `optimizer_skill`/`algorithm_skill` invoked this phase. |
| `smoke_all.py` | Standalone baseline-sweep runner — loops seed → run → collect across all 30 tasks at n=3, independent of any optimizer path, same pattern as v2's script of the same name. |
| `.env` / `scripts/env.sh` | Reuses v2's LiteLLM gateway credentials (already provides both the Anthropic-compatible endpoint parsec needs and the OpenAI-compatible one the simulations need — the v4 README explicitly says one gateway can serve both roles), plus v4's ports and `HARBOR_DATASET`. |

## Execution plan

1. Stand up the 5 simulations + patched parsec; confirm each service's
   `/healthz` before trusting it serves traffic.
2. Run **one task by hand** end-to-end
   (`install_seeds.py` → `harbor run -a parsec_harbor_agent:ParsecAgent`), and
   read `reward-detail.json`, not just `reward.json` — a `tool_calls: 0.0` can
   mean "no expected call matched" or "a forbidden call fired," which are very
   different findings.
3. If that's clean, run the full 30-task sweep via `smoke_all.py` at **n=3**
   per task (~9 hours wall-clock, serialized — no parallelism, since all tasks
   contend on the same 5 live services).
4. Record results in `parsec-history`: derived per-task score vectors plus a
   generated `results/v4/summary.md`. Every number in that summary comes from
   a script reading `results.json` — nothing hand-typed, per this repo's
   existing discipline (`skillsbench-history` caught real transcription drift
   this way, twice).

## Explicitly out of scope this phase

- Candidate injection into parsec's live prompts (the deferred hard problem).
- Any optimizer/hill-climb run.
- Cross-version comparison of v4's numbers against v1's or v2's — different
  task counts, different reward schemas, different tool surfaces. `v4 vs v1`
  or `v4 vs v2` is not a sentence this intake should produce.

## Risks carried over from v1/v2 (see `HANDOFF.md` for full detail)

- **Noise floor**: v4's own README already shows one task scoring 0.420 four
  times and 0.520 once with no change. n=3 is a first look, not a resolved
  measurement — it may need to grow before any per-task claim is trustworthy.
- **Infra errors must stay distinguishable from genuine zero scores** — both
  v1 and v2 miscounted errored trials as zeros at some point.
- **No hardcoded personal paths** in anything meant to ship (recipes, scripts).
- **Ask before pushing anything** — `origin/main`, any PR branch, or
  `parsec-history` — this design produces no push on its own.
