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
                iteration), tailoring the guidance + the "READ THESE" pointers (./trajectories/,
                ./guidance/<cap>/, ./STATE.md, ./MEMORY.md, ../tau2-bench) to this benchmark.
                For the tools capability, the primary edit is CODE-BEARING tools (a validation tool
                that enforces a policy rule in code then calls the existing tool and removes the raw
                one; a workflow tool that collapses a recurring sequence) — not docstring prose.

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
