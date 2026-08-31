---
name: spa
description: The Skillberry proxy intervention — put the optimized capability in the Skillberry Store and let the Skillberry Proxy-Agent (SPA) inject it into the agent's LLM calls, so the benchmark never sees skill files. Use when a capevolve.yaml sets `intervention: spa`, or when you need to provision, start, deploy to, stop or clean that stack.
component: intervention
argument-hint: "[--json]   # run.py reports status; lifecycle is driven from spa_env"
allowed-tools: Read, Write, Edit, Bash
provides: []
needs: []
---

# Intervention: SPA (the Skillberry proxy)

An **intervention** answers *how a candidate reaches the model under test* — as opposed to a
**capability**, which is *what gets edited*. The two are independent: the same
`skill-package` capability can be delivered by writing files where a runner reads them
(`intervention: direct`) or by this intervention.

In SPA mode:

```
benchmark runner
  └── the agent's LLM call ──► SPA (host:7000) ──► Skillberry Store (host:8000)
                                    │                  (resolves ONE skill:
                                    │                   prose -> prompt enrichment,
                                    │                   scripts/ -> callable tools)
                                    └──────────────► upstream LLM
  other LLM calls (user simulator, judge, verifier) ──► upstream LLM, NEVER SPA
```

The agent gets no skill files, no mounted directory, no visible prompt edit — which is
the shape Skillberry actually ships, so optimizing here optimizes the real thing.

## Requirements from the benchmark

Two things must already be true of the runner, and this intervention checks rather than
supplies them. Onboard a runner that lacks either and the data is wrong, not missing.

* **The runner must be SPA-aware.** Three integrations have to be present for SPA mode to
  produce correct data: Skillberry context headers on the agent's LLM calls, a merge of the
  proxy-side trajectory into the runner's own, and a `disconnect` at session end. A
  Skillberry-aware build carries them; a stock runner does not.
* **The benchmark must front its environment over HTTP.** Store-hosted tools execute in the
  store's process, not where the benchmark's state lives, so the skill's tools can only reach
  that state through a service the benchmark provides. This intervention only health-checks it,
  via `SPA_REMOTE_ENV_URL`.

## Inputs / outputs (manifest tokens)

`needs: []`, `provides: []` — deliberately. An intervention owns an out-of-process delivery
stack, not a step in the run DAG, so it neither consumes nor produces a pipeline token. It is
selected by the spec (`intervention: spa`), not sequenced by `orchestrate`.

## How to run

`run.py` reports STATUS and nothing else — there is no `up`/`deploy`/`down`/`clean`
subcommand:

```bash
python skills/interventions/llm-proxies/spa/scripts/run.py [--json]   # per-service: provisioned, running, healthy
python skills/interventions/llm-proxies/spa/scripts/check.py          # offline contract check, no services needed
```

Everything else is a call into the library, which is what an adapter and an onboarding
step use anyway — one place to change, no CLI surface to keep in sync:

```python
import sys; sys.path.insert(0, "skills/interventions/llm-proxies/spa/scripts")
import spa_env

spa_env.provision()                       # clone + venv + install both services (idempotent)
spa_env.start_store()                     # EXECUTE_PYTHON_LOCALLY=True, health-checked
spa_env.import_standalone_tools(mod, tags=(FROZEN_TAG,))   # the project's own tag
spa_env.upload_skill(skill_dir)           # primitives FIRST, then the skill
spa_env.start_spa(SKILL_NAME)             # SPA binds ONE skill at start
spa_env.status()                          # what run.py prints
spa_env.stop_spa(); spa_env.stop_store()
spa_env.clean()                           # drops clones/venvs/logs under vendor/
```

`start_store` / `start_spa` are idempotent: a healthy service is reported, never
restarted — restarting SPA mid-evaluation would swap the skill under a running rollout.

## Using it from an adapter

```python
from spa_env import Protection, reset_store_to_skill, restart_spa

PROTECT = Protection(tags=(FROZEN_TAG,))           # the frozen substrate, by tag

def apply(self, candidate_dir, edits=None):
    if edits:
        self.materialize(candidate_dir, edits)
    self._deploy_error = None                       # never inherit the last candidate's
    skill_dir = Path(candidate_dir) / SKILL_NAME
    if not (skill_dir / "SKILL.md").exists():
        self._deploy_error = f"{SKILL_NAME}/SKILL.md missing under {candidate_dir}"
        return
    try:
        reset_store_to_skill(skill_dir, SKILL_NAME, PROTECT)
        restart_spa(SKILL_NAME)
    except RuntimeError as e:
        self._deploy_error = str(e)                  # MUST NOT raise — see below
```

