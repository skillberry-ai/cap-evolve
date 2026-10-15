# appworld: cap-evolve vs ALTK-Evolve on AppWorld

Runs a controlled comparison on [AppWorld](https://github.com/StonyBrookNLP/appworld): everyday tasks
in simulated apps (music, payments, email, phone, files…), solved by an agent that writes Python
against the apps' APIs and is graded on the final app state. Three arms share one harness:

| arm | what it is | what it learns |
|---|---|---|
| `seed` | AppWorld's official simplified ReAct code agent, stock prompt | nothing |
| `cape-hc` | cap-evolve, `hill-climb --focus all`, capabilities `[system-prompt, tools]` | the prompt, REPL helper functions, API notes |
| `altk` | [ALTK-Evolve](https://github.com/AgentToolkit/altk-evolve) v1.3.0 | "lessons learned" guidelines in a memory slot |

Search uses only AppWorld's official `train` (90) and `dev` (57) splits; results come from
`test_normal` (168), scored for all three arms in one interleaved window. `test_challenge` is not
used. Defaults: agent `openai/gpt-oss-120b` on IBM RITS, optimizer `aws/claude-sonnet-5-5`, both
configurable.

## Layout

```
adapters/adapter.py     cap-evolve adapter: tasks, run_trials (one subprocess per episode), score
adapters/aw_agent.py    CapReActAgent + the one-episode worker (the harness)
adapters/lints.py       candidate lints, also run by the optimizer before it stops
seed_capability/        policy/instructions.txt (stock prompt, byte copy), tools/, memory/
optimizer/              intake-customized INSTRUCTIONS template for the optimizer
patches/                18-line AppWorld patch: header auth for the agent model, never logged
sandbox/                optimizer isolation: the `claude` namespace wrapper + settings templates
altk/                   the ALTK-Evolve arm: convert, mine, render, select the dose on dev
scripts/                data roots, splits, acceptance checks, launch, final window, analysis, scan
tests/                  offline tests (no AppWorld, no model)
```

## Setup

Everything heavy lives under `$AW_EVAL` (default `/tmp/aw_eval`).

1. AppWorld core + agents **from source** at `42b5bcf`, in a Python 3.11 venv `$AW_EVAL/venv-aw`
   with `pydantic>=2.12,<2.13` and `-e core`; apply `patches/appworld-extra-headers.patch`; run
   `appworld install --repo` and `appworld download data --root $AW_EVAL/root_full`. (The PyPI
   release `0.1.3.post1` has no simplified ReAct agent, and the head agents need pydantic 2.)
2. `python scripts/make_roots.py` builds `$AW_EVAL/root_opt` (train + dev tasks only; it greps that no
   test id is present). `python scripts/make_reference.py $AW_EVAL/reference` writes the optimizer's
   read-only docs (API index from the public API docs, how the agent runs).
3. ALTK-Evolve needs Python ≥ 3.12: install `altk-evolve==1.3.0` in the repo's `.venv` (or set
   `AW_ALTK_PYTHON`).
4. Put the agent-model key in a KEY=VALUE file (`AW_SECRETS_FILE`, default `<repo>/.env`). It is never
   exported: each episode worker reads it. Model endpoint: `AW_MODEL_NAME`, `AW_MODEL_URL`,
   `AW_KEY_HEADER`, `AW_KEY_ENV` (see `adapters/aw_agent.py`).
5. `bash scripts/setup_project.sh $AW_EVAL/runs/cape_hc_s0` scaffolds the cap-evolve project
   (intake), writes `split_ids.json` (train = val = train ∪ dev, test = []), renders the spec and
   settings, and runs `cap-evolve check`.

## Harness

`CapReActAgent` overrides only `initialize()` of AppWorld's agent: the prompt comes from the
candidate, an optional memory block goes right before the final `My name is: … Task:` block, and a
setup snippet defines `tools/helpers.py` in the REPL and adds `tools/api_notes.json` notes to the
API-doc lookups. With no memory, helpers or notes the first request is **byte-identical to stock**
(`scripts/check_injection.py`). The same harness, model client and limits serve all three arms.

Applied to every arm, because AppWorld `42b5bcf` does not:
- **REPL hardening.** `os`, `pathlib`, `io`, `shutil`, `glob` are removed from AppWorld's import
  allowlist: with them, agent code could list and read files (`pathlib.Path.read_text` passes the
  read-only `open`) and read `os.environ`. The model key is dropped from the environment after the
  client is built. Each episode records `fs_probe` if its code names a gold path.
- **Token cap.** `UsageTracker.exceeded()` never checks `max_output_tokens_per_task`; the episode
  loop enforces 100,000 completion tokens itself.
- **Gold-free records.** AppWorld's failure `trace` holds gold values; only requirement texts, the
  collateral-damage flag and counters are kept. AppWorld's native per-episode output dir (with the
  evaluation report) is deleted after each episode.

