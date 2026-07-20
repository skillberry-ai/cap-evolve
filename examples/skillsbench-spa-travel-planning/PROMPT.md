# The prompt — onboard SkillsBench-SPA and optimize travel-planning skills

Paste this to your coding agent (Claude Code) at the cap-evolve repo root and say
**"follow RUN.md."** Intake treats this as a brand-new benchmark: the integration
step **clones SkillsBench + BenchFlow + skillberry-store + skillberry-agent**,
installs all dependencies, starts the SPA stack (store → agent), wires the runner
(an OpenHands agent in a Docker sandbox routing LLM calls through SPA), writes the
adapter, runs the `cap-evolve check` gate, then the full baseline → optimize → gate
→ report loop. Everything below is the input intake needs.

```text
Follow RUN.md to run a cap-evolve optimization. Onboard this as a brand-new
benchmark — the intake/integration step should CLONE + INSTALL all dependencies (not
assume they exist). Here is everything intake needs:

# 1. CAPABILITY TO OPTIMIZE  (a copy is edited each iteration; the original is never touched)
- type:         [skill-package]      # the Agent Skill packages themselves
- what:         the 6 travel-planning skills that SkillsBench hands the agent:
                search-accommodations, search-attractions, search-cities,
                search-driving-distance, search-flights, search-restaurants.
                These skills are used by the travel-planning task; improving them
                helps the agent solve the task correctly.
- seed:         one canonical copy of each of the 6 skills, placed under
                seed_capability/{search-accommodations,search-attractions,
                search-cities,search-driving-distance,search-flights,
                search-restaurants}/ . Seed with the versions found in the cloned
                SkillsBench repo at tasks/travel-planning/environment/skills/.
- capability_path:   seed_capability   (a dir holding the 6 skill sub-packages)
- actions:      [edit]
- capability_sources:  []   (the skills are self-contained)
- NOTE for the integration step — the skill-package capability's handlers
  (scripts/abstract.py: materialize/apply/validate) operate on ONE skill dir. The
  seed holds SIX. If `cap-evolve check` shows the capability only sees one skill,
  treat it as a FRAMEWORK GAP and extend the skill-package handlers to walk every
  immediate sub-package under capability_path (namespacing components by
  "<skill>/SKILL.md", "<skill>/references/<f>.md") and validate each. Do not hand-wave
  it in the adapter.

# 2. BENCHMARK / DATASET  (the eval) — INSTALL ALL DURING INTAKE

## 2a. SkillsBench (the task suite)
- benchmark:    SkillsBench  (the first benchmark for how well agents USE skills)
- repo:         https://github.com/benchflow-ai/skillsbench   (latest main; record the resolved commit)
- ref:          5433cf15c343f0da5fb942b80dc7dcb7c76506df  (pin for reproducibility)
- install:      git clone; create .venv with python3.12 via `uv sync`; install
                BenchFlow editable on top (`uv pip install --editable <benchflow_dir>`)
- sandbox:      docker  (REQUIRED; each task runs in its own container)

## 2b. BenchFlow (the runner CLI)
- repo:         https://github.com/benchflow-ai/benchflow
- ref:          d65cd8dde8bcf74a7d8121b37d405c7b8803aad8  (pin for reproducibility)
- install:      git clone; installed editable into the SkillsBench .venv (above)

## 2c. Skillberry Store (SBS) — the skills repository service
- repo:         https://github.com/skillberry-ai/skillberry-store.git
- branch:       main
- install:      git clone; create .venv with python3.11; `make install-requirements`
- run:          `EXECUTE_PYTHON_LOCALLY=True make run` (background, port 8000)
- health check: curl http://localhost:8000/health OR http://localhost:8000/docs
- NOTE: SBS must be running BEFORE skillberry-agent starts (SPA depends on it).

## 2d. Skillberry Proxy-Agent (SPA) — the LLM proxy + skill orchestrator
- repo:         https://github.com/aviweit/skillberry-agent.git
- branch:       fix/openai-compat-chat-completions
- install:      git clone; create .venv with python3.11; `make install-requirements`
- run:          `make run` (background, port 7000; config UI on port 7001)
- health check: curl http://localhost:7000/health OR http://localhost:7000/docs
- DEPENDS ON:   skillberry-store (port 8000) must be running first
- env config (set BEFORE starting SPA, or in .env file):
    SPA_PROVIDER_NAME=litellm
    SPA_MODEL_NAME=<LLM_MODEL>         # e.g. gpt-4o (same model as --model flag)
    USE_AGENT_TOOLS=true
    USE_AGENT_PROMPTS=true
    MCP_PROMPTS_POSITION=postfix

## 2e. Tasks
- tasks:        single task: travel-planning
- task selection: adapter.tasks() returns ["travel-planning"] for all splits.

# 2f. THE 1 TASK + SPLIT  (temporary single-task setup)
- train == val == test  (1 task; train, val, and test are ALL the same id —
                the engine logs a splits_warning):
    travel-planning   (medium, uses 6 travel search skills)
- pin the split in split_ids.json:
    {"train":["travel-planning"],"val":["travel-planning"],"test":["travel-planning"]}

# 3. RUNNER  (the agent under test) + MODELS + CREDENTIALS

## Architecture
  OpenHands (in Docker) → BenchFlow litellm-proxy (in Docker) → SPA (host:7000) → Skillberry Store (host:8000) + real LLM

  The LLM call chain has TWO hops through proxies:
    1. OpenHands inside the Docker sandbox calls BenchFlow's built-in litellm proxy
       (also inside the container) using the model name passed via --model.
    2. BenchFlow's litellm proxy is pointed at SPA on the host via
       BENCHFLOW_PROVIDER_BASE_URL (NOT LLM_BASE_URL). This is the critical variable
       that routes bench's internal litellm to SPA.
    3. SPA enriches the request with skills from Skillberry Store, then forwards to
       the real upstream LLM using OPENAI_API_KEY + OPENAI_BASE_URL set on the HOST.

- agent under test:   openhands (runs inside Docker sandbox per task)
- LLM routing:        BenchFlow's internal litellm proxy uses BENCHFLOW_PROVIDER_BASE_URL
                      to reach SPA. OpenHands passes LLM_API_KEY and LLM_BASE_URL
                      as --agent-env but the actual LLM hop goes through bench's proxy.
- how to run ONE task (the call adapter.run_target builds):
    bench eval create \
      --tasks-dir <TASKS_DIR> \
      --agent openhands \
      --model <LLM_MODEL> \
      --sandbox docker \
      --concurrency 1 \
      --jobs-dir <PER_EVAL_OUTPUT_DIR> \
      --skill-mode with-skill \
      --skills-dir <CANDIDATE_SKILLS_DIR> \
      --agent-env LLM_API_KEY=$LLM_API_KEY \
      --agent-env LLM_BASE_URL=$LLM_BASE_URL
- BENCHFLOW_PROVIDER_BASE_URL (critical — this is what routes bench's litellm to SPA):
    Set this on the HOST before invoking bench (not as --agent-env):
      DOCKER_BRIDGE_IP=$(docker network inspect bridge \
        --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}')
      export BENCHFLOW_PROVIDER_BASE_URL=http://${DOCKER_BRIDGE_IP}:7000
    On macOS/Windows: export BENCHFLOW_PROVIDER_BASE_URL=http://host.docker.internal:7000
    Without this, BenchFlow's litellm proxy cannot reach SPA and no LLM trajectory is
    produced — the rollout appears to complete but leaves no trace.
- SKILL INJECTION (the key mechanism):
    passing --skill-mode with-skill --skills-dir <DIR> where <DIR> is the
    candidate's optimized seed_capability makes BenchFlow STRIP the task's bundled
    skills and mount <DIR> at /skills instead. So <DIR> = the candidate's optimized
    seed_capability is deployed to the task verbatim. ctx (the live candidate dir)
    IS that <DIR>; materialize writes the edited skills there.
- ABSOLUTE PATHS (critical, or every rollout fails): bench is invoked from a FIXED
    working dir (so it reuses its dataset clone cache), which is NOT cap-evolve's cwd.
    You MUST resolve EVERY path you pass to bench to ABSOLUTE before the call.
- UNIQUE JOBS DIR PER CANDIDATE: include the candidate id in the path so bench
    doesn't reuse a prior result. Symptom of this bug: a candidate eval that finishes
    in seconds with reward identical to the baseline.
- CLEAN SKILLS DIR: the candidate dir (ctx) accumulates optimizer scratch files.
    run_target MUST deploy a CLEAN skills dir containing ONLY the sub-packages with
    a SKILL.md. Never pass the raw candidate dir to --skills-dir.

- DOCKER NETWORKING (critical — or BenchFlow's litellm proxy cannot reach SPA):
    SPA runs on the HOST, not inside the Docker container. The proxy inside Docker
    cannot use localhost/127.0.0.1 (that resolves to the container itself). On
    Linux/WSL2 use the Docker bridge gateway IP (typically 172.17.0.1):
      DOCKER_BRIDGE_IP=$(docker network inspect bridge \
        --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}')
      export BENCHFLOW_PROVIDER_BASE_URL=http://${DOCKER_BRIDGE_IP}:7000
      export LLM_BASE_URL=http://${DOCKER_BRIDGE_IP}:7000/
    On macOS/Windows use host.docker.internal:
      export BENCHFLOW_PROVIDER_BASE_URL=http://host.docker.internal:7000
      export LLM_BASE_URL=http://host.docker.internal:7000/
    VERIFY connectivity: from inside a test container,
      `curl $BENCHFLOW_PROVIDER_BASE_URL/health` must succeed before running any task.

- models + credentials:
    LLM_MODEL:              the model name bench passes via --model. BenchFlow's
                            litellm proxy uses this as the model identifier when
                            calling SPA. Use the litellm-prefixed form expected by
                            bench (e.g. vllm/aws/gpt-oss-120b).
    SPA_MODEL_NAME:         the model name SPA's litellm provider uses when
                            forwarding upstream (may differ from LLM_MODEL prefix,
                            e.g. openai/aws/gpt-oss-120b). Set on HOST before SPA starts.
    LLM_API_KEY:            propagated into the Docker sandbox via --agent-env for
                            OpenHands. Also set as OPENAI_API_KEY on the HOST for SPA.
    OPENAI_API_KEY:         the API key for the upstream LLM provider, set on HOST
                            before starting SPA (SPA's litellm provider reads this).
    OPENAI_BASE_URL:        the upstream LLM endpoint SPA forwards to, set on HOST
                            before starting SPA.
    BENCHFLOW_PROVIDER_BASE_URL: set on HOST; points BenchFlow's internal litellm
                            proxy at SPA (see above). This is the variable that
                            determines whether an LLM trajectory is produced at all.
    IMPORTANT: OPENAI_API_KEY + OPENAI_BASE_URL + BENCHFLOW_PROVIDER_BASE_URL must
    all be set on the HOST before starting SPA and before invoking bench.

# 4. SCORER  (what to optimize against)
- metric:       per-task BINARY pass in {0,1}. SkillsBench verifiers (verifier/test.sh)
                run pytest and write /logs/verifier/reward.txt = 1 (all tests pass) or 0,
                plus a CTRF JSON at /logs/verifier/ctrf.json with per-test results.
- metric source: BenchFlow collects the verifier reward into the per-task result under
                --jobs-dir. Implement adapter.score() to read that reward.
                score() must be DETERMINISTIC on a fixed rollout — read the recorded
                reward, do not re-run.
- pass rate:    the objective = mean reward across tasks on the VAL split.
- feedback (the learning signal) — gold-SAFE and SPECIFIC: for each FAILING task, parse
                the CTRF ctrf.json for the failed TEST NAMES and their assertion messages
                and surface those as the feedback, so the optimizer knows WHICH behavior
                the skill failed to elicit. Gold-SAFE: surface only the agent's OWN
                output defect named by the test; NEVER read or echo the task's
                oracle/solve.sh, the gold output, or any expected value.

# 4b. TRAJECTORIES  (the FULL traces the optimizer reads)
- where:        BenchFlow writes each rollout's native artifacts under --jobs-dir.
- expose:       implement adapter.trajectories(split) to return that directory.

# 5. STARTUP SEQUENCE  (order matters)

The integration step must start services in this order:
  1. Clone all repos (skillsbench, benchflow, skillberry-store, skillberry-agent)
  2. Install dependencies for each (venvs, make install-requirements)
  3. Start skillberry-store (port 8000) — wait for health check
  4. Start skillberry-agent/SPA (port 7000) — wait for health check
  5. Install bench CLI (uv sync in skillsbench repo + editable benchflow)
  6. Verify Docker is available and bridge IP is reachable from containers
  7. Run a single smoke task to confirm end-to-end connectivity

# 6. OPTIMIZER  (proposes the edits) + MODEL + CREDENTIALS
- optimizer:    claude-code
- model:        claude-opus-4-8
- credentials:  the logged-in Claude Code session / the same LLM gateway env
- runner_repo_path:  the cloned skillsbench checkout (read-only context so the optimizer
                can consult task.md instructions, verifier tests, and the skills it edits)
- optimizer instructions: author .capevolve/project/optimizer/INSTRUCTIONS.md from the
                scaffolded template. SCOPE IT TO skill-package ONLY. Encode:
    * STEP-0 reading mandate: read ./guidance/skill-package/SKILL.md IN FULL before
      any edit — it defines the edit surface and validity rules.
    * FULL EDIT SURFACE — the WHOLE skill directory is the artifact, NOT just SKILL.md.
      The optimizer may CREATE, MODIFY, or DELETE any file inside each skill package:
      edit SKILL.md, edit/add/remove references/*.md, edit/add NEW scripts under
      scripts/, delete dead content, and RESTRUCTURE the package.
    * PLACEMENT RULE: every file the optimizer creates/edits MUST live INSIDE one of
      the 6 skill package dirs — only sub-packages containing a SKILL.md are deployed.
    * CROSS-ITERATION files: read ./LEDGER.md + ./JOURNAL.md + ./RUNMAP.md +
      ./prior_iterations/ FIRST.

# 7. BUDGET / GATE
- algorithm:        hill-climb  (--focus all)
- max_iterations:   5           num_trials: 1
- per-iteration optimizer $ cap:  optimizer_usd_per_iter 20
- optimizer_max_turns: 100
- max_optimizer_usd: 100        max_usd: 200
- gate:             paired (per-task paired SE), k_se 0.2
- store:            git
- note:             Docker rollouts are slow (~4 min/task); run in background.
```

> The bundled `examples/skillsbench-spa/` is the **result** of following this prompt:
> the adapter (`adapters/adapter.py`), the startup scripts, the seed skills
> (`seed_capability/{search-accommodations,...}/`), and the optimizer instructions
> are what the intake / implement-and-check flow produced. `setup.sh` is the
> executable transcript of onboarding; `run.sh` runs the full optimization.
