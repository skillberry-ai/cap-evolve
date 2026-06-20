# The prompt — onboard tau2-bench airline as a new benchmark and optimize it

Paste this to your coding agent (Claude Code) at the cap-evolve repo root and say
**"follow RUN.md."** Intake treats this as a brand-new benchmark: the integration
step **clones + installs tau2-bench**, wires RITS, writes the adapter, runs the
`cap-evolve check` gate, then the full optimize → gate → sealed-test → report loop
with a live dashboard. Everything below is the input intake needs.

```text
Follow RUN.md to run a cap-evolve optimization. Onboard this as a brand-new
benchmark — the intake/integration step should CLONE + INSTALL it (not assume it
exists). Here is everything intake needs:

# 1. CAPABILITY TO OPTIMIZE  (a copy is edited each iteration; the original is never touched)
- type:         [system-prompt, tools]      # the airline POLICY and the TOOLS, jointly
- tools means:  edit tool docstrings/descriptions; edit tool behavior/code; and
                ADD/REMOVE tools, including composite tools that call existing tools
- seed:         tau2-bench's canonical airline policy + its airline tool set
- seed tools:   the seed tools file must be CLEAN, runnable code as intake would
                produce it — real tool bodies, no baked-in optimizer/editing
                instructions in its docstrings (what the optimizer may change to the
                tools lives in the tools capability SKILL.md, not in the seed file)
- capability_sources:  set `capability_sources` to the benchmark's data-model/types
                module(s) the tools import (here tau2's airline data_model — the source
                of FlightDB, Reservation, Passenger, Payment, etc.). cap-evolve copies
                these verbatim into the optimizer's workdir so it can write correct
                new-tool code against the real types.

# 2. BENCHMARK / DATASET  (the eval) — INSTALL IT DURING INTAKE
- benchmark:    tau2-bench, airline domain
- repo:         https://github.com/sierra-research/tau2-bench   (latest main; record the resolved commit)
- install:      git clone as a sibling dir ../tau2-bench, then `pip install -e ../tau2-bench`
- tasks:        "adapter" — the adapter loads all 50 airline tasks from tau2
                (tau2.domains.airline.environment.get_tasks)
- splits:       all 50 tasks as train = val = test  (no-holdout fit metric; the engine
                logs a splits_warning and the report flags the test number as a fit metric)

# 3. RUNNER  (the agent under test) + MODELS + CREDENTIALS
- how to run:   tau2's own batch runner (adapter.run_batch -> tau2.runner.run_tasks)
- fast eval:    ALSO implement the optional adapter method
                run_trials(tasks, ctx, *, n_trials, base_seed) -> {task_id: [Rollout, ...]}.
                Run ALL num_trials in ONE tau2 run_tasks call with num_trials=N (grouped by
                sim.trial) at TAU2_MAX_CONCURRENCY=125, and return {task_id: [trial0, trial1, ...]}
                (len n_trials, trial-ordered). When present, cap-evolve calls it ONCE per candidate
                instead of looping run_batch per trial; per-trial persistence
                (rollouts/<split>/<task>__<tag>__t<k>.json) is UNCHANGED so pass^k / SE / resume
                keep working. This collapses N sequential eval passes into one batched run.
- agent AND user simulator:  openai/gpt-oss-120b  via IBM RITS
- RITS wiring:  litellm model "hosted_vllm/openai/gpt-oss-120b" + per-call api_base +
                extra_headers {"RITS_API_KEY": ...}  (NO litellm monkeypatch, NO tau2 fork)
- credentials:  RITS_API_KEY (+ RITS_API_URL) in the repo-root .env
- concurrency:  TAU2_MAX_CONCURRENCY=125

# 4. SCORER  (what to optimize against) — and WHERE the metric comes from
- metric:       tau2's own task reward in [0,1] (required actions performed + info communicated)
- metric source: tau2 computes it per simulation as `sim.reward_info.reward`; the per-check
                breakdown is in `sim.reward_info` (db_check / action_checks / communicate_checks /
                nl_assertions / env_assertions). Implement adapter.score() to read the reward +
                reward_info that run_batch stashes from each simulation, and verify score() is
                deterministic on a fixed rollout (the `cap-evolve check` gate enforces this).
- feedback:     gold-AWARE but gold-SAFE — which required actions/info were missed (the learning
                signal), derived from reward_info checks; never leak the gold answer.
- objective:    maximize mean reward on the VAL split

# 4b. TRAJECTORIES  (the FULL traces the optimizer reads) — PATH IS AN INPUT
- where:        tau2's batch runner can persist its native per-task simulation results
                (full message transcript + reward_info) to a directory via run_tasks(save_path=...).
                Point run_batch's save_path at a per-eval dir UNDER THE RUN, e.g.
                <run_dir>/trajectories/val/  (any structure/format tau2 writes is fine).
- expose:       implement adapter.trajectories(split) to return that directory. cap-evolve copies
                it VERBATIM into the optimizer's working dir as ./trajectories/ each iteration, so
                the optimizer reads the complete, unmodified traces (not a lossy summary).
                (If you cannot persist native files, return None — cap-evolve falls back to copying
                its own per-rollout JSON, which already embeds each rollout's full message trace.)

# 5. OPTIMIZER  (proposes the edits) + MODEL + CREDENTIALS + CONTEXT
- optimizer:    claude-code
- model:        claude-opus-4-6
- credentials:  a logged-in Claude Code session (or ANTHROPIC_API_KEY)
- runner_repo_path:  ../tau2-bench  (the cloned checkout — surfaced to the optimizer as
                read-only context so it can consult tau2's tools/scoring/task structure)
- optimizer instructions: author .capevolve/project/optimizer/INSTRUCTIONS.md from the scaffolded
                template (keep its {{...}} placeholders intact — the harness fills them per
                iteration). Keep it short on meta-narration but explicit and DEMANDING on iteration
                depth, and impose a DEPTH MANDATE: state the GOAL (maximize the eval score) and require
                each iteration to be a substantial multi-cluster, multi-edit-class sweep — improve
                multiple tools' code + validation + enriched returns/errors, add new tools, sharpen
                many tool docs, AND fix the prompt, together in ONE candidate, with each fix scoped to
                protect passing tasks (non-regression). "Freedom" does NOT mean do little — a single
                small edit is an under-used iteration; diagnose ALL clusters and fix as many as
                possible, fanning out one subagent per failure cluster, each in its own worktree, then
                merging all edits into ONE candidate. Tailor only the "READ THESE" pointers
                (./trajectories/, ./guidance/<cap>/SKILL.md for EACH selected capability,
                ./guidance/diagnose/SKILL.md, ./guidance/optimizer/claude-code.md, ./guidance/sources/
                [the data model], ./STATE.md, ./MEMORY.md, ../tau2-bench).
- scope to the SELECTED capabilities: BOTH system-prompt and tools are selected here, so the
                instructions reference BOTH skills and the optimizer may edit EITHER. (Generic rule: if
                only ONE capability were selected, the instructions, the guidance, and the editable
                files must cover ONLY that one — e.g. tools-only ⇒ no prompt-editing guidance, no
                system-prompt skill, the prompt is not presented as editable.)
- EDIT BOTH the prompt AND the tools — they are EQUALLY fair game; pick whatever fixes the clusters:
    * PROMPT (system-prompt), per ./guidance/system-prompt/SKILL.md: rewrite/clarify a rule, add the
      WHY, consolidate redundant rules, add a missing rule grounded in the trajectories, add an
      example, tighten the output contract. NEVER drop a needed rule (change/consolidate/add, don't
      delete). The prompt is HIGH-VALUE — not a last resort.
    * TOOLS, per ./guidance/tools/SKILL.md: prefer CODE-BEARING changes — a validation tool that
      enforces a rule in code then calls the existing tool and removes the raw one; a workflow/loop
      tool that collapses a recurring sequence; a composite WRITE tool that performs a stalled
      multi-step action in code (then removes the raw write primitives) so the agent can't analyze,
      confirm, then fail to execute. Improve tool docs AND RETURN VALUES (actionable errors + next
      steps) — the docstring and return are what the agent sees. Never bare-remove a tool — add a
      replacement that calls it, verify, then swap registration.
- process flow: READ ./MEMORY.md + ./STATE.md FIRST (don't re-submit a rejected edit verbatim — a
                redesigned version may still work; don't abandon a high-value cluster); analyze the
                current best step's ./trajectories/; use the per-task IMPACT of prior candidates + the
                currently-passing tasks the harness lists to steer AWAY from regressions (don't
                re-introduce a change that broke a task) WITHOUT freezing; make a bold, multi-part edit
                across the selected capabilities; end STATE.md with the rich "## Handover for next
                iteration" section (approaches tried, lessons, recommendation, what regressed as-tried).

# 6. BUDGET / GATE
- algorithm:        hill-climb  (--focus all)
- max_iterations:   10          num_trials: 10
- per-iteration optimizer $ cap:  optimizer_usd_per_iter 40   (claude --max-budget-usd, enforced by the CLI itself)
- optimizer_max_turns: 400      (generous; the $ cap is the real per-iteration ceiling)
- max_usd: 400      max_optimizer_usd: 400
- gate:             significant (paired), k_se 0.2
- store:            git          (every iteration committed for an inspectable process)
```

> The bundled `examples/tau2_airline/` is the **result** of following this prompt:
> the adapter (`adapters/adapter.py`), the RITS shim (`adapters/rits.py`), the seed
> capability (`seed_capability/`), and the optimizer instructions
> (`.capevolve/project/optimizer/INSTRUCTIONS.md`) are what the intake/implement-and-check
> flow produced — including `adapter.trajectories()` (native tau2 traces) and `score()`
> (reads `reward_info`). `setup.sh` is the executable transcript of that onboarding
> (clone+install tau2, scaffold via intake, wire the adapter + trajectories + scoring,
> `cap-evolve check`); `run.sh` runs the full optimization with the live dashboard. See `DEMO.md`.