## Lints

`adapters/lints.py` rejects a candidate before any episode runs (scored 0 with the violations as
feedback): the prompt must keep its three Jinja variables and `USER:`/`ASSISTANT:` structure and stay
under 8,000 tokens; helpers may not hardcode app/API names or `apis.<app>.` chains, import outside a
small allowlist, or make top-level calls; nothing may contain an 8-gram of a train/dev instruction or a
supervisor's contact. This is AppWorld's rule against task-specific hints, made executable.

## cap-evolve arm

`capevolve.yaml`: hill-climb, paired gate `k = 1.0`, 1 trial, 6 iterations, `max_metric_calls`
1,050, optimizer `claude-code`. Because train = val, its search score is a **fit metric**; only the
final window is held out.

## ALTK-Evolve arm

`altk/run_altk.sh`: reuse the seed's 90 train rollouts from the cap-evolve baseline, convert them to
OpenAI messages (instruction first, no outcome label), `save_trajectory` each (library defaults),
consolidate losslessly, render two doses (full playbook; core + top-10 retrieval per task), pick the
dose on dev. A dose that fails the 30,000-character memory lint is infeasible. Two gateway shims live
in `altk/altk_common.py`, in our process only: base URL/token/headers on every `litellm.completion`
(with per-call token logging), and "no response-schema support" for the optimizer model, because the
gateway rejects the forced `tool_choice` litellm uses to emulate it.

## Isolation

The claude-code optimizer has `Bash`, so by default it can read the whole host, including the gold
files the grader needs. In a first run its subagents did exactly that to "verify" helper code.
`sandbox/claude` closes this: put `sandbox/` first on the run's `PATH`
(`scripts/launch_cape_hc.sh` does) and every optimizer call runs the real CLI in a private mount
namespace where `$AW_EVAL` is an empty tmpfs except for a read-only allowlist (the venv, AppWorld code,
the reference docs, the lint cache) and the optimizer's own working dir. Other sessions' transcripts,
the claude temp dir and the secrets file are covered too. The call runs in a nested user namespace as
a normal user, so it cannot unmount any of it, and `/proc/<pid>/root` of outside processes is refused.
It needs Linux with unprivileged user namespaces; no root.

Claude Code's built-in sandbox (bubblewrap) is the alternative where it can start; in containers whose
`/dev/null` is bound from the host it cannot (every shell command fails). Either way:

- `bash scripts/check_optimizer_isolation.sh namespace|sandbox` plants a random secret where the
  answers live and asks a real optimizer call to dig it out (cat, Read, Grep, `find /`, copying a data
  root, an unsandboxed retry). It passes only if no secret reaches the transcript and normal work
  (writing files, the lint) still runs. **Run it before a search.**
- `scripts/scan_isolation.py` greps every optimizer transcript and workdir afterwards for test ids and
  gold-file names. AppWorld uses one canary string for all tasks, so only test ids count as evidence of
  test access.

## Final window

`scripts/final_window.py freeze` copies the three champions and hashes them; `run` scores 168 tasks ×
3 arms × 2 trials in one shuffled order (48 workers, seeds 5000 + trial, up to 3 infra retries, resumable,
`touch runs/final/PAUSE` to pause). Only rewards and counters are written; no test trajectory is kept.
`scripts/analyze.py` gives TGC, SGC, by difficulty, and paired differences with a scenario-clustered
bootstrap CI.

## Running

```
bash scripts/check_optimizer_isolation.sh namespace          # must PASS
bash scripts/launch_cape_hc.sh $AW_EVAL/runs/cape_hc_s0       # cape-hc search (~5 h)
bash altk/run_altk.sh                                         # starts after the cape-hc baseline
python scripts/scan_isolation.py
python scripts/final_window.py freeze && python scripts/final_window.py run
python scripts/analyze.py
```

`python scripts/status.py --every 300` keeps `$AW_EVAL/progress/PROGRESS.md` current. Offline tests:
`python -m pytest examples/appworld/tests`.
