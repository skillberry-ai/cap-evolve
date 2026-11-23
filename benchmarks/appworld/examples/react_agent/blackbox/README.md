# appworld blackbox: the system prompt and REPL tools, delivered by the Skillberry Store + Proxy-Agent

The same AppWorld agent and data as the direct example in [`..`](../README.md), but the capability under
optimization never reaches AppWorld's side. It lives in the Skillberry Store as a skill, and the
Skillberry Proxy-Agent (SPA) injects it into every LLM call.

| | direct (`..`) | blackbox (this folder) |
|---|---|---|
| Agent under test | AppWorld's simplified ReAct code agent, subclassed (`CapReActAgent`) | AppWorld's simplified ReAct code agent, **stock** |
| Prompt the client sends | the candidate's `policy/instructions.txt` | AppWorld's own stock `instructions.txt`, unchanged |
| Capabilities | `[system-prompt, tools]` (prompt, REPL helpers, API notes) | the same: `my_skill/SKILL.md` (the store skill), `tools/helpers.py`, `tools/api_notes.json` |
| Where the candidate goes | rendered by the harness, in-process | `SKILL.md`: the Skillberry Store, and the proxy injects it as the system prompt. `tools/`: the episode worker runs it in the trial's REPL before step 1, as direct does |
| The REPL | in the episode's process | the trial's own AppWorld environment server (`AW_REMOTE_REPL`, default on) |
| Data, splits, scoring, lints for task-specific hints, optimizer isolation | shared | shared (reused from `..`) |

There is no PROMPT.md: the approach is built from the direct one, not generated.

## Layout

```
adapters/adapter.py              the cap-evolve adapter: data, seal and scoring as in the direct example (..);
                                 run_trials lints the candidate, deploys it, then runs the episodes
adapters/appworld_tailoring.py   the context headers, the history-start marker, SPA's upstream model from AW_*,
                                 deploy(), the environment-server ports, and the tools' REPL code (repl_code)
adapters/aw_bb_agent.py          one episode: AppWorld's stock agent, its LLM calls sent to the proxy with the headers
adapters/aw_env_server.py        one AppWorld environment server (the remote REPL) for one trial
adapters/bb_lints.py             the lints: candidate folder, SKILL.md and tools/ (reuses ../adapters/lints.py)
optimizer/INSTRUCTIONS.template.md   the optimizer's instructions (edit surface: my_skill/SKILL.md and tools/)
seed_capability/                 the committed seed, which is what every candidate looks like:
  my_skill/SKILL.md              the store skill (the system prompt); the app list is a {{ app_descriptions }} placeholder
  tools/helpers.py               REPL helper functions (empty in the seed)
  tools/api_notes.json           API notes (empty in the seed); both tools/ files are the direct seed's own
scripts/setup_project.sh         scaffolds the project, renders the seed into it, provisions, runs cap-evolve check
scripts/make_seed_skill.py       renders the committed seed into the project (fills in the app list, which comes from
                                 AppWorld's installed app code and is never committed); --build rewrites the seed
scripts/provision_stack.py       the store and proxy at the pinned commits in the shared vendor/ (never deletes;
                                 a clone at another commit is an error)
scripts/launch.sh                runs (or resumes) a run with the optimizer isolated
capevolve.yaml                   the run spec: the full search (search settings = the direct example's, ..)
capevolve.smoke.yaml, smoke_split.json   1 task, 1 trial, 1 iteration
capevolve.fix10.yaml, fix10_split.json   the 10 fixed tasks (+ 5 held-out test tasks) shared with the direct
                                         approach, 5 trials, 3 iterations
PROJECT.template.md              the project's PROJECT.md (resolved inputs), rendered by setup_project.sh
tests/test_blackbox.py           offline tests (no AppWorld, store, proxy or model needed)
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
     (no tools bound: the skill is SKILL.md only)
        │
        ▼
AppWorld's stock agent runs the reply's code in its world, on the trial's own environment server.
```

