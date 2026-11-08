# The prompt — onboard VANILLA tau2-bench (airline) and optimize it, on ONE delivery arm

Paste this to your coding agent (Claude Code) at the cap-evolve repo root and say
**"follow RUN.md."** Intake treats tau2-bench as a brand-new benchmark: the onboarding
**clones and installs UNMODIFIED upstream tau2-bench** (sierra-research, latest `main`), seeds the
capability from tau2's own source, adds the tailoring the chosen arm needs FROM OUTSIDE the
benchmark, runs the `cap-evolve check` gate, then the optimize → gate → sealed-test → report loop
with a live dashboard. The delivery arm is ONE choice you make up front — `direct` or
`intervention: blackbox`. Everything below is the input intake needs.

```text
Use only information in this current cap-evolve repo root folder on the current Git branch, plus
the clones this prompt tells you to create. Do not use external documentation, web searches,
prior knowledge, other repositories, branches, tags, or commits. If required information is
missing, state that it is missing rather than guessing.
Start with RUN.md §1 and follow it. SKIP only RUN.md's INSTALL parts (§0 plugin loading,
./install.sh, pip install ./core): #2 below replaces them. The pipeline itself (RUN.md §3–§5:
baseline, algorithm, finalize, report) is run by `.venv/bin/cap-evolve run` (#6).
`cap-evolve` exists only inside the project venv: ALWAYS call it as `.venv/bin/cap-evolve`.

SOURCES YOU MAY READ — and nothing else:
  RUN.md; core/; skills/ (the core skills + skills/interventions/llm-proxies/blackbox/);
  templates/project/ (the generic project scaffold); docs/ADAPTER_CONTRACT.md (ignore its pointers
  into examples/); this prompt;
  vendor/tau2-bench (the clone from #2); [blackbox] vendor/skillberry-store and
  vendor/skillberry-agent once the intervention skill has provisioned them (#2b).
  Do NOT read anything under examples/ (other than this prompt), any tau2-specific template, any
  other branch, or any earlier tau2 project or run dir — they encode a different (forked) tau2
  and would mislead you.

RULES OF ENGAGEMENT — they apply to EVERY step below:
  R1 ORDER. Do the work in this order; do not start a step until the previous step's CHECK
     passed:
       0 ASK the arm and wait (#0)
       1 venv (#2)              2 clone + SHA rule (#2)        3 install (#2)
       4 resolve the models from shell/.env, no network (#3b models)
       5 scaffold (#2)          6 SHA record + splits (#2)
       7 fill capevolve.yaml + capevolve.smoke.yaml (#0, #1, #5, #6) — CHECK #0
       8 seam LOCATE, by grep (#2c)                            9 seed (#1)
      10 tailoring module + adapter (#2c, #3)                 11 install() ASSERTs (#2c CHECK)
      12 author optimizer/INSTRUCTIONS.md — CHECK #5           13 the gate (#3 CHECK)
      14 [blackbox] .env keys, provision + start the store, seed deploy, env service (#2b)
      15 gateway probe (#3b)    16 smoke run (#6)              17 budget run (#6)
  R2 CHECK. Every step ends with a CHECK and its EXPECTED result. Run the CHECK. A step is done
     only when the CHECK shows the EXPECTED result.
  R3 RETRY BOUND. If a CHECK fails: read the diagnostic the step names, and #7, fix the cause,
     run the CHECK again. If the SAME CHECK fails a SECOND time with the same error, STOP and
     report: the step, the command, the full error. Never try variations blindly, never loosen a
     CHECK to make it pass, never skip ahead.
  R4 EXACT VALUES. Every name, port, header, env var, path and signature below is literal. Copy
     it; do not paraphrase it, and do not substitute a value you remember.
  R5 READ, DON'T RECALL. When a step names a file in a clone, READ that file before writing code
     against it. tau2 changes on main; your memory of it is not a source. The Skillberry facts in
     #2c B2–B5 are authoritative AS WRITTEN here.
  R6 ASK AND WAIT only at these points: the arm (#0); intake's single confirm of the resolved
     spec (#2 scaffold); a missing credential (#3b); a clone whose SHA differs from upstream (#2);
     a seam whose ROLE you cannot locate (#2c); a CHECK that failed twice (R3). Decide everything
     else from this prompt.
  R7 NEVER: fork tau2, edit any file under vendor/tau2-bench, monkeypatch litellm, use tau2's
     deprecated flat-argument `tau2.run.run_tasks(...)`, use a LangChain agent, disconnect in
     `agent.stop()`, merge both trajectories after evaluation, pair tool results by id in a tau2
     or env-service trajectory (their ids are empty), put a REAL API key in `llm_args`, or turn
     on tau2's `verbose_logs`.

Follow RUN.md to run a cap-evolve optimization. Onboard this as a brand-new
benchmark — the intake/integration step CLONES + INSTALLS it (it does not exist yet).
Here is everything intake needs:

# 0. DELIVERY ARM  (pick EXACTLY ONE)
- glossary (these words mean exactly this everywhere below):
                  arm          — how a candidate reaches the model: `direct` or `blackbox`
                  primitive    — one of tau2's 14 airline tools, as tau2 implements it
                  wrapper      — [blackbox] the skill-package tool the model sees; it calls
                                 a primitive by bare name
                  env service  — tau2's own EnvironmentManager (HTTP, port 8004), see #2b
                  proxy        — the Skillberry Proxy-Agent (SPA, port 7000) + Skillberry
                                 Store (port 8000), owned by the blackbox intervention skill
                  sentinel     — the agent model name `ibm/skillberry-local`, routed to the
                                 proxy instead of the gateway
                  seam         — one tau2 API the tailoring hooks; all listed in #2c
                  tailoring    — OUR module beside the adapter that hooks the seams; the clone
                                 itself is never edited
                  trial        — one (task, trial-index) rollout; one tau2 worker thread runs it
                  phase        — baseline, the algorithm loop, finalize: each runs in a FRESH
                                 process; the loop's iterations SHARE one process (so module
                                 state set by apply() is replaced, never assumed fresh)
- the CAPABILITY is the same either way — the airline agent's TOOL SURFACE only (tools, not the
                system prompt / policy). Only the delivery differs:
                  direct   — no `intervention:` line in capevolve.yaml
                  blackbox — the top-level lines `intervention: blackbox` and
                             `skill_name: my_skill` in capevolve.yaml (the run's preflight needs
                             `skill_name` to start the proxy)
- ASK ME WHICH ONE and WAIT for the answer: `direct` or `blackbox`. Ask it as a PLAIN question
                with ONE SHORT SENTENCE per option — "direct: the runner loads the candidate's
                tool code in its own process, no extra services" / "blackbox: the candidate
                becomes a store skill the proxy injects, and needs the Skillberry stack plus
                tau2's environment service". No preview panes, option cards, or spec dumps.
                Prepare ONLY the arm I pick — one spec, one capability_path, one seed. Do NOT
                prepare both and do not scaffold the other "for later". The second arm is a
                SEPARATE onboarding in its own project (intake `--base`), done only if I ask.
- for `intervention: blackbox`, FOLLOW THE INTERVENTION SKILL —
                `skills/interventions/llm-proxies/blackbox/SKILL.md` — for provisioning, service
                lifecycle, store import order, and the per-candidate deploy. Do NOT re-derive any
                of that, and do not hand-roll a copy of blackbox_env. The skill says the runner
                must be "SPA-aware"; vanilla tau2 is NOT, and #2c is how you make it so FROM
                OUTSIDE. The seed shape is in #1; the optimizer's rules are in #5.
- CHECK:        `grep -nE "^(intervention|skill_name):" .capevolve/project/capevolve.yaml`
                EXPECTED: direct → no output; blackbox → `intervention: blackbox` and
                `skill_name: my_skill`.

# 1. CAPABILITY TO OPTIMIZE  (a copy is edited each iteration; the original is never touched)
- what:         the airline agent's TOOL SURFACE only (tools; the system prompt / policy is NOT
                part of the capability and is NOT edited by the optimizer)
- source:       READ vendor/tau2-bench/src/tau2/domains/airline/tools.py, class `AirlineTools`.
                The primitives are its methods decorated with an ACTIVE `@is_tool(...)` (a
                commented-out `# @is_tool` does not count). As of TAU2_REFERENCE_SHA there are 14:
                  book_reservation, calculate, cancel_reservation, get_flight_status,
                  get_reservation_details, get_user_details, list_all_airports,
                  search_direct_flight, search_onestop_flight, send_certificate,
                  transfer_to_human_agents, update_reservation_baggages,
                  update_reservation_flights, update_reservation_passengers
                The types they use are in vendor/tau2-bench/src/tau2/domains/airline/data_model.py.
