# The prompt — onboard tau2-bench airline as a new benchmark and optimize it (one intervention)

Paste this to your coding agent (Claude Code) at the cap-evolve repo root and say
**"follow RUN.md."** Intake treats this as a brand-new benchmark: the integration step
**clones + installs tau2-bench**, writes the adapter, seeds the capability, runs the
`cap-evolve check` gate, then the full optimize → gate → sealed-test → report loop with a
live dashboard. The delivery path is ONE choice you make up front — `direct` or `intervention: spa` — and the
intervention skill owns everything about how `spa` works. Everything below is the input
intake needs.

```text
Use only information in this current cap-evolve repo root folder on the current Git branch.
Do not use external documentation, web searches, prior knowledge, other repositories, branches, tags, or commits.
Treat this repository as the sole source of truth. If required information is missing, state that it is missing rather than guessing.
Start with RUN.md and follow it exactly.


Follow RUN.md to run a cap-evolve optimization. Onboard this as a brand-new
benchmark — the intake/integration step should CLONE + INSTALL it (not assume it
exists). Here is everything intake needs:

# 0. DELIVERY PATH  (pick EXACTLY ONE arm)
- the CAPABILITY is the same either way — the airline agent's TOOL SURFACE only (tools,
                not the system prompt / policy). Only the delivery differs, and that is a spec key:
                  direct (no `intervention:` line) | intervention: spa
- ASK ME WHICH ONE and WAIT for the answer: `direct` or `spa`. Ask it as a PLAIN question with
                ONE SHORT SENTENCE per option — "direct: the runner reads the candidate's files
                in its own process, no extra services" / "spa: the candidate becomes a store
                skill the proxy injects, and needs the Skillberry stack plus the benchmark's
                environment service". Do NOT render preview panes, option cards, or dumps of
                spec fields; one sentence each is the whole point of the question.
                Prepare ONLY the arm I pick — one
                spec, one capability_path, one seed. Do NOT prepare both, do not default to
                one, and do not scaffold the other "for later": an unused arm's seed goes
                stale, doubles the onboarding, and invites a spec/seed mismatch that delivers
                candidates one way while the record says the other. The second arm is a
                SEPARATE onboarding in its own project (intake `--base`), done only if I ask.
- for `intervention: spa`, FOLLOW THE INTERVENTION SKILL —
                `skills/interventions/llm-proxies/spa/SKILL.md` and the seeding reference it
                points to. It owns provisioning, service lifecycle, the seed shape (one skill
                package + a frozen primitives module), the wrapper authoring rules, store
                import order, and the per-candidate deploy. Do NOT re-derive any of that from
                this prompt, and do not hand-roll a copy of spa_env. This prompt supplies only
                what the skill cannot know: the benchmark and the environment.

# 1. CAPABILITY TO OPTIMIZE  (a copy is edited each iteration; the original is never touched)
- what:         the airline agent's TOOL SURFACE only (tools; the system prompt / policy is NOT
                part of the capability and is NOT edited by the optimizer)
- tool surface: tau2's airline toolkit — 14 primitives (book_reservation, calculate,
                cancel_reservation, get_reservation_details, get_user_details,
                list_all_airports, search_direct_flight, search_onestop_flight,
                send_certificate, update_reservation_baggages, update_reservation_flights,
                update_reservation_passengers, get_flight_status, transfer_to_human_agents).
                This is the extraction source for EITHER rendering.
- IF direct:    capabilities [tools]; seed = tau2's canonical airline tool set (NO system-prompt
                capability — the policy is fixed and not an edit surface);
                capability_sources = tau2's airline data_model (FlightDB,
                Reservation, Passenger, Payment) so the optimizer can write correct tool code.
                Seed tools must be CLEAN runnable code — no baked-in optimizer instructions in
                the docstrings.
- IF spa:       capabilities [tools]; the seed is GENERATED from the same 14 primitives
                per the intervention skill's seeding procedure. capability_sources [].
                THE SEED MUST BE NEUTRAL. my_skill/SKILL.md must be an EMPTY FILE (empty
                string). The optimizer edits only tools (scripts/<tool>.py); SKILL.md is
                not an edit surface.
- actions:      [edit]

# 1b. INTERVENTION  (how the capability reaches the model — a spec key)
- direct:       the spec has NO `intervention:` line (direct is the default).
- spa:          the spec gets the top-level line:  intervention: spa
                (`capabilities:` says WHAT is edited; `intervention:` says HOW it reaches the
                model. capevolve.yaml-only — no CLI override.)
- VERIFY:       `cap-evolve check .capevolve/project` green for the ONE spec you prepared, and
                `intervention: sap` (a typo) REJECTED BY NAME, not silently defaulted to
                direct.

# 2. BENCHMARK / DATASET  (the eval) — INSTALL IT DURING INTAKE
- cap-evolve itself: there is NO virtualenv and nothing installed — create one first
                (uv venv -p 3.11 .venv) and `pip install -e core`.
- benchmark:    tau2-bench, airline domain
- repo:         https://github.com/skillberry-ai/skillberry-benchmarks.git
                pin commit a3a83266008275e9d800fd709927fa3dc4f23ec5 → vendor/skillberry-benchmarks
- install:      pip install -e vendor/skillberry-benchmarks/tau2/tau2-bench[skillberry]
- WHY this build, whichever arm: its runner already carries what SPA mode needs — Skillberry
                context headers on the agent's LLM calls, a merge of the proxy-side trajectory
                into tau2's own, and a `disconnect` at session end — and it still exposes the
                plain airline domain for direct. Using one build regardless of arm is what keeps
                a later comparison meaningful; a different runner per arm makes it worthless.
- domain:       direct → "airline";  spa → "airline_skillberry"
- tasks:        "adapter" — all 50 airline tasks from
                tau2.domains.airline.environment.get_tasks; no network in tasks()
- splits:       all 50 as train = val = test (no-holdout fit metric; the engine logs a
                splits_warning and the report flags the test number as a fit metric). Pin them
                in split_ids.json.

# 2b. THE BENCHMARK'S ENVIRONMENT SERVICE  [SPA ONLY — skip entirely for direct]
- tau2 HAS one — the Environment Manager. The intervention skill requires such a service
                and aborts without it; these are the facts it cannot infer:
- start it:     port 8004, inline, from cap-evolve's venv:
                  LITELLM_LOCAL_MODEL_COST_MAP=True nohup python -c "
                  import asyncio
                  from tau2.orchestrator.environment_manager import EnvironmentManager
                  asyncio.run(EnvironmentManager(host='127.0.0.1', port=8004).run())
                  " > env_manager.log 2>&1 &
                ~10s to start (importing tau2 pulls in litellm); POLL the port rather than
                sleeping. LITELLM_LOCAL_MODEL_COST_MAP=True skips litellm's doomed remote
                cost-map fetch, which otherwise stalls startup until timeout.
- its CALL SHAPE (what the shim must speak):
                  base URL:     http://127.0.0.1:8004   (also set SPA_REMOTE_ENV_URL in .env)
                  URL:          {base}/{env_id}/tools/{tool_name}
                  request:      POST {"name": <tool>, "arguments": {...}}
                  success:      result["content"] is a JSON *string* — json.loads it
                  failure:      result["content"] is a plain message; non-200 → raise
- per-rollout identity: the store's executor injects `env_id`, so no session plumbing is
                needed here.

# 3. RUNNER  (the agent under test)
- how to run:   tau2's own batch runner (adapter.run_batch -> tau2.runner.run_tasks)
- fast eval:    ALSO implement the optional adapter method
                run_trials(tasks, ctx, *, n_trials, base_seed) -> {task_id: [Rollout, ...]}.
                Run ALL num_trials in ONE tau2 run_tasks call with num_trials=N (grouped by
                sim.trial) at TAU2_MAX_CONCURRENCY=125, and return {task_id: [trial0, trial1, ...]}
                (len n_trials, trial-ordered). When present, cap-evolve calls it ONCE per candidate
                instead of looping run_batch per trial; per-trial persistence
                (rollouts/<split>/<task>__<tag>__t<k>.json) is UNCHANGED so pass^k / SE / resume
                keep working. This collapses N sequential eval passes into one batched run.
- apply(): implement the ONE arm you were asked for and nothing else. For spa, call the
                intervention skill's deploy helpers; for direct, read the candidate's policy +
                tools and pass them to tau2's Environment constructor. Guard it on the
                CANDIDATE'S SHAPE (is a skill package present?) rather than on the spec, so a
                spec/seed mismatch fails loudly instead of delivering the wrong way silently.
                apply() must NEVER raise: record a deploy failure and let the rollouts come back
                errored, so the harness EXCLUDES the candidate instead of scoring it 0.0.
- models:       tau2 model settings TAU2_AGENT_MODEL / TAU2_USER_MODEL, as litellm
                "openai/<model>" strings against the gateway in 3b (e.g.
                openai/aws/gpt-oss-120b). [SPA ONLY] the AGENT's model is the SPA-routed name
                (default `ibm/skillberry-local`) while the user simulator stays on the gateway
                model — the intervention skill states why that boundary is a correctness rule.
- concurrency:  TAU2_MAX_CONCURRENCY=125 on the direct arm. [SPA ONLY] start LOW (e.g. 4) —
                every agent call funnels through one proxy and one store process.

# 3b. ENVIRONMENT — LLM ACCESS  (the run owner's environment supplies this; do not hardcode)
- endpoint:     an OpenAI-COMPATIBLE gateway the run owner configures — no host is fixed here.
- credentials:  OPENAI_BASE_URL (+ OPENAI_API_BASE, same value — litellm reads either) and
                OPENAI_API_KEY in the repo-root `.env`. Load them the way the existing example
                does (a small loader that walks parent dirs and setdefault()s, no python-dotenv
                dependency). NEVER hardcode an endpoint or key in adapter code and never invent
                one — if either is missing, ASK and WAIT, because a wrong value 401s/404s every
                rollout and the baseline is a row of zeros that reads as a bad capability rather
                than a bad config.
- the OPTIMIZER's credentials are SEPARATE and already handled: the `claude-code` optimizer
                inherits them from the run owner's Claude Code environment. Nothing about them
                belongs in the spec or the adapter.
- agent AND user simulator:  aws/gpt-oss-120b  (TAU2_AGENT_MODEL / TAU2_USER_MODEL), routed as
                the litellm string `openai/aws/gpt-oss-120b`. Normalize to that form ONCE and
                idempotently — `openai/openai/…` 404s. Model ids are gateway ALIASES and
                CASE-SENSITIVE (`Azure/…` and `azure/…` can coexist), so confirm the alias
                against the gateway's own catalog before the first run rather than assuming it.
- VERIFY BEFORE SPENDING: one non-agent probe call must return 200 before any baseline — a
                single completion with the RESOLVED model id, not a models listing, so the
                probe proves the key AND the alias. Give it a GENEROUS max_tokens: a reasoning
                model spends the budget on thinking and returns HTTP 200 with EMPTY content on
                a tight cap, which looks like a broken model rather than a truncated reply.
- TLS: if the endpoint's certificate is not trusted, fix it explicitly (point at the right CA
                bundle) and record what you did. Do not silently disable verification — a run
                whose transport security was turned off must say so in PROJECT.md.
- NEVER LEAK CREDENTIALS: they must not appear in logs, in the persisted trajectories, in
                PROCESS.md / JOURNAL.md, or in the run record. cap-evolve copies the
                trajectories VERBATIM into the optimizer's working dir each iteration and
                `store: git` COMMITS every iteration, so a credential echoed into a trace
                becomes a committed secret. Redact before persisting anything.
- CUSTOM-HEADER GATEWAYS ARE OUT OF SCOPE HERE. This prompt assumes bearer auth, which every
                path supports unmodified. A gateway that authenticates by a custom HTTP header
                needs BOTH pinned clones patched to send it — that is implementation work, not
                configuration; see the intervention skill plan's open decisions before attempting it.
- the OTHER environment facts live where they belong: venv + benchmark clone in section 2; the
                environment service in 2b; the Skillberry stack's ports and provisioning in the
                intervention skill, per section 0.

# 4. SCORER  (what to optimize against) — and WHERE the metric comes from
- metric:       tau2's own task reward in [0,1] (required actions performed + info communicated)
- metric source: `sim.reward_info.reward` per simulation; the per-check breakdown is in
                `sim.reward_info` (db_check / action_checks / communicate_checks /
                nl_assertions / env_assertions). adapter.score() reads the reward +
                reward_info that run_batch stashed. score() must be DETERMINISTIC on a fixed
                rollout (the check gate enforces it) — read the recorded reward, never re-run.
- feedback:     gold-AWARE but gold-SAFE, and ARGUMENT-LEVEL — this IS the learning signal, so a
                tool-name-only message ("action X was wrong") is too coarse: the optimizer can only
                pattern-match to prose rules and plateaus. For EACH failing check, localize the
                defect at the argument level:
                  * for each mismatched write/action, name the differing ARGUMENT key + the AGENT'S
                    OWN wrong value (e.g. "book_reservation: payment_id='credit_card_9' is not on the
                    user's profile; available=[credit_card_4421, gift_card_8]"; "update_reservation_flights:
                    called on reservation res_A but the task targets a different one");
                  * for communicate misses, name the un-stated value when derivable from the agent's
                    own state (e.g. "did not state the computed total cost ($150 from your own observed
                    amounts)").
                Gold-SAFE: NEVER read or print the gold/expected value — derive everything from the
                agent's OWN messages/tool-calls and the user's OWN profile/db state (parsed from the
                agent's get_user_details/get_reservation_details tool results in the trace). Use
                reward_info only to know WHICH action/argument failed (the gold action's arg KEYS are
                safe, its VALUES are not). Fall back to the tool-name message when a piece isn't safely
                derivable.
- objective:    maximize mean reward on the VAL split

# 4b. TRAJECTORIES  (the FULL traces the optimizer reads) — PATH IS AN INPUT
- where:        persist tau2's native per-task results (full transcript + reward_info) via
                run_tasks(save_path=...) into a per-eval dir UNDER THE RUN, e.g.
                <run_dir>/trajectories/val/. On the spa arm the Skillberry build already
                merges the proxy-side trajectory into tau2's own, so one trace covers both.
- expose:       adapter.trajectories(split) returns that directory; cap-evolve copies it
                VERBATIM into the optimizer's workdir as ./trajectories/ each iteration
                (return None to fall back to cap-evolve's own per-rollout JSON).

# 5. OPTIMIZER  (proposes the edits) + MODEL + CREDENTIALS + CONTEXT
- optimizer:    claude-code
- model:        claude-opus-4-8
- credentials:  a logged-in Claude Code session (or ANTHROPIC_API_KEY) — the optimizer's
                credentials are SEPARATE from the gateway in 3b, which is for the agent under
                test.
- runner_repo_path:  vendor/skillberry-benchmarks   (read-only context: task definitions, the
                real tool implementations, the reward checks)
- optimizer instructions: author .capevolve/project/optimizer/INSTRUCTIONS.md from the
                scaffolded template, keeping every {{...}} placeholder intact. ONE file, SCOPED to the
                capabilities of the arm you prepared, pointed at by
                optimizer_instructions_file. Do NOT re-author what the template already carries
                (depth mandate, non-overfitting guardrail, STEP-0 reading mandate,
                cross-iteration file protocol) and do NOT restate each capability's edit space —
                point at ./guidance/<cap>/SKILL.md, which the harness materializes.
- the benchmark facts to ADD (what the template cannot know): the trajectories live in
                ./trajectories/ as tau2 simulation records whose reward_info carries the
                per-check breakdown — use it to localize the exact defect (expected vs actual
                argument) while keeping every edit GENERAL; the scoring source is
                sim.reward_info.reward; the data-model module the direct arm's tool code imports
                is tau2's airline data_model, materialized under ./guidance/sources/.

# 6. BUDGET / GATE
- FIRST a quick test on EACH arm prepared: max_iterations 1, num_trials 1, a 1–2 task split,
                    optimizer_skill mock. A task must really execute and return a real reward
                    with rollout.error null — an instant all-zero baseline means the rollouts
                    errored, so fix that before spending anything.
- algorithm:        hill-climb  (--focus all)
- max_iterations:   2          num_trials: 5      task_id: 9
- per-iteration optimizer $ cap:  optimizer_usd_per_iter 40   (claude --max-budget-usd, CLI-enforced)
- optimizer_max_turns: 400      (generous; the $ cap is the real per-iteration ceiling)
- max_usd: 400      max_optimizer_usd: 400
- gate:             paired (per-task paired SE — banks real 1-task gains), k_se 0.2
- store:            git          (every iteration committed for an inspectable process)
- stall:            3
- ONE ARM PER RUN. If I later ask for the other arm, it is a separate onboarding in its own
                    project — and the two numbers are NOT like-for-like (under direct the
                    optimizer may change what the tools DO; under spa only how they are presented
                    and composed). Report them side by side, never averaged.
```