**The tools** (`tools/helpers.py` and `tools/api_notes.json`) are installed in that world once,
before step 1, exactly as the direct approach installs them: the adapter turns them into the direct
approach's REPL code (`aw_agent.setup_snippet`), once per candidate, and passes it in each episode's
spec; the episode worker runs it with `world.execute` right after the world exists, before the stock
agent starts (direct runs the same code at the same point, from `CapReActAgent.initialize`). The code
defines the helpers and wraps `apis.api_docs.show_api_doc` / `show_api_descriptions` to add a `note`
field, so a note shows up in the `Output:` of the agent's own doc lookup and stays in the history. What
the REPL printed is kept as `setup_output` in the episode record, as in direct.

The model is told about the helpers as in the direct approach: the SKILL.md deployed to the store
ends with direct's generated sentence (`aw_agent.helper_notice`: "Pre-defined helper functions are
available in the REPL (call them directly; see their docstrings with help(name)): name(a, b), …";
`appworld_tailoring.deployed_skill_md`). Direct puts it just before the final task block; the
deployed SKILL.md ends where the client's final task turn begins, so it is the same place, inside
the system prompt.

The benchmark is unchanged: the agent is AppWorld's stock one (no subclass, no override), and the
REPL is AppWorld's own supported remote environment. The app databases, which are what is scored,
are never touched. The load is not a tool the model calls: a model-called loader looped, and the
few-shot conversation example has no tool calls.

The proxy's `history_start_regex` and `template` hooks are opt-in per request: a client that sends
neither header gets the proxy's usual behaviour.

## Seed

The seed is committed in `seed_capability/`; the spec's `capability_path` is `seed_capability`, so a
candidate is that folder: `my_skill/SKILL.md` and `tools/`.

`SKILL.md` is AppWorld's stock prompt from its first line through the `**Key instructions**` turn,
byte for byte, plus frontmatter (`name: my_skill`) and a short header saying the USER/ASSISTANT
turns are a worked few-shot example. The final turn ("Using these APIs, now generate code to solve
the actual task: … Task: {{ instruction }}") is not in it: the client sends it, and the proxy keeps
it. `{{ app_descriptions }}` stays a placeholder in the committed file, as in the direct seed,
and is rendered into the project's copy at setup, exactly as AppWorld's agent renders it
(identical for every task); the `{{ main_user.* }}` slots stay for the proxy.

`tools/helpers.py` (a docstring) and `tools/api_notes.json` (`{}`) are the direct seed's own files:
they load nothing, so no loader is deployed and the seed is the stock agent.

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
- `my_skill/` holds `SKILL.md` only (any other file would be injected or become a tool), with
  frontmatter `name: my_skill`;
- `tools/` holds `helpers.py` and `api_notes.json` only, under the direct approach's rules for the
  same files;
- the only placeholders are the four `{{ main_user.* }}` fields, each kept at least once; no other
  `{{ }}`, no `{% %}` block, no filter, no `{{ instruction }}`;
- the rendered app list stays verbatim (in the direct approach the optimizer only sees its
  placeholder);
- the few-shot conversation example keeps its `USER:` / `ASSISTANT:` turns; at most 8,500 tokens;
- no 8-gram from a train/dev instruction and no supervisor contact (the direct approach's check).

## Setup

**One command:** `bash ../setup.sh --blackbox` does both steps below, and skips what is already in
place, so it is safe to re-run.

1. The direct approach's Setup steps 1-2 (`../README.md`): the patched AppWorld and
   `$AW_EVAL/.venv` (or `AW_VENV`), `root_full`, `root_opt`, the lint cache and the reference docs.
2. `bash scripts/setup_project.sh` (base folder `$AW_EVAL/.capevolve-blackbox` by default): scaffolds the project,
   renders the committed seed into it (and writes `$AW_EVAL/app_descriptions.json`), provisions the store and proxy at the
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

- The few-shot conversation example arrives as text inside one system message, not as real chat
  turns. The model can then continue it as a transcript (invented `USER: Output:` turns in one
  reply). The proxy drops `stop`, so a stop sequence cannot prevent it today; the optimizer
  instructions name the failure mode so it can be fixed in the prompt.
- No final-window script yet: `../scripts/final_window.py` runs the direct approach.
