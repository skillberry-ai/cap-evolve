# The prompt — onboard tau2-bench airline as a new benchmark and optimize it

Paste this to your coding agent (Claude Code) at the cap-evolve repo root and say
**"follow RUN.md."** Intake treats this as a brand-new benchmark: the integration step
**clones + installs tau2-bench**, wires the ETE gateway, writes the adapter, runs the
`cap-evolve check` gate, then the full optimize → gate → sealed-test → report loop with a live
dashboard. Everything below is the input intake needs.

**This prompt covers BOTH delivery arms of the same benchmark** — same tasks, same capability, same
scorer; only how the candidate reaches the model differs. §0 makes you pick one. A section or line
marked `[DIRECT ONLY]` or `[BLACKBOX ONLY]` applies to that arm alone; **everything unmarked applies
to both.**

```text
Use only information in this current cap-evolve repo root folder on the current Git branch.
Do not use external documentation, web searches, prior knowledge, other repositories, branches, tags, or commits.
Treat this repository as the sole source of truth. If required information is missing, state that it is missing rather than guessing.
Start with RUN.md and follow it exactly.


Follow RUN.md to run a cap-evolve optimization. Onboard this as a brand-new
benchmark — the intake/integration step should CLONE + INSTALL it (not assume it
exists). Here is everything intake needs:

# 0. DELIVERY ARM — PICK EXACTLY ONE, BEFORE ANYTHING ELSE
- the two arms:  DIRECT   — the candidate is edited in the project and the benchmark's own runner
                            loads it from disk. No extra services.
                 BLACKBOX — the candidate becomes ONE skill package in the Skillberry Store, and the
                            Skillberry Proxy-Agent injects it into the agent's LLM calls, so the
                            benchmark never sees skill files. Needs the store, the proxy, and the
                            benchmark's environment service.
- arm:          <direct|blackbox>     # FILL THIS IN before pasting, or be asked for it
- STATE YOUR CHOICE in your first reply and do not change it mid-run. Everything downstream — the
                spec, the seed shape, the domain, the models, the services — follows from it.
- IF THE ARM IS NOT STATED ABOVE OR IS AMBIGUOUS: ASK, and WAIT for the answer. Do NOT guess and do
                NOT default to direct. A run delivered one way and recorded as the other is a
                measurement that cannot be attributed, and nothing in the output reveals it.
- project base: DIRECT -> `.capevolve/`      BLACKBOX -> `.capevolve-blackbox/`
                SEPARATE ON PURPOSE, not a naming quirk: the two arms are separate onboardings of
                the same benchmark, so sharing a base would let one arm's scaffold and `run_*` dirs
                mix with the other's — and a run whose delivery cannot be attributed is not a
                measurement. Both are gitignored. Everywhere below, `<base>/project` means the
                project directory of the arm YOU picked.
- ONE ARM PER RUN. The spec, the seed and the record must all agree about how candidates were
                delivered.
- everything unmarked below applies to BOTH arms. Read the marked lines for YOUR arm and ignore the
                other arm's — but read them well enough to be sure which is which.

# 1. CAPABILITY TO OPTIMIZE  (a copy is edited each iteration; the original is never touched)
- type:         [tools]                     # the agent's TOOL SURFACE only
- tools means:  edit tool docstrings/descriptions; edit tool behavior/code; and ADD/REMOVE tools,
                including composite tools that call existing tools
- seed [DIRECT ONLY]:     tau2-bench's canonical airline tool set. The seed tools file must be
                CLEAN, runnable code as intake would produce it — real tool bodies, no baked-in
                optimizer/editing instructions in its docstrings (what the optimizer may change
                lives in the tools capability SKILL.md, not in the seed file).
- delivered as [BLACKBOX ONLY]:  ONE skill package in the store, whose scripts are the agent's
                tools. The intervention skill owns the package layout and the authoring rules that
                decide what becomes a tool (§1b) — follow it, do not re-derive them here.
- the POLICY is NOT part of the capability and is NEVER edited. It is the benchmark's own
                specification of the task — the rules the agent is GRADED against — so a candidate
                that could rewrite it would be editing the exam: soften an inconvenient rule and the
                reward rises, because the same text is what judges the agent. It stays PRESENT (the
                agent needs it) and unmodified.
                  * [DIRECT ONLY] seal it in the spec: protected_paths: ["policy/*"].
                  * [BLACKBOX ONLY] the policy reaches the agent UNCHANGED (the proxy keeps the
                    request's system messages, USE_AGENT_PROMPTS=true) and is not an artifact the
                    optimizer can see.
                NOTE `capabilities:` does NOT gate writes — it selects which validate() runs and
                which guidance is surfaced — so the SEAL is what closes this, not the capability
                list.
- the FROZEN substrate [BLACKBOX ONLY] is part of the SEED but NOT the capability: the benchmark's
                own primitives, plus the ONE bridge to the benchmark's environment service, are what
                make the measurement comparable across arms. SEAL every path the intervention
                skill's seed shape defines as substrate rather than capability, via
                protected_paths. That skill owns those paths (§1b) — take them from it rather than
                inventing them here, and seal ALL of them: an unsealed substrate path is an
                optimizer that can edit the thing the comparison rests on.
- SEALING SEMANTICS: editing a sealed path makes the candidate INDECISIVE (the measurement is void)
                rather than scored 0.0. Those are different verdicts — do not report one as the
                other.
- capability_sources:
                  * [DIRECT ONLY] the benchmark's data-model/types module(s) the tools import (here
                    tau2's airline data_model — the source of FlightDB, Reservation, Passenger,
                    Payment, etc.). cap-evolve copies these verbatim into the optimizer's workdir so
                    it can write correct new-tool code against the real types.
                  * [BLACKBOX ONLY] []  — the wrappers call primitives BY NAME through the store, so
                    no shared types module is imported by the editable code.

# 1b. INTERVENTION  (how the capability reaches the model — a spec key)   [BLACKBOX ONLY]
- the spec gets the top-level line:  intervention: blackbox
                (`capabilities:` says WHAT is edited; `intervention:` says HOW it reaches the model.
                capevolve.yaml-only — no CLI override.)
- skill_name: my_skill  — REQUIRED, not merely recommended: without it the delivery falls back to
                an inference that is SILENT and looks like success even when nothing was delivered,
                so a run can complete having injected no capability at all.
- FOLLOW THE INTERVENTION SKILL — skills/interventions/llm-proxies/blackbox/SKILL.md and the
                seeding reference it points to. It owns provisioning, service lifecycle, the seed
                shape, the wrapper authoring rules, store import order, and the per-candidate
                deploy. Do NOT re-derive any of that here, and do not hand-roll a copy of
                blackbox_env. This prompt supplies only what the skill cannot know: the benchmark,
                its environment service, and the TAILORING in §2c.
- VERIFY:       `cap-evolve check .capevolve-blackbox/project` green, and `intervention: sap` (a
                typo)
                REJECTED BY NAME, not silently defaulted to direct.

# 2. BENCHMARK / DATASET  (the eval) — INSTALL IT DURING INTAKE
- benchmark:    tau2-bench, airline domain
- repo:         https://github.com/sierra-research/tau2-bench   (latest main; record the resolved commit)
- install:      git clone into vendor/tau2-bench, then
                  pip install -e vendor/tau2-bench "websockets>=13.0"
                WHY the extra package: tau2's data_model imports its voice stack UNCONDITIONALLY,
                but `websockets` ships only in the [voice] extra — so a base install cannot even
                `import tau2`. `websockets` alone is enough; do NOT install [voice], which drags in
                livekit, boto3 and google-cloud-aiplatform.
- UNMODIFIED:   install the benchmark AS PUBLISHED. Do NOT fork it, do not edit the checkout, do not
                install a tailored build of it. A benchmark edited to suit the harness stops being
                comparable to anyone else's numbers, including our own earlier ones. If you believe
                it must be changed, STOP and say so rather than changing it — for the blackbox arm,
                §2c is how that need is met instead.
- RECORD the resolved commit in PROJECT.md. It is part of the MEASUREMENT, not bookkeeping: the
                benchmark owns the policy text the agent reads, the task set, and the reward checks,
                so two numbers are comparable only if both name the commit behind them.
- domain:       [DIRECT ONLY]   "airline" — tau2's own.
                [BLACKBOX ONLY] "airline_skillberry" — registered by OUR tailoring module at
                apply() time, NOT by the benchmark. Its environment is a PLAIN vanilla tau2 airline
                environment (see §2c for why that matters).
- tasks:        "adapter" — the adapter loads all 50 airline tasks from tau2
                (tau2.domains.airline.environment.get_tasks); no network in tasks()
- splits:       all 50 tasks as train = val = test  (no-holdout fit metric; the engine logs a
                splits_warning and the report flags the test number as a fit metric). Pin them in
                split_ids.json.

# 2b. THE BENCHMARK'S ENVIRONMENT SERVICE   [BLACKBOX ONLY]
- WHY it is needed: store-hosted tools execute in the STORE's process, not where the benchmark's
                state lives, so the skill's tools can only reach that state through a service the
                benchmark fronts over HTTP. The intervention health-checks this and aborts without
                it.
- tau2 HAS one, and it is UPSTREAM code — tau2.orchestrator.environment_manager.EnvironmentManager
                is vanilla tau2, not something we add. Do NOT reimplement it; only its launcher is
                ours (scripts/start_tau2_env_manager.py).
- start it:     port 8004, from cap-evolve's venv. ~10s to start (importing tau2 pulls in litellm),
                so POLL the port rather than sleeping — and probe a route it actually serves (/docs
                or /). It serves NO /health, so probing that reports a live service as dead and a
                readiness loop burns every attempt.
                LITELLM_LOCAL_MODEL_COST_MAP=True skips litellm's doomed remote cost-map fetch,
                which otherwise stalls startup until it times out.
- its CALL SHAPE (what the frozen primitives speak):
                  base URL:     http://127.0.0.1:8004   (also set SPA_REMOTE_ENV_URL in .env)
                  URL:          {base}/{env_id}/tools/{tool_name}
                  request:      POST {"name": <tool>, "arguments": {...}}
                  success:      result["content"] is a JSON *string* — json.loads it
                  failure:      result["content"] is a plain message; non-200 → raise
- per-rollout identity: the store's executor injects `env_id` into the tool module, so the
                primitives need no session plumbing of their own. Getting the RIGHT env_id there is
                what §2c's context header is for.

# 2c. TAILORING THE BENCHMARK — FROM OUTSIDE, NEVER INSIDE   [BLACKBOX ONLY]
This arm needs five things stock tau2 does not do. They are supplied by a module BESIDE the adapter
(adapters/tau2_tailoring.py, deployed into the project's adapters/), installed from apply(). They are
NEVER obtained by editing the benchmark.
- the five:     (1) Skillberry context headers on the AGENT's LLM calls (never the user simulator's,
                never a judge's); (2) routing the agent's model to the proxy; (3) a domain + agent
                for the arm; (4) retrieving the proxy-side trajectory and merging it into the
                runner's own; (5) a vMCP disconnect at session end.
- PREFER THE RUNNER'S PUBLIC EXTENSION POINTS. For tau2 all of (1)-(3) need no patch at all:
                  * registry.register_domain(...) and registry.register_agent_factory(...) are
                    public, and a late registration is honoured because domains resolve lazily.
                  * `llm_args` is forwarded from run config -> agent -> generate() -> the LLM client
                    UNFILTERED, so extra_headers / base_url / api_key / custom_llm_provider all
                    travel that way. The AGENT FACTORY is the right home for it: it runs exactly
                    ONCE per rollout and receives `task`, so it can start this rollout's remote
                    environment, keep the env_id on the agent, and bake the header in.
- Where NO public seam exists, a NARROW, IDEMPOTENT wrapper installed at apply() time is allowed —
                never an edit to the checkout, never a fork, never sys.modules surgery. Two are
                needed here, one per merge window below.
- DO NOT put the remote session on the ENVIRONMENT. It is the obvious place and it is wrong: the
                evaluator re-invokes the registered domain constructor 1-3 MORE times per rollout,
                so an environment that starts a session in __init__ orphans remote environments and
                makes env_id ambiguous. The arm's domain must be a PLAIN environment,
                side-effect-free and identical to tau2's own airline, so the evaluator may build it
                freely AND its real tools let the evaluator's state replay rebuild a local DB.
- THE TWO MERGES HAVE DIFFERENT WINDOWS. This is the subtlest requirement here and the easiest to
                get wrong, so it is stated outright:
                  * the ENV-SERVICE trajectory (the PRIMITIVE calls, port 8004) must be merged
                    BEFORE evaluation. Under this arm every real mutation happens in the store
                    against the remote environment, so tau2's own trajectory never saw those calls;
                    without them the evaluator's state replay reconstructs nothing, the DB check
                    goes false and reward collapses to 0. Its messages are properly paired (a call,
                    then its result), which is what makes them legal replay input.
                  * the PROXY trajectory (the COMPOUND/skill calls, port 7000) must be merged AFTER
                    evaluation, and before the runner persists the result. It is filtered to drop
                    primitives (they already arrived via the env service), and it is NOT legal
                    replay input — merging it early both changes the reward and can hard-fail the
                    rollout into a retry storm.
                  Getting either window wrong produces a plausible-looking trace and a WRONG score,
                  with no error anywhere.
- ASSERT EVERY SEAM, at install time, in an offline verify() the check gate runs. A SEAM YOU CANNOT
                ASSERT IS A SEAM YOU MAY NOT USE. This is not optional hardening: the benchmark
                tracks latest main, and the two highest-risk seams fail SILENTLY — if `llm_args`
                stops reaching the client the context header vanishes and the proxy falls back to a
                shared default session; if the pre-evaluation merge stops firing the DB check goes
                false. Both read as a worse capability rather than broken wiring. PROVE the llm_args
                passthrough by stubbing the client call and asserting the header arrived — do not
                merely inspect a signature. Every failure message must name the seam, the tau2
                version+commit it ran against, what it costs, and that validating a changed commit
                is the operator's responsibility.

# 3. RUNNER  (the agent under test) + MODELS + CREDENTIALS
- how to run:   tau2's own batch runner (adapter.run_batch -> tau2.runner.run_tasks with a
                TextRunConfig; the 1.0.x API, not the deprecated flat-kwargs form)
- fast eval:    ALSO implement the optional adapter method
                run_trials(tasks, ctx, *, n_trials, base_seed) -> {task_id: [Rollout, ...]}.
                Run ALL num_trials in ONE run_tasks call with num_trials=N (grouped by sim.trial)
                and return {task_id: [trial0, trial1, ...]} (len n_trials, trial-ordered). When
                present, cap-evolve calls it ONCE per candidate instead of looping run_batch per
                trial; per-trial persistence (rollouts/<split>/<task>__<tag>__t<k>.json) is
                UNCHANGED so pass^k / SE / resume keep working. This collapses N sequential eval
                passes into one batched run.
- apply() [BLACKBOX ONLY]: deploy the candidate as THE store skill (primitives FIRST so a skill
                redeploy cannot cascade into the frozen substrate, then rebind the proxy) AND
                install the §2c tailoring. Guard on the CANDIDATE'S SHAPE (is a skill package
                present?) rather than on the spec, so a spec/seed mismatch fails loudly instead of
                delivering the wrong way silently.
- apply() must NEVER raise: record the deploy failure and let the rollouts come back errored, so the
                harness EXCLUDES the candidate instead of scoring it 0.0 — a failed deployment is
                infrastructure noise, not a verdict on the capability.
- AGENT model:  [DIRECT ONLY]   aws/gpt-oss-120b via the internal ETE LiteLLM gateway.
                [BLACKBOX ONLY] the proxy-routed sentinel (default `ibm/skillberry-local`). It is a
                MODEL NAME, not a URL; the route is decided by exact string match, so do not
                normalize it.
- USER SIMULATOR model: a real gateway model (aws/gpt-oss-120b).
                [BLACKBOX ONLY] NEVER the sentinel. That boundary is a CORRECTNESS rule, not a
                preference — routing the simulator through the proxy injects the capability into the
                very thing measuring the agent.
- gateway wiring:  OpenAI-compatible endpoint, standard bearer auth, catalog ids normalized once to
                `openai/<alias>`  (NO litellm monkeypatch, NO tau2 fork)
- credentials:  OPENAI_BASE_URL (or OPENAI_API_BASE) + OPENAI_API_KEY in the repo-root .env
- NEVER put an API key in the llm_args you hand the runner: tau2 records llm_args VERBATIM into its
                results file, which trajectories() exposes, cap-evolve copies to the optimizer, and
                `store: git` COMMITS. A key passed that way becomes a committed secret that was also
                shipped to the optimizer.
- concurrency:  [DIRECT ONLY]   TAU2_MAX_CONCURRENCY=125.
                [BLACKBOX ONLY] start LOW (e.g. TAU2_MAX_CONCURRENCY=4) — every agent call funnels
                through ONE proxy and ONE store process.
- cost [BLACKBOX ONLY]: the proxy reports no token usage, so rollout cost_usd/tokens are 0 and any
                max_usd ceiling is INERT — only optimizer budgets bind. A 0 in the cost panel means
                NOT MEASURED, not free. Say so rather than presenting it as free.

# 4. SCORER  (what to optimize against) — and WHERE the metric comes from
- metric:       tau2's own task reward in [0,1] (required actions performed + info communicated)
- metric source: tau2 computes it per simulation as `sim.reward_info.reward`; the per-check
                breakdown is in `sim.reward_info` (db_check / action_checks / communicate_checks /
                nl_assertions / env_assertions). Implement adapter.score() to read the reward +
                reward_info that the run stashes from each simulation, and verify score() is
                deterministic on a fixed rollout (the `cap-evolve check` gate enforces this).
                NOTE for airline: `reward_basis` is [DB, COMMUNICATE] — action_checks are reported
                but do NOT enter the reward. Do not chase action matches to explain a 0.0.
- feedback:     gold-AWARE but gold-SAFE, and ARGUMENT-LEVEL — this IS the learning signal, so a
                tool-name-only message ("action X was wrong") is too coarse: the optimizer can only
                pattern-match to prose rules and plateaus. For EACH failing check, localize the
                defect at the argument level:
                  * for each mismatched write/action, name the differing ARGUMENT key + the AGENT'S
                    OWN wrong value (e.g. "book_reservation: payment_id='credit_card_9' is not on
                    the user's profile; available=[credit_card_4421, gift_card_8]";
                    "update_reservation_flights: called on reservation res_A but the task targets a
                    different one");
                  * for communicate misses, name the un-stated value when derivable from the agent's
                    own state (e.g. "did not state the computed total cost ($150 from your own
                    observed amounts)").
                Gold-SAFE: NEVER read or print the gold/expected value — derive everything from the
                agent's OWN messages/tool-calls and the user's OWN profile/db state (parsed from the
                agent's own get_user_details/get_reservation_details tool results in the trace). Use
                reward_info only to know WHICH action/argument failed (the gold action's arg KEYS
                are safe; its VALUES are not). Fall back to the tool-name message when a piece isn't
                safely derivable. score() must stay deterministic on a fixed rollout.
- objective:    maximize mean reward on the VAL split

# 4b. TRAJECTORIES  (the FULL traces the optimizer reads) — PATH IS AN INPUT
- where:        persist tau2's native per-task simulation results (full message transcript +
                reward_info) via run_tasks(save_path=...), at the ONE path format every tau2 adapter
                in this repo shares:
                <run_dir>/native_sims/<tag>/<split>/results_<YYYYmmdd_HHMMSS>_<pid>.json
                (<tag> is the candidate dir from ctx; <split> stands in for the phase, which no
                adapter is told. The timestamp+pid matters: tau2 reads an existing results file as a
                run to RESUME and prompts on stdin, which an eval does not have.)
- expose:       implement adapter.trajectories(split) to return that directory. cap-evolve copies it
                VERBATIM into the optimizer's working dir as ./trajectories/ each iteration, so the
                optimizer reads the complete, unmodified traces (not a lossy summary).
                (If you cannot persist native files, return None — cap-evolve falls back to copying
                its own per-rollout JSON, which already embeds each rollout's full message trace.)
- [BLACKBOX ONLY] these native files are ALSO the record that §2c's two merges worked: the persisted
                simulation must contain BOTH the primitive calls and the compound skill calls. A
                trace with only one of them is a WIRING BUG, not a bad candidate — say so rather
                than letting the optimizer chase a phantom capability problem.

# 5. OPTIMIZER  (proposes the edits) + MODEL + CREDENTIALS + CONTEXT
- optimizer:    claude-code
- model:        claude-opus-4-6
- credentials:  a logged-in Claude Code session (or ANTHROPIC_API_KEY)
- runner_repo_path:  ../../vendor/tau2-bench  (the cloned checkout — surfaced to the optimizer as
                read-only context so it can consult tau2's tools/scoring/task structure. READ-ONLY
                is literal: it must never be edited, per §2's UNMODIFIED rule.)
- optimizer instructions: author <base>/project/optimizer/INSTRUCTIONS.md (§0) from the scaffolded
                template (keep its {{...}} placeholders intact — the harness fills them per
                iteration). Keep it short on meta-narration but explicit and DEMANDING on iteration
                depth, and impose a DEPTH MANDATE: state the GOAL (maximize the eval score) and
                require each iteration to be a substantial multi-cluster, multi-edit-class sweep —
                improve multiple tools' code + validation + enriched returns/errors, add new tools,
                sharpen many tool docs, together in ONE candidate, with each fix scoped to protect
                passing tasks (non-regression). "Freedom" does NOT mean do little — a single small
                edit is an under-used iteration; diagnose ALL clusters and fix as many as possible.
- the authored INSTRUCTIONS MUST demand BREADTH: each iteration diagnoses EVERY failure cluster in
                the trajectories and ships a fix for as many of them as pass the three tests
                (REAL/SAFE/VERIFIED) in this ONE candidate — solving many issues across many
                trajectories, not just the biggest. A one- or two-edit iteration is under-used; the
                only edits left out are the speculative ones that fail a test.
- the authored INSTRUCTIONS MUST also encode all of:
                (i)   a STEP-0 reading mandate — "read ./guidance/<cap>/SKILL.md (for EACH selected
                      cap) + ./guidance/optimizer/ before diagnosing";
                (ii)  the EXISTING-tool-code mandate — "convert violated rules into in-code checks
                      across MANY EXISTING tool bodies; most violated rules govern a tool that
                      already exists, so the fix is an in-body guard there, not a new tool — a
                      docstring-only iteration (or one that only adds a single new tool + rewords
                      docstrings, leaving rules as prose) is under-used";
                (iii) the explicit TWO-PHASE subagent pattern — Phase 1 diagnose fan-out (one
                      read-only subagent per trajectory-group → tight issue list; main dedups into
                      clusters), Phase 2 implement fan-out (one edit-subagent per ISSUE, each in its
                      own worktree, each PREFERRING to edit the EXISTING tool's code body to enforce
                      its rule), then merge all edits into ONE candidate;
                (iv)  the NON-OVERFITTING guardrail — every tool edit must be a GENERAL
                      rule/validation that generalizes across the class of inputs; NEVER hardcode a
                      task-specific id/value/date/name/answer (a guard fires on the general
                      condition, e.g. "payment_id not on the user's profile", NOT
                      `if reservation_id == "ABC123"`); a literal special-case overfits, fails the
                      held-out gate, and hurts other tasks; per-task specifics are for understanding
                      the failure CLASS only;
                (v)   EXPLOIT GROUND TRUTH for diagnosis — the native trajectories include
                      reward_info with the per-check breakdown; USE it to localize the exact defect
                      (expected vs actual action/argument/value), but keep the resulting edit
                      GENERAL (guardrail iv) and never copy a gold value into the prompt or tool
                      code;
                (vi)  the CROSS-ITERATION FILE CONTRACT + NEW-TOOLS-FIRST-CLASS mandate — READ all
                      four cross-iteration files first (LEDGER facts, the whole JOURNAL handover,
                      RUNMAP + prior_iterations diffs/PROCESS); each iteration FILL ./PROCESS.md
                      (required explainability: ranked issues with
                      KNOWLEDGE/BEHAVIORAL/CAPABILITY-GAP tags, every edit + class, verify-the-fix,
                      subagents/features used, what to preserve, what was skipped) and APPEND its
                      entry to ./JOURNAL.md (tried/worked/regressed/refuted/plateau-signal/
                      focus-next); and it must require MULTIPLE edit classes per iteration and ADD
                      at least one NEW code-bearing tool (composite atomic-WRITE / loop /
                      validation) whenever a CAPABILITY-GAP or action-STALL cluster is present —
                      adding new tools is ENCOURAGED, not an exception.
- Tailor only the "READ THESE" pointers (./trajectories/, ./guidance/<cap>/SKILL.md for EACH
                selected capability, ./guidance/diagnose/SKILL.md,
                ./guidance/optimizer/claude-code.md, ./guidance/sources/ [the data model],
                ./LEDGER.md, ./JOURNAL.md, ./RUNMAP.md + ./prior_iterations/, ./PROCESS.md,
                ../../vendor/tau2-bench).
- scope to the SELECTED capability: tools ONLY is selected here, so the instructions, the guidance
                and the editable files must cover ONLY that one — no prompt-editing guidance, no
                system-prompt skill, and the policy is NOT presented as editable.
- WHAT TO EDIT, per ./guidance/tools/SKILL.md: prefer CODE-BEARING changes — a validation tool that
                enforces a rule in code then calls the existing tool and removes the raw one; a
                workflow/loop tool that collapses a recurring sequence; a composite WRITE tool that
                performs a stalled multi-step action in code (then removes the raw write primitives)
                so the agent can't analyze, confirm, then fail to execute. Improve tool docs AND
                RETURN VALUES (actionable errors + next steps) — the docstring and the return are
                what the agent sees. Never bare-remove a tool — add a replacement that calls it,
                verify, then swap registration.
                  * [DIRECT ONLY]   the edits land in the project's tools file(s).
                  * [BLACKBOX ONLY] the edits land in the skill's scripts/, and the wrapper calls
                    the FROZEN primitive by name through the store.
- process flow: READ ./LEDGER.md + the whole ./JOURNAL.md + ./RUNMAP.md (and the ./prior_iterations/
                entries for clusters you'll touch) FIRST (don't re-submit a rejected edit verbatim —
                a redesigned version may still work; don't abandon a high-value cluster); analyze
                the current best step's ./trajectories/; use LEDGER's per-task broke/fixed columns +
                the currently-passing tasks the harness lists to steer AWAY from regressions (don't
                re-introduce a change that broke a task) WITHOUT freezing; make a bold, multi-part
                edit across the selected capabilities (multiple edit classes, incl. a NEW tool for
                any capability-gap/stall cluster), scoping each edit to fire only on its failing
                condition and confirming it doesn't change a passing task's behavior; fill
                ./PROCESS.md (per-edit verify + blast-radius lines) and APPEND your entry to
                ./JOURNAL.md.

# 6. BUDGET / GATE
- algorithm:        hill-climb  (--focus all)
- max_iterations:   10          num_trials: 10
- per-iteration optimizer $ cap:  optimizer_usd_per_iter 40   (claude --max-budget-usd, enforced by the CLI itself)
- optimizer_max_turns: 400      (generous; the $ cap is the real per-iteration ceiling)
- max_usd: 400      max_optimizer_usd: 400
                [BLACKBOX ONLY] NOTE: the runner side is unmetered here — see §3's cost line.
- gate:             paired (per-task paired SE — banks real 1-task gains), k_se 0.2
- store:            git          (every iteration committed for an inspectable process)
- ALSO author a cheap SMOKE spec beside the full one (capevolve.smoke.yaml + its own pinned split):
                2 tasks, num_trials 1, max_iterations 1, max_usd ~10. It exists to prove the WHOLE
                loop end to end — intake, deploy, rollout, score, gate, sealed test, report — for a
                couple of dollars, before anyone spends the full budget. Keep every other key
                identical to the full spec so the smoke exercises the same wiring; only the SCALE
                differs. [BLACKBOX ONLY] that means the same intervention, the same skill_name and
                the same protected_paths, over the same stack (provision, deploy the skill, rebind
                the proxy), and setup.sh must DEPLOY both specs and both splits.
- WIRE the smoke so one flag selects it and VERIFY that flag actually resolves to the smoke spec: a
                `--smoke` that silently falls back to the full spec turns a $10 check into a $400
                run, and nothing in the output says so.
- ONE ARM PER RUN (§0). The spec, the seed and the record must agree about how candidates were
                delivered, or the number cannot be attributed.
```