- CHECK:        `grep -cE "^    @is_tool" vendor/tau2-bench/src/tau2/domains/airline/tools.py`
                EXPECTED: 14. Any other count → the toolkit changed upstream: list the active
                tools you found and ASK (R6) before seeding.
- spec keys (both arms): capabilities: [tools]; capability_path: seed_capability;
                capability_sources: [seed_capability/reference/data_model.py] — the path is
                relative to the PROJECT dir; a wrong path is skipped silently and the optimizer
                gets no data model; actions: [edit].
- IF direct:    create under .capevolve/project/seed_capability/:
                  tools/tools.py          a BYTE-FOR-BYTE copy of tau2's airline tools.py (its
                                          imports, every private `_get_*` / `_payment_for_update`
                                          helper, and the 14 tools), then append one line:
                                          `REMOVE_TOOLS: set[str] = set()`
                  reference/data_model.py byte-for-byte copy of tau2's airline data_model.py
                tools.py keeps tau2's own imports: the direct arm runs it in tau2's process.
                protected_paths: ["reference/*"].
                CHECK: `diff vendor/tau2-bench/src/tau2/domains/airline/data_model.py
                .capevolve/project/seed_capability/reference/data_model.py` prints nothing;
                `diff` of tools.py against tau2's shows ONLY the appended REMOVE_TOOLS line; a
                `.venv/bin/python -c` that imports tools/tools.py by path and builds
                `AirlineTools(FlightDB.load(AIRLINE_DB_PATH))` returns 14 from `len(.get_tools())`.
                EXPECTED: all three.
