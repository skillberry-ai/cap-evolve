# appworld blackbox: the system prompt, delivered by the Skillberry Store + Proxy-Agent

The same AppWorld agent and data as the direct example in [`..`](../README.md), but the capability under
optimization never reaches AppWorld's side. It lives in the Skillberry Store as a skill, and the
Skillberry Proxy-Agent (SPA) injects it into every LLM call.

| | direct (`..`) | blackbox (this folder) |
|---|---|---|
| Agent under test | AppWorld's simplified ReAct code agent, subclassed (`CapReActAgent`) | AppWorld's simplified ReAct code agent, **stock** |
| Prompt the client sends | the candidate's `policy/instructions.txt` | AppWorld's own stock `instructions.txt`, unchanged |
| Capabilities | `[system-prompt, tools]` (prompt, REPL helpers, API notes) | `[system-prompt]` only: the store skill's `SKILL.md` |
| Where the candidate goes | rendered by the harness, in-process | the Skillberry Store; the proxy injects it as the system prompt |
| Data, splits, scoring, lints for task-specific hints, optimizer isolation | shared | shared (reused from `..`) |

There is no PROMPT.md: the approach is built from the direct one, not generated.

## Layout

```
adapters/adapter.py              the cap-evolve adapter: data/seal/score as in the direct example (..); run_trials lints, deploys, runs episodes
adapters/appworld_tailoring.py   context headers, the history-start marker, SPA's upstream model from AW_*, deploy()
adapters/aw_bb_agent.py          one episode: AppWorld's stock agent, LLM calls to the proxy with the headers
adapters/bb_lints.py             SKILL.md lints (reuses ../adapters/lints.py)
optimizer/INSTRUCTIONS.template.md   the optimizer's instructions for a SKILL.md-only edit surface
scripts/make_seed_skill.py       writes the seed SKILL.md at setup time (never committed: it embeds AppWorld's app list)
scripts/provision_stack.py       store + proxy at the pinned commits in the shared vendor/ (never deletes; a stale clone is an error)
scripts/setup_project.sh         scaffold the project, generate the seed, provision, run cap-evolve check
scripts/launch.sh                run (or resume) with the optimizer isolated; AW_SPEC=capevolve.smoke.yaml for a smoke
capevolve.yaml, capevolve.smoke.yaml, smoke_split.json   the run spec (search settings = the direct example, ..) and a 1-task smoke
tests/test_blackbox.py           offline tests (no AppWorld, store, proxy or model)
```

The project also gets `../adapters/aw_agent.py` and `lints.py` (the harness: hardened code
guard, gold-free records, error redaction, worker-environment allowlist, the 8-gram and
supervisor-contact checks) and uses `../sandbox` and `../scripts` for the
optimizer's isolation, splits and roots.

## How a call flows

```
AppWorld's stock ReAct agent (one process per episode, aw_bb_agent.py)
  sends: its 23 stock prompt messages + the episode so far, model openai/ibm/skillberry-local
  headers: skillberry-context-env_id (per episode), -task_id, -plugin: appworld,
           -history_start_regex: ^\s*Using these APIs, now generate code to solve the actual task:
           -template-main_user-{first_name,last_name,email,phone_number} (the task's supervisor)
        │
        ▼
Skillberry Proxy-Agent (pinned in skills/interventions/llm-proxies/blackbox/scripts/blackbox_env.py)
  1. drops the client's messages before the real task turn (the marker)
  2. fetches my_skill's prompt (SKILL.md) from the store and renders it with the main_user values
  3. sends to SPA_MODEL_NAME: [system: rendered SKILL.md] + the real task turn + the episode so far
```

The proxy's `history_start_regex` and `template` hooks are opt-in per request: a client that sends
neither header gets the proxy's usual behaviour.

## Seed

