# appworld: cap-evolve on AppWorld

Optimizes an agent on [AppWorld](https://github.com/StonyBrookNLP/appworld): everyday tasks in
simulated apps (music, payments, email, phone, files…), solved by an agent that writes Python
against the apps' APIs and graded on the final app state. Two arms share one harness:

| arm | what it is | what it learns |
|---|---|---|
| `seed` | AppWorld's official simplified ReAct code agent, stock prompt | nothing |
| `cape-hc` | cap-evolve, `hill-climb --focus all`, capabilities `[system-prompt, tools]` | the prompt, REPL helper functions, API notes |

Search uses only AppWorld's official `train` (90) and `dev` (57) splits; results come from
`test_normal` (168), scored for both arms in one interleaved window. `test_challenge` is not used.
Defaults: agent `openai/gpt-oss-120b` on IBM RITS, optimizer `aws/claude-sonnet-5-5`, both
configurable.

## Layout

```
adapters/adapter.py     cap-evolve adapter: tasks, run_trials (one subprocess per episode), score
adapters/aw_agent.py    CapReActAgent + the one-episode worker (the harness)
adapters/lints.py       candidate lints, also run by the optimizer before it stops
seed_capability/        policy/instructions.txt (stock prompt, byte copy), tools/
optimizer/              intake-customized INSTRUCTIONS template for the optimizer
patches/                18-line AppWorld patch: header auth for the agent model, never logged
sandbox/                optimizer isolation: the `claude` shim, the namespace fallback, settings templates
scripts/                data roots, splits, acceptance checks, launch, final window, analysis, scan
tests/                  offline tests, one file per module under test (no AppWorld, no model)
```

## Setup

Everything heavy lives under `$AW_EVAL` (default `/tmp/aw_eval`).

1. AppWorld + its agents **from source** at `42b5bcf`, in a Python 3.11 venv `$AW_EVAL/venv-aw`,
   with cap-evolve itself (`launch_cape_hc.sh` runs `$AW_EVAL/venv-aw/bin/cap-evolve`):

   ```
   git clone https://github.com/StonyBrookNLP/appworld $AW_EVAL/appworld
   cd $AW_EVAL/appworld && git checkout 42b5bcf && git lfs pull
   git apply <repo>/examples/appworld/patches/appworld-extra-headers.patch
   uv venv --python 3.11 $AW_EVAL/venv-aw
   uv pip install --python $AW_EVAL/venv-aw/bin/python -e . -e "experiments[simplified]" \
       "pydantic>=2.12,<2.13" "fastapi==0.135.0" "starlette>=0.48" -e <repo>/core
   $AW_EVAL/venv-aw/bin/appworld install --repo
   $AW_EVAL/venv-aw/bin/appworld download data --root $AW_EVAL/root_full
   ```

   The PyPI release `0.1.3.post1` has no simplified ReAct agent, and the head agents need pydantic 2.
   `42b5bcf` leaves fastapi and starlette unpinned. It breaks with fastapi ≥ 0.155
   (`Path(embed=...)`) and with starlette < 0.48 (`HTTP_422_UNPROCESSABLE_CONTENT`). The pins above
   were checked with `scripts/check_injection.py`.
2. `python scripts/make_roots.py` builds `$AW_EVAL/root_opt` (train + dev tasks only; it greps that no
   test id is present) and the lint cache `$AW_EVAL/lint_cache.json` built from it. `python scripts/make_reference.py $AW_EVAL/reference` writes the optimizer's
   read-only docs (API index from the public API docs, how the agent runs).
3. Put the agent-model key in a KEY=VALUE file (`AW_SECRETS_FILE`, default `<repo>/.env`). It is never
   exported: each episode worker reads only the key named by `AW_KEY_ENV` and the endpoint URL
   (`RITS_URL`/`MODEL_SERVER_URL`) from it and ignores every other line. Model endpoint: `AW_MODEL_NAME`, `AW_MODEL_URL`,
   `AW_KEY_HEADER`, `AW_KEY_ENV` (see `adapters/aw_agent.py`).
4. `bash scripts/setup_project.sh $AW_EVAL/runs/cape_hc_s0` scaffolds the cap-evolve project
   (intake), writes `split_ids.json` (train = val = train ∪ dev, test = []), renders the spec and
   settings, and runs `cap-evolve check`.

## Harness

`CapReActAgent` overrides only `initialize()` of AppWorld's agent: the prompt comes from the
candidate, a one-line notice naming the helpers goes right before the final `My name is: … Task:`
block, and a setup snippet defines `tools/helpers.py` in the REPL and adds `tools/api_notes.json`
notes to the API-doc lookups. With no helpers or notes the first request is **byte-identical to stock**
(`scripts/check_injection.py`, which also checks that AppWorld's agent accepts every constructor argument we pass; re-run it after changing the AppWorld pin). The same harness, model client and limits serve both arms.

Applied to both arms, because AppWorld `42b5bcf` does not:
- **REPL hardening.** `os`, `pathlib`, `io`, `shutil`, `glob` are removed from AppWorld's import
  allowlist: with them, agent code could list and read files (`pathlib.Path.read_text` passes the
  read-only `open`) and read `os.environ`. `pydoc` and `unittest` go too, because they import any
  module by its name (`pydoc.locate("os")`). The model key is dropped from the environment after the
  client is built. The episode worker's environment is an allowlist (`aw_agent.WORKER_ENV_NAMES`),
  so the optimizer's credentials in the `cap-evolve run` environment never reach it. Each episode records `fs_probe` if its code names a gold path.
- **Attribute guard.** AppWorld checks literal imports only, and allowed modules hand out blocked
  ones as attributes (`uuid.os`, `contextlib.os`, `random._os`). A second check
  (`aw_agent.code_guard_violations`) runs after AppWorld's and refuses `.os`/`.sys`/… attributes,
  every private (`_x`) attribute, dunder and frame walks,
  `getattr` on a module, `eval`/`exec`/`globals`/`vars`, and IPython `!`/`%` lines. Each episode
  records `guard_blocked` (refused steps) and `guard_probe`; `analyze.py` reports both per arm.
  This is defence in depth, not a sandbox: in-process Python can still reach memory (including the
  key held by the model client) and any file the worker may read. What protects the run is that the
  worker holds no other credential, that answers are absent from `root_opt` during search, and that
  probes are counted. Keeping the key out of the worker (a local header-adding proxy) is follow-up work.
- **Token cap.** `UsageTracker.exceeded()` never checks `max_output_tokens_per_task`; the episode
  loop enforces 100,000 completion tokens itself.
- **Gold-free records.** AppWorld's failure `trace` holds gold values; only requirement texts, the
  collateral-damage flag and counters are kept. AppWorld's native per-episode output dir (with the
  evaluation report) is deleted after each episode.
  An episode that raises is reported by exception type, phase and frames only. Its message is kept
  (paths and the key replaced, 300 chars) only outside the evaluate phase. A crashed worker's stderr
  is reduced to the exception type.

## Lints

`adapters/lints.py` rejects a candidate before any episode runs (scored 0 with the violations as
feedback): the prompt must keep its three Jinja variables and `USER:`/`ASSISTANT:` structure and stay
under 8,000 tokens; helpers may not hardcode app/API names or `apis.<app>.` chains, import outside a
small allowlist, or make top-level calls; nothing may contain an 8-gram of a train/dev instruction or a
supervisor's contact. This is AppWorld's rule against task-specific hints, made executable.
The lint data comes from the cache that `make_roots.py` writes (built from `root_opt`, never from the
episode root). The optimizer cannot see `root_opt`, so it lints from that cache. If the cache is missing
and `root_opt` is unreadable, the lint prints `"ok": false` with "lint data unavailable" and exits 2.
`setup_project.sh`, `launch_cape_hc.sh` and `check_optimizer_isolation.sh` refuse to start without it.

## cap-evolve arm

`capevolve.yaml`: hill-climb, paired gate `k = 1.0`, 1 trial, 6 iterations, `max_metric_calls`
1,050, optimizer `claude-code`. Because train = val, its search score is a **fit metric**; only the
final window is held out.

## Isolation

The claude-code optimizer has `Bash`, so by default it can read the whole host, including the gold
files the grader needs. In a first run its subagents did exactly that to "verify" helper code.
Every optimizer call therefore goes through `sandbox/claude` (put first on the run's `PATH` by
`scripts/launch_cape_hc.sh`), which runs the real CLI isolated in one of two ways (`AW_ISOLATION`):

- **`sandbox` (default): Claude Code's built-in sandbox** (bubblewrap), with
  `optimizer-sandbox.json`: `failIfUnavailable`, no unsandboxed retries, no network, and reads
  denied on both data roots, the final-window outputs, AppWorld's `generate/` (the task
  generators, i.e. the solution and evaluation logic of every train/dev scenario; in one run an
  optimizer subagent read it), the secrets file and other sessions' transcripts.
