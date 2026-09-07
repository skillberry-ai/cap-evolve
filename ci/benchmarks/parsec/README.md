# parsec

**Parsec** ([`rhpds/parsec`](https://github.com/rhpds/parsec)) is Red Hat's
internal LLM-agentic troubleshooting tool for the Red Hat Demo Platform. It
routes a user question to one of six sub-agents (`orchestrator`, `icinga`,
`aap2`, `babylon`, `ocpv`, `cost`), each running an LLM → tool loop over a
shared pool of ~21 tools until it produces an answer.

This benchmark evaluates cap-evolve's ability to optimize a **single Parsec
sub-agent's SKILL.md** against a curated set of tasks. Both tiers target the
**aap2 sub-agent**.

---

## Internal-only, and local-only

Read this before anything else: **this benchmark cannot be run outside
IBM/Red Hat.** Not "is awkward to run" — cannot. Two of its three inputs do not
exist publicly:

| Input | Where it lives | Public? |
|---|---|---|
| The task trees (v1's `harbor-tasks/`, v2's authored `tasks_v2/`) | internal RH task-extraction output | **no** — not in the public `rhpds/parsec` repo |
| kaegis, the simulation harness that backs every tool call | `github.ibm.com/kaegis/simulation-harness` | **no** — IBM-internal |
| The model gateway | the IBM VPC LiteLLM gateway | no — VPC-internal (as for every bench here) |

Consequences, all deliberate:

- **Nothing is committed but metadata.** The task bodies are never checked in;
  each tier's dataset is regenerated at run time by a patcher in `utils/` from an
  external checkout you supply by env var. Only the small `<tier>/tasks.json`
  (ids + tags + provenance agent) is in git. This mirrors how `skillsbench`
  treats its Anthropic-licensed clone.
- **Every external input fails loudly when unset.** Anything that points outside
  this repo — the RH task trees, the aap2 OpenAPI spec, the kaegis checkout — has
  *no* default, because no default could be right for anyone but the author; the
  error names the env var to set. Paths *inside* the repo (the `e2e/` shadows one
  stage hands to the next) do have defaults, chained so each stage's output is the
  next stage's input with nothing to configure.
- **parsec is deliberately NOT CI-dispatchable** — see the next section.

### Deliberately not wired into CI

`parsec` is absent from `benchmarks.yml`'s `BENCHES` list and its dispatch
`options`, from `ALL_BENCHES` in `core/tests/test_benchmarks_plan_legs.py`, from
`BENCHES` in `core/tests/test_site_live_panel_tiers.py`, from `JOB_RE` in
`site/benchmarks.js`, and from the `case` block in `ci/benchmarks/lib/ci_setup.sh`.

That is the intended end state for now, not an oversight. Every one of those
gates CI-dispatchability, and a dispatched parsec leg could only ever fail: the
self-hosted `ibm-vpc` runner reaches the model gateway, but it has no RH task
tree, no kaegis checkout, and — for v2 — no way to bring up ten host-bound
simulator processes as part of a job. A leg that is red for infrastructure
reasons on every single run teaches people to ignore red legs.

What *is* wired: `run_suite.sh` accepts `parsec` as its `<bench>` argument, so a
person on a suitably provisioned machine runs the same code path CI would.
Revisit the wiring if and when the dataset and the sims become reachable from a
runner.

---

## Tiers

| Tier | Count | Task set | Sims | Held-out test? |
|---|---:|---|---|---|
| `smoke` | 5 | subset of v1's 30 | 4 shared kaegis endpoints | no (FIT) |
| `pilot` | 30 | v1 — extracted from real Parsec traces | 4 shared kaegis endpoints | no (FIT) |
| `v2` | 10 | v2 — newly authored `bench-aap2-*` | 1 isolated kaegis **per task** | no (FIT) |

**No tier ships a `split_ids.json`, so every tier is a no-holdout FIT tier**
(`train == val == test ==` all of the tier's tasks). `run_suite.sh` treats the
presence of `<tier>/split_ids.json` as the opt-in to a genuine held-out split;
with the file absent it builds the FIT split and the report labels the number as
a fit metric rather than a generalization claim. Same as `swebench`'s pilot.

> **A committed `pilot/split_ids.json` was withdrawn.** The original intake
> shipped a seeded 60/20/20 split whose held-out `test` set was
> `{0005, 0032, 0047, 0048, 0088, 0104}` — and the very optimizer pilot published
> below had already been tuned directly against `0047` and `0048`. The "held-out"
> test was contaminated by this benchmark's own experiment before it was ever
> sealed, so the honest fix was to delete the file rather than regenerate it: the
> pilot is a FIT tier, which is what the numbers below actually are. A real
> held-out split can be added later, generated from tasks no published run has
> touched.

---

## Tier v1 — `smoke` (5) and `pilot` (30)

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

30 aap2 tasks total. `smoke` is a 5-task subset chosen for coverage of the score
distribution: `perfect-solve` (aap2-0037), `trajectory-match` (aap2-0023, 0074),
`gate-failed` (aap2-0047, 0048).

### Sims — four SHARED endpoints

| Sim endpoint | Port | Tools |
|---|---:|---|
| aap2 | 8086 | `query_aap2` |
| github | 8087 | `fetch_github_file`, `search_github_repo`, `search_github_code`, `search_agnosticv_prs` |
| babylon | 8088 | `lookup_catalog_item`, `query_babylon_catalog` |
| provisions_db | 8090 | `query_provisions_db`, `db_describe_table` |

All 30 tasks share these four. The icinga sim (`:8089`) is optional and unused by
any aap2 task; its `api.json` currently fails kaegis skill-generation (no
`components.schemas`) and is tracked for a future upstream fix.

### Setup

```bash
# 1. the agent base image (once; both tiers need it)
bash ci/benchmarks/parsec/utils/build-parsec-agent-base.sh

# 2. the task shadow — writes <repo>/e2e/parsec/harbor-tasks-patched/
PARSEC_HARBOR_TASKS_SRC=/path/to/your/rhpds-parsec/harbor-tasks \
  bash ci/benchmarks/parsec/utils/patch-harbor-tasks.sh

# 3. bring up the four kaegis sims on 8086/8087/8088/8090 (kaegis's own tooling)

# 4. run
TIER=smoke bash ci/benchmarks/lib/run_suite.sh parsec
TIER=pilot bash ci/benchmarks/lib/run_suite.sh parsec
```

`patch-harbor-tasks.sh` shadow-copies the RH tree and applies three edits the
pilot needs: swap `docker_image` to `localhost/parsec-agent-base:latest`; replace
the single `${BACKEND_MCP_URL}` mcp_servers block with the four concrete sim URLs
(Harbor's docker environment does not interpolate `${VAR}` in `task.toml`); and
strip the `mcp__<server>__` prefix inside `verify.py`'s `parse_transcript` so
trajectory-match compares against the bare tool names in `expected.json`. The RH
original is never modified.

---

## Tier v2 — 10 authored tasks, one simulator each

`v2` is a **second, independent experiment**, not a refinement of v1. It targets
the same aap2 sub-agent and reuses the same `HARBOR_LOCAL_ASIS` adapter path, but
differs materially:

| | v1 (`smoke`/`pilot`) | v2 |
|---|---|---|
| Tasks | 30, extracted from real Parsec traces | 10, **newly authored** (`bench-aap2-001-single-job-outcome` … `-010-log-does-not-say`) |
| Per-task files | `task.toml`, `instruction.md`, `tests/{expected.json,verify.py,test.sh}` | the same **plus** `golden.json`, `seed.json`, `provenance.md` |
| Simulators | **4 shared** endpoints (8086/8087/8088/8090) across all 30 tasks | **1 isolated** kaegis per task (10 processes, 9086–9095), each seeded from that task's own `seed.json` |
| Tools exercised | `query_aap2` + github/babylon/provisions_db | `query_aap2` only |
| Setup | patch the shadow, then run | **bake + start 10 sims + a second patch pass** before running |
| Held-out test | none (FIT) | none (FIT) — the intake's own split file has `test: []`, `test_used: false` |

The isolation is the point: one simulator per task, seeded from that task's own
`seed.json`, means one task's fixture data cannot leak into another task's
answers, which four shared endpoints across 30 tasks cannot guarantee.

### The dataset is `harbor-tasks-v2.1`, not `harbor-tasks-v2`

v2's pipeline has two patch passes, and the tier's `HARBOR_DATASET` is the
**second** one. `v2.1` is a downstream patch of `v2` that fixes three bugs which
only appear once the tier actually runs inside a Harbor/Podman container:

- **MCP server name** `"backend"` → `"aap2"`. Claude Code namespaces MCP tools as
  `mcp__<serverName>__<toolName>`, so `name = "backend"` made SKILL.md's bare
  `query_aap2` resolve to `mcp__backend__query_aap2`, which the agent then invoked
  as bare `query_aap2` → "No such tool available".
- **`verify.py` prefix strip.** The scorer compares against bare `query_aap2` in
  `expected.json`; without the strip, namespaced `tool_use` names never match and
  `tool_calls` is 0.0 no matter how correct the calls were. (Same class of fix as
  v1's patcher applies to its own `verify.py`.)
- **`127.0.0.1` → `host.containers.internal`.** The sims bind to the *host's*
  loopback. Inside a Podman task container `127.0.0.1` is the container's own
  loopback, so the MCP SSE handshake fails and the agent runs with no
  `mcp__aap2__*` tools at all. Podman's host-bridge alias reaches the host sockets
  through gvproxy/slirp port forwarding.

### Setup — order matters

Five stages, in this order. Stage 3 mutates stage 1's output (writing each task's
live sim URL into its `task.toml`), and stage 4 reads the result — so rerunning an
earlier stage means rerunning the later ones.

```bash
# 0. the agent base image (once; shared with v1)
bash ci/benchmarks/parsec/utils/build-parsec-agent-base.sh

# 1. shadow the authored tasks  -> <repo>/e2e/parsec/v2/harbor-tasks-v2/
PARSEC_HARBOR_TASKS_V2_SRC=/path/to/your/parsec/tasks_v2 \
  bash ci/benchmarks/parsec/utils/patch-harbor-tasks-v2.sh

# 2. bake the aap2 kaegis skill once, offline
PARSEC_AAP2_SPEC_SRC=/path/to/your/parsec/aap2.json \
HARNESS_SRC=/path/to/your/kaegis/simulation-harness \
  bash ci/benchmarks/parsec/utils/bake-aap2-skill.sh

# 3. start the 10 isolated sims (9086..9095) and write each task's MCP URL
HARNESS_SRC=/path/to/your/kaegis/simulation-harness \
  bash ci/benchmarks/parsec/utils/start-sims-v2.sh

# 4. container-correctness pass  -> <repo>/e2e/parsec/v2/harbor-tasks-v2.1/
bash ci/benchmarks/parsec/utils/patch-harbor-tasks-v2.1.sh

# 5. run
TIER=v2 bash ci/benchmarks/lib/run_suite.sh parsec

# teardown when you're done (kills the sims, removes the manifest)
bash ci/benchmarks/parsec/utils/stop-sims-v2.sh
```

`start-sims-v2.sh` refuses to start over a live `sims-v2.manifest.json`; run
`stop-sims-v2.sh` first. Both need `jq`, `curl`, `lsof` and `uv` on `PATH`; the
bake and the sims need a kaegis checkout.

### v2 env vars

| Var | Required? | Default | Used by |
|---|---|---|---|
| `PARSEC_HARBOR_TASKS_V2_SRC` | **yes** | *(none — fails loudly)* | stage 1 |
| `PARSEC_AAP2_SPEC_SRC` | **yes** | *(none — fails loudly)* | stage 2 |
| `HARNESS_SRC` | **yes** | *(none — fails loudly)* | stages 2, 3 |
| `PARSEC_HARBOR_TASKS_V2_STAGE` | no | `<repo>/e2e/parsec/v2/harbor-tasks-v2` | stages 1, 3, 4 |
| `PARSEC_HARBOR_TASKS_V2_DST` | no | `<repo>/e2e/parsec/v2/harbor-tasks-v2.1` | stage 4, `run_suite.sh` |
| `PARSEC_V2_WORK` | no | `<repo>/e2e/parsec/v2` | stages 2, 3, teardown |
| `KAEGIS_PORT_BASE` | no | `9086` | stage 3 |
| `KAEGIS_HOST` | no | `127.0.0.1` | stage 3 |

`PARSEC_HARBOR_TASKS_V2_DST`'s default is the same string as `run_suite.sh`'s
`TIER=v2` `HARBOR_DATASET` default — producer and consumer agree under their own
documented defaults, which was not true of the intake scripts.

`PARSEC_V2_WORK` is the **runtime scratch root**: the baked kaegis artifacts, the
generated harness configs, the per-task skills-store shadows, the sims manifest
and the sim logs all live under it. It defaults under the gitignored `e2e/` and
deliberately *not* under `ci/benchmarks/parsec/` — a committed source tree must
not double as a runtime scratch directory.

The intake worktree's `env.sh` is **not** promoted here. It pinned
`HARBOR_DATASET` at `harbor-tasks-v2` (stale — the tier's dataset is `v2.1`, the
copy with the three container fixes) and hardcoded one laptop's podman-machine
`DOCKER_HOST` socket path. Its durable content — the agent config,
`KAEGIS_PORT_BASE`, and the order of operations — is the table above plus the five
stages; `run_suite.sh` exports the agent config itself.

---

## Environment (both tiers)

Harbor-based, same runner shape as `swebench` — but with `HARBOR_LOCAL_ASIS=1`,
because Parsec's task dirs already ship every per-task artifact and Harbor's
default `package_dataset` repacking would blow them away. `run_suite.sh`'s
`parsec)` case exports that (and the rest of the Harbor config) unconditionally;
no tier ships an `overrides.env`.

Both tiers run against `localhost/parsec-agent-base:latest`, a ubi9 image built by
`utils/build-parsec-agent-base.sh`. It exists because Harbor's claude-code
installer runs `yum install -y curl procps-ng` inside the task image, and vanilla
ubi9 ships `curl-minimal`, which conflicts with `curl` — the install fails, the
container exits, and no trajectory is recorded. The image pre-resolves that with
`--allowerasing` and bakes in node/npm.

## What's optimized

`capabilities: [system-prompt]` — cap-evolve mutates the aap2 sub-agent's SKILL.md
only (from
[`rhpds/parsec:config/prompts/aap2_agent.md`](https://github.com/rhpds/parsec/blob/main/config/prompts/aap2_agent.md)).
Tools are held fixed at their sim-served implementations. The wrapper architecture
for tool-code optimization is queued for a later phase.

## Scoring

Each task's `tests/verify.py` (stdlib-only, deterministic) reads the agent's
transcript from `/logs/agent` and writes `/logs/verifier/reward.json`:

```
reward = gate · (0.5 · trajectory + 0.5 · assertions)
```

- **gate** ∈ `{0, 1}` — 0 if the agent didn't complete or produced an empty answer.
- **trajectory** ∈ `{0, 1}` — subset match against the expected tool sequence. The
  extractor writes bare tool names to `expected.json` while claude-code emits
  MCP-prefixed ones (`mcp__aap2__query_aap2`), so both tiers' patchers strip the
  `mcp__<server>__` prefix in `parse_transcript`. Without that, trajectory-match is
  0 for every task.
- **assertions** ∈ `[0, 1]` — fraction of `answer_contains` substrings present in
  the answer. v1's assertions are all `needs_review: true` (LLM-drafted by the task
  extractor) — their quality is an open item with RH. v2's are authored alongside
  each task's `seed.json`, so its assertions and its fixture data are correlated by
  construction.

## v1 baseline (2026-08-12)

30 aap2 tasks, seed capability unmodified, `aws/claude-sonnet-4-5`, 4 sims live,
single trial per task:

- **mean 0.240** · stdev 0.281 · min/max 0.000/1.000
- 5 tasks hit `trajectory=1.0` (the `query_aap2`-only subset) — mean **0.730**
- 25 multi-tool tasks — mean **0.142**
- 1 perfect solve: `aap2-0037`
- 3 tasks scored `assertions=1.0` without trajectory — the 50/50 weighting caps
  them at 0.5 (honesty check working as designed)
- 2 gate-failed tasks (`aap2-0047`, `aap2-0048`) — the agent looped
  combinatorially and never emitted a final answer

## v1 N=30 optimization pilot (2026-08-17)

**Question:** can the optimizer discover a SKILL.md edit that improves reward on
the two hardest-scoring aap2 tasks (`aap2-0047`, `aap2-0048`)?

**Setup:** those 2 tasks only, both gate-failed at the Aug-12 baseline;
`train = val = test = {0047, 0048}` (no holdout — a fit metric); `num_trials: 30`
(chosen to average out per-trial `gate=0/1` stochasticity that N=10 could not
distinguish from optimizer signal); `hill-climb`, `max_iterations: 5`, `stall: 2`,
paired-SE gate at `k=1.0`; optimizer `claude-code` / `claude-opus-4-7` at
`optimizer_max_turns: 60`.

| | val reward | stderr | verdict |
|---|---:|---:|---|
| seed | 0.317 | 0.035 | baseline |
| seed (train) | 0.342 | 0.033 | consistent |
| cand_0001 | 0.225 | 0.025 | **rejected** (Δ = −0.092, 2.5 · SE) |
| cand_0002 | 0.157 | 0.029 | **rejected** (Δ = −0.160, 7 · SE) |
| finalize test (best = `seed`) | 0.326 | 0.050 | `test_delta = 0.000` |

Both proposals regressed. `stall = 2` triggered → halted at iter=2 of 5. Optimizer
spend: $8.61 of a $40 budget.

**What we learned:**

1. **Parsec's seed `aap2_agent.md` is already at a local optimum** for these 2
   tasks. Optimizer additions ("always emit final report", "budget your rounds",
   "no controller sweep") over-constrain the agent and hurt reward; the paired-SE
   gate correctly caught both regressions.
2. **N=10 is not enough on gate-stochastic tasks.** An earlier N=10 pilot on the
   same 2 tasks measured seed val **0.017** → cand_0001 **0.215** (Δ = +0.198).
   That evaporated on finalize test (`test_delta = −0.003`). At N=30 the seed's
   true mean is **0.317**; the N=10 measurement was dominated by a window in which
   95% of trials scored `gate=0`.
3. **The paired-SE gate produced false-positive accepts at N=10.** At N=30 all
   stderrs shrink to ~0.03 and it correctly rejects noise-dominated deltas.
4. **`optimizer_max_turns=30` was too tight** for real edits to a ~24 KB SKILL.md
   — the optimizer emitted byte-identical candidates on retry. 60 fixed it.

**Framework implications for cap-evolve upstream** (not blocking):

- For `gate`-stochastic tasks, N ≥ 25–30 is needed to separate optimizer signal
  from measurement noise at reasonable gate `k`.
- Consider surfacing `completion` (the `gate` term) as a first-class side-metric,
  so "same capability, higher emit rate" is distinguishable from "genuinely better
  answers".
- Consider a longer default `optimizer_max_turns` for capabilities whose seed
  content exceeds ~15 KB.

## v2 baseline

Not yet published here. v2's intake produced local baselines against the 10
authored tasks; they are not comparable to v1's 0.240 (different task set,
different simulator topology, and only `query_aap2` exercised). A v2 number goes in
this section once it has been measured through
`TIER=v2 bash ci/benchmarks/lib/run_suite.sh parsec` rather than through the
intake's own scripts.

---

## Direction of travel

Parsec is turning into a **versioned benchmark family** — v1, v2, and a future v3
— rather than one benchmark with tiers. v1 and v2 already share only the sub-agent
under test: different task provenance (extracted vs authored), different simulator
topology (shared vs per-task), different per-task file shape, and separate setup
pipelines. Carrying that as `<tier>/tasks.json` under one `ci/benchmarks/parsec/`
is already a stretch.

The intent is to move parsec's versions out to a **dedicated benchmark repo** —
locally, and in a dedicated IBM GitHub repo — and treat them the way a
multi-version family is normally treated (the analogy: "maybe like
tau1/tau2/tau3"), with cap-evolve consuming them as an external dataset rather
than vendoring their pipelines here.

Nothing in this PR builds toward that yet; it is recorded so the current shape is
read as a way-station, not a destination.

## Related

- `templates/adapters/harbor/` — the adapter. `HARBOR_LOCAL_ASIS=1` (the opt-in
  that lets Harbor use a hand-authored task dir verbatim) is added there
  separately; `run_suite.sh`'s `parsec)` case exports it.
- `ci/benchmarks/README.md` — the suite-wide runner/tier/dispatch documentation.
- `PalmPalm7/parsec#4` — draft PR against `PalmPalm7:migration/full-sdk` adding
  the `PARSEC_TOOLS_DIR` hook to Parsec's `src/__init__.py` (needed for the later
  wrapper architecture; harmless today).