**`apply()` must never raise.** cap-evolve enters `live()` inline, so an exception aborts
the whole run with the budget half spent over one flaky restart. Record the failure and
let `run_batch`/`run_trials` return errored rollouts: the harness then *excludes* the
candidate instead of scoring it 0.0, which is correct, because a failed deployment is
infrastructure noise and not a verdict on the capability.

## Facts that cost someone a debugging session

* **SPA serves exactly ONE skill**, resolved `SKILL_UUID` > `SKILL_NAME` > *a search of
  the chat history*. That last fallback is silent and looks like success **even against an
  empty store**, so `start_spa()` requires a name and clears `SKILL_UUID`.
* **Ports 7000/7001 are fixed** in SPA and hardcoded by its consumers. On macOS,
  ControlCenter holds 7000 for AirPlay Receiver by default (System Settings > General >
  AirDrop & Handoff).
* **A stale PID sentinel** makes `make run` print "service is already running" and exit 0
  without starting anything, after which the health check can only time out. `make stop`
  does not remove it; we always do.
* **`lsof -ti :PORT` needs `-sTCP:LISTEN`** — without it, lsof also lists *clients* of the
  port, and cap-evolve's own runner is a client of SPA.
* **SPA must bind `0.0.0.0`** to be reachable from a container, which reaches the host at
  the Docker bridge gateway (Linux/WSL2, usually `172.17.0.1`) or `host.docker.internal`.
* **The store's delete cascade silently leaves tools behind.** `delete_skill` deletes the
  manifest first and the tools second, for that reason.
* **Every public top-level function** in a skill's `scripts/*.py` becomes its own tool;
  helpers must be nested and `_`-prefixed.
* **SPA reports no token usage.** Rollout `cost_usd`/`tokens` are 0 and any `max_usd`
  ceiling is inert — only optimizer budgets bind. A 0 in the cost panel means *not
  measured*, not free.
* **Never put an API key in the `llm_args` you hand a runner.** A runner may record the
  config it was given — a runner may write `llm_args` verbatim into its results file
  (e.g. under `info.agent_info.llm_args` / `info.user_info.llm_args`). That file is the one adapters
  persist and expose via `trajectories()`, which cap-evolve copies VERBATIM into the
  optimizer's workdir each iteration and `store: git` COMMITS. So a key passed that way
  becomes a committed secret that was also shipped to the optimizer. `upstream_llm_args()`
  therefore returns **no** `api_key` by default (litellm reads `OPENAI_API_KEY` from the
  environment on the `openai/` route); it still validates the key so a missing credential
  fails at config time instead of as a wall of 401s. Observed for real on a benchmark
  baseline. Scrub defensively too — persisted traces are the last place to discover this.

## Pinned versions

`scripts/spa_env.py` holds the pins (store tag `0.2.1`, agent commit `e359494`), each
env-overridable (`SKILLBERRY_STORE_REF`, `SKILLBERRY_AGENT_REF`) for a bisect. Both
services need their own Python 3.11 venv, created with `uv`.

## What good vs bad looks like

* **Good:** the stack is provisioned once at onboarding and only STARTED by a run; every
  candidate's deploy resets the store to that candidate's single skill and restarts SPA; the
  frozen substrate survives each reset; the agent's calls go through SPA while the user
  simulator and any judge go straight upstream.
* **Bad:** a run that provisions on the operator's behalf; a deploy whose failure raises out
  of `apply()` and aborts the run instead of erroring the candidate's rollouts; a restart that
  silently keeps serving the previous candidate's skill; a simulator or judge routed through
  SPA, which injects the capability into the very thing measuring it.

## References

* `scripts/spa_env.py` — the library: provisioning, service lifecycle, store deployment,
  agent routing. Read it before adding a command; everything else here calls into it.
* `scripts/check.py` — the offline contract check (pins, vendor layout), runnable with no
  services up.
* `core/cap_evolve/intervention.py` — the `intervention:` spec field: validation by name,
  preflight, and the refusal to provision.