- **`namespace`: the fallback** for hosts where bubblewrap cannot start (containers whose
  `/dev/null` is bound from the host; every shell command then fails). `sandbox/ns_exec.sh` runs the
  call in a private mount namespace where `$AW_EVAL` is an empty tmpfs except for a read-only
  allowlist (the venv, AppWorld's `src/` and `experiments/`, the reference docs, the lint cache) and
  the optimizer's own working dir. The same places are covered. The call runs in a nested user
  namespace as a normal user, so it cannot unmount any of it. It needs Linux with unprivileged user
  namespaces; no root.

Either way the shim fails closed (no settings file, no call), and:

- `bash scripts/check_optimizer_isolation.sh sandbox|namespace` plants a random secret where the
  answers live and asks a real optimizer call, through the same shim, to dig it out (cat, Read, Grep,
  `find /`, copying a data root, an unsandboxed retry). It passes only if no secret reaches the
  transcript and normal work (writing files, the lint) still runs. `launch_cape_hc.sh` refuses to
  start without a passing check for its mode that is newer than the rendered settings
  (`scripts/isolation_gate.py`).
- `scripts/scan_isolation.py` greps every optimizer transcript and workdir afterwards for test ids and
  gold-file names. AppWorld uses one canary string for all tasks, so only test ids count as evidence of
  test access.

## Final window

`scripts/final_window.py freeze` copies the seed and the cape-hc champion and hashes them; `run`
scores 168 tasks × 2 arms × 2 trials in one shuffled order (48 workers, seeds 5000 + trial, up to 3 infra retries, resumable,
`touch runs/final/PAUSE` to pause). Only rewards and counters are written; no test trajectory is kept.
`scripts/analyze.py` gives TGC, SGC, by difficulty, and paired differences with a scenario-clustered
bootstrap CI.

## Integration test

`bash scripts/itest.sh` is this example's one-task regression run, like
`examples/tau2_airline/itest.sh`: train task `82e2fac_1` (difficulty 1), 1 trial, 1 iteration
(`capevolve.itest.yaml`, `itest_split.json`). It scaffolds the project with `setup_project.sh`,
runs a fresh isolation check, and runs through `launch_cape_hc.sh`, so it takes the real launch
path. `scripts/assert_itest.py` then gates the run dir. It requires that the run completed
(`baseline.json`, `final.json`, `report.md`), that one iteration ran, and that the final test reward
is not below the baseline val reward. It also requires that no rollout is an infrastructure error or
a lint reject (a broken key scores 0.0 like a failed task), and that no record is gold-bearing. With
one iteration the gate usually rejects the edit; that is a pass.

`bash scripts/itest.sh --dry-run` runs everything up to the first model call: preflight, project,
`cap-evolve check`, and `cap-evolve run --dry-run`.

## Running

```
bash scripts/check_optimizer_isolation.sh sandbox            # must PASS (or namespace, with AW_ISOLATION=namespace)
bash scripts/launch_cape_hc.sh $AW_EVAL/runs/cape_hc_s0       # cape-hc search (~5 h)
python scripts/scan_isolation.py
python scripts/final_window.py freeze && python scripts/final_window.py run
python scripts/analyze.py
```

`python scripts/status.py --every 300` keeps `$AW_EVAL/progress/PROGRESS.md` current. Offline tests:
`python -m pytest examples/appworld/tests`.
