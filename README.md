# cap-evolve

<!-- badges: replace OWNER/REPO once published -->
![status](https://img.shields.io/badge/status-beta%20(0.x)-orange)
![tests](https://img.shields.io/badge/tests-28%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![deps](https://img.shields.io/badge/runtime%20deps-0%20(stdlib)-success)
![license](https://img.shields.io/badge/license-MIT-informational)
![skills](https://img.shields.io/badge/agent%20skills-25-7c5cff)

**Optimize any AI agent's capabilities — its skills, tools/MCP, and prompts —
against your own eval. Host-agnostic. Honest train/val/test. Every iteration
versioned in git.**

cap-evolve is a library of [Agent Skills](https://www.anthropic.com/news/skills)
(plus a tiny stdlib core) that turns "make this agent better at X" into a
disciplined loop *any* coding agent can run: collect inputs → wire a 4-method
adapter → evaluate → diagnose failures → propose edits → keep only what beats a
held-out set → report. It optimizes what your agent *reads*, and reports a single,
honest number you can trust.

> **Status:** beta (`0.x`) — APIs may change. Working end to end; proven on a real
> benchmark (see [Results](#results)).

**Contents:** [Quickstart](#quickstart-60-seconds) ·
[Optimize your own](#optimize-your-own-skill-tool-or-agent) · [Results](#results) ·
[Supported agent hosts](#supported-agent-hosts) · [Install](#install) ·
[Usage](#usage-swap-one-word) · [How it works](#how-it-works) ·
[Dashboard](#dashboard) · [Comparison](#how-it-compares) ·
[Skill library](#skill-library) · [Examples](#examples) ·
[How-to guides](#how-to-guides) · [Extending](#extending) ·
[Contributing](#contributing) · [Citation](#citation)

![cap-evolve demo](docs/demo.gif)

## Quickstart (60 seconds)

**Prerequisites:** Python 3.10+ and git — that's all for this example (it's
**zero-API**, so no model key needed). A *real* optimization additionally needs a
coding-agent CLI to act as the optimizer (e.g. `claude`, `codex`, `gemini`) plus
its API key — see [Optimize your own](#optimize-your-own-skill-tool-or-agent). Some
benchmarks (e.g. skills-bench) also need Docker.

**Step 1 — verify the install with a real, zero-API run** (the `toy_calc` example:
a deterministic agent whose score depends on its system prompt; the `mock` optimizer
edits the prompt, so no API is called):

```bash
git clone <repo> cap-evolve && cd cap-evolve
pip install ./core                         # the honest-eval substrate (CLI: cap-evolve)
./install.sh                               # place skills into your agent host
bash examples/toy_calc/run.sh              # scaffold a tmp project dir and run end-to-end
```
```jsonc
{
  "baseline_val": 0.0,        // seed prompt fails every task
  "test_reward": 1.0,         // optimized prompt, scored ONCE on the sealed test split
  "test_pass_k": {"1": 1.0},
  "dashboard": ".capevolve/run_*/dashboard.html"   // open in any browser
}
```
Open the printed `dashboard.html` to see the run. That confirms the install works.

**Step 2 — optimize your own skill / tool / agent:** see the next section.
Or, host-agnostic: point any agent at [`RUN.md`](RUN.md) and say *"follow RUN.md."*

## Optimize your own skill, tool, or agent

The Quickstart runs a *bundled* example. To optimize **your** capability against
**your** benchmark, you supply three things and cap-evolve runs the loop:

1. **The capability to optimize** — a skill (`SKILL.md` package), a tool's code, an
   MCP tool definition, or a system prompt. A *copy* is edited each iteration; your
   original is never touched.
2. **Tasks** — your benchmark's eval cases (each with an id + a gold/criterion).
3. **A scorer** — how one run becomes a reward in `[0,1]` (+ short feedback).

You connect these once through a tiny **4-method adapter**
(`tasks · run_target · score · apply`). There are two ways to get there — pick one:

### Path A — let your coding agent build and run it (no Python from you)
Open the coding agent you already use (**Claude Code**, Codex, Gemini CLI, opencode,
…) at the repo root and tell it to follow `RUN.md`. It loads the `intake` skill, asks
you for anything missing, **writes the adapter for you**, runs the `cap-evolve check` gate,
then the full optimize → significance-gate → sealed-test → report loop, and prints the
dashboard path. (This is exactly how [`examples/date_tool`](examples/date_tool) was
built — the optimizer agent wrote the adapter from scratch and improved the tool
**0.125 → 1.0**, no human edits.)

Give it the details `intake` needs up front (anything you omit, it will ask for — and
will **never fabricate a NEEDED input**). Copy this template and fill it in:

```text
Follow RUN.md to run a cap-evolve optimization. Here is everything intake needs:

# 1. CAPABILITY TO OPTIMIZE  (what gets edited each iteration)
- type:            system-prompt | tools | mcp-tool | skill-package   (one or a list)
- local path:      <path to the skill dir / tool file / prompt / policy to optimize>

# 2. BENCHMARK / DATASET  (the eval)
- benchmark repo:  <local path or git URL of the benchmark, e.g. ./my-bench>
- tasks:           <tasks.jsonl path>  OR  "adapter" (the adapter builds them from the benchmark)
- task format:     each case has an id, an input, and a gold/criterion
- splits:          ratio 0.5/0.25/0.25 (seeded)  |  explicit ids file  |  all-in-each (no holdout, fit metric)

# 3. RUNNER  (the agent under test) + MODELS + CREDENTIALS
- how to run one task: <your agent's CLI/SDK/HTTP entrypoint, or the benchmark's own batch runner>
- runner model(s): <e.g. watsonx/openai/gpt-oss-120b>
- credentials:     <env vars / .env keys the runner needs, e.g. RITS_API_KEY, WATSONX_*>

# 4. SCORER  (what to optimize against)
- metric:          <exact-match | task reward in [0,1] | rubric | a pass/fail rule>
- where it comes from: <the benchmark's verifier, or your scoring function>
- objective:       maximize mean reward on the VAL split

# 5. OPTIMIZER  (proposes the edits) + MODEL + CREDENTIALS
- optimizer:       claude-code | codex | gemini-cli | opencode | ibm-bob | generic
- optimizer model: <e.g. claude-opus-4-6>   (omit to use the optimizer's default)
- credentials:     <e.g. ANTHROPIC_API_KEY, or BOBSHELL_API_KEY for ibm-bob>

# 6. BUDGET / GATE
- algorithm:       all-at-once | cyclic | hardest-first | gepa-reflective
- max_iterations:  <N>     num_trials: <K, use >=3 for a stochastic agent>
- gate:            significant (k_se, e.g. 1.0) | strict | threshold
```

**Worked example — tau2-bench airline, from scratch** (this is the bundled
[`examples/tau2_airline`](examples/tau2_airline); the adapter is provided, so the agent
just wires the inputs and runs):

```text
Follow RUN.md to run a cap-evolve optimization:
# 1. CAPABILITY: [system-prompt, tools]  (optimize the airline policy AND the tool docstrings/code)
#    local path: examples/tau2_airline/seed_caps   (policy/policy.md + tools/tools.py)
# 2. BENCHMARK: tau2-bench airline; repo local at ../tau2-bench; tasks via "adapter" (50 airline tasks)
#    splits: all 50 tasks in train/val/test (no holdout, fit metric) -> run_full/split_ids_all50.json
# 3. RUNNER: agent AND user simulator = watsonx/openai/gpt-oss-120b via IBM RITS;
#    credential RITS_API_KEY in the repo-root .env; tau concurrency 7 (TAU2_MAX_CONCURRENCY=7)
# 4. SCORER: tau2's own task reward in [0,1] (required actions performed + info communicated);
#    objective = maximize mean reward on val
# 5. OPTIMIZER: ibm-bob  (or claude-code @ claude-opus-4-6); credential BOBSHELL_API_KEY (or ANTHROPIC_API_KEY)
# 6. BUDGET: algorithm all-at-once; max_iterations 20; num_trials 5; gate significant (k_se 0.5)
```

The exact, copy-pasteable commands for that run are in
[`examples/tau2_airline/run_full/README.md`](examples/tau2_airline/run_full/README.md),
and the full Bob-optimizer walkthrough (phases, what Bob wrote, metrics) is in
[`examples/tau2_airline/run_full/BOB_EXPERIMENT.md`](examples/tau2_airline/run_full/BOB_EXPERIMENT.md).

### Path B — drive it yourself with the `cap-evolve` CLI
```bash
# 1. scaffold a project (adapter STUB + capevolve.yaml + PROJECT.md)
python3 skills/phases/intake/scripts/run.py --base .capevolve

# 2. implement the 4 methods in .capevolve/project/adapters/adapter.py:
#      tasks(split)               -> your benchmark's tasks  (id, input, target)
#      run_target(task, cand_dir) -> run YOUR agent/skill/tool on the task w/ the candidate applied
#      score(task, rollout)       -> reward in [0,1] + feedback
#      apply(cand_dir, edits)     -> make the candidate "live" (often a no-op for a skill/tool dir)
#    Fastest path: copy the closest example adapter below and edit it.

# 3. fill .capevolve/project/capevolve.yaml  (capabilities / optimizer / algorithm / splits)

# 4. hard gate, then run
cap-evolve check .capevolve/project
cap-evolve run --spec .capevolve/project/capevolve.yaml --project .capevolve/project
open .capevolve/run_*/dashboard.html
```

**Start from the closest worked example** — copy its `adapter.py`, point it at your
data, swap `capabilities` in `capevolve.yaml`:

| You want to optimize… | Copy this example | `capabilities:` |
|---|---|---|
| a **tool's code** | [`examples/date_tool`](examples/date_tool) | `[tools]` |
| a **skill package** (`SKILL.md`) | [`examples/skills_bench`](examples/skills_bench) | `[skill-package]` |
| a **system prompt + tools** (real agent) | [`examples/tau2_airline`](examples/tau2_airline) | `[system-prompt, tools]` |
| a simple **prompt** / extractor | [`examples/toy_calc`](examples/toy_calc) · [`examples/json_extract`](examples/json_extract) | `[system-prompt]` |

### Pointing it at your own benchmark
Your benchmark plugs in **only** through the adapter — nothing else changes:
- `tasks(split)` reads your benchmark's cases (its files, or an API call).
- `run_target(task, candidate_dir, split)` runs your agent on one task **with the
  candidate capability applied**, capturing output/trace into a `Rollout`.
- `score(task, rollout)` turns that into a reward using your benchmark's metric.

If your benchmark ships its **own batch runner**, implement `run_batch` instead of
per-task `run_target` (see [`examples/tau2_airline/adapter.py`](examples/tau2_airline/adapter.py))
so cap-evolve drives the benchmark's runner directly. Splits, trials, the gate,
pass^k, the sealed test, and the dashboard are all handled for you.

## Results

Real [tau2-bench](https://github.com/sierra-research/tau2-bench) **airline** run —
optimizing the airline **policy + tools together** with a Claude-Opus optimizer and
`gpt-oss-120b` as both agent and user simulator, over all 50 tasks:

| | reward |
|---|---|
| baseline (seed policy + default tool docs) | **0.46** |
| **optimized** (policy + tool docstrings, 8 iterations) | **0.80** · pass^1 0.80 · pass@2 0.87 |

**+0.34** on 50 tasks (31/50 fully solved) — every iteration a git commit, the
optimizer's reasoning kept in `STATE.md` / `rejected.jsonl`. Exact commands, inputs,
and intake answers: [docs/REPRODUCE_tau2.md](docs/REPRODUCE_tau2.md); measured
numbers: [examples/tau2_airline/RESULTS.md](examples/tau2_airline/RESULTS.md).

## Supported agent hosts

Any of these can drive the **optimizer** (the agent that proposes edits). Verified
headless commands; details in `skills/optimizers/<name>/SKILL.md`.

| Host (optimizer) | Skill | Headless command | Status |
|---|---|---|---|
| Claude Code | `claude-code` | `claude -p … --permission-mode acceptEdits` | stable |
| OpenAI Codex CLI | `codex` | `codex exec --sandbox workspace-write …` | stable |
| Gemini CLI | `gemini-cli` | `gemini -p … --approval-mode=yolo` | stable |
| opencode | `opencode` | `opencode run --dangerously-skip-permissions …` | stable |
| OpenClaw | `openclaw` | configurable (`CAPEVOLVE_OPENCLAW_CMD`) | beta |
| IBM Bob | `ibm-bob` | via `AGENTS.md` (configurable) | beta |
| Any CLI agent | `generic` | `CAPEVOLVE_OPTIMIZER_CMD` template | stable |
| (tests / CI) | `mock` | deterministic, zero-API | stable |

`install.sh` auto-detects each host's skill dir (Claude Code `.claude/skills`,
Codex `.agents/skills`, opencode native, Gemini extensions, …).

## Install
```bash
pip install ./core            # package: cap-evolve-core, CLI: cap-evolve
./install.sh                  # copy skills into your host's skills dir (optionally --host <name>)
```

## Usage (swap one word)

Pick the optimizer in `capevolve.yaml`; the loop is identical — only the host changes:

```yaml
# .capevolve/project/capevolve.yaml
capabilities: [system-prompt, tools]   # list of capabilities to optimize jointly
                                       #   any of: system-prompt | tools | mcp-tool | skill-package
optimizer_skill:  claude-code      # ← swap: codex | gemini-cli | opencode | generic | mock
algorithm_skill:  all-at-once      # all-at-once | cyclic | hardest-first | gepa-reflective
num_trials: 4
store: git                         # versions every iteration; or: copy | command (e.g. a skills store)
```
```bash
python3 -m cap_evolve.cli run --spec .capevolve/project/capevolve.yaml --project .capevolve/project
```

## How it works
1. **Intake** — interview the user, scaffold `.capevolve/project/`, gather inputs (ask if missing).
2. **Implement & check** — fill the 4-method adapter (`tasks · run_target · score · apply`); `cap-evolve check` is a hard gate.
3. **Baseline** — freeze seeded train/val/test (test **sealed**), score the seed on val.
4. **Optimize** — each iteration: diagnose failing traces → the optimizer edits a candidate → score on **val** → a **significance gate** (Δ > k·SE) accepts or rejects → commit to git, update memory.
5. **Finalize** — score the best candidate on the **sealed test split, exactly once**.
6. **Report** — `report.md` + a self-contained `dashboard.html`.

Honesty is enforced in code, not docs: the only place rewards are aggregated,
splits are made, the gate is applied, and test is sealed is `cap_evolve` —
see [docs/HONEST_EVAL.md](docs/HONEST_EVAL.md). You implement four adapter methods
once; everything else is provided ([docs/ADAPTER_CONTRACT.md](docs/ADAPTER_CONTRACT.md)).

## Dashboard
Every run writes a single-file `dashboard.html` (run data inlined; opens offline):
KPI cards, baseline→val→test, score-over-iterations, a **per-task reward heatmap**,
an accept/reject timeline, a frontier scatter, and a candidate leaderboard with
pass^k / pass@k.

## How it compares

| | cap-evolve | DSPy | GEPA | promptfoo |
|---|:--:|:--:|:--:|:--:|
| Optimizes prompts | ✅ | ✅ | ✅ | ❌ (eval only) |
| Optimizes tools/MCP + skills | ✅ | ➖ | ➖ | ❌ |
| **Sealed test + significance gate enforced in code** | ✅ | ➖ | ➖ | ➖ |
| pass^k *and* pass@k + bootstrap CI | ✅ | ❌ | ❌ | ❌ |
| Reflective Pareto evolution (GEPA) | ✅ | ✅ | ✅ | — |
| **Runs on any agent host (no framework)** | ✅ | ❌ | ❌ | ➖ |
| Git-versioned iterations + optimizer memory | ✅ | ❌ | ❌ | ❌ |
| Zero runtime dependencies | ✅ | ❌ | ❌ | ❌ |

Whitespace: **skills-native + host-agnostic + honesty enforced in code.** Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md).

## Skill library

| Component | Skills |
|-----------|--------|
| orchestrate | `orchestrate` |
| phases | `intake` · `implement-and-check` · `baseline` · `evaluate` · `diagnose` · `gate` · `finalize` · `report` |
| capabilities | `system-prompt` · `skill-package` · `tools` · `mcp-tool` |
| algorithms | `all-at-once` · `cyclic` · `hardest-first` · `gepa-reflective` |
| optimizers | `claude-code` · `codex` · `gemini-cli` · `opencode` · `openclaw` · `ibm-bob` · `generic` · `mock` |

## Examples
- [`examples/toy_calc`](examples/toy_calc) — zero-API deterministic proof (the CI gate).
- [`examples/json_extract`](examples/json_extract) — a new benchmark from scratch (adapter + data only).
- [`examples/tau2_airline`](examples/tau2_airline) — the real tau2-bench run above.

## How-to guides

Step-by-step recipes for specific harness + benchmark combinations:

| Guide | What it covers |
|---|---|
| [cap-evolve with Exgentic / tau2-bench](docs/how-to/cap-evolve-with-exgentic-tau2.md) | Optimize airline `policy.md` + `tools.py` via the exgentic harness and a LiteLLM proxy |

More guides will be added here over time.

## Extending
A new capability / algorithm / optimizer is **one folder** — clone `templates/skill`,
fill `meta.yaml`, drop it in; the registry auto-discovers it by `needs`/`provides`.
See [docs/EXTENDING.md](docs/EXTENDING.md).

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).
Report security issues via [SECURITY.md](SECURITY.md). Changes: [CHANGELOG.md](CHANGELOG.md).

## Citation
```bibtex
@software{cap-evolve,
  title  = {cap-evolve: a skills-native, host-agnostic harness for honestly
            optimizing AI-agent capabilities},
  year   = {2026},
  note   = {https://github.com/OWNER/cap-evolve}
}
```
Builds on GEPA, DSPy, SkillOpt, SkillGrad, Trace2Skill, evo/evo-graph/governor,
tau-bench/tau2-bench, and the Agent Skills standard — see [docs/sources.bib](docs/sources.bib).

## License
MIT.
