# cap-evolve project — Parsec / aap2 sub-agent (pilot)

Filled by the `intake` skill on **2026-08-10**; scope reshaped **2026-08-11** after
smoke-testing revealed an architectural gap (see `../../parsec-results/docs/architecture-brief.html`).
This file is the honest ledger of what was decided, what was defaulted, and
what still BLOCKS a live run.

## Phase-1 scope (2026-08-12 update after JB review)

**Option B — no wrapper, two sim MCPs.** After a review with JB and the kaegis
team, we agreed on the simplest architecture that unblocks a meaningful
baseline: skip the MCP wrapper entirely for phase 1 and let claude-code call
each external system's sim MCP endpoint directly. Wrappers become a phase-2
question, addressed only when we're ready to promote specific tools from "sim'd"
to "real code, optimizable."

**Key architectural clarification from the JB session:**
- **One sim = one MCP endpoint.** Each kaegis process hosts a single active
  simulation. To sim two external systems (AAP2 + GitHub), we run *two*
  kaegis instances at *two* ports, and `task.toml` declares TWO
  `[[environment.mcp_servers]]` entries so claude-code sees both.
- **`parsec-simulation-skills/` maps to external systems, not sub-agents.**
  The five sim skills (aap2, babylon, github, icinga, provisions-db) each
  represent one external system. The aap2 sub-agent's tool set spans multiple
  of these (aap2 backend + github + occasionally provisions_db + babylon
  catalog); each domain gets its own sim endpoint.

**Missed in intake — noted for the record:** the initial setup provisioned only
the aap2 sim. That reflected a mental-model error ("one sim per sub-agent") not
missing information — `parsec-simulation-skills/parsec-github/` was visible from
day one, and kaegis's README explicitly stated the one-sim-per-process
constraint. Going forward, each new sub-agent onboarding walks the tool set,
collects distinct external systems, and provisions one sim per system.

**Sim / real-code stance for phase 1:** everything the agent calls is sim'd
behind the MCP surface (POV 1). Feeding sim skills with real Parsec code to
improve response fidelity is opportunistic and low-priority — sim quality is
not the current bottleneck; tool availability is. Real-code-with-optimization
(POV 2, via wrappers) is deferred to phase 2 where it becomes the mechanism
that makes tool-code edits visible to the eval.

