# The prompt — onboard tau2 airline (SPA variant) and optimize the single `airline_skill`

Paste this to your coding agent (Claude Code) at the cap-evolve repo root and say
**"follow RUN.md."** Intake treats this as a brand-new benchmark: the integration
step **clones tau2-bench + skillberry-store + skillberry-agent**, installs all
dependencies, starts the SPA stack (store → env manager → SPA), imports the frozen
primitive tools and the single `airline_skill`, writes the adapter, runs the
`cap-evolve check` gate, then the full baseline → optimize → gate → report loop.
Everything below is the input intake needs.

```text
Follow RUN.md to run a cap-evolve optimization. Onboard this as a brand-new
benchmark — the intake/integration step should CLONE + INSTALL all dependencies.

# 1. CAPABILITY TO OPTIMIZE

- type:         [skill-package]
- what:         ONE skill named `airline_skill`, modified IN PLACE. Its SKILL.md is
                what SPA injects as system prompt enrichment; its scripts/ is the
                exact tool set sent to the LLM.
- frozen:       The 14 primitive tools are STANDALONE store tools imported from
                seed_capability/primitive_tools/functions.py and tagged
                `primitive-tool` (book_reservation, calculate, cancel_reservation,
                get_reservation_details, get_user_details, list_all_airports,
                search_direct_flight, search_onestop_flight, send_certificate,
                update_reservation_baggages, update_reservation_flights,
                update_reservation_passengers, get_flight_status,
                transfer_to_human_agents). They are NOT a skill and are never
                modified. `_make_api_call` lives in that module as an internal
                helper and is NOT registered as a tool (the importer's AST filter
                skips `_`-prefixed functions).
- seed:         seed_capability/airline_skill/ holds SKILL.md + 14 baseline wrapper
                tools, one per primitive, named `<primitive>_wrapper`.
                seed_capability/primitive_tools/ is READ-ONLY reference.
- capability_path:   seed_capability
- actions:      [modify]   (modify airline_skill in place — never a sibling skill)
- skill_name:   airline_skill
- capability_sources:  []

## CONSTRAINTS ON THE SINGLE SKILL

1. There is exactly ONE skill: `airline_skill`. Never create a sibling skill.
   The `name:` in its SKILL.md frontmatter must stay `airline_skill`.
2. The SKILL.md prose is what SPA injects as system prompt enrichment.
3. **scripts/ = the COMPLETE tool set sent to the LLM.** Each .py file's single
   top-level public function becomes a callable tool. The LLM sees ONLY scripts/.
4. **Tools call primitives BY NAME** — `cancel_reservation(...)`,
   `get_user_details(...)`. The store auto-detects the dependency; nothing is
   imported or declared. NO tool in the skill may call `_make_api_call` — that is
   infrastructure used only inside the primitives themselves.
5. **Helpers are NESTED and `_`-prefixed.** Any helper logic must be a function
   defined inside the tool's body with a name starting with `_`; a module-level
   helper would be registered as its own tool and shown to the LLM.
6. Each file in scripts/ has exactly ONE top-level public function whose name
   matches the filename, with a Google-style docstring (the store parses it into
   the tool schema).
7. adapter.apply() DELETES `airline_skill` from the store (cascading to its own
   tools), re-imports the candidate's `airline_skill/`, and restarts SPA with
   SKILL_NAME=airline_skill. The standalone primitives survive the cascade.

## THREE OPTIMIZATION PATTERNS

### Pattern 1: GUARD an existing wrapper

When the agent misuses a tool (wrong args, skips a check, violates policy): edit
the wrapper in place, adding a nested `_`-helper that checks the failing condition,
returns an error when it fires, and delegates to the primitive otherwise. The agent
sees ONLY the wrapper — it cannot bypass the guard. BOUNDED.

### Pattern 2: ADD an aggregation tool

When the agent needs a multi-step operation it does incorrectly or not at all: add
a new .py file to scripts/ whose function calls several primitives by name (e.g.
get_user_details then get_reservation_details per reservation id). The agent gains
one correct tool. BOUNDED (nothing existing changes).

### Pattern 3: REMOVE a tool

When a tool's presence causes misfires (wasted turns, premature escalation): delete
its .py file. UNBOUNDED — it changes the agent's options on every task, including
passing ones. Requires strong evidence.

All patterns: NEVER touch `seed_capability/primitive_tools/`.

# 2. BENCHMARK / DATASET

## 2a. tau2-bench (the task suite + runner)
- benchmark:    tau2-bench airline domain (airline_skillberry variant)
- repo:         https://github.com/skillberry-ai/skillberry-benchmarks.git (subdir tau2/tau2-bench)
- commit:       a3a83266008275e9d800fd709927fa3dc4f23ec5
- install:      git clone; git checkout a3a8326; pip install -e tau2/tau2-bench
- domain:       airline_skillberry
- agent type:   llm_agent (with LLM calls routed through SPA)

## 2b. Skillberry Store (holds the frozen primitive tools + the single airline_skill)
- repo:         https://github.com/skillberry-ai/skillberry-store.git
- tag:          0.2.1
- install:      git clone --branch 0.2.1; python3.11 -m venv .venv; make install-requirements
- run:          EXECUTE_PYTHON_LOCALLY=True make run  (port 8000)
- health:       curl http://localhost:8000/health

## 2c. Skillberry Proxy-Agent (SPA — enriches LLM calls with skill prompts)
- repo:         https://github.com/skillberry-ai/skillberry-agent.git
- commit:       e359494f18267e339f9561acbd7a930e3b51189e
- install:      git clone; python3.11 -m venv .venv; make install-requirements
- run:          make run  (ports 7000 main + 7001 config)
- health:       curl http://localhost:7000/health
- DEPENDS ON:   store (port 8000) must be running first
- PORT IS FIXED at 7000 and is NOT configurable by env var. Three places outside
  this example hardcode it: tau2's `config.py`
  (`SKILLBERRY_AGENT_URL = "http://127.0.0.1:7000"`), two literals in `tau2/run.py`,
  and `uvicorn.run(..., port=7000)` in SPA's `main.py`. A knob here would move the
  health check without moving the routing, so there deliberately isn't one.
  * Both 7000 and 7001 must be FREE before `setup.sh` — it preflights them and
    stops with the offending PID named.
  * On macOS, port 7000 is held by `ControlCenter` (AirPlay Receiver) by DEFAULT.
    Turn it off: System Settings > General > AirDrop & Handoff > AirPlay Receiver.
  * To run SPA on another port you must patch those three locations yourself; the
    example does not support it.
  * `stop_spa()`/`teardown.sh` kill only the PID SPA recorded in
    `/tmp/skillberry-agent-service.pid`, and fall back to the port owner ONLY after
    confirming it is SPA — so a foreign process squatting 7000 is reported, never
    SIGKILLed.
- env config:
    SKILL_NAME=airline_skill
    USE_AGENT_TOOLS=false
    USE_AGENT_PROMPTS=true
    MCP_PROMPTS_POSITION=postfix
    SPA_PROVIDER_NAME=litellm
    SPA_MODEL_NAME=openai/aws/gpt-oss-120b

## 2d. tau2 Environment Manager (the HTTP API primitive tools call)
- port:         8004
- start:        cd tau2-bench && python scripts/start_tau2_environment_manager.py

## 2e. Tasks
- all 50 airline tasks (IDs "0" through "49")
- configurable via split_ids.json (or split_ids.quick-test.json for single-task runs)

# 3. RUNNER + MODELS + CREDENTIALS

## Architecture
  tau2 run_tasks (host)
    ├── agent LLM → SPA (host:7000, SKILL_NAME=airline_skill) → Store (host:8000) + upstream LLM
    │                 ↓
    │         injects airline_skill's SKILL.md as system prompt enrichment
    │         airline_skill's scripts/ are the callable tools; each delegates to
    │         a frozen primitive, which calls the Env Manager
    └── user simulator LLM → OPENAI_BASE_URL directly (no SPA)

  tau2 Env Manager (host:8004) ← primitive tool HTTP calls

## Models + credentials
- agent model:      ibm/skillberry-local  (litellm alias → SPA on localhost:7000)
- user sim model:   openai/aws/gpt-oss-120b  (direct via OPENAI_BASE_URL)
- OPENAI_API_KEY:   API key for upstream LLM
- OPENAI_API_BASE / OPENAI_BASE_URL: two names for ONE value — the upstream LLM
                    endpoint URL. litellm reads OPENAI_API_BASE; the user simulator
                    path reads OPENAI_BASE_URL (spa_env._upstream_llm_args). Set
                    EITHER and setup.sh derives the other; setting both to DIFFERENT
                    URLs is refused rather than silently resolved.

## Critical: skill replacement + SPA restart per candidate
Before each evaluation, adapter.apply() does:
  1. DELETE /skills/airline_skill?delete_tools=true&delete_snippets=true
     (cascade removes the skill's own wrapper tools; the standalone primitives are
     referenced by no skill manifest and survive untouched)
  2. Upload the candidate's airline_skill/: POST /skills/import-anthropic
  3. Stop SPA (make stop / kill port 7000)
  4. Export SKILL_NAME=airline_skill
  5. Start SPA (make run)
  6. Wait for health check

# 4. SCORER
- metric:       tau2's own reward in [0,1] (per-task)
- deterministic: reads reward from rollout.metadata (never re-runs)
- feedback:     gold-SAFE, argument-level: names the wrong ARGUMENT key + the
                AGENT'S OWN wrong value. Never the gold value.
- shown metrics: reward (primary), db_match, cost_usd (display-only)
- cost_usd is ALWAYS 0.0 and tokens ALWAYS 0 — only optimizer spend is budgeted.
  See "ONLY OPTIMIZER SPEND IS BUDGETED HERE" under §7 for the mechanism.

# 5. STARTUP SEQUENCE

  1. Clone skillberry-benchmarks (@ a3a8326), skillberry-store (tag 0.2.1), skillberry-agent (@ e359494)
  2. Install dependencies for each
  3. Start skillberry-store (port 8000) — wait for health check
  4. Start tau2 Env Manager (port 8004)
  5. Purge store, then import the 14 primitive tools individually as STANDALONE
     tools (not a skill), tagging each `primitive-tool`:
       for each PUBLIC func in seed_capability/primitive_tools/functions.py
         (public = not starting with '_', so _make_api_call is excluded):
       POST /tools/add?selected_func=<name>&update=true   -F "tool=@functions.py"
       GET /tools/<name> -> set tags=['primitive-tool'] -> PUT /tools/<name>
  6. Import the single skill AFTER the primitives (so the store can auto-detect
     each wrapper's dependency on the primitive it calls by bare name):
       POST /skills/import-anthropic  -F source_type=folder
         -F folder_path=<abs>/seed_capability/airline_skill -F snippet_mode=file
  7. Start SPA (port 7000) with SKILL_NAME=airline_skill — wait for health
  8. cap-evolve check

# 6. OPTIMIZER
- optimizer:    claude-code
- model:        claude-opus-4-8
- instructions: scope to MODIFYING the single airline_skill. Encode:
    * READ the primitive signatures FIRST (seed_capability/primitive_tools/functions.py)
    * The optimizer edits ./airline_skill/ in place — SKILL.md, existing wrapper
      tools, new composite tools, and removal of tools it can justify
    * Never edit primitive_tools/; never create a sibling skill
    * Tools call primitives BY NAME; no tool calls _make_api_call
    * Helpers must be nested inside their tool and _-prefixed

# 7. BUDGET / GATE   (mirrors capevolve.yaml — keep the two in sync)
- algorithm:        hill-climb (--focus all)
- max_iterations:   5           stall: 3
- num_trials:       10
- per-iteration optimizer $ cap: optimizer_usd_per_iter 40
- optimizer_max_turns: 100
- max_optimizer_usd: 100        max_usd: 200
- gate:             paired, k_se 0.0
- store:            git
- The smoke/quick-test specs override the numbers above.

## ONLY OPTIMIZER SPEND IS BUDGETED HERE
**Every rollout reports `cost_usd: 0.0` and `tokens: 0`. Only OPTIMIZER spend is
actually budgeted, and the dashboard's cost panel is blank for the agent half.**

Why, precisely (tau2 prices a run per message):
- `get_response_cost()` prices each LLM response with litellm's `completion_cost`
  (`tau2/utils/llm_utils.py:91`).
- `get_cost(messages)` sums those into `(agent_cost, user_cost)` — but returns `None`
  if **any** message has no cost (`llm_utils.py:327-345`), and the orchestrator then
  records `agent_cost = user_cost = None` (`orchestrator/orchestrator.py:264-268`).
- SPA proxies the agent's calls without returning usage, so the agent's messages are
  unpriced. Because the rule above is all-or-nothing, that zeroes the
  **user-simulator** half too — even though those calls go straight to the upstream
  LLM and never touch SPA.
- The model strings here (`ibm/skillberry-local`, `openai/aws/gpt-oss-120b`) are also
  absent from litellm's price map, so even a fully-reported path would price at 0.
- `Rollout.tokens` is hardcoded 0 by the adapter. tau2 does expose
  `get_token_usage()`, but the adapter does not plumb it.

What follows from that:
- **`max_usd` (200) can never bind.** It caps RUNNER spend, which always measures 0.
  The budgets that actually stop a run are `max_optimizer_usd` (100) and the
  per-iteration `optimizer_usd_per_iter` (40). Treat `max_usd` as inert here, not as
  a safety net.
- **A 0 in the cost panel means "not measured", NOT "free".** The upstream LLM is
  really being billed for every agent turn and every user-simulator turn of every
  task, on every trial, for both the baseline and each candidate.
- **Never use reported cost to compare candidates or size a run.** Get the real
  figure from the upstream provider's own accounting.

Fixing this properly requires returning usage from SPA, which is deliberately OUT OF
SCOPE for this example. Until then it is a DOCUMENTED LIMITATION, not an adapter bug:
`_shown_metrics()` still emits `cost_usd` as a display-only secondary metric, so the
panel stays honestly at 0 instead of inventing a number.

# 8. SETUP / TEARDOWN SCRIPT REQUIREMENTS

setup.sh and teardown.sh are generated alongside adapters/adapter.py and
adapters/spa_env.py. Several paths under the repo are SHARED with the other
examples (examples/skillsbench, examples/tau2_airline), so teardown must remove
ONLY what this example created.

## teardown.sh contract
Does exactly three things, in this order:
  1. stop the three services (SPA, store, tau2 env manager)
  2. remove their PID sentinels (/tmp/skillberry-{agent,store}-service.pid) and
     this example's log files
  3. remove the repos this example cloned:
     vendor/skillberry-{store,agent,benchmarks}

One option: `--keep-clones` — stop the services but keep the clones. Nothing else.
No flag may exist that deletes anything shared.

## NEVER touched, by default or by any flag
- $REPO/.venv        SHARED — skillsbench and tau2_airline install cap-evolve core
                     into the same venv. Removing it would force them to re-run
                     their setup.sh.
- $REPO/.capevolve   NOT TOUCHED AT ALL. It holds run_* artifacts (measurements)
                     and the project dir that all three examples scaffold into.
                     Cleaning it is the USER's responsibility. teardown needs no
                     access: setup.sh refreshes this example's files there on
                     every run, so nothing stale survives a re-setup.
- $REPO/vendor/      the DIRECTORY itself — skillsbench keeps vendor/skillsbench
                     inside it. Remove only this example's own subdirectories, and
                     rmdir vendor/ only if it ends up empty.

## Before exiting, teardown MUST warn
Print, as an explicit closing section, that `.venv` was NOT removed and that
`.capevolve` was NOT touched — each with the reason and the path, so the user knows
exactly what is left to clean up by hand. Report how many run_* directories remain.

## setup.sh must copy the optimizer instructions INTO the project
`cap-evolve` resolves `optimizer_instructions_file` relative to the CWD first and
only then relative to the project (core/cap_evolve/cli.py). A repo-relative value
therefore resolves only when the run happens to start from the repo root; from any
other directory the flag is silently omitted and the optimizer gets the GENERIC
scaffolded template instead — losing the MODIFY-only constraint and the
store-import rules (nested `_`-prefixed helpers, one public function per file,
never call `_make_api_call`) with no warning. So:
  - setup.sh: mkdir -p "$PROJECT/optimizer" and copy optimizer/INSTRUCTIONS.md there
  - every spec: `optimizer_instructions_file: optimizer/INSTRUCTIONS.md` (project-relative)
This also satisfies `pipeline_selftest.py`, which resolves the key STRICTLY
project-relative and reports a problem when it points outside the project.
Keep every `{{...}}` placeholder intact — the harness fills them per iteration.

## Deletion guardrails (both scripts)
- Verify $REPO is the cap-evolve checkout ($REPO/core/cap_evolve exists) before
  removing anything.
- Vet every path before `rm -rf`: refuse "/", $HOME, $REPO itself, .capevolve and
  anything under it, the shared venv, and anything resolving outside $REPO.
  `set -u` does NOT protect here — these variables are always set, just
  potentially wrong, so `rm -rf "$VENDOR/$d"` with a bad VENDOR is the failure
  mode to defend against.
- Stop services by the PID recorded in the service's own sentinel. Fall back to
  the port owner ONLY after confirming the process is that service, and use
  `lsof -sTCP:LISTEN` (unfiltered lsof also returns CLIENTS of the port — on a
  live run that includes cap-evolve's own runner talking to SPA).
- SIGTERM before SIGKILL.
- Both scripts must be idempotent — a second run exits 0 and changes nothing.

# 9. CONFIGURING TASK SCOPE
- Default: all 50 tasks (split_ids.json)
- Narrower scope: use one of the shipped split files —
    split_ids.smoke.json       (10 tasks)
    split_ids.quick-test.json  (1 task)
- Switch by editing the spec's `split_ids_file:`, or by running the matching spec
  (capevolve.smoke.yaml / capevolve.quick-test.yaml). `cap-evolve run` takes
  `--spec`; there is NO `--split-ids-file` flag.
```

> The bundled `examples/tau2_airline_spa/` is the **result** of following this prompt:
> the adapter (`adapters/adapter.py` + `adapters/spa_env.py`), the seed capability
> (`seed_capability/airline_skill/` + the frozen `seed_capability/primitive_tools/`),
> and `setup.sh` + `teardown.sh` are what the intake / implement-and-check flow
> produced. §8 is the contract those two scripts must satisfy.