- IF blackbox:  create under .capevolve/project/seed_capability/:
                  my_skill/
                    SKILL.md              EMPTY FILE (zero bytes)
                    scripts/<tool>.py     one wrapper per primitive, 14 files
                  primitive_tools/
                    functions.py          the 14 frozen primitives
                  reference/
                    data_model.py         byte-for-byte copy of tau2's airline data_model.py
                Breaking any rule below silently produces a broken tool rather than an error.
                (a) WRAPPER `my_skill/scripts/<tool>.py`: ONE public top-level `def`, named like
                    the file, its `def` line on ONE line. Every top-level `def` becomes its own
                    tool, so a helper must be nested and `_`-prefixed.
                (b) Copy from tau2's method: the parameter list WITHOUT `self`, the parameter
                    NAMES and types, and the docstring — verbatim. Do NOT copy the `@is_tool`
                    decorator, the return annotation (`-> Reservation`), or the BODY: the body
                    stays in tau2 and runs inside the env service. The wrapper body is one line:
                    `return env_<tool>(<each param>=<each param>)`. The scorer matches actions by
                    name and argument, and the published schema is built from signature +
                    docstring, so both must match tau2's tool.
                (c) A STRUCTURED parameter (enum, object, list of objects) keeps its type: copy
                    the `Literal[...]` aliases and the Pydantic `BaseModel` classes it uses from
                    data_model.py into the SAME wrapper file, annotated `List[Model | dict]` where
                    tau2 has a list of models. Imports are only `typing` and `pydantic`; never a
                    `tau2.*` import; no self-referential model. Otherwise the published schema is
                    flat and the model guesses the field names.
                (d) PRIMITIVES `primitive_tools/functions.py`: one `env_<tool>` per primitive,
                    same parameter names in PLAIN types (str/int/list/dict), same docstring. Each
                    body is `return _make_api_call(<each param>=<each param>)`. ONE private
                    helper `_make_api_call(**kwargs)`:
                      - tool name = the CALLING frame's function name with `env_` stripped
                        (`sys._getframe(1).f_code.co_name`);
                      - `env_id` = `globals().get("env_id")` — the store injects it per call from
                        the `skillberry-context-env_id` header; if absent, raise RuntimeError
                        "no env_id in the execution context";
                      - POST `{SPA_REMOTE_ENV_URL or http://127.0.0.1:8004}/{env_id}/tools/{tool}`
                        with body `json.dumps({"name": <tool>, "arguments": kwargs},
                        default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o))`
                        and header `Content-Type: application/json` (#2b);
                      - non-200 → raise RuntimeError naming the tool and status;
                      - 200 → take `content` from the JSON response; if it parses as JSON return
                        the parsed value, else return the string (a tool-level error message).
                    Use only the standard library (json, os, sys, urllib.request).
                (e) `my_skill/SKILL.md` stays EMPTY, so THE SEED IS NEUTRAL. The optimizer edits
                    only `my_skill/scripts/<tool>.py`.
                    protected_paths: ["primitive_tools/*", "my_skill/SKILL.md", "reference/*"].
                CHECK: 14 files under my_skill/scripts/, each with exactly one top-level `def`
                named like the file (`grep -c "^def " <file>` = 1); `wc -c my_skill/SKILL.md` = 0;
                the data_model `diff` prints nothing; `functions.py` defines 14 `env_` functions
                (`grep -c "^def env_"` = 14). EXPECTED: all four.

# 2. BENCHMARK / DATASET  (the eval) — INSTALL IT DURING INTAKE
- TAU2_REFERENCE_SHA = 4ce7c0397c1eb65c9bbe59aeacfe1ca44a1cd699
                (upstream `main` on 2026-10-06, tau2 1.0.1). Every LAST-KNOWN name and signature in
                this prompt is as of this commit.
- tools needed: `git`, `uv`, `curl`; [blackbox] also `make` (the intervention skill's
                provisioning uses it). CHECK: `command -v git uv curl` (+ `make`) prints a path for
                each. EXPECTED: no missing tool.
- venv:         tau2 needs Python >=3.12,<3.14. Create the project venv with
                  uv venv -p 3.12 .venv
                CHECK: `.venv/bin/python --version` → EXPECTED: Python 3.12.x
- skills dir:   `export CAPEVOLVE_SKILLS_DIR=$PWD/skills` in EVERY shell that runs cap-evolve.
                Read skills from the repo's `skills/`, not from a globally installed Skill tool.
- repo:         https://github.com/sierra-research/tau2-bench   branch `main` → vendor/tau2-bench
- CLONE RULE — always compare before cloning:
                  UPSTREAM_SHA = first field of
                    git ls-remote https://github.com/sierra-research/tau2-bench main
                  no vendor/tau2-bench           → git clone the repo into vendor/tau2-bench and
                                                   check out UPSTREAM_SHA
                  HEAD == UPSTREAM_SHA           → keep the clone; do NOT re-clone
                  HEAD != UPSTREAM_SHA           → ASK ME AND WAIT (R6). Show both SHAs and say a
                                                   re-clone means re-tailoring (#2c). On "yes":
                                                   delete vendor/tau2-bench, clone fresh at
                                                   UPSTREAM_SHA, reinstall. On "no": keep it.
                Do this ONLY at onboarding — never between baseline and finalize; changing the
                benchmark mid-project makes the candidates incomparable.
                CHECK: `git -C vendor/tau2-bench rev-parse HEAD` → EXPECTED: the SHA you chose;
                and `git -C vendor/tau2-bench status --porcelain` → EXPECTED: no output. A dirty
                clone is NOT upstream: treat it as "!= TAU2_REFERENCE_SHA" and ASK (R6).
- install:      VIRTUAL_ENV=.venv uv pip install -e core -e vendor/tau2-bench "websockets>=13.0"
                (`import tau2` needs websockets, which upstream declares only in its `voice` extra;
                without it the CHECK below fails with ModuleNotFoundError: websockets.)
                CHECK: `.venv/bin/python -c "from tau2.domains.airline.environment import
                get_tasks; print(len(get_tasks('base')))"` → EXPECTED: 50
- scaffold:     `.venv/bin/python skills/phases/intake/scripts/run.py --base .capevolve --workdir .`
                creates .capevolve/project/ from templates/project/. IGNORE the `discovered` list
                it prints (it scans files SOURCES forbids). Intake's interview is PRE-ANSWERED by
                this prompt — do NOT ask its numbered question batch and do NOT run its
                `gh auth status` step; ignore its pointer to an example's setup.sh. Its ONE
                "confirm before scaffolding" echo of the resolved spec stays (R6). Values:
                  orchestration_mode: deterministic     memory_skill: md-files
                  github_integration: false             metric_primary: ""   (the reward)
                  target_model: <the GATEWAY agent model, bare (no `openai/` prefix) — on BOTH
                                 arms; on blackbox it is the model behind SPA_MODEL_NAME, never
                                 the sentinel>
                  dataset_source: adapter               every other key: this prompt's #1–#6
                CHECK: `.capevolve/project/capevolve.yaml` and
                `.capevolve/project/adapters/adapter.py` exist. EXPECTED: both.
- SHA RECORD:   write the SHA in use to vendor/tau2-bench.COMMIT and to
                .capevolve/project/PROJECT.md (the runner section), with one of
                "= TAU2_REFERENCE_SHA" or "!= TAU2_REFERENCE_SHA". If it is "!=", every seam in
                #2c MUST go through its LOCATE procedure before use (re-tailoring).
                CHECK: `cat vendor/tau2-bench.COMMIT` equals `git -C vendor/tau2-bench rev-parse
                HEAD`, and PROJECT.md contains that SHA. EXPECTED: both.
- domain:       direct → "airline_candidate";  blackbox → "airline_skillberry".
                BOTH are registered by OUR tailoring module (#2c) through tau2's public
                `register_domain` / `register_tasks`; tau2 itself only knows "airline".
- tasks:        dataset_source "adapter" — all 50 airline tasks from
                tau2.domains.airline.environment.get_tasks("base"); no network in tasks().
- splits:       THREE split files in .capevolve/project/, each no-holdout (train = val = test; the
                engine logs a splits_warning and the report flags the test number as a fit
                metric). Each is JSON `{"train": [...], "val": [...], "test": [...]}` with string
                task ids:
                  split_ids_smoke.json   ["9"]                                (the smoke, #6)
                  split_ids_budget.json  ["8","10","20","23","35","42","44"]  (the budget run, #6)
                  split_ids.json         all 50 ids                           (a later full run)

# 2b. THE BLACKBOX STACK + THE BENCHMARK'S ENVIRONMENT SERVICE  [BLACKBOX ONLY — skip for direct]
- .env FIRST:   add these to the repo-root `.env`, without touching existing keys, BEFORE the
                store starts (the store copies the environment once, at start):
                  SPA_REMOTE_ENV_URL=http://127.0.0.1:8004   (the store's primitives read it)
                  SPA_MODEL_NAME=openai/<the resolved agent model, #3b>
                TAU2_AGENT_MODEL is the ONE source of the agent model. If `.env` already has a
                SPA_MODEL_NAME that is not `openai/<TAU2_AGENT_MODEL>`, ASK (R6) — do not
                pick one. If TAU2_AGENT_MODEL is unset but SPA_MODEL_NAME is set, the agent
                model is SPA_MODEL_NAME without its `openai/` prefix.
- the stack:    provisioning and lifecycle belong to the intervention skill. From the project
                venv, in a script that inserts skills/interventions/llm-proxies/blackbox/scripts
                on sys.path:
                  import blackbox_env
                  blackbox_env.provision()       # clones + installs store and proxy, idempotent
                  blackbox_env.start_store()
                If a preflight message says "Run the example's setup.sh first", it means THIS step.
                CHECK: `.venv/bin/python skills/interventions/llm-proxies/blackbox/scripts/run.py
                --json` → EXPECTED: store.provisioned, agent.provisioned and store.healthy are
                true. IGNORE its exit code here: it exits 1 while the proxy is not yet running.
- seed deploy (once, so the proxy has a skill to bind when the run's preflight starts it):
                in the same script, with PROTECT = blackbox_env.Protection(tags=(
                "tau2_airline_primitives",)):
                  blackbox_env.import_standalone_tools(
                      ".capevolve/project/seed_capability/primitive_tools/functions.py",
                      tags=("tau2_airline_primitives",))
                  blackbox_env.reset_store_to_skill(
                      ".capevolve/project/seed_capability/my_skill", "my_skill", PROTECT)
                CHECK: `len(PROTECT.present_names())` == 14; and
                `curl -s "http://127.0.0.1:$(.venv/bin/python -c 'import sys; sys.path.insert(0,
                "skills/interventions/llm-proxies/blackbox/scripts"); import blackbox_env;
                print(blackbox_env.store_port())')/skills/my_skill?fields=wide"` returns JSON whose
                `tool_uuids` has 14 entries. EXPECTED: both. (The proxy silently falls back to
                searching the store when the named skill is missing — this CHECK catches it.)
- the env service — tau2's OWN `EnvironmentManager`
                (vendor/tau2-bench/src/tau2/orchestrator/environment_manager.py), UNMODIFIED. Only
                the launcher is ours. It holds one airline environment per `env_id` and records
                every tool call made on it.
- start it:     port 8004, from the project venv:
                  LITELLM_LOCAL_MODEL_COST_MAP=True nohup .venv/bin/python -c "import asyncio; from tau2.orchestrator.environment_manager import EnvironmentManager; asyncio.run(EnvironmentManager(host='127.0.0.1', port=8004).run())" > /tmp/env_manager.log 2>&1 &
                (ONE line: an indented `-c` body is a Python IndentationError.)
                ~10s to start; POLL, don't sleep. LITELLM_LOCAL_MODEL_COST_MAP=True skips
                litellm's remote cost-map fetch, which otherwise stalls startup — export it in
                EVERY shell that runs cap-evolve too (the adapter imports tau2 and litellm).
                CHECK: `curl -s http://127.0.0.1:8004/status` → EXPECTED: {"status":"ok"}
                (`/status` is a health check only; it does not count environments.)
- routes (LAST-KNOWN; LOCATE: `grep -n "@self.app\." vendor/tau2-bench/src/tau2/orchestrator/
                environment_manager.py`):
                  POST /start_environment            body {"domain": "airline"}  → {"env_id": "<uuid>"}
                  POST /{env_id}/tools/{tool_name}   body {"name": <tool>, "arguments": {...}}
                                                     → a ToolMessage; `content` is a string
                  GET  /{env_id}/trajectory          → {"trajectory": [message dicts]}
                  GET  /{env_id}/info                → 200 while open; error once stopped
                  POST /{env_id}/stop_environment    → {"status": "success"}; deletes the env and
                                                       its trajectory
                The start body field is `domain` (the class docstring says `domain_name`; the
                request model `StartEnvironmentRequest` says `domain` — the model wins).

# 2c. TAILORING — FROM OUTSIDE THE BENCHMARK, NEVER INSIDE
- the rule:     vanilla tau2 lacks what each arm needs. Supply it from a module BESIDE the
                adapter — .capevolve/project/adapters/tau2_tailoring.py — through tau2's public
                extension points, plus a few narrow wrappers where tau2 offers none. The clone
                stays byte-identical to upstream (R7). WHY: an edited benchmark is no longer the
                benchmark; its numbers stop being comparable to anyone else's tau2 results.
- module contract:
                - importing it has NO side effects (no registration, no network): `cap-evolve
                  check` imports the adapter offline;
                - ONE entry point `install(arm)` called from the adapter's apply(); IDEMPOTENT,
                  because every phase is a fresh process and EACH registration raises on a
                  duplicate name — guard each one separately:
                    register_domain        only if name not in registry.get_domains()
                    register_tasks         only if name not in registry.get_task_sets()
                    register_agent_factory only if registry.get_agent_factory(name) is None
                    every wrapper          only if the target is not already our wrapper
                - `install()` first runs the ASSERTs of S1–S10 (all offline) and raises naming
                  the seam and the SHA in use; apply() catches it (#3). S11 needs the running
                  service and is asserted by the #2b CHECK instead. A seam you cannot assert,
                  you may not use.
- SEAM TABLE — the ONLY place a tau2 API is named. Paths are under vendor/tau2-bench/src/tau2/.
                Before using a seam, run its LOCATE. If LOCATE shows the LAST-KNOWN name and
                signature, use it. If not (tau2 moved on main): (1) find the API that fills the
                same ROLE — grep for the LANDMARKS its LAST-KNOWN text names (a caller, a nested
                function, a module), the package's `__init__` exports, and docstrings; (2) confirm
                it by its signature AND by one call site inside tau2; (3) use it, record
                "seam <id>: <LAST-KNOWN> → <found>" in PROJECT.md, and SUBSTITUTE the found name
                everywhere this prompt uses the old one (that seam's ASSERT, the T/B rules, #7) —
                R4 yields to a recorded replacement; (4) if nothing fills the ROLE, STOP and
                ASK (R6). Never guess a signature, never fall back to a
                deprecated API.
  S1 batch runner
                ROLE      run a list of tasks for N trials from a run config; write results to one
                          JSON file
                LAST-KNOWN tau2.runner.run_tasks(config, tasks, *, save_path=None, save_dir=None,
                          evaluation_type=EvaluationType.ALL, console_display=True,
                          results_format="json") -> Results        (runner/batch.py)
                LOCATE    grep -n "^def run_tasks" -A10 runner/batch.py
                ASSERT    inspect.signature(tau2.runner.run_tasks) has `config`, `tasks`, `save_path`
  S2 run config
                ROLE      the text-mode run configuration
                LAST-KNOWN tau2.data_model.simulation.TextRunConfig with fields domain, agent,
                          llm_agent, llm_args_agent, user, llm_user, llm_args_user, num_trials,
                          max_steps, max_errors, max_concurrency, seed, verbose_logs, workers
                LOCATE    grep -n "^class TextRunConfig\|^class BaseRunConfig" data_model/simulation.py
                ASSERT    those field names are in TextRunConfig.model_fields
  S3 registry
                ROLE      register an environment factory, a task loader and an agent factory by name
                LAST-KNOWN from tau2.registry import registry
                          registry.register_domain(get_environment, name)
                          registry.register_tasks(get_tasks, name, get_task_splits=None)
                          registry.register_agent_factory(factory, name, task_filter=None,
                                                          metadata=None)
                          registry.get_domains(), registry.get_task_sets(),
                          registry.get_env_constructor(name), registry.get_agent_factory(name)
                LOCATE    grep -n "    def register_\|    def get_" registry.py
                ASSERT    the seven callables exist with those parameter names
  S4 agent factory call
                ROLE      how tau2 calls a registered agent factory
                LAST-KNOWN runner/build.py build_agent → factory(tools=..., domain_policy=...,
                          llm=..., llm_args=..., task=..., audio_native_config=...,
                          audio_taps_dir=...). The factory gets `task` but NOT the environment.
                          The environment is built BEFORE the agent, on the same thread
                          (build_text_orchestrator: build_environment → build_agent).
                LOCATE    grep -n "agent_factory(" -A9 runner/build.py
                ASSERT    the call passes `llm_args` and `task`
  S5 stock LLM agent
                ROLE      the stock tool-calling agent; its llm_args reach litellm unfiltered
                LAST-KNOWN tau2.agent.llm_agent.create_llm_agent(tools, domain_policy, **kwargs) →
                          LLMAgent(tools, domain_policy, llm, llm_args); every call is
                          generate(model=llm, ..., **llm_args) → litellm.completion(**kwargs)
                          (utils/llm_utils.py does `from litellm import completion`)
                LOCATE    grep -n "^def create_llm_agent" agent/llm_agent.py;
                          grep -n "response = completion(" -A6 utils/llm_utils.py
                ASSERT    OFFLINE PROOF, not inspection, exactly this:
                          1. define `class _Probe(Exception)`; save
                             `orig = tau2.utils.llm_utils.completion`;
                          2. set `tau2.utils.llm_utils.completion` to a stub that stores its
                             kwargs and raises `_Probe` (so nothing after completion runs);
                          3. agent = create_llm_agent(tools=[], domain_policy="p", llm="probe",
                             llm_args={"extra_headers": {"x-probe": "1"}});
                          4. call agent.generate_next_message(UserMessage(role="user",
                             content="hi"), agent.get_init_state()) and catch `_Probe`;
                          5. restore `orig` in a `finally`;
                          6. assert the stored kwargs["extra_headers"] == {"x-probe": "1"}
                          (UserMessage is in tau2.data_model.message)
  S6 trajectory finalize
                ROLE      the list of messages that becomes SimulationRun.messages and is replayed
                          by the evaluator
                LAST-KNOWN tau2.orchestrator.orchestrator.Orchestrator.get_trajectory(self) →
                          sorted by timestamp, turn_idx renumbered; called once from _finalize,
                          AFTER agent.stop()
                LOCATE    grep -n "def get_trajectory\|self.get_trajectory()\|self.agent.stop" orchestrator/orchestrator.py
                ASSERT    the method exists; it is the original or ours (idempotent install)
  S7 per-trial worker
                ROLE      build + run + evaluate ONE trial; called BY NAME from the batch loop
                LAST-KNOWN tau2.runner.batch.run_single_task(config, task, *, seed, evaluation_type,
                          save_dir, ...) -> SimulationRun. Inside it: build_orchestrator (env,
                          agent, user) → run_simulation (orchestrator.run, then evaluate). The
                          batch loop calls it as `return run_single_task(` inside a nested
                          `_execute`, RETRIES it on raise, and saves the result AFTER it returns.
                          When retries are exhausted it does NOT raise: it returns a placeholder
                          SimulationRun with termination_reason "infrastructure_error" and
                          reward_info None (runner/progress.py).
                LOCATE    grep -n "^def run_single_task\|return run_single_task(" runner/batch.py
                ASSERT    tau2.runner.batch.run_single_task is a function, and the batch module
                          source contains "return run_single_task("
  S8 env constructions
                ROLE      every place tau2 builds the domain environment
                LAST-KNOWN registry.get_env_constructor(<domain>) is called:
                          - ONCE per run_tasks call on the MAIN thread, before any trial
                            (run_tasks → prepare_batch → get_info → get_environment_info,
                            runner/helpers.py);
                          - per trial, inside S7: the rollout env (build_environment), then the
                            evaluator 3 more times with <the rollout env's get_domain_name()>:
                            tool types (evaluator/evaluator.py), then inside
                            EnvironmentEvaluator.calculate_reward (a classmethod,
                            evaluator/evaluator_env.py) PREDICTED = constructor(solo_mode=...,
                            **env_kwargs), replayed with the trial's messages, then GOLD =
                            constructor(**env_kwargs), replayed with the task's expected actions.
                          A failed gold action is only a warning.
                LOCATE    grep -n "environment_constructor(\|get_env_constructor(" evaluator/*.py runner/helpers.py
                ASSERT    in inspect.getsource(EnvironmentEvaluator.calculate_reward),
                          "predicted_environment = environment_constructor(" occurs BEFORE
                          "gold_environment = environment_constructor(" — on the ORIGINAL: T2's
                          wrapper MUST use functools.wraps, so inspect follows `__wrapped__` on a
                          second install()
  S9 replay
                ROLE      how the evaluator rebuilds DB state from messages
                LAST-KNOWN Environment.set_state(..., message_history, strict=True)
                          (environment/environment.py): every ToolMessage must IMMEDIATELY
                          follow the message holding its call, with ToolMessage.id ==
                          ToolCall.id (empty == empty is fine); a replayed mutating call whose
                          output differs from the recorded ToolMessage RAISES; a call to an
                          unknown tool replays as a no-op. Its three error strings:
                          "Tool call id mismatch", "Tool message expected",
                          "Tool message not expected"
                LOCATE    grep -n "def set_state\|Tool call id mismatch\|Tool message expected\|Tool message not expected" environment/environment.py
                ASSERT    the three strings exist
  S10 messages
                ROLE      the message types a merged trajectory must contain
                LAST-KNOWN tau2.data_model.message: AssistantMessage, ToolMessage, ToolCall(id="",
                          name, arguments, requestor="assistant"); each message has `timestamp`
                          and `turn_idx`
                LOCATE    grep -n "^class AssistantMessage\|^class ToolMessage\|^class ToolCall" data_model/message.py
                ASSERT    the three classes import
  S11 env service routes
                ROLE / LAST-KNOWN / LOCATE: #2b
                ASSERT    by the #2b CHECK (the service must be running): /status answers
                          {"status":"ok"}. NOT part of install().
- DIRECT ARM tailoring (install("direct")):
                T1 domain "airline_candidate": register_domain(factory, "airline_candidate") and
                   register_tasks(<tau2 airline get_tasks>, "airline_candidate"). The factory
                   signature is `(db=None, solo_mode=False, **env_kwargs)`; it raises on
                   solo_mode (as tau2's airline factory does); it builds
                   Environment(domain_name="airline_candidate", policy=<tau2's policy.md text>,
                   tools=<the CURRENT candidate's AirlineTools on a FRESHLY loaded FlightDB>).
                   FRESH DB on every construction — WHY: trials run in parallel; a shared DB
                   leaks state between them and corrupts the DB check.
                   "Current candidate" = a module-level path that apply() sets; the factory
                   execs tools/tools.py fresh (importlib, a unique module name per load) so an
                   edit is always picked up. REMOVE_TOOLS is honoured by a subclass that filters
                   the `tools` property (what live tool calls dispatch through), get_tools(self,
                   include=None) (keep the `include` parameter), and has_tool() — never by
                   deleting attributes.
                T2 GOLD IS PRISTINE: wrap EnvironmentEvaluator.calculate_reward (S8) so that,
                   for the duration of one call, a thread-local scope counts constructions: the
                   1st (PREDICTED) gets the candidate env; the 2nd (GOLD) gets tau2's own
                   `registry.get_env_constructor("airline")()`. Re-wrap it as a classmethod.
                   WHY: otherwise the task's expected outcome is computed with the CANDIDATE's
                   tools — a candidate that breaks or removes a write tool changes BOTH sides of
                   the DB check and scores as if correct. Pristine gold also scores the two arms
                   the same way.
                T3 the agent stays tau2's stock "llm_agent" (S5) with the gateway model (#3b).
- BLACKBOX ARM tailoring (install("blackbox")) — one trial = one SESSION:
                B0 SCOPE. A thread-local session scope with THREE states:
                     IDLE   — no trial in progress (the default, and the main thread always);
                     ARMED  — the B5 wrapper has started a trial attempt; holds task_id, seed and
                              attempt (B5); no env_id yet;
                     OPEN   — the trial's remote env exists; holds env_id, task_id, seed, attempt.
                B1 SESSION START + remote-env domain "airline_skillberry":
                   register_domain(factory, "airline_skillberry") + register_tasks(<tau2 airline
                   get_tasks>, "airline_skillberry"). Factory `(db=None, solo_mode=False,
                   **env_kwargs)`, raises on solo_mode. On each construction:
                     ARMED → POST /start_environment {"domain": "airline"} (#2b) → env_id; set the
                             scope OPEN with env_id; append one line to the current session log
                             (B5); return Environment(domain_name="airline_skillberry",
                             policy=<tau2 policy.md>, tools=tau2's own AirlineTools on a fresh
                             FlightDB) with `env_id` set as an attribute on it.
                     IDLE or OPEN → return the same kind of local env with NO POST and no env_id
                             (this covers S8's main-thread get_info build and the evaluator's
                             three builds).
                   WHY: unguarded, every construction POSTs another /start_environment — orphan
                   remote envs, and a clobbered env_id.
                   Tools stay LOCAL tau2 AirlineTools: the evaluator replays the merged
                   primitive calls (B4) on them to rebuild the DB.
                B2 CONTEXT HEADERS: register_agent_factory(factory, "llm_agent_skillberry"). The
                   factory reads env_id from the OPEN scope (S4: the env is built before the
                   agent, on the same thread) and task.id from its `task` argument, then returns
                   create_llm_agent(tools, domain_policy, llm=..., llm_args=<merged>) (S5) where
                   <merged> = the config's llm_args plus
                     "extra_headers": {
                       "skillberry-context-plugin":  "tau2",
                       "skillberry-context-env_id":  <env_id>,
                       "skillberry-context-task_id": <task.id> }
                   WHY: the store routes each tool call to its trial's env by these headers; a
                   missing header fails the call ("no env_id in the execution context").
                   The agent's own `tools` (tau2's 14) still go in the request; the proxy
                   ignores them (the intervention skill starts it with USE_AGENT_TOOLS=false) and
                   serves the skill's wrappers instead.
                B3 SENTINEL ROUTING through the same llm_args (S5), no litellm patch:
                     llm_agent      = "ibm/skillberry-local"
                     llm_args_agent = {"custom_llm_provider": "openai",
                                       "base_url": blackbox_env.spa_base_url(),
                                       "api_key": "EMPTY", "temperature": 0.0}
                   "EMPTY" is a placeholder the proxy ignores, not a credential (R7). The USER
                   SIMULATOR stays on the gateway (#3b), never the proxy.
                B4 THE TWO MERGE WINDOWS — this is the single most important rule:
                   (i)  BEFORE evaluation — the env-service trajectory. Wrap
                        Orchestrator.get_trajectory (S6): if self.environment has an env_id,
                        GET /{env_id}/trajectory (#2b), parse each dict with
                        AssistantMessage(**d) / ToolMessage(**d) (S10), add them to the original
                        result, sort by timestamp, renumber turn_idx. PURE: never mutate
                        self.trajectory (a second call must not duplicate).
                   (ii) AFTER evaluation — the proxy trajectory. In the B5 wrapper, after the
                        original returns the evaluated SimulationRun: GET
                        <spa_base_url()>/trajectory with the B2 headers → {"trajectory": [dicts]};
                        let NAMES = {t.name for t in <a local airline env>.get_tools()}; DROP every
                        tool call whose name is in NAMES and every ToolMessage answering a dropped
                        call (map call id → name from the same response); drop an assistant
                        message left with no content and no calls; parse the rest with S10; add
                        to sim.messages; sort by timestamp; renumber turn_idx.
                   WHY: the primitives ran in the env service, not in tau2's env. The evaluator
                   only sees them if they are in the trajectory BEFORE it replays (S9). Merge both
                   after evaluation and the replay reconstructs nothing: db_match is false and
                   reward 0 on every trial, which looks like a bad capability, not a wiring bug.
                   The proxy trajectory carries the compound/skill calls for the optimizer to
                   read; it must NOT reach the evaluator, because its pairs would break S9's
                   strict pairing. Dropping calls whose name is in NAMES is INTENTIONAL: a seed
                   wrapper shares its primitive's name, and that primitive's call and result are
                   already in the trace from B4 (i). What survives is every NEW or renamed tool.
                B5 SESSION LIFECYCLE — wrap tau2.runner.batch.run_single_task (S7):
                     1. set the scope ARMED with task.id, the `seed` argument, and attempt = a
                        per-(task.id, seed) counter starting at 1 (a tau2 retry calls the wrapper
                        again with the same seed, so the counter counts retries);
                     2. call the original;
                     3. it returned (it raises otherwise; the infrastructure_error placeholder is
                        built OUTSIDE it, by the retry loop): do B4 (ii);
                     4. in `finally`, ALWAYS: if the scope is OPEN, in this order
                          POST <spa_base_url()>/disconnect with the B2 headers
                          POST /{env_id}/stop_environment (#2b)
                        and then, whatever the state, set the scope IDLE.
                   Every network call in steps 3–4 is wrapped in try/except and logged; the
                   wrapper re-raises ONLY the original's own exception. WHY: S7 RETRIES on raise —
                   a failure of OUR bookkeeping must degrade the trace, not re-run the trial.
                   Do NOT use agent.stop() for any of this: it runs BEFORE get_trajectory (S6).
                   SESSION LOG: ONE log file per run_tasks call, named after that call's results
                   file — `<save_path dir>/started_env_ids_<YYYYmmdd_HHMMSS>_<pid>.txt`, the same
                   stamp as #4b. The adapter sets the tailoring module's log path right before
                   each run_tasks call. Each line is `<task_id> <seed>-<attempt> <env_id>`. The
                   file outlives the process. After the batch, a SWEEP stops every env_id in THAT
                   call's log that still answers GET /{env_id}/info with 200.
                   WHY: tau2's Skillberry fork never stopped the env — sessions piled up and the
                   service held one DB per open session.
                CHECK (after the smoke, #6): in the EARLIEST-stamped log under
                <run_dir>/native_sims/seed/ (the baseline call), each line is one trial ATTEMPT:
                the number of lines per `<task_id> <seed>` equals that trial's highest attempt
                number (1 when tau2 did not retry); every env_id in it answers
                GET /{env_id}/info with non-200 (stopped); and at least one trial has
                reward_info.db_check.db_match == true. EXPECTED: all three.
- CHECK (R1 step 11, offline, no services): call `install(<arm>)` twice in one process; neither
                call raises; registry.get_domains() contains the arm's domain; [blackbox]
                registry.get_agent_factory("llm_agent_skillberry") is not None. EXPECTED: all hold.

# 3. RUNNER  (the agent under test) — the adapter, .capevolve/project/adapters/adapter.py
- required methods (core/cap_evolve/adapter.py; `cap-evolve check` refuses a stub):
                tasks(split), run_target(task, ctx, *, seed=0), score(task, rollout). Implement
                run_target as `self.run_trials([task], ctx, n_trials=1, base_seed=seed)[task.id][0]`.
- how to run:   tau2's batch runner S1 with a S2 config:
                  TextRunConfig(domain=<#2 domain>, agent=<"llm_agent" | "llm_agent_skillberry">,
                    llm_agent=<agent model>, llm_args_agent=<#3b | B3>,
                    user="user_simulator", llm_user=<user model>, llm_args_user=<#3b>,
                    num_trials=<n>, max_steps=100, max_errors=10,
                    max_concurrency=<below>, seed=<base_seed>, verbose_logs=False, workers=0)
                  run_tasks(config, <tau2 Task objects>, save_path=<#4b path>,
                            console_display=False)
                `workers=0` keeps every trial in this process — worker processes would bypass the
                in-process tailoring.
- fast eval:    implement run_trials(tasks, ctx, *, n_trials, base_seed) -> {task_id:
                [Rollout, ...]}: ALL trials in ONE run_tasks call with num_trials=n_trials, grouped
                by sim.task_id and sim.trial, returned trial-ordered (len n_trials). cap-evolve
                calls it once per candidate EVALUATION (the same candidate can be evaluated more
                than once — e.g. the seed at baseline and again at finalize). run_batch(tasks,
                ctx, *, seed) is the same with num_trials=1.
- unknown ids FIRST: before computing any path or calling run_tasks, any task id not in tau2's
                airline task set → Rollout(task_id, error="unknown task"), with no other side
                effect. WHY: `cap-evolve check` probes run_target with Task(id="__probe__") and
                ctx "." — without this guard it writes native_sims/ into the repo root.
- rollout mapping (one Rollout per SimulationRun; core/cap_evolve/types.py):
                  task_id  = sim.task_id
                  trace    = sim.model_dump(mode="json")   — the FULL simulation (messages +
                             reward_info); this is what the optimizer reads (#4b)
                  output   = the content of the last assistant message, or ""
                  cost_usd = (sim.agent_cost or 0) + (sim.user_cost or 0)
                  error    = (sim.info or {}).get("error") or "infrastructure_error" when
                             sim.termination_reason == "infrastructure_error" or
                             sim.reward_info is None; else None
                A (task, trial) missing from the results → Rollout(task_id, error="omitted").
                WHY: the harness EXCLUDES a rollout with `error` set; without it an infra failure
                is scored 0.0 as if the capability failed.
- apply():      implement the ONE arm you were asked for. Guard on the CANDIDATE'S SHAPE, not on
                the spec: direct needs tools/tools.py; blackbox needs my_skill/SKILL.md and
                primitive_tools/functions.py. Then:
                  direct   — install("direct"); set the current-candidate path (T1)
                  blackbox — install("blackbox"); then the intervention skill's deploy:
                             PROTECT = Protection(tags=("tau2_airline_primitives",));
                             if len(PROTECT.present_names()) < 14:
                               import_standalone_tools(".capevolve/project/seed_capability/primitive_tools/functions.py",
                                                       tags=("tau2_airline_primitives",));
                             reset_store_to_skill(<apply's candidate_dir>/my_skill, "my_skill", PROTECT);
                             restart_spa("my_skill", SPA_MODEL_NAME=<"openai/<agent model>">)
                apply() must NEVER raise: record the error, return; run_batch/run_trials then
                return errored rollouts, so the harness EXCLUDES the candidate instead of scoring
                it 0.0.
- models:       [direct] agent = the gateway model (#3b). [blackbox] agent = the sentinel (B3);
                the PROXY forwards to SPA_MODEL_NAME, which MUST be the same gateway model in
                litellm form `openai/<model>`, passed explicitly to restart_spa as above — unset,
                the proxy silently uses its built-in default `openai/gpt-oss-120b`. The user
                simulator is ALWAYS the gateway model (#3b), on both arms.
- concurrency:  max_concurrency 125 on direct; 4 on blackbox (every agent call funnels through one
                proxy and one store process).
- sentinel cost: litellm has no price for `ibm/skillberry-local`; register it once with
                litellm.register_model({"ibm/skillberry-local": {"input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0, "litellm_provider": "openai", "mode": "chat"}}).
- CHECK (the gate): `.venv/bin/python skills/phases/implement-and-check/scripts/run.py
                --project .capevolve/project` — it runs `cap-evolve check` AND the instructions
                render self-test. EXPECTED: exit code 0 and the printed JSON has `"ok": true`.

# 3b. ENVIRONMENT — LLM ACCESS  (the run owner's environment supplies this; do not hardcode)
- endpoint:     an OpenAI-COMPATIBLE gateway the run owner configures — no host is fixed here.
- credentials:  OPENAI_BASE_URL and OPENAI_API_BASE (same value; litellm reads either) and
                OPENAI_API_KEY, in the repo-root `.env`. Load `.env` in the adapter with a small
                loader: walk up from the adapter file to the first `.env`, parse KEY=VALUE lines
                (skip blanks and `#`), strip quotes, `os.environ.setdefault` each — no python-dotenv.
                NEVER hardcode an endpoint or key, never invent one. If any of the three is missing, ASK AND
                WAIT (R6): a wrong value 401s/404s every rollout and the baseline is a row of zeros
                that reads as a bad capability.
- llm_args:     gateway calls use {"api_base": <OPENAI_BASE_URL>, "temperature": 0.0} and NO
                api_key — litellm reads OPENAI_API_KEY from the environment on the `openai/`
                route. WHY: tau2 records the run config's llm_args in the results file, which is
                copied to the optimizer and committed; a key there becomes a committed secret.
- models:       TAU2_AGENT_MODEL / TAU2_USER_MODEL (and, on blackbox, SPA_MODEL_NAME) from the
                shell or the repo `.env` WIN. Precedence: shell > `.env` > this prompt.
                `aws/gpt-oss-120b` is only the fallback for an unset key, and the gateway may not
                serve it. Route as the litellm string `openai/<model>`; normalize ONCE and
                idempotently — `openai/openai/…` 404s. Ids are gateway ALIASES and CASE-SENSITIVE.
                Record the resolved models in PROJECT.md.
- VERIFY BEFORE SPENDING: for EACH distinct resolved model (agent and user simulator), one
                completion through litellm, exactly as tau2 will call it:
                  .venv/bin/python -c "import litellm, os; r = litellm.completion(
                  model='openai/<model>', api_base=os.environ['OPENAI_BASE_URL'],
                  messages=[{'role': 'user', 'content': 'Say OK.'}], max_tokens=2000);
                  print(repr(r.choices[0].message.content))"
                (load .env first; max_tokens 2000 because a reasoning model returns HTTP 200 with
                EMPTY content on a tight cap). CHECK: no exception and a non-empty string printed.
                EXPECTED: both, for every model.
- TLS:          if the endpoint's certificate is not trusted, point at the right CA bundle and
                record it in PROJECT.md. Never silently disable verification.
- NEVER LEAK CREDENTIALS into logs, persisted trajectories, PROCESS.md / JOURNAL.md, or the run
                record: cap-evolve copies trajectories VERBATIM to the optimizer and `store: git`
                commits every iteration. `verbose_logs=False` (#3) is part of this: with it on,
                tau2 writes every LLM call's kwargs to disk.
- the OPTIMIZER's credentials are SEPARATE: the `claude-code` optimizer inherits them from the
                run owner's Claude Code environment. Nothing about them belongs in the spec or the
                adapter.

# 4. SCORER  (what to optimize against) — and WHERE the metric comes from
- metric:       tau2's own task reward in [0,1]. For airline, reward_basis = ["DB", "COMMUNICATE"]:
                the final DB must match the gold DB, and the required info must be communicated.
- metric source: rollout.trace["reward_info"]["reward"] (#3 rollout mapping); the breakdown is in
                reward_info (db_check, action_checks, communicate_checks, nl_assertions,
                env_assertions). score() is DETERMINISTIC on a fixed rollout (the check gate calls
                it twice) — read the recorded reward, never re-run. When rollout.trace is None or
                has no reward_info (the check gate's probe rollout has trace None), return reward
                0.0 with feedback "no simulation recorded" — never raise.
- feedback (the TEXT score() returns): gold-AWARE but gold-SAFE, and ARGUMENT-LEVEL. For EACH
                failing check, localize the defect at the argument level:
                  * for each mismatched write/action, name the differing ARGUMENT key + the AGENT'S
                    OWN wrong value (e.g. "book_reservation: payment_id='credit_card_9' is not on
                    the user's profile; available=[credit_card_4421, gift_card_8]");
                  * for communicate misses, name the un-stated value when derivable from the
                    agent's own state.
                Gold-SAFE applies to this feedback TEXT: never print a gold VALUE in it — derive
                values from the agent's OWN messages/tool calls and the user's OWN profile/db state
                (parsed from the get_user_details / get_reservation_details results in the trace);
                use reward_info only to know WHICH action/argument failed (gold arg KEYS are safe,
                VALUES are not). Fall back to the tool-name message when a piece isn't safely
                derivable. (The optimizer separately sees the full trace including reward_info,
                by design — #5.)
- pairing:      pair each tool result with its call BY POSITION (the n-th result after an
                assistant turn answers its n-th call), never by id: the env service records
                every call and result with an EMPTY id (S9, S10).
- objective:    maximize mean reward on the VAL split

# 4b. TRAJECTORIES  (the FULL traces the optimizer reads)
- what the optimizer reads: cap-evolve copies its OWN per-rollout JSON (each Rollout, whose
                `trace` is the full simulation, #3) into the optimizer's ./trajectories/ each
                iteration. adapter.trajectories() is only its fallback.
- native file:  ALSO persist tau2's results file, for humans and the fallback. S1's `save_path` =
                  <run_dir>/native_sims/<tag>/results_<YYYYmmdd_HHMMSS>_<pid>.json
                where ctx is the candidate dir: <run_dir> = Path(ctx).parent.parent and
                <tag> = Path(ctx).name (ctx is <run_dir>/candidates/<tag> or <run_dir>/work/<tag>).
                A NEW file per call: tau2 treats an existing results file as a run to RESUME and
                prompts on stdin. Remember the last directory written; trajectories(split) returns
                it. [blackbox] the file holds both the primitive calls (B4 i) and the compound
                calls (B4 ii), and that call's session log started_env_ids_<stamp>_<pid>.txt (B5) sits
                beside it.

# 5. OPTIMIZER  (proposes the edits) + MODEL + CREDENTIALS + CONTEXT
- optimizer:    optimizer_skill: claude-code
- model:        optimizer_model: claude-opus-4-8
- credentials:  a logged-in Claude Code session (or ANTHROPIC_API_KEY) — SEPARATE from #3b.
- runner_repo_path:  ../../vendor/tau2-bench   (spec paths resolve against the PROJECT dir
                .capevolve/project/; read-only context: task definitions, the real tool
                implementations, the reward checks). CHECK: `ls
                .capevolve/project/../../vendor/tau2-bench/src/tau2` lists files. EXPECTED: yes.
- optimizer instructions: author .capevolve/project/optimizer/INSTRUCTIONS.md from the scaffolded
                template; `optimizer_instructions_file: optimizer/INSTRUCTIONS.md` (relative is
                correct — spec paths resolve against the project dir; intake's "write it
                absolute" caution is obsolete). Edit the template, do not
                re-author it from scratch:
                  - DELETE the `{{EMPTY_SEED}}` line. The `tools` capability recognises content
                    only in a tools.json, so it would report this .py seed as EMPTY and tell the
                    optimizer to "create from scratch".
                  - KEEP every other placeholder exactly: {{TARGET_READER}}, {{FOCUS_SUMMARY}},
                    {{FAILURES}} (both occurrences), {{BENCH_REPO}}, {{PARALLEL_NOTE}},
                    {{PASSING}}, {{CAP_BRIEF}}, {{ALGO_BRIEF}}.
                  - The policy is NOT editable on either arm: delete the template's
                    prompt/policy-editing sentences (its "EDIT BOTH ARTIFACTS" framing, every
                    "(Prompt capability: …)" aside, and `policy.md` in examples) and keep its
                    tool-code guidance. Prose fixes go in a tool's docstring.
                  - Replace every `tools.py` with the arm's edit surface: direct →
                    `tools/tools.py`; blackbox → `my_skill/scripts/<tool>.py`.
                  - Keep the template's depth mandate, non-overfitting guardrail, STEP-0 reading
                    mandate and cross-iteration file protocol unchanged.
                  - ./guidance/tools/SKILL.md describes a tools.json artifact; say in the
                    instructions that its edit TYPES apply but its tools.json FORMAT does not.
                  This file is gated by the #3 CHECK's render self-test. Intake's "never delete a
                  placeholder" rule does not apply to `{{EMPTY_SEED}}`: the implement-and-check
                  self-test only needs some `{{…}}` to remain.
- the benchmark facts to ADD (what the template cannot know): ./trajectories/ holds one JSON per
                rollout whose `trace` is the full tau2 simulation, including reward_info with the
                per-check breakdown and the expected (gold) actions — use it to localize the exact
                defect, and keep every edit GENERAL (the template's non-overfitting guardrail:
                never hardcode a task's id or value); the score is reward_info.reward; tau2's
                airline data_model is under ./guidance/sources/.
- [DIRECT ONLY] the edit surface is tools/tools.py (class AirlineTools). The optimizer may change
                bodies, add tools (methods decorated `@is_tool(ToolType.READ)`, `WRITE` or
                `GENERIC`), and list tool names in REMOVE_TOOLS. Scoring stays honest because gold
                is pristine (T2).
- [BLACKBOX ONLY] the delivery rules to ADD. Each `my_skill/scripts/<tool>.py` becomes ONE tool
                the proxy injects; a broken rule silently breaks the tool.
                (1) ONE public top-level `def` per file, named exactly like the file; helpers
                    nested and `_`-prefixed.
                (2) Signature + docstring are the schema the model reads (Google style `Args:`).
                    The SEED's signatures are FROZEN. A NEW tool uses str/int/list/dict by
                    default; for a genuinely structured parameter, copy the class from
                    ./guidance/sources/data_model.py into the tool's own file WITH its
                    dependencies — only value models + typing/pydantic imports, never `tau2.*`,
                    never a DB class. The `def` stays on one line; no self-referential model.
                (3) Reach the environment ONLY by calling an `env_<tool>` primitive BY BARE NAME
                    — list all 14 names from #1. A primitive returns the parsed result on success
                    and an error STRING on a tool-level failure.
                (4) NEVER call `_make_api_call`, NEVER edit `primitive_tools/`, leave SKILL.md
                    empty.
                (5) A new/composite tool is a new FILE that calls primitives by bare name;
                    removing a tool means deleting its file.
- CHECK:        `grep -c "{{EMPTY_SEED}}" .capevolve/project/optimizer/INSTRUCTIONS.md` = 0 and
                each of the 8 kept placeholders is present. EXPECTED: both.

# 6. BUDGET / GATE
- two spec files in .capevolve/project/, identical except for the keys below:
                  capevolve.smoke.yaml  split_ids_file: split_ids_smoke.json, max_iterations: 1,
                                        num_trials: 1, optimizer_skill: mock
                  capevolve.yaml        split_ids_file: split_ids_budget.json, max_iterations: 2,
                                        num_trials: 5, optimizer_skill: claude-code
- SMOKE FIRST (once per arm):
                  .venv/bin/cap-evolve run --spec .capevolve/project/capevolve.smoke.yaml
                CHECK: the baseline rollout for task 9 has a real reward and error null;
                [blackbox] the B5 CHECK holds. EXPECTED: all hold. An instant all-zero baseline
                means the rollouts errored — see #7.
                Task 9 is a SMOKE, not a measurement: the seed already scores high on it, so it
                cannot show an improvement.
- BUDGET RUN:     .venv/bin/cap-evolve run --spec .capevolve/project/capevolve.yaml
                on tasks 8 10 20 23 35 42 44 — ones the seed fails some of the time, so there is
                room to improve.
- algorithm:        hill-climb  (--focus all)
- per-iteration optimizer $ cap:  optimizer_usd_per_iter 40   (claude --max-budget-usd, CLI-enforced)
- optimizer_max_turns: 400      (generous; the $ cap is the real per-iteration ceiling)
- max_usd: 400      max_optimizer_usd: 400
                max_usd binds only on cost the adapter reports (#3 cost_usd), and litellm prices
                only models it knows. [blackbox] the proxy reports no token usage, so the AGENT
                side is unmeasured; the user simulator's gateway cost still counts. A 0 in the
                cost panel means NOT MEASURED, not free.
- gate:             gate_mode: paired (per-task paired SE)      gate_k_se: 0.2
- store:            git          (every iteration committed for an inspectable process)
- stall:            3
- ONE ARM PER RUN. The other arm is a separate onboarding in its own project. To compare the two,
                run them on the SAME split file, num_trials and models, and report them side by
                side per task — never averaged.

# 7. FAILURE SIGNATURES  (symptom → cause → fix; read this before retrying anything, R3)
- every baseline reward 0 instantly, rollout.error set
                → rollouts errored (credentials, model alias, or a seam) → read rollout.error and,
                  on blackbox, /tmp/env_manager.log; fix the named cause
- the optimizer prompt says the capability is EMPTY
                → `{{EMPTY_SEED}}` left in INSTRUCTIONS.md → #5
- the optimizer has no ./guidance/sources/data_model.py
                → capability_sources path not project-relative → #1 spec keys
- 401 / 404 on every call
                → wrong key or model alias, or `openai/openai/` double prefix → #3b
- HTTP 200 with empty content
                → max_tokens too low for a reasoning model → raise it (#3b)
- `cap-evolve run` fails "intervention preflight failed"
                → stack not provisioned (#2b) or `skill_name` missing (#0)
- [blackbox] db_match false on EVERY trial, but write tools returned success
                → the env-service trajectory is not merged before evaluation → B4 (i)
- [blackbox] "Tool call id mismatch" / "Tool message expected" / "Tool message not expected"
                during evaluation
                → the proxy trajectory reached the evaluator, or a merge broke the call/result
                  adjacency → B4 (ii) runs only AFTER evaluation; keep pairs adjacent (S9)
- [blackbox] more env_ids for a trial than its attempts in started_env_ids_*.txt, or env_ids
                still open
                → a non-trial construction is being armed, or B5 did not stop them → B0, B1, B5
- [blackbox] tool calls fail with "no env_id in the execution context"
                → the B2 headers are missing → B2, S5 ASSERT
- [blackbox] the agent behaves like a different model
                → SPA_MODEL_NAME not passed → #3 apply(), #2b .env
- [blackbox] a tool's published schema has no field names (the model guesses them)
                → a #1 (c) / #5 (2) rule broken (class in another file, multi-line def, recursion)
- [direct] a candidate that breaks a write tool still scores the DB check
                → gold is not pristine → T2
- [direct] AttributeError on a `_get_*` helper mid-rollout
                → tools/tools.py is not a byte-for-byte copy → #1
- the project behaves like an older version of a skill
                → CAPEVOLVE_SKILLS_DIR not set → #2
- a registration raises "already registered"
                → install() not idempotent → #2c module contract
```