**Phase-2 restore path** (kept from earlier draft, still applies when we're
ready to promote a tool from sim'd to real-code-optimizable):
```bash
mkdir -p .capevolve/project/seed_capability/tools
cp /Users/boazc/workarea/Python/rhdp-parsec-src/src/tools/aap2*.py \
   .capevolve/project/seed_capability/tools/
# Then flip capevolve.yaml: capabilities: [system-prompt, tools]
# And stand up a host-side MCP wrapper that runs the code + delegates externals to sims.
```

**Why deferred, not dropped.** The first real container smoke revealed Harbor
spins up a bare `ubi9 + claude-code CLI`, not Parsec's uvicorn runtime — so the
bind-mount + `PARSEC_TOOLS_DIR` hook we built delivers to a runtime the eval
doesn't exercise. The hook (PR `feat/parsec-tools-dir-hook`) stays as draft
against `PalmPalm7/parsec` for phase 2; the adapter's tool-mount logic stays
in place and no-ops when `seed_capability/tools/` is absent.

**Phase-2 restore path** (one command when we're ready):
```bash
mkdir -p .capevolve/project/seed_capability/tools
cp /Users/boazc/workarea/Python/rhdp-parsec-src/src/tools/aap2*.py \
   .capevolve/project/seed_capability/tools/
# Then flip capevolve.yaml: capabilities: [system-prompt, tools]
```

## What we're optimizing
- **Capabilities:** `system-prompt` **and** `tools` (in tandem, per proposal §33-35).
- **Artifact dir:** `seed_capability/` — a copy is edited each iteration.
  - `seed_capability/SKILL.md` ← `config/prompts/aap2_agent.md` in [rhpds/parsec PR #40](https://github.com/rhpds/parsec/pull/40) (branch `migration/full-sdk`, fork `PalmPalm7/parsec`).
  - `seed_capability/tools/aap2*.py` ← `src/tools/aap2*.py` (4 files, 1256 lines total).
- **Allowed edits:** `edit, add, remove` (tools capability supports all three).
- **Explicitly OUT of scope for phase 1:** `config/prompts/shared_context.md` (shared across all six sub-agents — editing would leak into orchestrator/babylon/icinga/ocpv/cost).

## How we run the target (the RUNNER)
- **Runner:** Harbor (subprocess, `capevolve_harbor/run.py`). One `harbor run` invocation per evaluation, parallel=4.
- **Adapter:** `adapters/adapter.py` — forked from `templates/adapters/harbor/adapter.py`. Key delta: `HARBOR_LOCAL_ASIS=1` mode preserves the pre-built `harbor-tasks/` dir instead of repacking (Parsec tasks need their own `task.toml` + `${BACKEND_MCP_URL}` + `tests/verify.py` + `expected.json`).
- **Backend under test:** ubi9 container with the aap2 **LLM-simulated** MCP server (`parsec-simulation-skills/parsec-aap2/`) — NOT real Red Hat systems. Simulator sources: `SKILL.md` operator brief + `api.json` (OpenAPI 3.1) + `schema.json` + `db.json` seed + `scenarios.json`.
- **Consuming model:** `claude-sonnet-4-20250514` (proposal §186).
- **Candidate injection:** the aap2 `SKILL.md` is appended to each task's `instruction.md` via Harbor's `--extra-instruction-path` flag. See [BLOCKED-2](#blocked-2) for the tools-injection gap.

## How we score
- **Primary metric:** `reward ∈ [0,1]` — from each task's `tests/verify.py` (stdlib-only, deterministic).
- **Formula:** `reward = gate · (0.5·trajectory + 0.5·assertions)`.
  - `gate ∈ {0,1}` — completion + nonempty-answer check.
  - `trajectory ∈ {0,1}` — expected tool sequence per `match: subset|exact-set|exact-sequence`.
  - `assertions ∈ [0,1]` — substring hits in the answer.
- **Feedback signal:** `capevolve_harbor.build_feedback(TrialResult)` — gold-safe, argument-level. Never reads/prints the gold value; derives from the agent's own trajectory + verifier stdout.
- **Sub-scores (`gate`, `trajectory`, `assertions`):** available in `TrialResult.reward_json`; not surfaced as display metrics yet (add to `metrics_display` in a later iteration).

## Data
- **Source:** `dataset_source: adapter` → adapter reads `HARBOR_TASK_IDS` env var (list of 30 aap2 IDs) or scans `HARBOR_DATASET`.
- **Dataset path:** `/Users/boazc/workarea/Python/rhdp-parsec/harbor-tasks/` (113 task dirs total).
- **Phase-1 filter:** 30 `traces_parsec-aap2-*` tasks (proposal §142 — largest / most instrumented / highest-win subdomain).
- **Split:** seeded 60/20/20 → **18 train / 6 val / 6 test** (`split_seed: 0`). Test is sealed; `finalize` scores it once.
- **Distribution across all 113 tasks** (for reference): icinga 30, aap2 30, orchestrator 25, babylon 21, ocpv 4, cost 3.

## Optimizer + algorithm
- **Optimizer:** `claude-code` — matches target-model family, native parallel subagents enable the two-phase diagnose→implement fan-out the intake SKILL demands.
- **Algorithm:** `hill-climb`, focus `hardest-first` (n=18 train → prioritize failing tasks).
- **Orchestration:** `deterministic` (cap-evolve sequences the pipeline; honesty is code-enforced).
- **External baseline:** pure GEPA via Harbor (proposal §144). Cap-evolve's algorithm here is intentionally NOT GEPA — this is a "hill-climb inside cap-evolve vs. GEPA outside cap-evolve" comparison. Switch to `algorithm_skill: gepa` for an apples-to-apples same-algorithm variant.
- **Budget (pilot preset):** `max_iterations=5`, `stall=2`, `max_usd=50`, `max_optimizer_usd=20`, `optimizer_max_turns=30`, `optimizer_usd_per_iter=4`.

## Inputs status
- **NEEDED inputs resolved:**
  - ✅ tasks dataset → `/Users/boazc/workarea/Python/rhdp-parsec/harbor-tasks/` filtered to 30 aap2 IDs.
  - ✅ target agent (runner) → Harbor via `harbor_run(...)` in the adapter.
  - ✅ scorer → per-task `tests/verify.py`, cap-evolve reads via `adapter.score()`.
  - ✅ metric extraction / scoring source → Harbor's `verifier/reward.json` (or `reward.txt`), pass-through in `adapter.score()`.
  - ✅ trajectories path → Harbor's job dir via `Adapter._last_jobs_dir` (contains `agent/trajectory.json`, `verifier/*`, `result.json`).
  - ✅ capability artifact → `seed_capability/{SKILL.md, tools/*.py}` cloned from `PalmPalm7/parsec:migration/full-sdk`.
- **RECOMMENDED inputs & defaults logged:**
  - `num_trials: 1` — Parsec verifier is deterministic; the LLM-simulated backend adds variance. Bump to 3+ after pilot proves wiring so the significance gate has power.
  - `split_ids_file: ""` — using ratio split, not pinned IDs. If a canonical Parsec split emerges (or once the 19 multi-turn sessions are compiled into `harbor-tasks/`), swap to pinned.
  - `github_integration: false` — off for pilot; enable later against a mirror repo.
  - `metrics_display: [reward]` — could surface `gate` / `trajectory` / `assertions` sub-scores from `reward_json` in a later iteration. Doesn't affect the gate.

## ✅ Resolved on 2026-08-10 — BLOCKED-1 (Harbor CLI + container runtime)
Installed:
- Harbor CLI 0.20.0 at `~/.local/bin/harbor` via `uv tool install harbor`.
- Podman 6.0.2 (rootless mode, Fedora Machine OS 6.0 VM) via `brew install podman`.
- Docker→Podman compat shim at `~/.local/bin/docker` (forwards to podman).
- `DOCKER_HOST` persisted in `~/.zshrc` pointing at the podman API socket.
- `registry.access.redhat.com/ubi9/ubi:latest` pulled into the Podman machine.
- Harbor's `DockerEnvironment.preflight()` returns `preflight: OK`.

## ✅ Resolved on 2026-08-10 — BLOCKED-2 (tools-capability injection)
Chose **option 1**: bind-mount candidate tools + a tiny Parsec-side runtime hook.

**Parsec side** — draft PR at **https://github.com/PalmPalm7/parsec/pull/4** (branch `feat/parsec-tools-dir-hook` on `github.com/bcarmeli/parsec`, HEAD `519002b`, target `PalmPalm7:migration/full-sdk`). Adds a `_load_tool_overrides()` function to `src/__init__.py`: when `PARSEC_TOOLS_DIR` names an existing directory, every `<name>.py` file in it is loaded and registered in `sys.modules['src.tools.<name>']` BEFORE any `from src.tools.aap2 import …` executes at `src.app` import time. Files starting with `_` are skipped. Unset env var = no-op (production behavior unchanged). Smoke-tested locally with a stub override module — the loaded module's `query_aap2()` correctly returns the override value; both `unset` and `bad-path` cases are no-ops.

**Cap-evolve side** — [adapters/adapter.py](adapters/adapter.py) `run_batch()` now appends `{"type":"bind","source":<candidate>/tools,"target":"/capability/tools","readonly":true}` to the Harbor mounts list and sets `PARSEC_TOOLS_DIR=/capability/tools` in `agent_env` whenever `candidate_dir/tools/` exists. It ALSO optionally bind-mounts the hook file itself at `/app/src/__init__.py` when the `PARSEC_INIT_HOOK_FILE` env var is set to an existing file — this lets the pilot run BEFORE the PR lands upstream and the ubi9 image is rebuilt. No effect on runs where the capability has no `tools/` subdir (backwards-compatible for the pure-prompt case).

**Pilot env vars to set before the first `cap-evolve check`** (persist in `.envrc` / `.env` / shell rc as fits your workflow):
```bash
# Container runtime (already persisted in ~/.zshrc by BLOCKED-1 resolution)
export DOCKER_HOST='unix:///var/folders/sf/ntm2w4vx0sn57cz6lxrp04440000gn/T/podman/podman-machine-default-api.sock'

# Harbor dataset — Parsec's tasks, shadow-copied with our own container image
# (see ../../parsec-results/docs/container-build.md). Original RH-authored harbor-tasks/ is left
# untouched at /Users/boazc/workarea/Python/rhdp-parsec/harbor-tasks; the shadow
# swaps docker_image to localhost/parsec-agent-base:latest per task.toml.
export HARBOR_DATASET=$(pwd)/.capevolve/project/harbor-tasks-patched
export HARBOR_LOCAL_ASIS=1
export HARBOR_TASK_IDS=$(ls -d "$HARBOR_DATASET"/traces_parsec-aap2-* | xargs -n1 basename | paste -sd, -)
export HARBOR_AGENT=claude-code
# HARBOR_MODEL: proposal §186 says claude-sonnet-4-20250514, but IBM's LiteLLM
# gateway (our .env's ANTHROPIC_BASE_URL) doesn't allowlist that exact revision.
# aws/claude-sonnet-4-5 is the closest on-allowlist version — same family, one
# minor revision newer. Divergence tracked in "Open items" below.
export HARBOR_MODEL=aws/claude-sonnet-4-5
export HARBOR_PARALLEL=4
export HARBOR_TIMEOUT=1800

# Route claude-code inside the container at IBM's gateway (not api.anthropic.com).
# When HARBOR_AGENT_BASE_URL is set, the adapter's _build_agent_env passes
# ANTHROPIC_BASE_URL + ANTHROPIC_MODEL + ANTHROPIC_API_KEY through as --ae flags.
# NOTE: In that branch, ANTHROPIC_API_KEY inside the container is sourced from
# HARBOR_AGENT_API_KEY (not from the shell's ANTHROPIC_API_KEY) — and it falls
# back to the literal string "dummy" if HARBOR_AGENT_API_KEY isn't set. Must set
# BOTH env vars for the container to authenticate.
export HARBOR_AGENT_BASE_URL="$ANTHROPIC_BASE_URL"
export HARBOR_AGENT_API_KEY="$ANTHROPIC_AUTH_TOKEN"

# Parsec agent inference credentials — used by the cap-evolve adapter itself
# (for feedback synthesis, cost tracking); the container gets a copy via
# HARBOR_AGENT_API_KEY above.
export ANTHROPIC_API_KEY="$ANTHROPIC_AUTH_TOKEN"

# Backend MCP simulator (aap2 LLM-driven backend, kaegis/simulation-harness on :8086).
# host.containers.internal is Podman's built-in DNS name for the host from inside a
# container (host.docker.internal is an alias). See "aap2 simulation harness" section
# below for how to start the harness.
export BACKEND_MCP_URL=http://host.containers.internal:8086/mcp/sse

# Pilot-only: overlay the hook into the container until PR lands + image rebuilds.
# Delete this line once bcarmeli/parsec#4 → PalmPalm7#40 → rhpds ships an image
# with src/__init__.py already carrying the hook.
export PARSEC_INIT_HOOK_FILE=/Users/boazc/workarea/Python/rhdp-parsec-src/src/__init__.py
```

## ✅ Resolved on 2026-08-10 — aap2 simulation harness (backend MCP)
Cloned `github.ibm.com/kaegis/simulation-harness` (v0.1.1+) to `/Users/boazc/workarea/Python/simulation-harness`. `make dev-install` populated the uv venv; `make start` runs the server as `uv run python -m simulation_harness` at `http://localhost:8086` (PID in `.harness.pid`).

**Harness `.env`** (600-perm, gitignored): `LLM_API_KEY` + `LLM_API_BASE` are copied from your IBM gateway (`OPENAI_API_KEY` / `OPENAI_BASE_URL` in your workspace-level `.env`) via a pipe — values never enter the transcript. Two harness overrides pin the simulator's LLM:
```
HARNESS_LLM_SKILL_GENERATION_MODEL=aws/gpt-oss-120b
HARNESS_LLM_SIMULATION_MODEL=aws/gpt-oss-120b
```
Rationale: the IBM gateway is LiteLLM-flavored and serves `aws/*` model names (per your `SKILLSBENCH_MODEL=aws/gpt-oss-120b` in the sibling worktree). The harness default `azure/gpt-5.4` wouldn't route.

**Seed the aap2 simulation** (~2 min first time, cached afterwards):
```bash
python3 -c "import json; s=json.load(open('/Users/boazc/workarea/Python/rhdp-parsec/parsec/aap2.json')); \
  print(json.dumps({'openapi_spec': s, 'name': 'parsec-aap2'}))" > /tmp/aap2_body.json
curl -sS -X POST http://localhost:8086/api/v1/simulation \
  -H 'content-type: application/json' --data-binary @/tmp/aap2_body.json
# Poll until "status":"ready" (phases: extracting_model → describing_behavior → seeding_database → ready).
curl -sS http://localhost:8086/api/v1/simulation | python3 -m json.tool
```

**Verified tool inventory** (1 tool, action-dispatched — matches the OpenAPI spec):
- `query_aap2(action, controller?, job_id?, ...)` with actions `find_jobs | get_job | get_job_events | get_job_log`.

Only `query_aap2` reaches the simulator; the other three Parsec tool modules (`aap2_debug`, `aap2_fix`, `aap2_stdout`) are local Python helpers that don't need a backend.

**Container reachability**: from inside a Podman container, both `host.containers.internal` and `host.docker.internal` resolve to the host; both return `{"status":"ready"}` from the harness. Confirmed via `podman run --rm ubi9 curl http://host.containers.internal:8086/readyz`.

**Skillberry Store is NOT needed**: it's a catalog UI on top of the harness. Parsec talks to the harness directly at `/mcp/sse`.

**Harness lifecycle**:
- Start: `cd /Users/boazc/workarea/Python/simulation-harness && make start`
- Stop: `make stop`
- Restart: `make restart` (clears session state, keeps generated skills cached in `skills/`)
- Logs: `simulation-harness/logs/`

## Open items (non-blocking) — track and resolve mid-flight

- **Runtime-model divergence from proposal §186.** Proposal names
  `claude-sonnet-4-20250514`; IBM gateway allowlist has `aws/claude-sonnet-4-5`
  as the closest match. Pilot uses `aws/claude-sonnet-4-5`. Two options if this
  matters: (a) request the exact 20250514 revision be added to the gateway
  allowlist, (b) accept the divergence and note it in the final report. Track
  whether the score differs meaningfully between the two revisions.

- **`lookup_catalog_item` gap in the github sim** (2026-08-12). 22 of 30 aap2
  tasks expect `lookup_catalog_item` in their trajectory, but the JB team's
  `parsec-simulation-skills/parsec-github/api.json` exposes only
  `fetch_github_file`, `search_github_repo`, `search_github_code`, and
  `search_agnosticv_prs`. In Parsec's real code, `lookup_catalog_item` is not a
  direct GitHub API call — it builds an in-memory index by walking 4 agnosticv
  repos with the primitives above. Three options for JB to weigh in on:
  (a) add `lookup_catalog_item` as a fifth operation in the github sim spec
  (fastest — sim answers as if it did the walk),
  (b) instruct the aap2 SKILL.md to build the composite from primitives (moves
  the load to the agent's tool selection),
  (c) accept the coverage gap and exclude the 22 tasks that need it from the
  first baseline (smaller val set but honest signal on the 8 remaining tasks).
  Recommendation from us: option (a) for the phase-1 pilot, revisit for phase 2
  when we're deciding what to promote from sim to real code.

- **Coverage of the current 2-sim setup: 5 of 30 aap2 tasks** (2026-08-12).
  With aap2 sim on :8086 (query_aap2) + github sim on :8087
  (fetch_github_file, search_github_repo, search_github_code, search_agnosticv_prs),
  the tasks whose expected trajectory is fully covered are exactly the 5
  query_aap2-only tasks: `traces_parsec-aap2-{0023, 0037, 0053, 0074, 0113}`.
  The remaining 25 tasks each need at least one gap tool (22 need
  `lookup_catalog_item`, 5 need `query_provisions_db`/`db_describe_table`,
  1 needs `query_babylon_catalog`). To reach the "~25 tasks" target the JB
  session set as the phase-1 baseline goal, we need at minimum the
  `lookup_catalog_item` gap closed. Provisions/babylon are optional (they'd
  each add ~5 tasks) but need their own kaegis instances.

- **MCP tool-name prefix in trajectory scoring** (2026-08-12). claude-code
  exposes MCP tools with names like `mcp__aap2__query_aap2`. Parsec's
  `tests/verify.py` (each task ships its own) compares against bare tool names
  (`query_aap2`) via exact `in list` match — so trajectory-match returns 0 for
  every task regardless of what the agent does. Fixed in our shadow by patching
  each task's `verify.py` to strip the `mcp__<server>__` prefix inside
  `parse_transcript` (see `scripts/patch-harbor-tasks.sh`). Marked with a
  `STRIP_MCP_PREFIX_PATCHED` comment for idempotency. To propagate upstream:
  RH's task extractor could either (a) produce MCP-aware `expected.json` names
  or (b) update the shipped `verify.py` template to be prefix-agnostic. The
  shadow patch is easy to remove once either lands.

- **First live run (2026-08-12): sim response quality bottleneck.** With both
  sims wired and the prefix fix in place, `traces_parsec-aap2-0004` still
  scores 0.045 — but for a NEW reason. The agent called `query_aap2` once, got
  an LLM-simulated response that claimed "session expired," and gave up
  without exploring github tools. Real Parsec would never emit that response.
  This is the exact class of issue POV 1 addresses (feeding the sim with real
  code as reference material to improve response fidelity) but is out of scope
  for phase 1. In the meantime, the seed SKILL.md's "give up on ambiguous
  errors" behavior is exactly what prompt-optimization (Option A) targets.

## Full 30-task baseline (2026-08-12, evening)

All 30 aap2 tasks, seed capability unmodified, single trial each, model
`aws/claude-sonnet-4-5`, **four kaegis sims** running (aap2 :8086, github :8087,
babylon :8088, provisions_db :8090), single `harbor run` invocation with
`--parallel 4`. Zero infrastructure errors.

```
MEAN         0.240
STDEV        0.281
MIN / MAX    0.000 / 1.000
WALL         36.4 min (parallel=4)
ERRORS       0 / 30

reward distribution:
        0.00    7  ███████
   0.01-0.24   12  ████████████
   0.25-0.49    3  ███
   0.50-0.74    6  ██████
   0.75-0.99    1  █
        1.00    1  █
```

Breakdown by cohort:

| Cohort | Count | Mean | Notes |
|---|---:|---:|---|
| Trajectory-match = 1.0 (all expected tools called) | 5 | **0.730** | Same 5 query_aap2-only tasks; scores identical to the earlier 5-task baseline — pipeline is deterministic |
| Trajectory=0, assertions>0 (agent gave up mid-task) | 12 | 0.276 | Agent typically called `query_aap2` once, got a plausible-looking response, and answered without exploring |
| Zeros (traj=0, assert=0, gate=1) | 5 | 0.000 | Agent produced a non-empty but content-free answer |
| Gate-failed (completion=0) | 2 (0047, 0048) | 0.000 | Agent didn't emit a non-empty answer at all |
| Perfect assertions with trajectory=0 (honest-signal check) | 3 (0016, 0036, 0052) | 0.500 | Agent produced correct answer content without calling expected tools — the 50/50 weighting caps reward at 0.5, exactly the honest-scoring behavior we designed for |
| Trajectory=1 but assertions=0 | 1 (0113) | 0.500 | Correct tool sequence, wrong answer content |

The 5 tasks with trajectory=1.0 are exactly the query_aap2-only tasks; the
other 25 all need multiple tools and the agent (seed capability, no
optimization) does not follow through on multi-tool workflows. This is what
prompt-optimization will target in the next phase.

Reproduce: `python3 .capevolve/project/smoke_all.py --all` with the env
checklist at the top of this file.

Previous 5-task run (2026-08-12, midday, only aap2+github sims live) — kept for reference:

```
task                               reward   comp   traj  assert    sec
----------------------------------------------------------------------
traces_parsec-aap2-0023             0.625    1.0   1.00    0.25   93.3
traces_parsec-aap2-0037             1.000    1.0   1.00    1.00  109.5
traces_parsec-aap2-0053             0.625    1.0   1.00    0.25  243.8
traces_parsec-aap2-0074             0.900    1.0   1.00    0.80  124.8
traces_parsec-aap2-0113             0.500    1.0   1.00    0.00  121.4
----------------------------------------------------------------------
MEAN                                0.730
STDEV                               0.210
MIN / MAX                           0.500 / 1.000
```

Reproduce: `python3 .capevolve/project/smoke_batch.py traces_parsec-aap2-{0023,0037,0053,0074,0113}` with the env checklist at the top of this file.

Notes:
- Trajectory-match hit 1.0 on every task — the MCP-prefix strip in `verify.py`
  is working, and the aap2 sim exposes enough of `query_aap2` for these five
  tasks' expected trajectories.
- `aap2-0037` scored a full 1.0. Seed capability solves it without any
  optimization — strongest possible signal that the pipeline is honest.
- Score spread now lives on the assertion axis. `aap2-0113` scored 0/1
  assertions (the sim didn't produce the specific token the grader expected);
  `aap2-0053` scored 1/4. That's the class of gap prompt-optimization will target.
- Wall-clock: 93-244s per task, ~13min total for 5 tasks. Full 30-task set at
  the same pace would be ~1h; with the standard `HARBOR_PARALLEL=4` about 15 min.
- Raw JSON at `baseline_<epoch>.json` in the project dir.
- **Simulator gold-safety recheck** — grep of `parsec-simulation-skills/parsec-aap2/` shows no reference to `expected.json` (good). Re-verify once running live: does the simulator ever see the assertions, expected answer, or expected tool sequence? If yes, that's a gold-leak that would inflate scores.
- **`answer_contains` quality** — proposal §127 notes most assertions are LLM-drafted with `needs_review: true`. Human review by RH team is on the phase-1 milestones list (§157). Track score correlation with reviewed vs unreviewed subsets.
- **Simulator drift measurement** (proposal §107, §145) — phase-1 milestone. Sample tasks against real RH systems (when accessible) to bound the sim-vs-real divergence.
- **Multi-turn eval set** (proposal §50) — 19 multi-turn sessions not yet in `harbor-tasks/`. Compile them and use as sealed held-out once ready.
- **Cross-subdomain generalization** — phase-1 optimizes aap2 only; verify (later) that the aap2 optimizations don't regress babylon/icinga via a spot-check.

## Reproducibility
- **cap-evolve worktree:** `/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v1` on branch `parsec-intake`, HEAD `8d08d805` (matches `origin/main`).
- **Parsec source (PR #40):** `/Users/boazc/workarea/Python/rhdp-parsec-src` — clone of `git@github.com:PalmPalm7/parsec.git` branch `migration/full-sdk` (single-branch).
- **Parsec materials:** `/Users/boazc/workarea/Python/rhdp-parsec/` (proposal doc + 113 harbor-tasks + 5 simulator skills).