> The bundled `examples/tau2_airline/` is the **result** of following this prompt, once per arm.
> Every asset name in `blackbox/` mirrors the direct arm one level up, so
> `diff ../capevolve.yaml capevolve.yaml` shows exactly the delivery delta and nothing else.
>
> | | DIRECT — `examples/tau2_airline/` | BLACKBOX — `examples/tau2_airline/blackbox/` |
> |---|---|---|
> | adapter | `adapters/adapter.py` | `adapters/adapter.py` (its own, one arm per adapter) |
> | gateway | `adapters/gateway.py` | `adapters/gateway.py` (sentinel passthrough) |
> | tailoring (§2c) | — | `adapters/tau2_tailoring.py` |
> | seed | `seed_capability/` (policy + tools) | `seed_capability/` (`my_skill/` + frozen `primitive_tools/`) |
> | optimizer | authored into `.capevolve/project/optimizer/INSTRUCTIONS.md` by setup.sh (not committed) | `optimizer/INSTRUCTIONS.md` (committed) |
>
> `setup.sh` in each is the executable transcript of that onboarding (clone+install tau2, scaffold
> via intake, wire the adapter + trajectories + scoring, `cap-evolve check`); `run.sh` runs the
> optimization — starting the stack first, for the blackbox arm. See `DEMO.md`.