`SKILL.md` is AppWorld's stock prompt from its first line through the `**Key instructions**` turn,
byte for byte, plus frontmatter (`name: my_skill`) and a short header saying the USER/ASSISTANT
turns are a worked few-shot example. The final turn ("Using these APIs, now generate code to solve
the actual task: … Task: {{ instruction }}") is not in it: the client sends it, and the proxy keeps
it. `{{ app_descriptions }}` is rendered at setup from AppWorld's app list, exactly as AppWorld's
agent renders it (identical for every task); the `{{ main_user.* }}` slots stay for the proxy.

## Models

The proxy's upstream model comes from the same variables the direct approach uses
(`../adapters/aw_agent.py`):

| Variable | Meaning in this approach |
|---|---|
| `AW_MODEL_NAME` | the model; an OpenAI-compatible provider prefix (`hosted_vllm/`, `litellm_proxy/`) becomes `openai/` for SPA's litellm. `AW_SPA_MODEL` overrides. |
| `AW_MODEL_URL` | the endpoint (`{{MODEL_SERVER_URL}}` filled from `MODEL_SERVER_URL` / `RITS_URL`) |
| `AW_KEY_HEADER` | must be `bearer`: the proxy sends a standard `Authorization: Bearer` key, so RITS's custom `RITS_API_KEY` header cannot be served |
| `AW_KEY_ENV`, `AW_SECRETS_FILE` | the key's variable name, read from the secrets file (only that line); handed to the proxy, never to the episode worker |

## Lints

`adapters/bb_lints.py` rejects a candidate before any episode runs:
- the skill folder holds `SKILL.md` only, with frontmatter `name: my_skill`;
- the only placeholders are the four `{{ main_user.* }}` fields, each kept at least once; no other
  `{{ }}`, no `{% %}` block, no filter, no `{{ instruction }}`;
- the rendered app list stays verbatim (in the direct approach the optimizer only sees its
  placeholder);
- the demo keeps its `USER:` / `ASSISTANT:` turns; at most 8,500 tokens;
- no 8-gram from a train/dev instruction and no supervisor contact (the direct approach's check).

## Setup

1. The direct approach's Setup steps 1-2 (`../README.md`): the patched AppWorld and
   `venv-aw` under `$AW_EVAL`, `root_full`, `root_opt`, the lint cache and the reference docs.
2. `bash scripts/setup_project.sh` (base folder `$AW_EVAL/.capevolve-blackbox` by default): scaffolds the project, writes the
   seed `SKILL.md` and `$AW_EVAL/app_descriptions.json`, provisions the store and proxy at the
   pinned commits in the repo's shared `vendor/`, and runs
   `cap-evolve check`. A clone there at another commit stops setup: delete it
   (e.g. `rm -rf vendor/skillberry-agent`) and run setup again to clone the pin.

## Running

```
export AW_EVAL=... AW_MODEL_NAME=... AW_MODEL_URL=... AW_KEY_HEADER=bearer AW_KEY_ENV=...   # README: Models
bash ../scripts/check_optimizer_isolation.sh sandbox       # must PASS (as in the direct approach)
AW_SPEC=capevolve.smoke.yaml bash scripts/launch.sh   # 1 task, 1 trial, 1 iteration
bash scripts/launch.sh                                # the full search
AW_RUN_TS=20261118_171500 bash scripts/launch.sh "" --resume   # resume that run in place
```

One base folder (default `$AW_EVAL/.capevolve-blackbox`) holds the project and every run: `project/` and one
`run_<YYYYMMDD_HHMMSS>` per launch, named by its start time. It must be under `$AW_EVAL`, because the
optimizer's isolation only binds a working dir inside it. Pass another base folder as the first
argument to keep a separate set.

Offline tests: `python -m pytest benchmarks/appworld/examples/react_agent/blackbox/tests`.

## Known gaps

- The demo arrives as text inside one system message, not as real chat turns. The model can then
  continue it as a transcript (invented `USER: Output:` turns in one reply). The proxy drops
  `stop`, so a stop sequence cannot prevent it today; the optimizer instructions name the failure
  mode so it can be fixed in the prompt.
- No final-window script yet: `../scripts/final_window.py` runs the direct approach.
